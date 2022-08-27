"""
Create torrent file
"""

import collections
import datetime
import errno
import hashlib
import math
import os
import time

from .. import __project_name__, __version__, constants, errors, utils
from . import LazyModule, fs, types

torf = LazyModule(module='torf', namespace=globals())


def create(*, content_path, announce, source, torrent_path,
           use_cache=True, exclude=(), reuse_torrent_path=None,
           init_callback, progress_callback):
    """
    Generate and write torrent file

    :param str content_path: Path to the torrent's payload
    :param str announce: Announce URL
    :param str source: Value of the ``source`` field in the torrent. This makes
        the torrent unique for each tracker to avoid cross-seeding issues, so it
        is usually the tracker's abbreviated name.
    :param str torrent_path: Path of the generated torrent file
    :param init_callback: Callable that is called once before torrent generation
        commences. It gets `content_path` as a tree where each node is a tuple
        in which the first item is the directory name and the second item is a
        sequence of `(file_name, file_size)` tuples.

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
    :param progress_callback: Callable that is called at regular intervals with
        a :class:`CreateTorrentProgress` or :class:`FindTorrentProgress` object
        as a positional argument
    :param exclude: Sequence of regular expressions that are matched against
        file system paths. Matching files are not included in the torrent.
    :param bool use_cache: Whether to get piece hashes from previously created
        torrents or from `reuse_torrent_path`
    :param reuse_torrent_path: Path to existing torrent file to get hashed
        pieces and piece size from. If the given torrent file doesn't match the
        files in the torrent we want to create, hash the pieces normally.

        If this is a directory, search it recursively for ``*.torrent`` files
        and use the first one that matches.

        Non-existing or otherwise unreadable paths as well as falsy values
        (e.g. ``""`` or `None`) are silently ignored.

        If this is a sequence, its items are expected to be directory or file
        paths and handled as described above.

    Callbacks can cancel the torrent creation by returning `True` or any other
    truthy value.

    :raise TorrentError: if anything goes wrong

    :return: `torrent_path` or `None` if cancelled
    """
    if not announce:
        raise errors.TorrentError('Announce URL is empty')
    if not source:
        raise errors.TorrentError('Source is empty')

    # Create Torrent object
    torrent = _get_torrent(
        content_path=content_path,
        exclude=exclude,
        announce=announce,
        source=source,
    )
    # Report files with `exclude` applied
    cancelled = init_callback(_make_file_tree(torrent.filetree))
    if cancelled:
        return None

    if use_cache:
        # Try to get piece hashes from existing torrent
        cancelled = _find_hashes(
            torrent=torrent,
            reuse_torrent_path=reuse_torrent_path,
            callback=progress_callback,
        )
        if cancelled:
            return None

    if not torrent.is_ready:
        # Hash pieces
        cancelled = _generate_hashes(
            torrent=torrent,
            callback=progress_callback,
        )
        if cancelled:
            return None

    # Write generic torrent so we can reuse the hashes in the future
    _store_generic_torrent(torrent)

    # Write torrent to `torrent_path`
    _write_torrent_path(torrent, torrent_path)
    return torrent_path


def _get_torrent(*, content_path, exclude, announce, source):
    try:
        return torf.Torrent(
            path=content_path,
            exclude_regexs=exclude,
            trackers=((announce,),),
            source=source,
            private=True,
            created_by=f'{__project_name__} {__version__}',
            creation_date=time.time(),
        )
    except torf.TorfError as e:
        raise errors.TorrentError(str(e))


def _generate_hashes(*, torrent, callback):
    wrapped_callback = _CreateTorrentCallback(callback)
    try:
        torrent.generate(
            callback=wrapped_callback,
            interval=1.0,
        )
    except torf.TorfError as e:
        raise errors.TorrentError(str(e))
    else:
        return wrapped_callback.return_value


def _find_hashes(*, torrent, reuse_torrent_path, callback):
    wrapped_callback = _FindTorrentCallback(callback)
    try:
        torrent.reuse(
            _get_reuse_torrent_paths(torrent, reuse_torrent_path),
            callback=wrapped_callback,
            interval=1.0,
        )
    except torf.TorfError as e:
        raise errors.TorrentError(str(e))
    else:
        return wrapped_callback.return_value


def _get_reuse_torrent_paths(torrent, reuse_torrent_path):
    reuse_torrent_paths = []
    if reuse_torrent_path:
        if isinstance(reuse_torrent_path, str):
            reuse_torrent_paths.append(reuse_torrent_path)
        elif isinstance(reuse_torrent_path, collections.abc.Iterable):
            reuse_torrent_paths.extend(p for p in reuse_torrent_path if p)
        else:
            raise ValueError(f'Invalid reuse_torrent_path: {reuse_torrent_path!r}')

    generic_torrent_path = _get_generic_torrent_path(torrent=torrent, create_directory=False)
    reuse_torrent_paths.insert(0, generic_torrent_path)
    return reuse_torrent_paths


def _store_generic_torrent(torrent):
    generic_torrent = torf.Torrent(
        private=True,
        created_by=f'{__project_name__} {__version__}',
        creation_date=time.time(),
        comment='This torrent is used to cache previously hashed pieces.',
    )
    _copy_torrent_info(torrent, generic_torrent)
    generic_torrent_path = _get_generic_torrent_path(generic_torrent, create_directory=True)
    generic_torrent.write(generic_torrent_path, overwrite=True)


def _write_torrent_path(torrent, torrent_path):
    try:
        torrent.write(torrent_path, overwrite=True)
    except torf.TorfError as e:
        raise errors.TorrentError(str(e))


def _get_generic_torrent_path(torrent, create_directory=True):
    directory = constants.GENERIC_TORRENTS_DIRPATH
    if create_directory:
        try:
            fs.mkdir(directory)
        except errors.ContentError as e:
            raise errors.TorrentError(f'{directory}: {e}')

    cache_id = _get_torrent_id(torrent)
    filename = f'{torrent.name}.{cache_id}.torrent'
    return os.path.join(directory, filename)


def _get_torrent_id_info(torrent):
    return {
        'name': torrent.name,
        'files': tuple((str(f), f.size) for f in torrent.files),
    }


def _get_torrent_id(torrent):
    return utils.semantic_hash(_get_torrent_id_info(torrent))


def _copy_torrent_info(from_torrent, to_torrent):
    from_info, to_info = from_torrent.metainfo['info'], to_torrent.metainfo['info']
    to_info['pieces'] = from_info['pieces']
    to_info['piece length'] = from_info['piece length']
    to_info['name'] = from_info['name']
    if 'length' in from_info:
        to_info['length'] = from_info['length']
    else:
        to_info['files'] = from_info['files']


def _make_file_tree(filetree):
    files = []
    for name,file in filetree.items():
        if isinstance(file, collections.abc.Mapping):
            subtree = _make_file_tree(file)
            files.append((name, subtree))
        else:
            files.append((name, file.size))
    return tuple(files)


class _CallbackBase:
    def __init__(self, callback):
        self._callback = callback
        self._progress_samples = []
        self._time_started = time.time()
        self.return_value = None

    def __call__(self, progress):
        self.return_value = return_value = self._callback(progress)
        return return_value

    def _calculate_info(self, items_done, items_total):
        time_now = time.time()
        percent_done = items_done / items_total * 100
        seconds_elapsed = time_now - self._time_started
        items_per_second = 0
        items_remaining = items_total - items_done
        seconds_remaining = 0

        self._add_sample(time_now, items_done)

        # Estimate how long torrent creation will take
        samples = self._progress_samples
        if len(samples) >= 2:
            # Calculate the difference between each pair of samples
            diffs = [
                b[1] - a[1]
                for a, b in zip(samples[:-1], samples[1:])
            ]
            items_per_second = self._get_average(diffs, weight_factor=1.1)
            if items_per_second > 0:
                seconds_remaining = items_remaining / items_per_second

        seconds_total = seconds_elapsed + seconds_remaining
        time_finished = self._time_started + seconds_total

        return {
            'percent_done': percent_done,
            'items_remaining': items_remaining,
            'items_per_second': items_per_second,
            'seconds_elapsed': datetime.timedelta(seconds=seconds_elapsed),
            'seconds_remaining': datetime.timedelta(seconds=seconds_remaining),
            'seconds_total': datetime.timedelta(seconds=seconds_total),
            'time_finished': datetime.datetime.fromtimestamp(time_finished),
            'time_started': datetime.datetime.fromtimestamp(self._time_started),
        }

    def _add_sample(self, time_now, items_done):
        def get_sample_age(sample):
            time_sample = sample[0]
            return time_now - time_sample

        samples = self._progress_samples
        samples.append((time_now, items_done))

        # Prune samples older than 10 seconds
        while samples and get_sample_age(samples[0]) > 10:
            del samples[0]

    def _get_average(self, samples, weight_factor, get_value=lambda sample: sample):
        # Give recent samples more weight than older samples
        # https://en.wikipedia.org/wiki/Moving_average
        weights = []
        for _ in range(len(samples)):
            try:
                weight = weights[-1]
            except IndexError:
                weight = 1
            weights.append(weight * weight_factor)

        return sum(
            get_value(sample) * weight
            for sample, weight in zip(samples, weights)
        ) / sum(weights)


class _CreateTorrentCallback(_CallbackBase):
    def __call__(self, torrent, filepath, pieces_done, pieces_total):
        info = self._calculate_info(pieces_done, pieces_total)
        piece_size = torrent.piece_size
        bytes_per_second = types.Bytes(info['items_per_second'] * piece_size)
        progress = CreateTorrentProgress(
            pieces_done=pieces_done,
            pieces_total=pieces_total,
            percent_done=info['percent_done'],
            bytes_per_second=bytes_per_second,
            piece_size=piece_size,
            total_size=torrent.size,
            filepath=filepath,
            seconds_elapsed=info['seconds_elapsed'],
            seconds_remaining=info['seconds_remaining'],
            seconds_total=info['seconds_total'],
            time_finished=info['time_finished'],
            time_started=info['time_started'],
        )
        return super().__call__(progress)


class _FindTorrentCallback(_CallbackBase):
    def __call__(self, torrent, filepath, files_done, files_total, status, exception):
        info = self._calculate_info(files_done, files_total)

        # Ignore "No such file or directory". This should only happen if the
        # generic torrent does not exist yet. For all other paths, torrent files
        # are collected from traversing directories.
        if isinstance(exception, torf.ReadError) and exception.errno == errno.ENOENT:
            exception = None

        progress = FindTorrentProgress(
            files_done=files_done,
            files_total=files_total,
            percent_done=info['percent_done'],
            files_per_second=info['items_per_second'],
            filepath=filepath,
            status=status,
            exception=errors.TorrentError(str(exception)) if exception else None,
            seconds_elapsed=info['seconds_elapsed'],
            seconds_remaining=info['seconds_remaining'],
            seconds_total=info['seconds_total'],
            time_finished=info['time_finished'],
            time_started=info['time_started'],
        )
        return super().__call__(progress)


class CreateTorrentProgress(collections.namedtuple(
    typename='CreateTorrentProgress',
    field_names=(
        'bytes_per_second',
        'filepath',
        'percent_done',
        'piece_size',
        'pieces_done',
        'pieces_total',
        'seconds_elapsed',
        'seconds_remaining',
        'seconds_total',
        'time_finished',
        'time_started',
        'total_size',
    ),
)):
    """
    :func:`~.collections.namedtuple` with these attributes:

        - ``bytes_per_second`` (:class:`~.types.Bytes`)
        - ``filepath`` (:class:`str`)
        - ``percent_done`` (:class:`float`)
        - ``piece_size`` (:class:`~.types.Bytes`)
        - ``pieces_done`` (:class:`int`)
        - ``pieces_total`` (:class:`int`)
        - ``seconds_elapsed`` (:class:`~.datetime.datetime.timedelta`)
        - ``seconds_remaining`` (:class:`~.datetime.datetime.timedelta`)
        - ``seconds_total`` (:class:`~.datetime.datetime.timedelta`)
        - ``time_finished`` (:class:`~.datetime.datetime.datetime`)
        - ``time_started`` (:class:`~.datetime.datetime.datetime`)
        - ``total_size`` (:class:`~.types.Bytes`)
    """


class FindTorrentProgress(collections.namedtuple(
    typename='CreateTorrentProgress',
    field_names=(
        'exception',
        'filepath',
        'files_done',
        'files_per_second',
        'files_total',
        'percent_done',
        'seconds_elapsed',
        'seconds_remaining',
        'seconds_total',
        'status',
        'time_finished',
        'time_started',
    ),
)):
    """
    :func:`~.collections.namedtuple` with these attributes:

        - ``exception`` (:class:`~.errors.TorrentError` or `None`)
        - ``filepath`` (:class:`str`)
        - ``files_done`` (:class:`int`)
        - ``files_per_second`` (:class:`int`)
        - ``files_total`` (:class:`int`)
        - ``percent_done`` (:class:`float`)
        - ``seconds_elapsed`` (:class:`~.datetime.datetime.timedelta`)
        - ``seconds_remaining`` (:class:`~.datetime.datetime.timedelta`)
        - ``seconds_total`` (:class:`~.datetime.datetime.timedelta`)
        - ``status`` (``hit``, ``miss`` or ``verifying``)
        - ``time_finished`` (:class:`~.datetime.datetime.datetime`)
        - ``time_started`` (:class:`~.datetime.datetime.datetime`)
    """


class TorrentFileStream:
    """
    Traverse files as they are described in a torrent

    :param torrent: :class:`~.torf.Torrent` object
    :param location: Path to location of files in `torrent`

    Instances should be used as a context manager to ensure all files are closed
    properly.

    Example:
    >>> torrent = torf.Torrent(...)
    >>> with TorrentFileStream(torrent, location='path/to/files') as tfs:
    >>>     # Get the 29th piece of the concatenated file stream
    >>>     piece = tfs.get_piece(29)
    """

    def __init__(self, torrent, location):
        self._torrent = torrent
        self._location = location
        self._open_files = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        """
        Close all opened files

        This is called automatically when the instance is used as a context
        manager.
        """
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
            for f in self._torrent.files:
                pos += f.size - 1
                if pos >= byte_index:
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
        pos = 0
        files = []
        for file in self._torrent.files:
            file_first_byte_index = pos
            file_last_byte_index = pos + file.size - 1
            if (
                    # Is first byte of file inside of range?
                    first_byte_index <= file_first_byte_index <= last_byte_index or
                    # Is last byte of file inside of range?
                    first_byte_index <= file_last_byte_index <= last_byte_index or
                    # Are all bytes of file inside of range?
                    (first_byte_index >= file_first_byte_index and last_byte_index <= file_last_byte_index)
            ):
                files.append(file)
            pos += file.size
        return files

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
        file_piece_indexes = self.get_piece_indexes_for_file(file)
        pi_abs_min = file_piece_indexes[0]
        pi_abs_max = file_piece_indexes[-1]
        pi_rel_min = 0
        pi_rel_max = pi_abs_max - pi_abs_min

        validated_piece_indexes = set()
        for pi_rel in relative_piece_indexes:
            pi_rel = int(pi_rel)

            # Convert negative to absolute index
            if pi_rel < 0:
                pi_rel = pi_rel_max - abs(pi_rel) + 1

            # Ensure relative piece_index is within bounds
            pi_rel = max(pi_rel_min, min(pi_rel_max, pi_rel))

            # Convert to absolute piece_index
            pi_abs = pi_abs_min + pi_rel
            validated_piece_indexes.add(pi_abs)

        return sorted(validated_piece_indexes)

    def get_piece(self, piece_index):
        """
        Return piece at `piece_index` or `None` if required files don't exist

        :param piece_index: Piece index within stream of concatenated files

        Errors from reading files existing (e.g. :class:`PermissionError`) are
        raised as :class:`~.errors.ContentError`.
        """
        piece_size = self._torrent.piece_size
        torrent_size = sum(f.size for f in self._torrent.files)

        min_piece_index = 0
        max_piece_index = math.floor((torrent_size - 1) / piece_size)
        if not min_piece_index <= piece_index <= max_piece_index:
            raise ValueError(f'piece_index must be in range {min_piece_index} - {max_piece_index}: {piece_index}')

        # Find out which files we need to read from
        first_byte_index_of_piece = piece_index * piece_size
        last_byte_index_of_piece = min(
            first_byte_index_of_piece + piece_size - 1,
            torrent_size - 1,
        )
        relevant_files = self.get_files_for_byte_range(first_byte_index_of_piece, last_byte_index_of_piece)

        # Find out where to start reading in the first relevant file
        if len(relevant_files) == 1:
            # Our piece belongs to a single file
            file_pos = self.get_file_position(relevant_files[0])
            seek_to = first_byte_index_of_piece - file_pos
        else:
            # Our piece is spread over multiple files
            file = self.get_file_at_position(first_byte_index_of_piece)
            file_pos = self.get_file_position(file)
            seek_to = file.size - ((file_pos + file.size) % piece_size)

        # Read piece data from `relevant_files`
        bytes_to_read = piece_size
        piece = bytearray()
        for f in relevant_files:
            fh = self._get_open_file(f)

            # We can't read the piece if any `relevant_file` is missing
            if fh is None:
                return None

            # It's theoretically possible that a differntly sized file can
            # produce the correct piece, but we assume the file is not what
            # we're looking for if it doesn't have the expected size.
            elif f.size != self._get_file_size_from_fs(f):
                return None

            try:
                fh.seek(seek_to)
                seek_to = 0

                content = fh.read(bytes_to_read)
                bytes_to_read -= len(content)
                piece.extend(content)
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
        assert len(piece) == exp_piece_size, (len(piece), exp_piece_size)
        return bytes(piece)

    def _get_file_size_from_fs(self, file):
        filepath = os.path.join(self._location, file)
        if os.path.exists(filepath):
            try:
                return os.path.getsize(filepath)
            except OSError:
                # Return None instead of raising an exception
                pass

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
        try:
            stored_piece_hash = self.torrent_piece_hashes[piece_index]
        except IndexError:
            max_piece_index = len(self.torrent_piece_hashes) - 1
            raise ValueError(f'piece_index must be in range 0 - {max_piece_index}: {piece_index}')

        generated_piece_hash = self.get_piece_hash(piece_index)
        if generated_piece_hash is not None:
            return stored_piece_hash == generated_piece_hash
