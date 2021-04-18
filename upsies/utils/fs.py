"""
File system helpers
"""

import functools
import os
import re

from .. import __project_name__, errors
from . import LazyModule, os_family, string

import logging  # isort:skip
_log = logging.getLogger(__name__)

tempfile = LazyModule(module='tempfile', namespace=globals())
natsort = LazyModule(module='natsort', namespace=globals())


def assert_file_readable(filepath):
    """Raise :exc:`~.ContentError` if `open(filepath)` fails"""
    try:
        open(filepath).close()
    except OSError as e:
        if e.strerror:
            raise errors.ContentError(f'{filepath}: {e.strerror}')
        else:
            raise errors.ContentError(f'{filepath}: {e}')


def assert_dir_usable(path):
    """Raise :exc:`~.ContentError` if `dirpath` can not be used as a directory"""
    if not os.path.isdir(path):
        raise errors.ContentError(f'{path}: Not a directory')
    elif not os.access(path, os.R_OK):
        raise errors.ContentError(f'{path}: Not readable')
    elif not os.access(path, os.W_OK):
        raise errors.ContentError(f'{path}: Not writable')
    elif not os.access(path, os.X_OK):
        raise errors.ContentError(f'{path}: Not executable')


@functools.lru_cache(maxsize=None)
def tmpdir():
    """Return path to existing temporary directory in /tmp/ or similar location"""
    tmpdir_ = tempfile.mkdtemp()
    parent_path = os.path.dirname(tmpdir_)
    tmpdir = os.path.join(parent_path, __project_name__)
    if os.path.exists(tmpdir):
        os.rmdir(tmpdir_)
    else:
        os.rename(tmpdir_, tmpdir)
    assert_dir_usable(tmpdir)
    _log.debug('Using temporary directory: %r', tmpdir)
    return tmpdir


@functools.lru_cache(maxsize=None)
def projectdir(content_path, base=None):
    """
    Return path to existing directory in which jobs put their files and cache

    :param str content_path: Path to torrent content
    :param str base: Location of the project directory; defaults to
        :func:`tmpdir`

    :raise ContentError: if `content_path` exists and is not a directory or has
        insufficient permissions
    """
    if content_path:
        if not base:
            base = tmpdir()
        else:
            mkdir(base)
        path = os.path.join(base, basename(content_path) + '.upsies')
    else:
        path = '.'
    if not os.path.exists(path):
        mkdir(path)
    _log.debug('Using project directory: %r', path)
    return path


def limit_directory_size(path, max_total_size):
    """
    Delete oldest files (by access time) until maximum size is not exceeded

    :func:`prune_empty_directories` is also called with `path`.

    :param path: Path to directory
    :param max_total_size: Maximum combined size of all files in `path` and its
        subdirectories
    """
    def size(path):
        return sum(file_size(f) for f in file_list(path))

    # This should return mtime if file system was mounted with noatime.
    def atime(filepath):
        statinfo = os.stat(filepath)
        return statinfo.st_atime

    # Remove oldest file until `path` size is small enough
    while size(path) > max_total_size:
        files = sorted(file_list(path), key=atime)
        if files:
            try:
                os.unlink(files[0])
            except OSError as e:
                if e.strerror:
                    raise RuntimeError(f'{files[0]}: Failed to prune: {e.strerror}')
                else:
                    raise RuntimeError(f'{files[0]}: Failed to prune: {e}')
                break

    prune_empty_directories(path)


def prune_empty_directories(path):
    """Remove empty subdirectories recursively"""
    try:
        for dirpath, dirnames, _ in os.walk(path, topdown=False):
            for dirname in dirnames:
                subdirpath = os.path.join(dirpath, dirname)
                if not os.listdir(subdirpath):
                    os.rmdir(subdirpath)
        if not os.listdir(path):
            os.rmdir(path)
    except OSError as e:
        if e.strerror:
            raise RuntimeError(f'{subdirpath}: Failed to prune: {e.strerror}')
        else:
            raise RuntimeError(f'{subdirpath}: Failed to prune: {e}')


def mkdir(path):
    """
    Create directory and its parents

    Existing directories are ignored.

    :raise ContentError: if directory creation fails
    """
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        if e.strerror:
            raise errors.ContentError(f'{path}: {e.strerror}')
        else:
            raise errors.ContentError(f'{path}: {e}')
    else:
        assert_dir_usable(path)


def basename(path):
    """
    Return last segment in `path`

    Unlike :func:`os.path.basename`, this removes any trailing directory
    separators first.

    >>> os.path.basename('a/b/c/')
    ''
    >>> upsies.utils.basename('a/b/c/')
    'c'
    """
    return os.path.basename(str(path).rstrip(os.sep))


def dirname(path):
    """
    Remove last segment in `path`

    Unlike :func:`os.path.dirname`, this removes any trailing directory
    separators first.

    >>> os.path.dirname('a/b/c/')
    'a/b/c'
    >>> upsies.utils.dirname('a/b/c/')
    'a/b'
    """
    return os.path.dirname(str(path).rstrip(os.sep))


def file_and_parent(path):
    """Return `path`'s filename and parent directoy name if there is one"""
    if os.sep in path:
        return (
            basename(path),
            basename(dirname(path)),
        )
    else:
        return (path,)


def sanitize_filename(filename):
    """
    Replace illegal characters in `filename` with "_"
    """
    if os_family() == 'windows':
        for char in ('<', '>', ':', '"', '/', '\\', '|', '?', '*'):
            filename = filename.replace(char, '_')
        return filename
    else:
        return filename.replace('/', '_')


def file_extension(path):
    """
    Return file extension

    Unlike :func:`os.path.splitext`, this function expects the extension to be 1-3
    characters long and consist only of ascii characters or numbers.

    :param str path: Path to file or directory

    :return: file extension
    :rtype: str
    """
    path = str(path)
    if '.' in path:
        return re.sub(r'^.*\.([a-zA-Z0-9]{1,3})$', r'\1', path).lower()
    else:
        return ''

def strip_extension(path, only=()):
    """
    Return `path` without file extension

    If `path` doesn't have a file extension, return it as is.

    A file extension is 1-3 characters long and consist only of ascii characters
    or numbers.

    :param str path: Path to file or directory
    :param only: Only strip extension if it exists in this sequence
    :type only: sequence of :class:`str`

    :return: file extension
    :rtype: str
    """
    path = str(path)
    if '.' in path:
        match = re.search(r'^(.*)\.([a-zA-Z0-9]{1,3})$', path)
        if match:
            name = match.group(1)
            ext = match.group(2)
            if only:
                if ext in only:
                    return name
            else:
                return name
    return path


def file_size(path):
    """Return file size in bytes or `None`"""
    if not os.path.isdir(path):
        try:
            return os.path.getsize(path)
        except OSError:
            pass
    return None


def file_list(path, extensions=()):
    """
    List naturally sorted files in `path` and any subdirectories

    If `path` is not a directory, it is returned as a single item in a list
    unless `extensions` are given and they don't match.

    Unreadable directories are ignored.

    :param str path: Path to a directory
    :param str extensions: List of file extensions to include

    :return: Tuple of file paths
    """
    extensions = tuple(str(e).casefold() for e in extensions)

    def ext_ok(filename):
        return file_extension(filename).casefold() in extensions

    if not os.path.isdir(path):
        if ext_ok(path):
            return (str(path),)
        else:
            return ()

    files = []
    for root, dirnames, filenames in os.walk(path):
        for filename in filenames:
            if not extensions or ext_ok(filename):
                files.append(os.path.join(root, filename))
    return tuple(natsort.natsorted(files, key=str.casefold))


# Stolen from torf-cli
# https://github.com/rndusr/torf-cli/blob/master/torfcli/_utils.py

_DOWN       = '\u2502'  # noqa: E221  # │
_DOWN_RIGHT = '\u251C'  # noqa: E221  # ├
_RIGHT      = '\u2500'  # noqa: E221  # ─
_CORNER     = '\u2514'  # noqa: E221  # └

def file_tree(tree, _parents_is_last=()):
    """
    Create a pretty file tree as multi-line string

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
            lines.append(f'{indent}{name} ({string.pretty_bytes(node)})')
        else:
            lines.append(f'{indent}{name}')
            # Descend into child node
            sub_parents_is_last = _parents_is_last + (is_last,)
            lines.append(file_tree(node, _parents_is_last=sub_parents_is_last))

    return '\n'.join(lines)


_bytes_regex = re.compile(r'^(\d+(?:\.\d+|)) ?([a-zA-Z]{,3})$')
_bytes_multipliers = {
    '': 1,
    'k': 1000,
    'M': 1000**2,
    'G': 1000**3,
    'T': 1000**4,
    'P': 1000**5,
    'Ki': 1024,
    'Mi': 1024**2,
    'Gi': 1024**3,
    'Ti': 1024**4,
    'Pi': 1024**5,
}

class Bytes(int):
    """:class:`int` subclass that interprets units and unit prefixes"""

    @classmethod
    def from_string(cls, string):
        match = _bytes_regex.search(string)
        if not match:
            raise ValueError(f'Invalid size: {string}')
        else:
            number = match.group(1)
            unit = match.group(2)
            if unit and unit[-1].upper() == 'B':
                unit = unit[:-1]
            try:
                multiplier = _bytes_multipliers[unit]
            except KeyError:
                raise ValueError(f'Invalid unit: {unit}')
            else:
                return cls(int(float(number) * multiplier))

    def __new__(cls, value):
        if isinstance(value, str):
            return cls.from_string(value)
        else:
            return super().__new__(cls, value)
