"""
File system helpers
"""

import functools
import os
import re
import time

from .. import __project_name__, constants, errors
from . import LazyModule, os_family, types

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
def projectdir(content_path, base=None):
    """
    Return path to existing directory in which jobs put their files and cache

    :param str content_path: Path to torrent content
    :param str base: Location of the project directory; defaults to
        :attr:`~.constants.CACHE_DIRPATH`

    :raise ContentError: if `content_path` exists and is not a directory or has
        insufficient permissions
    """
    if content_path:
        if not base:
            base = constants.CACHE_DIRPATH
        path = os.path.join(base, basename(content_path) + f'.{__project_name__}')
    else:
        path = '.'
    if not os.path.exists(path):
        mkdir(path)
    _log.debug('Using project directory: %r', path)
    return path


def limit_directory_size(path, max_total_size, min_age=None, max_age=None):
    """
    Delete oldest files (by access time) until maximum size is not exceeded

    Empty files and directories are always deleted.

    :param path: Path to directory
    :param max_total_size: Maximum combined size of all files in `path` and its
        subdirectories
    :param min_age: Preserve files that are younger than this
    :type min_age: int or float
    :param max_age: Preserve files that are older than this
    :type max_age: int or float
    """
    def combined_size(filepaths):
        return sum(file_size(f) for f in filepaths
                   if os.path.exists(f) and not os.path.islink(f))

    # This should return mtime if file system was mounted with noatime.
    def atime(filepath):
        statinfo = os.stat(filepath, follow_symlinks=False)
        return statinfo.st_atime

    def get_filepaths(dirpath):
        return file_list(dirpath, min_age=min_age, max_age=max_age, follow_dirlinks=False)

    # Keep removing oldest file until `path` size is small enough
    filepaths = get_filepaths(path)
    while combined_size(filepaths) > max_total_size:
        oldest_file = sorted(filepaths, key=atime)[0]
        try:
            os.unlink(oldest_file)
        except OSError as e:
            if e.strerror:
                raise RuntimeError(f'{oldest_file}: Failed to prune: {e.strerror}')
            else:
                raise RuntimeError(f'{oldest_file}: Failed to prune: {e}')
        else:
            filepaths = get_filepaths(path)

    prune_empty(path, files=True, directories=True)


def prune_empty(path, files=False, directories=True):
    """
    Remove empty subdirectories recursively

    :param path: Path to directory
    :param bool files: Whether to prune empty files
    :param bool directories: Whether to prune empty directories

    Dead symbolic links are removed after pruning files and directories.

    If `path` is not a directory, do nothing.
    """
    if not os.path.isdir(path):
        return

    def raise_error(e, path):
        if e.strerror:
            raise RuntimeError(f'{path}: Failed to prune: {e.strerror}')
        else:
            raise RuntimeError(f'{path}: Failed to prune: {e}')

    # Prune empty files
    if files:
        for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    if os.path.exists(filepath) and file_size(filepath) <= 0:
                        os.unlink(filepath)
                except OSError as e:
                    raise_error(e, filepath)

    # Prune empty directories
    if directories:
        for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
            for dirname in dirnames:
                subdirpath = os.path.join(dirpath, dirname)
                try:
                    if not os.path.islink(subdirpath) and not os.listdir(subdirpath):
                        os.rmdir(subdirpath)
                except OSError as e:
                    raise_error(e, subdirpath)

    # Prune dead links
    for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                if os.path.islink(filepath):
                    if not os.path.exists(filepath):
                        os.unlink(filepath)
            except OSError as e:
                raise_error(e, filepath)

    try:
        if directories and not os.listdir(path):
            os.rmdir(path)
    except OSError as e:
        raise_error(e, path)


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
        illegal_chars = ('<', '>', ':', '"', '/', '\\', '|', '?', '*')
    else:
        illegal_chars = ('/',)

    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename


def file_extension(path):
    """
    Return file extension

    Unlike :func:`os.path.splitext`, this function expects the extension to be 1-3
    characters long and consist only of ascii characters or numbers.

    :param str path: Path to file or directory

    :return: file extension
    :rtype: str
    """
    filename = os.path.basename(path)
    match = re.search(r'\.([a-zA-Z0-9]{1,3})$', filename)
    if match:
        return match.group(1).lower()
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


def file_list(path, extensions=(), min_age=None, max_age=None, follow_dirlinks=False):
    """
    List naturally sorted files in `path` and any subdirectories

    If `path` is not a directory, it is returned as a single item in a list
    unless `extensions` are given and they don't match.

    Unreadable directories are excluded.

    :param str path: Path to a directory
    :param str extensions: Exclude files without one of these extensions
    :param min_age: Exclude files that are younger than this
    :type min_age: int or float
    :param max_age: Exclude files that are older than this
    :type max_age: int or float
    :param follow_dirlinks: Whether to include the contents of symbolic links to
        directories or the links themselves

    :return: Tuple of file paths
    """
    extensions = tuple(str(e).casefold() for e in extensions)

    def ext_ok(filename):
        return not extensions or file_extension(filename).casefold() in extensions

    def age_ok(filepath, now=time.time()):
        statinfo = os.stat(filepath, follow_symlinks=False)
        age = round(now - statinfo.st_atime)
        return (min_age or age) <= age <= (max_age or age)

    if not os.path.isdir(path):
        if ext_ok(path):
            return (str(path),)
        else:
            return ()

    files = []
    for root, dirnames, filenames in os.walk(path, topdown=True, followlinks=follow_dirlinks):
        for filename in sorted(filenames):
            filepath = os.path.join(root, filename)
            if ext_ok(filename) and age_ok(filepath):
                files.append(filepath)

        # Symbolic links to directories are in `dirnames`
        if not follow_dirlinks:
            # For symbolic links that point to a directory, os.walk() can only
            # include the contents (followlinks=True) or completely ignore the
            # link. Here we look for links to directories and a) include them in
            # the returned list and b), remove them from `dirnames` so os.walk()
            # doesn't recurse into them. It is important to pass topdown=True
            # for b) to work.
            for dirname in tuple(dirnames):
                # Contrary to what the docs say, this returns `True` for dead
                # and living symbolic links
                dirpath = os.path.join(root, dirname)
                if os.path.islink(dirpath):
                    del dirnames[dirnames.index(dirname)]
                    files.append(dirpath)

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
            lines.append(f'{indent}{name} ({types.Bytes(node)})')
        else:
            def sum_node_size(nodelist):
                size = 0
                for node in nodelist:
                    if isinstance(node, tuple):
                        if len(node) >= 2 and isinstance(node[1], int):
                            size += node[1]
                        else:
                            size += sum_node_size(node)
                return size

            lines.append(f'{indent}{name} ({types.Bytes(sum_node_size(node))})')
            # Descend into child node
            sub_parents_is_last = _parents_is_last + (is_last,)
            lines.append(file_tree(node, _parents_is_last=sub_parents_is_last))

    return '\n'.join(lines)
