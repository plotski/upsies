import functools
import os
import re

from .. import __project_name__
from . import LazyModule, pretty_bytes

import logging  # isort:skip
_log = logging.getLogger(__name__)

tempfile = LazyModule(module='tempfile', namespace=globals())


def _check_dir_access(path):
    if not os.path.isdir(path):
        raise OSError(f'Not a directory: {path}')
    elif not os.access(path, os.R_OK):
        raise OSError(f'Not readable: {path}')
    elif not os.access(path, os.W_OK):
        raise OSError(f'Not writable: {path}')
    elif not os.access(path, os.X_OK):
        raise OSError(f'Not executable: {path}')


@functools.lru_cache(maxsize=None)
def tmpdir():
    """Return temporary directory path in /tmp/ or similar"""
    tmpdir_ = tempfile.mkdtemp()
    parent_path = os.path.dirname(tmpdir_)
    tmpdir = os.path.join(parent_path, __project_name__)
    if os.path.exists(tmpdir):
        os.rmdir(tmpdir_)
    else:
        os.rename(tmpdir_, tmpdir)
    _check_dir_access(tmpdir)
    _log.debug('Using temporary directory: %r', tmpdir)
    return tmpdir


@functools.lru_cache(maxsize=None)
def projectdir(content_path):
    """
    Return path to existing directory in which jobs put their files

    :param str content_path: Path to torrent content

    :raise RuntimeError: if `content_path` exists and is not a directory or has
        insufficient permissions
    """
    if content_path:
        path = basename(content_path)
        path += '.upsies'
    else:
        path = '.'
    if not os.path.exists(path):
        os.mkdir(path)
    _check_dir_access(path)
    _log.debug('Using project directory: %r', path)
    return path


def basename(path):
    """
    Return last segment in `path`

    Unlike :func:`os.path.basename`, this `rstrip`s any directory separators
    first.

    >>> os.path.basename('a/b/c/')
    ''
    >>> os.path.basename('a/b/c/'.rstrip('/'))
    'c'
    """
    return os.path.basename(str(path).rstrip(os.sep))


def dirname(path):
    """
    Remove last segment in `path`

    Unlike :func:`os.path.dirname`, this `rstrip`s any directory separators
    first.

    >>> os.path.dirname('a/b/c/')
    'a/b/c'
    >>> os.path.dirname('a/b/c/'.rstrip('/'))
    'a/b'
    """
    return os.path.dirname(str(path).rstrip(os.sep))


def file_extension(path):
    """
    Extract file extension

    Unlike :func:`os.path.splitext`, this function expects the extension to be 1-3
    characters long and consist only of ascii characters or numbers.

    :param str path: Path to file

    :return: file extension
    :rtype: str
    """
    path = str(path)
    if '.' in path:
        return re.sub(r'^.*?\.([a-zA-Z0-9]{1,3})$', r'\1', path).lower()
    else:
        return ''


# Stolen from torf-cli
# https://github.com/rndusr/torf-cli/blob/master/torfcli/_utils.py

_DOWN       = '\u2502'  # noqa: E221  # │
_DOWN_RIGHT = '\u251C'  # noqa: E221  # ├
_RIGHT      = '\u2500'  # noqa: E221  # ─
_CORNER     = '\u2514'  # noqa: E221  # └

def file_tree(tree, _parents_is_last=()):
    """
    Create a pretty file tree

    :param tree: Nested 2-tuples: The first item is the file or directory name,
        the second item is the file size for files or a tuple for directories
    """
    lines = []
    max_i = len(tree) - 1
    for i,(name,node) in enumerate(tree):
        is_last = i >= max_i

        # Assemble indentation string (`_parents_is_last` being empty means
        # this is the top node)
        indent = ''
        if _parents_is_last:
            # `_parents_is_last` holds the `is_last` values of our ancestors.
            # This lets us construct the correct indentation string: For
            # each parent, if it has any siblings below it in the directory,
            # print a vertical bar ('|') that leads to the siblings.
            # Otherwise the indentation string for that parent is empty.
            # We ignore the first/top/root node because it isn't indented.
            for parent_is_last in _parents_is_last[1:]:
                if parent_is_last:
                    indent += '  '
                else:
                    indent += f'{_DOWN} '

            # If this is the last node, use '└' to stop the line, otherwise
            # branch off with '├'.
            if is_last:
                indent += f'{_CORNER}{_RIGHT}'
            else:
                indent += f'{_DOWN_RIGHT}{_RIGHT}'

        if isinstance(node, int):
            lines.append(f'{indent}{name} ({pretty_bytes(node)})')
        else:
            lines.append(f'{indent}{name}')
            # Descend into child node
            sub_parents_is_last = _parents_is_last + (is_last,)
            lines.append(file_tree(node, _parents_is_last=sub_parents_is_last))

    return '\n'.join(lines)
