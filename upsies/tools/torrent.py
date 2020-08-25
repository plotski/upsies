from os.path import exists as _path_exists

import torf

from .. import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


def create(content_path, announce_url, torrent_path,
           init_callback, progress_callback,
           source=None, exclude_regexs=()):

    def cb(torrent, filepath, pieces_done, pieces_total):
        return progress_callback(pieces_done / pieces_total * 100)

    if _path_exists(torrent_path):
        _log.debug('Torrent file already exists: %r', torrent_path)
    else:
        try:
            torrent = torf.Torrent(
                path=content_path,
                trackers=((announce_url,),),
                source=source,
                exclude_regexs=exclude_regexs,
            )
            init_callback(_make_file_tree(torrent.filetree))
            success = torrent.generate(callback=cb, interval=0.5)
        except torf.TorfError as e:
            raise errors.TorrentError(e)

        if success:
            try:
                torrent.write(torrent_path)
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
