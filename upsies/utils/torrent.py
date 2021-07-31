"""
Create torrent file
"""

import collections
import hashlib
import math
import os
import time
from os.path import exists as _path_exists

from .. import __project_name__, __version__, errors
from . import LazyModule

import logging  # isort:skip
_log = logging.getLogger(__name__)

torf = LazyModule(module='torf', namespace=globals())


def create(*, content_path, announce, torrent_path,
           init_callback, progress_callback,
           overwrite=False, source=None, exclude=()):
    """
    Generate and write torrent file

    :param str content_path: Path to the torrent's payload
    :param str announce: Announce URL
    :param str torrent_path: Path of the generated torrent file
    :param str init_callback: Callable that is called once before torrent
        generation commences. It gets `content_path` as a tree where a node is a
        tuple in which the first item is the directory name and the second item
        is a list of `(file_name, file_size)` tuples.

        Example:

        .. code::

           ('Parent',
               ('Foo', (
                   ('Picture.jpg', 82489),
                   ('Music.mp3', 5315672),
                   ('More files', (
                       ('This.txt', 57734),
                       ('And that.txt', 184),
                       ('Also some of this.txt', 88433),
                   )),
               )),
               ('Bar', (
                   ('Yee.mp4', 288489392),
                   ('Yah.mkv', 3883247384),
               )),
           )
    :param str progress_callback: Callable that gets the progress as a number
        between 0 and 100. Torrent creation is cancelled if `progress_callback`
        returns `True` or any other truthy value.
    :param bool overwrite: Whether to overwrite `torrent_path` if it exists
    :param str source: Value of the "source" field in the torrent or `None` to
        leave it out
    :param exclude: Sequence of regular expressions; matching files are not
        included in the torrent

    :raise TorrentError: if anything goes wrong

    :return: `torrent_path`
    """
    if not announce:
        raise errors.TorrentError('Announce URL is empty')

    def cb(torrent, filepath, pieces_done, pieces_total):
        return progress_callback(pieces_done / pieces_total * 100)

    if not overwrite and _path_exists(torrent_path):
        _log.debug('Torrent file already exists: %r', torrent_path)
        return torrent_path
    else:
        try:
            torrent = torf.Torrent(
                path=content_path,
                exclude_regexs=exclude,
                trackers=((announce,),),
                private=True,
                source=source,
                created_by=f'{__project_name__} {__version__}',
                creation_date=time.time(),
            )
            init_callback(_make_file_tree(torrent.filetree))
            success = torrent.generate(callback=cb, interval=0.5)
        except torf.TorfError as e:
            raise errors.TorrentError(e)

        if success:
            try:
                torrent.write(torrent_path, overwrite=overwrite)
            except torf.TorfError as e:
                raise errors.TorrentError(e)
            else:
                return torrent_path


def _make_file_tree(tree):
    files = []
    for name,file in tree.items():
        if isinstance(file, collections.abc.Mapping):
            subtree = _make_file_tree(file)
            files.append((name, subtree))
        else:
            files.append((name, file.size))
    return tuple(files)


class TorrentFileStream:
    """
    Traverse files as they are described in a torrent

    :param torrent: :class:`~.torf.Torrent` object
    :param location: Path to location of files in `torrent`

    Instances should be used as a context manager to ensure all files are closed
    properly.

    Example:
    >>> torrent = torf.Torrent(...)
    >>> TorrentFileStream(torrent, location='path/to/files') as tfs:
    >>>     # Get the 29th piece of the concatenated file stream
    >>>     piece = tfs.get_piece(29)
    """

    def __init__(self, torrent, location):
        self._torrent = torrent
        self._location = location
        self._open_files = {}
        _log.debug('Created stream from torrent files:')
        for f in self._torrent.files:
            _log.debug('  %r', f)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        _log.debug('Closing opened files: %r', self._open_files)
        for filepath, fh in tuple(self._open_files.items()):
            fh.close()
            del self._open_files[filepath]

    def get_file_position(self, file):
        """
        Return index of first byte of `file` in stream of concatenated files

        :param file: :class:`~torf.File` object
        """
        file_index = self._torrent.files.index(file)
        stream_pos = sum(f.size for f in self._torrent.files[:file_index])
        return stream_pos

    def get_file_at_position(self, byte_index):
        """
        Return file that belongs to the byte at `byte_index` in stream of
        concatenated files

        :param byte_index: Index of the byte; minimum is 0, maximum is the
        torrent's size minus 1
        """
        if byte_index >= 0:
            pos = 0
            # _log.debug('Finding file at byte index %r', byte_index)
            for f in self._torrent.files:
                # _log.debug('  %r, size=%r: %r += %r - 1 = %r', f, f.size, pos, f.size, pos + f.size - 1)
                pos += f.size - 1
                if pos >= byte_index:
                    # _log.debug('    Found %r at %r!', byte_index, pos)
                    return f
                else:
                    pos += 1
        raise ValueError(f'byte_index is out of bounds (0 - {self._torrent.size}): {byte_index}')

    def get_piece_indexes_for_file(self, file):
        """
        Return indexes of pieces that contain at least one byte of `file`

        :param file: :class:`~torf.File` object
        """
        stream_pos = self.get_file_position(file)
        first_piece_index = math.floor(stream_pos / self._torrent.piece_size)
        last_piece_index = math.floor((stream_pos + file.size - 1) / self._torrent.piece_size)
        return list(range(first_piece_index, last_piece_index + 1))

    def get_files_for_byte_range(self, first_byte_index, last_byte_index):
        """
        Return list of files that have at least one byte at `first_byte_index`,
        `last_byte_index` or between those two in the stream of concatenated
        files
        """
        assert first_byte_index <= last_byte_index, (first_byte_index, last_byte_index)
        # _log.debug('Finding files from byte index %r to %r', first_byte_index, last_byte_index)
        pos = 0
        files = []
        for file in self._torrent.files:
            file_first_byte_index = pos
            file_last_byte_index = pos + file.size - 1
            # _log.debug('    %s starts at %r, ends at %r', file, file_first_byte_index, file_last_byte_index)
            # _log.debug('    if (')
            # _log.debug(f'        {first_byte_index} <= {file_first_byte_index} <= {last_byte_index} or')
            # _log.debug(f'        {first_byte_index} <= {file_last_byte_index} <= {last_byte_index} or')
            # _log.debug(f'        ({first_byte_index} >= {file_first_byte_index} and {last_byte_index} <= {file_last_byte_index})')
            # _log.debug('    ):')
            if (
                    # Is first byte of file inside of range?
                    first_byte_index <= file_first_byte_index <= last_byte_index or
                    # Is last byte of file inside of range?
                    first_byte_index <= file_last_byte_index <= last_byte_index or
                    # Are all bytes of file inside of range?
                    (first_byte_index >= file_first_byte_index and last_byte_index <= file_last_byte_index)
            ):
                # _log.debug('    Including %r', file)
                files.append(file)
            pos += file.size
        return files

    # def get_relative_piece_indexes(self, file, wanted_piece_indexes):
    #     """
    #     Return list of sanitized relative piece indexes for `file`

    #     :param wanted_piece_indexes: Sequence of list indexes, e.g. [0, 12, -1, -2]

    #     :param file: :class:`~torf.File` object

    #     Example:

    #     >>> # Assuming `file` covers 100 pieces in the stream of concatenated files
    #     >>> tfs.validate_piece_indexes(file, (0, 1, 50, 60, -3, -2, -1, 1000))
    #     >>> [0, 1, 50, 60, 97, 98, 99]
    #     """
    #     # _log.debug('Validating piece indexes: %r', wanted_piece_indexes)
    #     validated_piece_indexes = set()
    #     min_piece_index = 0
    #     max_piece_index = math.floor((file.size - 1) / self._torrent.piece_size)
    #     # _log.debug(f'max_piece_index = math.floor({file.size - 1} / {self._torrent.piece_size}) = {max_piece_index}')
    #     for wpi in wanted_piece_indexes:
    #         vwpi = int(wpi)
    #         if wpi < 0:
    #             # _log.debug(f'vwpi = {max_piece_index} - abs(int({wpi}))')
    #             vwpi = max_piece_index - abs(wpi) + 1
    #         vwpi = max(min_piece_index, min(max_piece_index, vwpi))
    #         # _log.debug('Validated piece index %r: %r', wpi, vwpi)
    #         validated_piece_indexes.add(vwpi)
    #     # _log.debug('Validated piece indexes: %r', sorted(validated_piece_indexes))
    #     return sorted(validated_piece_indexes)

    def get_absolute_piece_indexes(self, file, relative_piece_indexes):
        """
        Return list of sanitized absolute piece indexes

        :param file: :class:`~torf.File` object
        :param relative_piece_indexes: Sequence of piece indexes within `file`;
            negative values address pieces at the end of `file`, e.g. [0, 12,
            -1, -2]

        Example:

        >>> # Assume `file` starts in the 50th piece in the stream of
        >>> # concatenated files and is 100 pieces long. `1000` and `-1000` are
        >>> # ignored because they are out of bounds.
        >>> tfs.validate_piece_indexes(file, (0, 1, 70, 75, 1000, -1000, -3, -2, -1))
        [50, 51, 120, 125, 147, 148, 149]
        """
        # _log.debug('###############################')
        # _log.debug('Absolutizing relative piece indexes: %r', relative_piece_indexes)
        file_piece_indexes = self.get_piece_indexes_for_file(file)
        # _log.debug('Piece indexes for %r: %r', file, file_piece_indexes)
        pi_abs_min = file_piece_indexes[0]
        pi_abs_max = file_piece_indexes[-1]
        pi_rel_min = 0
        pi_rel_max = pi_abs_max - pi_abs_min
        # _log.debug(f'  pi_rel_min = {pi_rel_min}')
        # _log.debug(f'  pi_rel_max = {pi_rel_max}')

        validated_piece_indexes = set()
        for pi_rel in relative_piece_indexes:
            pi_rel = int(pi_rel)
            # _log.debug('  relative piece index: %r', pi_rel)

            # Convert negative to absolute index
            if pi_rel < 0:
                # _log.debug(f'    pi_rel = {pi_rel_max} - abs({pi_rel}) + 1')
                pi_rel = pi_rel_max - abs(pi_rel) + 1

            # Ensure relative piece_index is within bounds
            pi_rel = max(pi_rel_min, min(pi_rel_max, pi_rel))

            # Convert to absolute piece_index
            pi_abs = pi_abs_min + pi_rel
            # _log.debug(f'    pi_abs = {pi_abs_min} + {pi_rel} = {pi_abs}')
            validated_piece_indexes.add(pi_abs)

        # _log.debug('Validated piece indexes: %r', sorted(validated_piece_indexes))
        return sorted(validated_piece_indexes)

    def get_piece(self, piece_index):
        """
        Return piece at `piece_index` or `None` if required files don't exist

        :param piece_index: Piece index within stream of concatenated files

        Errors from reading files existing (e.g. :class:`PermissionError`) are
        raised as :class:`~.errors.ContentError`.
        """
        # _log.debug('###############################')
        piece_size = self._torrent.piece_size
        torrent_size = sum(f.size for f in self._torrent.files)
        # for f in self._torrent.files:
        #     _log.debug(f'{f}: {f.size}')
        # _log.debug(f'total: {torrent_size}')
        min_piece_index = 0
        max_piece_index = math.floor((torrent_size - 1) / piece_size)
        # _log.debug(f'max_piece_index = math.floor(({torrent_size} - 1) / {piece_size}) = {max_piece_index}')
        if not min_piece_index <= piece_index <= max_piece_index:
            raise ValueError(f'piece_index must be in range {min_piece_index} - {max_piece_index}: {piece_index}')

        # Find out which files we need to read from
        first_byte_index_of_piece = piece_index * piece_size
        last_byte_index_of_piece = min(
            first_byte_index_of_piece + piece_size - 1,
            torrent_size - 1,
        )
        relevant_files = self.get_files_for_byte_range(first_byte_index_of_piece, last_byte_index_of_piece)
        _log.debug('Relevant files for %r .. %r: %r', first_byte_index_of_piece, last_byte_index_of_piece, relevant_files)

        # Find out where to start reading in the first relevant file
        if len(relevant_files) == 1:
            # Our piece belongs to a single file
            file_pos = self.get_file_position(relevant_files[0])
            seek_to = first_byte_index_of_piece - file_pos
            _log.debug(f'  seek_to = {first_byte_index_of_piece} - {file_pos} = {seek_to}')

        else:
            # Our piece is spread over multiple files
            file = self.get_file_at_position(first_byte_index_of_piece)
            file_pos = self.get_file_position(file)

            if file == relevant_files[0]:
                # Our piece starts at or after the first byte of `file`, e.g.
                seek_to = file.size - ((file_pos + file.size) % piece_size)
                _log.debug(f'  seek_to = {file.size} - (({file_pos} + {file.size}) % {piece_size}) = {seek_to}')

            else:
                raise RuntimeError('Implement me!')
                # # Our piece starts before the first byte of `file`, e.g.
                # # Piece Index: 0       1_______2       3
                # # File Stream: aaaaaaaaaabbbbbbbbbbbbbbbbbbbb
                # first_relevant_file_pos = self.get_file_position(relevant_files[0])
                # _log.debug(f'  {relevant_files[0]} starts at %r', first_relevant_file_pos)
                # seek_to = relevant_files[0].size - ((first_relevant_file_pos + relevant_files[0].size) % piece_size)
                # _log.debug(f'  seek_to = {relevant_files[0].size} - (({first_relevant_file_pos} + '
                #            f'{relevant_files[0].size}) % {piece_size}) = {seek_to}')

        # Read piece data from `relevant_files`
        bytes_to_read = piece_size
        piece = bytearray()
        for f in relevant_files:
            _log.debug('Reading from %r', f)
            fh = self._get_open_file(f)

            # We can't read the piece if any `relevant_file` is missing
            if fh is None:
                return None

            # It's theoretically possible that a differntly sized file can
            # produce the correct piece, b ut we assume the file is not what
            # we're looking for if it doesn't have the expected size.
            elif f.size != self._get_file_size_from_fs(f):
                _log.debug('  Mismatching file sizes: %r != %r', f.size, self._get_file_size_from_fs(f))
                return None

            try:
                if seek_to != 0:
                    _log.debug('  Seeking to %r in %r', seek_to, f)
                    fh.seek(seek_to)
                    seek_to = 0

                _log.debug('  Reading %r bytes at %r', bytes_to_read, fh.tell())
                content = fh.read(bytes_to_read)
                bytes_to_read -= len(content)
                _log.debug('  Read %d bytes: %r', len(content), _display_piece(content))
                _log.debug('  %d left to read', bytes_to_read)
                piece.extend(content)
                _log.debug('  Piece has now %d bytes: %r', len(piece), _display_piece(piece))
            except OSError as e:
                msg = e.strerror if e.strerror else e
                raise errors.ContentError(f'Failed to read from {f}: {msg}')

        # Ensure expected `piece` length
        if last_byte_index_of_piece == torrent_size - 1:
            exp_piece_size = torrent_size % piece_size
            if exp_piece_size == 0:
                exp_piece_size = piece_size
        else:
            exp_piece_size = piece_size
        # _log.debug('  Expected piece size: %r', exp_piece_size)
        # _log.debug('    Actual piece size: %r', len(piece))

        ### Not needed since we exlude any size-mismatching files
        # # Add padding zero bytes if one file was shorter than expected
        # if len(piece) < exp_piece_size:
        #     padding = b'\x00' * (exp_piece_size - len(piece))
        #     _log.debug('  Adding %d padding bytes: %r', len(padding), padding)
        #     piece.extend(padding)

        assert len(piece) == exp_piece_size, (len(piece), exp_piece_size)
        return bytes(piece)

    def _get_file_size_from_fs(self, file):
        filepath = os.path.join(self._location, file)
        if os.path.exists(filepath):
            try:
                return os.path.getsize(filepath)
            except OSError as e:
                _log.debug('Ignoring OSError: %r', e)
        else:
            _log.debug('No such file: %r', filepath)

    def _get_open_file(self, file):
        filepath = os.path.join(self._location, file)
        if filepath not in self._open_files:
            if not os.path.exists(filepath):
                return None
            else:
                try:
                    self._open_files[filepath] = open(filepath, 'rb')
                except OSError as e:
                    msg = e.strerror if e.strerror else e
                    raise errors.ContentError(f'Failed to open {filepath}: {msg}')
        return self._open_files.get(filepath, None)

    def get_piece_hash(self, piece_index):
        """
        Read piece at `piece_index` from file(s) and return its SHA1 hash

        :raise ContentError: if a file exists but cannot be read

        :return: :class:`bytes`
        """
        piece = self.get_piece(piece_index)
        _log.debug('Piece %d: %r bytes: %r',
                   piece_index,
                   None if piece is None else len(piece),
                   None if piece is None else _display_piece(piece))
        if piece is not None:
            return hashlib.sha1(piece).digest()

    @property
    def torrent_piece_hashes(self):
        """Sequence of piece hashes stored in torrent"""
        pieces = self._torrent.metainfo['info']['pieces']
        piece_hashes = tuple(
            pieces[i : i + 20]
            for i in range(0, len(pieces), 20)
        )
        assert pieces[:20] == piece_hashes[0], (pieces[:20], piece_hashes[0])
        assert pieces[-20:] == piece_hashes[-1], (pieces[-20:], piece_hashes[-1])
        return piece_hashes

    def verify_piece(self, piece_index):
        """
        Generate SHA1 hash for piece at `piece_index` and compare to the expected
        hash in the torrent

        :raise ContentError: if a file exists but cannot be read

        :return: `True` if both hash values are equal, `False` otherwise
        """
        _log.debug('Verifying piece index: %r', piece_index)
        try:
            stored_piece_hash = self.torrent_piece_hashes[piece_index]
        except IndexError:
            max_piece_index = len(self.torrent_piece_hashes) - 1
            raise ValueError(f'piece_index must be in range 0 - {max_piece_index}: {piece_index}')

        generated_piece_hash = self.get_piece_hash(piece_index)
        if generated_piece_hash is not None:
            _log.debug('Comparing piece hash: %r =? %r', stored_piece_hash, generated_piece_hash)
            return stored_piece_hash == generated_piece_hash


def _display_piece(piece):
    import binascii
    return (binascii.hexlify(piece[:4], ':')
            + b'...'
            + binascii.hexlify(piece[-4:], ':'))
