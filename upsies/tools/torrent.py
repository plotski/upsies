from os.path import exists as _path_exists

from .. import __project_name__, __version__, errors
from ..utils import LazyModule

import logging  # isort:skip
_log = logging.getLogger(__name__)

torf = LazyModule(module='torf', namespace=globals())


def create(*, content_path, announce, torrent_path,
           init_callback, progress_callback,
           overwrite=False, source=None, exclude=()):
    """
    Generate and write torrent file

    :param str content_path: Path to the torrent's content
    :param str announce: Announce URL
    :param str torrent_path: Path of the generated torrent file
    :param str init_callback: Callable that is called once before torrent
        generation commences, gets a nested sequence of `(directory_name,
        ((file_name, file_size), ...))` `(file_name, file_size)` tuples
    :param str progress_callback: Callable that gets the generation progress as
        a number between 0 and 100
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
    else:
        try:
            torrent = torf.Torrent(
                path=content_path,
                exclude_regexs=exclude,
                trackers=((announce,),),
                private=True,
                source=source,
                created_by=f'{__project_name__} {__version__}',
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
