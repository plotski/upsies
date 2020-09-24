from os.path import exists as _path_exists

from .. import errors
from ..utils import LazyModule

import logging  # isort:skip
_log = logging.getLogger(__name__)

torf = LazyModule(module='torf', namespace=globals())


def create(*, content_path, announce_url, torrent_path,
           init_callback, progress_callback,
           overwrite=False, source=None, exclude_regexs=()):

    def cb(torrent, filepath, pieces_done, pieces_total):
        return progress_callback(pieces_done / pieces_total * 100)

    if not overwrite and _path_exists(torrent_path):
        _log.debug('Torrent file already exists: %r', torrent_path)
    else:
        try:
            torrent = torf.Torrent(
                path=content_path,
                exclude_regexs=exclude_regexs,
                trackers=((announce_url,),),
                private=True,
                source=source,
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

    assert _path_exists(torrent_path)
    return torrent_path


def _make_file_tree(tree):
    files = []
    for name,file in tree.items():
        if isinstance(file, dict):
            subtree = _make_file_tree(file)
            files.append((name, subtree))
        else:
            files.append((name, file.size))
    return tuple(files)
