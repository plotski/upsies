"""
Find download path for a torrent, hardlinking existing files
"""

import functools
import os

from ..utils import LazyModule, cached_property, fs, torrent
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
        self._default_location = default
        self._locations = tuple(location for location in locations if location)
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
                target_location = self._find_target_location()
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

    def _each_file(self, *paths):
        # Yield (filepath, path) tuples where the first item is always an
        # existing file beneath the path in the second item and the second item
        # is a path from `paths`. If there is a file path in `paths`, it is
        # yielded as both items of the tuple.
        for path in paths:
            if not os.path.isdir(path):
                yield path, path
            else:
                for root, dirnames, filenames in os.walk(path, followlinks=True):
                    for filename in filenames:
                        yield os.path.join(root, filename), path

    @cached_property
    def _torrent_files(self):
        # List of files in torrent, sorted by size (descending)
        return sorted(self._torrent.files, key=lambda file: file.size, reverse=True)

    def _find_target_location(self):
        target_location = None
        missing_torrent_files = list(self._torrent_files)
        for file in self._torrent_files:
            for filepath, location in self._each_file(*self._locations):

                # Exclude files with wrong size
                if self._is_size_match(file, filepath):
                    # The first location any matching file is found in is the
                    # torrent's download path
                    _log.debug('Size match: %r: %r', file, filepath)
                    if target_location is None:
                        target_location = location

                    # Ensure the expected path exists
                    target_path = os.path.join(target_location, str(file))
                    self._create_link(filepath, target_path)

                    # Compare some pieces to address file size collisions
                    if self._is_pieces_match(location, file):
                        _log.debug('Pieces match: %r: %r', file, filepath)

                        # Stop searching if we have found all files
                        if file in missing_torrent_files:
                            missing_torrent_files.remove(file)
                        if not missing_torrent_files:
                            break

                    else:
                        _log.debug('Pieces mismatch: %r: %r', file, filepath)

                        # Remove the link we created because pieces in torrent
                        # don't match the content of the existing file
                        self._remove_link(target_path)

                        # If this was the first size-matching file we found,
                        # forget any previously set target_location
                        if not self._links_created:
                            target_location = None

        return target_location

    @functools.lru_cache(maxsize=None)
    def _is_size_match(self, torrentfile, filepath):
        # Return whether a file in a torrent and an existing file are the same.
        return torrentfile.size == fs.file_size(filepath)

    @functools.lru_cache(maxsize=None)
    def _is_pieces_match(self, location, file):
        with torrent.TorrentFileStream(self._torrent, location) as tfs:
            file_piece_indexes = tfs.get_absolute_piece_indexes(file, (
                0,
                1,
                -2,
                -1,
            ))
            _log.debug('##################################################')
            _log.debug('Verifying pieces of %r: %r', file, file_piece_indexes)
            for piece_index in file_piece_indexes:
                if tfs.verify_piece(piece_index):
                    _log.debug('Piece %d is valid', piece_index)
                else:
                    _log.debug('Piece %d is invalid!', piece_index)
                    return False
        return True

    def _create_link(self, source, target):
        if not os.path.exists(target):
            # Create parent directory if it doesn't exist
            target_parent = os.path.dirname(target)
            try:
                _log.debug(f'os.makedirs({target_parent!r}, exist_ok=True)')
                os.makedirs(target_parent, exist_ok=True)
            except OSError as e:
                msg = e.strerror if e.strerror else e
                self.error(f'Failed to create directory: {target_parent}: {msg}')
            else:
                # Create hardlink
                _log.debug(f'os.link({source!r}, {target!r})')
                try:
                    os.link(source, target)
                except OSError as e:
                    msg = e.strerror if e.strerror else e
                    self.error(f'Failed to create link: {target}: {msg}')
                else:
                    self._links_created[target] = source

    def _remove_link(self, target):
        # Only remove links we created ourselves
        if target in self._links_created and os.path.exists(target):
            try:
                _log.debug('Removing falsely created link: %r', target)
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
