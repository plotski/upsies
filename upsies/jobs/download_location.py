"""
Find download path for a torrent, hardlinking existing files
"""

import collections
import functools
import os

from ..utils import LazyModule, fs, torrent
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

torf = LazyModule(module='torf', namespace=globals())


class DownloadLocationJob(JobBase):
    """
    Find download path for a torrent, hardlinking existing files

    :param torrent: Path to torrent file
    :param locations: Sequence of directory paths that are searched for files in
        `torrent`
    :param default: Default download path if the files in `torrent` are not
        found
    """

    name = 'download-location'
    label = 'Download Location'
    hidden = True
    cache_id = None

    def initialize(self, *, torrent, locations, default=None):
        """
        Set internal state

        :param torrent: Path to torrent file
        """
        self._torrent_filepath = torrent
        # The torrent file is read in execute()
        self._torrent = None
        self._default_location = default
        self._locations = tuple(location for location in locations if location)
        # Map target paths to source paths
        self._links_created = {}

    def execute(self):
        if not self._locations:
            self.error('You must provide at least one location.')
        else:
            try:
                self._torrent = torf.Torrent.read(self._torrent_filepath)
            except torf.TorfError as e:
                self.error(e)
            else:
                target_location = self._get_target_location()
                if target_location is not None:
                    _log.debug('Outputting target location: %r', target_location)
                    self.send(target_location)
                elif self._default_location:
                    _log.debug('Outputting default location: %r', self._default_location)
                    self.send(self._default_location)
                else:
                    _log.debug('Outputting first location: %r', self._locations[0])
                    self.send(self._locations[0])
                self.finish()

    def _get_target_location(self):
        file_candidates = self._get_file_candidates()
        if file_candidates:
            _log.debug('### Finding piece-matching files')
        else:
            _log.debug('### Failed to find any size-matching files')

        links = {}
        target_location = None
        # `paths` maps relative file paths expected by torrent to a
        # candidate dictionary from `file_candidates`.
        for paths in self._each_set_of_linked_candidates(self._check_location, file_candidates):
            for file, candidate in paths.items():
                if file not in links:
                    if self._verify_file(file):
                        if target_location is None:
                            _log.debug('Setting target location: %r', candidate['location'])
                            target_location = candidate['location']

                        _log.debug('Using %r', candidate['filepath'])
                        links[file] = (candidate['filepath'], os.path.join(target_location, file))
                    else:
                        _log.debug('Not using %r', candidate['filepath'])
                else:
                    _log.debug('Already linked: %r', file)

        for source, target in links.values():
            self._create_hardlink(source, target)

        return target_location

    def _verify_file(self, file):
        _log.debug('Verifying content of %r at %r', file, self._check_location)
        with torrent.TorrentFileStream(self._torrent, self._check_location) as tfs:
            # Don't check the first and the last piece of a file as they likely
            # overlap with another file that might be either invalid or missing
            file_piece_indexes = tfs.get_absolute_piece_indexes(file, (1, -2))
            _log.debug('Verifying pieces: %r', file_piece_indexes)
            for piece_index in file_piece_indexes:
                piece_ok = tfs.verify_piece(piece_index)
                if piece_ok is True:
                    _log.debug('Piece %d is valid', piece_index)
                elif piece_ok is False:
                    _log.debug('Piece %d is invalid!', piece_index)
                    return False
                elif piece_ok is None:
                    _log.debug('Piece %d is unverifiable; assume non-existing file', piece_index)
                    return None
        return True

    def _each_set_of_linked_candidates(self, location, file_candidates):
        _log.debug('Iterating over sets of symlinks beneath %r', location)
        for pairs in _Combinator(file_candidates):
            links_created = []
            try:
                for file, candidate in pairs:
                    source = os.path.abspath(candidate['filepath'])
                    target = os.path.join(location, file)
                    self._create_symlink(source, target)
                    links_created.append((source, target))

                yield {file: candidate for file, candidate in pairs}

            finally:
                for source, target in links_created:
                    self._remove_link(target)

    def _get_file_candidates(self):
        # Map relative file paths expected by torrent to lists of files that
        # have the same size. A candidate is a dictionary that stores relevant
        # paths (see below).
        size_matching_files = collections.defaultdict(lambda: [])
        torrent_files = tuple(self._torrent.files)
        for filepath, location in self._each_file(*self._locations):
            for file in torrent_files:
                if self._is_size_match(file, filepath):
                    _log.debug('Size match for %r: %r', file, filepath)
                    #     file: Relative path within torrent
                    # location: Download path to give to the BitTorrent client
                    #           along with the torrent file
                    # filepath: Existing file path with same size as `file`
                    size_matching_files[file].append({
                        'location': location,
                        'filepath': filepath,
                    })
        return size_matching_files

    def _each_file(self, *paths):
        # Yield (filepath, path) tuples where the first item is a file (more
        # specifically: a non-directory) beneath the second item. The second
        # item is a path from `paths`. If there is a file path in `paths`, it is
        # yielded as both items of the tuple.
        for path in paths:
            _log.debug('Searching %s', path)
            if not os.path.isdir(path):
                yield str(path), str(path)
            else:
                for root, dirnames, filenames in os.walk(path, followlinks=True):
                    for filename in filenames:
                        yield str(os.path.join(root, filename)), str(path)

    @functools.lru_cache(maxsize=None)
    def _is_size_match(self, torrentfile, filepath):
        # Return whether a file in a torrent and an existing file are the same size
        return torrentfile.size == fs.file_size(filepath)

    def _create_hardlink(self, source, target):
        return self._create_link(os.link, source, target)

    def _create_symlink(self, source, target):
        return self._create_link(os.symlink, source, target)

    def _create_link(self, create_link_function, source, target):
        if not os.path.exists(target):
            # Create parent directory if it doesn't exist
            target_parent = os.path.dirname(target)
            try:
                # _log.debug(f'os.makedirs({target_parent!r}, exist_ok=True)')
                os.makedirs(target_parent, exist_ok=True)
            except OSError as e:
                msg = e.strerror if e.strerror else e
                self.error(f'Failed to create directory: {target_parent}: {msg}')
            else:
                # Create hardlink
                _log.debug(f'{create_link_function.__qualname__}({source!r}, {target!r})')
                try:
                    create_link_function(source, target)
                except OSError as e:
                    msg = e.strerror if e.strerror else e
                    self.error(f'Failed to create link: {target}: {msg}')
                else:
                    # Keep track of created links so that _remove_link() can
                    # refuse to delete anything we didn't create.
                    self._links_created[target] = source
        else:
            _log.debug('Already exists: %r', target)

    def _remove_link(self, target):
        # Only remove links we created ourselves.
        if target not in self._links_created:
            _log.debug('Refusing to delete %r: %r', target, self._links_created)
        elif os.path.exists(target):
            try:
                _log.debug(f'os.unlink({target!r})')
                os.unlink(target)
            except OSError as e:
                self.exception(e)
            else:
                del self._links_created[target]

                # Remove empty parent directories
                target_parent = os.path.dirname(target)
                try:
                    os.removedirs(target_parent)
                except OSError:
                    pass

    @property
    def _check_location(self):
        """Where to create temporary symlinks to verify pieces"""
        return os.path.join(self.cache_directory, self.name)


class _Combinator(collections.abc.Iterable):
    """
    Take a dictionary that maps keys to lists and turn it into a list of all
    possible ``(key, list item)`` combinations

    Example:

    >>> things = {
    >>>     'a': ['a1', 'a2'],
    >>>     'b': ['b1'],
    >>>     'c': ['c1', 'c2', 'c3', 'c4'],
    >>> }
    >>> _Combinator(things).combinations
    >>> [
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c3')],
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c4')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c1')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c2')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c3')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c4')],
    >>> ]
    """

    def __init__(self, candidates):
        self._candidates = {
            key: tuple(cands)
            for key, cands in candidates.items()
        }
        self._keys = tuple(self._candidates)
        self._indexes = {key: 0 for key in self._keys}

    def __len__(self):
        # Product of numbers of candidates
        length = 1
        for cands in self._candidates.values():
            length *= len(cands)
        return length

    def _advance(self):
        # Increase the rightmost index or reset it to zero
        # and increase the next index on the left
        for key in reversed(self._keys):
            if self._indexes[key] < len(self._candidates[key]) - 1:
                self._indexes[key] += 1
                break
            else:
                self._indexes[key] = 0

    @property
    def _pairs(self):
        # List of (key, list item) tuples for each key
        # using current list indexes
        pairs = []
        for key in self._keys:
            list_item = self._candidates[key][self._indexes[key]]
            pairs.append((key, list_item))
        return pairs

    def __iter__(self):
        combinations = []
        for _ in range(len(self)):
            combinations.append(self._pairs)
            self._advance()
        return iter(combinations)
