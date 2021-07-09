"""
Find download path for a torrent, hardlinking existing files
"""

import os

from ..utils import LazyModule, cached_property, fs
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

    def execute(self):
        if not self._locations:
            self.error('You must provide at least one location.')
        else:
            try:
                self._torrent = torf.Torrent.read(self._torrent_filepath)
            except torf.TorfError as e:
                self.error(e)
            else:
                link_map, target_location = self._make_link_map()
                for source, target in link_map.items():
                    _log.debug('\nln\n  %s\n  %s', source, target)
                    self._create_link(source, target)

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

    def _make_link_map(self):
        link_map = {}
        target_location = None
        missing_torrent_files = list(self._torrent_files)
        for file in self._torrent_files:
            for filepath, location in self._each_file(*self._locations):
                if self._is_match(file, filepath):
                    _log.debug('Match: %r: %r', file, filepath)
                    if target_location is None:
                        target_location = location

                    target_path = os.path.join(target_location, str(file))
                    link_map[filepath] = target_path

                    if file in missing_torrent_files:
                        missing_torrent_files.remove(file)
                    if not missing_torrent_files:
                        break

        return link_map, target_location

    def _create_link(self, source, target):
        if not os.path.exists(target):
            target_parent = os.path.dirname(target)
            try:
                _log.debug(f'os.makedirs({target_parent!r}, exist_ok=True)')
                os.makedirs(target_parent, exist_ok=True)
            except OSError as e:
                msg = e.strerror if e.strerror else e
                self.error(f'Failed to create directory: {target_parent}: {msg}')
            else:
                _log.debug(f'os.link({source!r}, {target!r})')
                try:
                    os.link(source, target)
                except OSError as e:
                    msg = e.strerror if e.strerror else e
                    self.error(f'Failed to create link: {target}: {msg}')

    def _is_match(self, torrentfile, filepath):
        # Return whether a file in a torrent and an existing file are the same.
        return torrentfile.size == fs.file_size(filepath)

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
        """List of files in torrent, sorted by size (descending)"""
        return sorted(self._torrent.files, key=lambda file: file.size, reverse=True)
