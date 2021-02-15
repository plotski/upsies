"""
Scene release search and verification
"""

import asyncio
import os
import re

from ... import errors, utils
from ..types import ReleaseType, SceneCheckResult
from . import predb, srrdb
from .base import SceneDbApiBase
from .common import SceneQuery, assert_not_abbreviated_filename

import logging  # isort:skip
_log = logging.getLogger(__name__)

_PREDB = predb.PreDbApi()
_SRRDB = srrdb.SrrDbApi()

_NEEDED_MOVIE_KEYS = ('title', 'year', 'resolution', 'source', 'video_codec', 'group')
_NEEDED_SERIES_KEYS = ('title', 'episodes', 'resolution', 'source', 'video_codec', 'group')


def scenedbs():
    """Return list of :class:`.SceneDbApiBase` subclasses"""
    return utils.subclasses(SceneDbApiBase, utils.submodules(__package__))


def scenedb(name, **kwargs):
    """
    Create :class:`.SceneDbApiBase` instance

    :param str name: Name of the scene release database. A subclass of
        :class:`.SceneDbApiBase` with the same :attr:`~.SceneDbApiBase.name` must
        exist in one of this package's submodules.
    :param kwargs: All keyword arguments are passed to the subclass specified by
        `name`

    :raise ValueError: if no matching subclass can be found

    :return: :class:`.SceneDbApiBase` instance
    """
    for scenedb in scenedbs():
        if scenedb.name == name:
            return scenedb(**kwargs)
    raise ValueError(f'Unsupported scene release database: {name}')


async def search(*args, **kwargs):
    """Search with the recommended :class:`~.SceneDbApiBase` subclass"""
    return await _PREDB.search(*args, **kwargs)


async def is_scene_release(release):
    """
    Check if `release` is a scene release or not

    :param release: Release name, path to release or
        :class:`~.release.ReleaseInfo` instance

    :return: :class:`~.types.SceneCheckResult`
    """
    if isinstance(release, str):
        release_info = utils.release.ReleaseInfo(release)
    else:
        release_info = release

    # NOTE: Simply searching for the group does not work because some scene
    #       groups make non-scene releases and vice versa.
    #       Examples:
    #         - Prospect.2018.720p.BluRay.DD5.1.x264-LoRD
    #         - How.The.Grinch.Stole.Christmas.2000.720p.BluRay.DTS.x264-EbP
    query = SceneQuery.from_release(release_info)
    results = await _PREDB.search(query)
    if results:
        # Do we have enough information to find a single release?
        if release_info['type'] is ReleaseType.movie:
            needed_keys = _NEEDED_MOVIE_KEYS
        elif release_info['type'] in (ReleaseType.season, ReleaseType.episode):
            needed_keys = _NEEDED_SERIES_KEYS
        else:
            # If we don't even know the type, we certainly don't have enough
            # information to pin down a release.
            return SceneCheckResult.unknown

        if not all(release_info[k] for k in needed_keys):
            return SceneCheckResult.unknown
        else:
            return SceneCheckResult.true

    # If this is a file like "abd-mother.mkv" without a properly named parent
    # directory and we didn't find it above, it's possibly a scene release, but
    # we can't be sure.
    try:
        assert_not_abbreviated_filename(release_info.path)
    except errors.SceneError:
        return SceneCheckResult.unknown

    return SceneCheckResult.false


async def release_files(release_name):
    """
    Map release file names to file information

    This function uses :class:`~.predb.PreDbApi` for searching and
    :class:`~.srrdb.SrrDbApi` to get the file information.

    :param str release_name: Exact name of the release
    """
    files = await _SRRDB.release_files(release_name)
    if files:
        return files
    else:
        _log.debug('No such release: %r', release_name)
        files = {}

    # If scene released "Foo.S01E0{1,2,3,...}.720p.BluRay-BAR" and we're
    # searching for "Foo.S01.720p.BluRay-BAR", we might not get any results. But
    # we can get release names of individual episodes by searching for the
    # season pack, and then we can call release_files() for each episode.
    release_info = utils.release.ReleaseInfo(release_name)
    if release_info['type'] is ReleaseType.season:
        query = SceneQuery.from_release(release_info)
        results = await _PREDB.search(query)
        if results:
            files = await asyncio.gather(
                *(_SRRDB.release_files(result) for result in results)
            )
            # Join sequence of dictionaries into single dictionary
            files = {fname:f for files_ in files for fname,f in files_.items()}
            _log.debug('Season pack from multiple episode releases: %r', files)

    # If scene released season pack (or any other multi-file thing) and we're
    # searching for a single episode, we might not get any results. Search for
    # the season pack to get all files.
    elif release_info['type'] is ReleaseType.episode:
        # Remove single episodes from seasons
        release_info['episodes'].remove_specific_episodes()
        results = await _PREDB.search(SceneQuery.from_release(release_info))
        if len(results) == 1:
            _log.debug('Getting files from single result: %r', results[0])
            files = await _SRRDB.release_files(results[0])

    # Go through all files and find the exact release name we're looking for.
    # Don't do this exclusively for episodes because not all multi-file releases
    # are a list of episodes (e.g. extras may not contain any "Exx").
    for file_name, file_info in files.items():
        if utils.fs.strip_extension(release_name) == utils.fs.strip_extension(file_name):
            files = {file_name: file_info}
            _log.debug('Single file from season pack release: %r', files)
            break

    return files


async def verify_release_name(content_path, release_name):
    """
    Check if release was renamed

    :param content_path: Path to release file or directory
    :param release_name: Known exact release name, e.g. from :func:`search`
        results

    `content_path` is ok if its last segment is equal to `release_name` (file
    extension is ignored) or equal to one of the files from the release
    specified by `release_name`.

    :raise SceneRenamedError: if release was renamed
    :raise SceneError: if release name is not a scene release or if
        `content_path` points to an abbreviated file name
        (e.g. "abd-mother.mkv")
    """
    assert_not_abbreviated_filename(content_path)
    if not await is_scene_release(release_name):
        raise errors.SceneError(f'Not a scene release: {release_name}')

    content_filename = utils.fs.basename(content_path)
    content_release_name = utils.fs.strip_extension(content_filename)

    if content_release_name == release_name:
        return

    files = await release_files(release_name)
    if content_filename in files:
        return

    raise errors.SceneRenamedError(
        original_name=release_name,
        existing_name=content_release_name,
    )


async def verify_release_files(content_path, release_name):
    """
    Check if files released by scene have the correct size

    :param content_path: Path to release file or directory
    :param release_name: Known exact release name, e.g. from :func:`search`
        results

    The return value is a sequence of :class:`~.errors.SceneError` exceptions.
    For every file that is part of the scene release specified by
    `release_name`, include:

        * :class:`~.errors.SceneFileSizeError` if it has the wrong size
        * :class:`~.errors.SceneMissingInfoError` if file information is missing
        * :class:`~.errors.SceneError` if release name is not a scene release or
          if `content_path` points to an abbreviated file name
          (e.g. "abd-mother.mkv")
    """
    exceptions = []
    try:
        assert_not_abbreviated_filename(content_path)
    except errors.SceneError as e:
        exceptions.append(e)
    if not await is_scene_release(release_name):
        exceptions.append(errors.SceneError(f'Not a scene release: {release_name}'))
    if exceptions:
        return tuple(exceptions)

    fileinfos = await release_files(release_name)

    def get_release_filesize(filename):
        return fileinfos.get(filename, {}).get('size', None)

    # Map file paths to expected file sizes
    if os.path.isdir(content_path):
        exp_filesizes = {filepath: get_release_filesize(utils.fs.basename(filepath))
                         for filepath in utils.fs.file_list(content_path)}
    else:
        if len(fileinfos) == 1:
            filename = tuple(fileinfos)[0]
            exp_filesize = get_release_filesize(filename)
            exp_filesizes = {
                # Title.2015.720p.BluRay.x264-FOO.mkv
                content_path: exp_filesize,
                # Title.2015.720p.BluRay.x264-FOO/foo-title.mkv
                os.path.join(utils.fs.strip_extension(content_path), filename): exp_filesize,
            }
        else:
            filename = utils.fs.basename(content_path)
            exp_filesizes = {content_path: get_release_filesize(filename)}

    # Compare expected file sizes to actual file sizes
    _log.debug('file sizes: %r', exp_filesizes)
    for filepath, exp_size in exp_filesizes.items():
        filename = utils.fs.basename(filepath)
        actual_size = utils.fs.file_size(filepath)
        _log.debug('Checking file size: %s: %r ?= %r', filename, actual_size, exp_size)
        if exp_size is None:
            _log.debug('No info: %s', filename)
            exceptions.append(errors.SceneMissingInfoError(filename))
        elif actual_size is not None:
            if actual_size != exp_size:
                _log.debug('Wrong size: %s', filename)
                exceptions.append(
                    errors.SceneFileSizeError(
                        filename=filename,
                        original_size=exp_size,
                        existing_size=actual_size,
                    )
                )
            else:
                _log.debug('Correct size: %s', filename)
        else:
            _log.debug('No such file: %s', filename)

    return tuple(e for e in exceptions if e)
