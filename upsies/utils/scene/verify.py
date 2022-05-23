"""
Check if scene release was altered
"""

import asyncio
import collections
import difflib
import os
import re

from ... import constants, errors, utils
from ..types import ReleaseType, SceneCheckResult
from . import common, find, srrdb

import logging  # isort:skip
_log = logging.getLogger(__name__)

_srrdb = srrdb.SrrdbApi()

_abbreviated_scene_filename_regexs = (
    # Match names with group in front
    re.compile(r'^[a-z0-9]+-[a-z0-9_\.-]+?(?!-[a-z]{2,})\.(?:mkv|avi)$'),
    # Match "ttl.720p-group.mkv"
    re.compile(r'^[a-z0-9]+[\.-]\d{3,4}p-[a-z]{2,}\.(?:mkv|avi)$'),
    # Match "GR0UP1080pTTL.mkv"
    re.compile(r'^[a-zA-Z0-9]+\d{3,4}p[a-zA-Z]+\.(?:mkv|avi)$'),
    # Match "grptitlenospace.mkv"
    re.compile(r'^[a-zA-Z0-9]+\.(?:mkv|avi)$'),
)


def assert_not_abbreviated_filename(filepath):
    """
    Raise :class:`~.errors.SceneError` if `filepath` points to an abbreviated
    scene release file name like ``abd-mother.mkv``
    """
    filename = os.path.basename(filepath)
    for regex in _abbreviated_scene_filename_regexs:
        if regex.search(filename):
            raise errors.SceneAbbreviatedFilenameError(filename)


def is_abbreviated_filename(filepath):
    """
    Whether `filepath` points to an abbreviated scene release file name like
    ``abd-mother.mkv``
    """
    try:
        assert_not_abbreviated_filename(filepath)
    except errors.SceneAbbreviatedFilenameError:
        return True
    else:
        return False


_nogroup_regexs = (
    re.compile(r'^$'),
    re.compile(r'^(?i:nogroup)$'),
    re.compile(r'^(?i:nogrp)$'),
)


@utils.asyncmemoize
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

    # Empty group or names like "NOGROUP" are non-scene
    if (
        # Abbreviated file names also have an empty group, but we handle that
        # after doing a search
        not is_abbreviated_filename(release_info.path)
        # Any NOGROUP-equivalent means it's not scene
        and any(regex.search(release_info['group']) for regex in _nogroup_regexs)
    ):
        return SceneCheckResult.false

    # NOTE: Simply searching for the group does not work because some scene
    #       groups make non-scene releases and vice versa.
    #       Examples:
    #         - Prospect.2018.720p.BluRay.DD5.1.x264-LoRD
    #         - How.The.Grinch.Stole.Christmas.2000.720p.BluRay.DTS.x264-EbP

    results = await find.search(release)
    if results:
        # Do we have enough information to pinpoint a single release?
        needed_keys = common.get_needed_keys(release_info)
        if not needed_keys:
            # If we don't know how to identify a release uniquely, we are not in
            # a position to make any claims.
            return SceneCheckResult.unknown
        elif all(release_info[k] for k in needed_keys):
            return SceneCheckResult.true
        else:
            return SceneCheckResult.unknown

    # If this is a file like "abd-mother.mkv", it's possibly a scene release,
    # but we can't be sure. If it is placed in a properly named parent
    # directory, ReleaseInfo() should've picked that up above.
    if is_abbreviated_filename(release_info.path):
        return SceneCheckResult.unknown

    return SceneCheckResult.false


async def is_mixed_scene_release(directory):
    """
    Whether `directory` is a season pack with scene releases from different
    groups
    """
    if not os.path.isdir(directory):
        return False

    release_info = utils.release.ReleaseInfo(directory)
    if release_info['type'] is not ReleaseType.season:
        return False

    groups_found = set()
    for filepath in utils.fs.file_list(directory):
        # Ignore files without release group
        filepath_info = utils.release.ReleaseInfo(filepath)
        if filepath_info['group']:

            # Find relevant scene release(s)
            results = await find.search(filepath)
            for result in results:

                # Collect group names
                result_info = utils.release.ReleaseInfo(result)
                if result_info['group']:
                    groups_found.add(result_info['group'])

                # If there are 2 or more different groups, we know enough
                if len(groups_found) >= 2:
                    return True

    return False


async def release_files(release_name):
    """
    Map release file names to file information

    This function uses :func:`~.find.search` for searching and
    :class:`~.srrdb.SrrdbApi` to get the file information.

    :param str release_name: Exact name of the release
    """
    files = await _srrdb.release_files(release_name)
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
        results = await find.search(release_info, only_existing_releases=True)
        if results:
            files = await asyncio.gather(
                *(_srrdb.release_files(result) for result in results)
            )
            # Join sequence of dictionaries into single dictionary
            files = {fname:f for files_ in files for fname,f in files_.items()}
            _log.debug('Season pack from multiple episode releases: %r', files)

    # If scene released season pack and we're searching for a single episode, we
    # might not get any results. Search for the season pack to get all files.
    elif release_info['type'] is ReleaseType.episode:
        # Remove single episodes from seasons
        release_info['episodes'].remove_specific_episodes()
        results = await find.search(release_info)
        if len(results) == 1:
            _log.debug('Getting files from single result: %r', results[0])
            files = await _srrdb.release_files(results[0])

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

    :param content_path: Path to release file or directory (does not have to
        exist)
    :param release_name: Known exact release name, e.g. from :func:`search`
        results

    :raise SceneRenamedError: if release was renamed
    :raise SceneError: if release name is not a scene release
    """
    _log.debug('Verifying release name: %r =? %r', content_path, release_name)

    if not await is_scene_release(release_name):
        raise errors.SceneError(f'Not a scene release: {release_name}')

    files = await release_files(release_name)
    content_path = content_path.strip(os.sep)

    # Figure out which file is the actual payload. Note that the release may not
    # contain any files, e.g. Wrecked.2011.DiRFiX.LIMITED.FRENCH.720p.BluRay.X264-LOST.
    main_release_file = None
    if files:
        content_file_extension = utils.fs.file_extension(content_path)
        if content_file_extension:
            # `content_path` points to a file, not a directory
            content_file = utils.fs.basename(content_path)
            # We don't know if `content_file` was renamed, so we find the match
            # in the actual file names
            filename_matches = difflib.get_close_matches(content_file, files)
            if filename_matches:
                main_release_file = filename_matches[0]

        if not main_release_file:
            # Default to the largest file if the release has files
            main_release_file = sorted(
                (info for info in files.values()),
                key=lambda info: info['size'],
            )[0]['file_name']

    # No files in this release, default to `release_name`
    if not main_release_file:
        main_release_file = release_name
    _log.debug('Main release file: %r', main_release_file)

    # Generate list of paths that are valid for this release
    acceptable_paths = {release_name}

    # Properly named directory that contains the released file. This covers
    # abbreviated files and all other files.
    for file in files:
        acceptable_paths.add(os.path.join(release_name, file))

    # Any non-abbreviated files may exist outside of a properly named parent
    # directory
    for file in files:
        if not is_abbreviated_filename(file):
            acceptable_paths.add(file)

    # If `release_name` is an episode, it may be inside a season pack parent
    # directory. This only matters if we're dealing with an abbreviated file
    # name; normal file names are independent of their parent directory name.
    if is_abbreviated_filename(content_path):
        season_pack_name = common.get_season_pack_name(release_name)
        for file in files:
            acceptable_paths.add(f'{season_pack_name}/{file}')

    # Standalone file is also ok if it is named `release_name` with the same
    # file extension as the main file
    main_release_file_extension = utils.fs.file_extension(main_release_file)
    acceptable_paths.add('.'.join((release_name, main_release_file_extension)))

    # Release is correctly named if `content_path` ends with any acceptable path
    for path in (p.strip(os.sep) for p in acceptable_paths):
        if re.search(rf'(?:^|{re.escape(os.sep)}){re.escape(path)}$', content_path):
            return

    # All attempts to match `content_path` against `release_name` have failed.
    # Produce a useful error message.
    if is_abbreviated_filename(content_path):
        # Abbreviated files should never be handled without a parent
        original_name = os.path.join(release_name, main_release_file)
    elif utils.fs.file_extension(content_path):
        # Assume `content_path` refers to a file, not a directory
        # NOTE: We can't use os.path.isdir(), `content_path` may not exist.
        original_name = main_release_file
    else:
        # Assume `content_path` refers to directory
        original_name = release_name

    # Use the same number of parent directories for original/existing path. If
    # original_name contains the parent directory, we also want the parent
    # directory in existing_name.
    original_name_parts_count = original_name.count(os.sep)
    content_path_parts = content_path.split(os.sep)
    existing_name = os.sep.join(content_path_parts[-original_name_parts_count - 1:])

    raise errors.SceneRenamedError(
        original_name=original_name,
        existing_name=existing_name,
    )


async def verify_release_files(content_path, release_name):
    """
    Check if files released by scene have the correct size

    :param content_path: Path to release file or directory
    :param release_name: Known exact release name, e.g. from :func:`search`
        results

    The return value is a sequence of :class:`~.errors.SceneError` exceptions:

        * :class:`~.errors.SceneFileSizeError` if a file has the wrong size
        * :class:`~.errors.SceneMissingInfoError` if information about a file
          cannot be found
        * :class:`~.errors.SceneError` if `release_name` is not a scene release
    """
    exceptions = []

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
    _log.debug('File sizes: %r', exp_filesizes)
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
                _log.debug('Correct size: %s', filepath)
        else:
            _log.debug('No such file: %s', filepath)

    return tuple(e for e in exceptions if e)


async def verify_release(content_path, release_name=None):
    """
    Find matching scene releases and apply :func:`verify_release_name` and
    :func:`verify_release_files`

    :param content_path: Path to release file or directory
    :param release_name: Known exact release name or `None` to :func:`search`
        for `content_path`

    :return: :class:`~.types.SceneCheckResult` enum from
        :func:`is_scene_release` and sequence of :class:`~.errors.SceneError`
        exceptions from :func:`verify_release_name` and
        :func:`verify_release_files`
    """
    if release_name:
        return await _verify_release(content_path, release_name)

    # Find possible `release_name` values. For season packs that were released
    # as single episodes, this will get us a sequence of episode release names.
    existing_release_names = await find.search(content_path)
    if not existing_release_names:
        return SceneCheckResult.false, ()

    # Maybe `content_path` was released by scene as it is (as file or directory)
    for existing_release_name in existing_release_names:
        is_scene_release, exceptions = await _verify_release(content_path, existing_release_name)
        if is_scene_release and not exceptions:
            return SceneCheckResult.true, ()

    # Maybe `content_path` is a directory (season pack) and scene released
    # single files (episodes).
    return await _verify_release_per_file(content_path)


async def _verify_release_per_file(content_path):
    _log.debug('Verifying each file beneath %r', content_path)
    is_scene_releases = []
    combined_exceptions = collections.defaultdict(lambda: [])
    filepaths = utils.fs.file_list(content_path, extensions=constants.VIDEO_FILE_EXTENSIONS)
    for filepath in filepaths:
        existing_release_names = await find.search(filepath)
        _log.debug('Search results for %r: %r', filepath, existing_release_names)

        # If there are no search results, default to "not a scene release"
        is_scene_release = SceneCheckResult.false

        # Match each existing_release_name against filepath
        for existing_release_name in existing_release_names:
            is_scene_release, exceptions = await _verify_release(filepath, existing_release_name)
            _log.debug('Verified %r against %r: %r, %r',
                       filepath, existing_release_name, is_scene_release, exceptions)
            if is_scene_release and not exceptions:
                # Match found, don't check other existing_release_names
                break
            elif is_scene_release:
                # Remember exceptions per file (makes debugging easier)
                combined_exceptions[filepath].extend(exceptions)

        # Remember the SceneCheckResult when the for loop ended. True if we
        # found a scene release at any point, other it's the value of the last
        # existing_release_name.
        is_scene_releases.append(is_scene_release)

    # Collapse `is_scene_releases` into a single value
    if is_scene_releases and all(isr is SceneCheckResult.true for isr in is_scene_releases):
        _log.debug('All files are scene releases')
        is_scene_release = SceneCheckResult.true
    elif is_scene_releases and all(isr is SceneCheckResult.false for isr in is_scene_releases):
        _log.debug('All files are non-scene releases')
        is_scene_release = SceneCheckResult.false
    else:
        _log.debug('Uncertain scene status: %r', is_scene_releases)
        is_scene_release = SceneCheckResult.unknown

    return is_scene_release, tuple(exception
                                   for exceptions in combined_exceptions.values()
                                   for exception in exceptions)


async def _verify_release(content_path, release_name):
    _log.debug('Verifying %r against release: %r', content_path, release_name)

    # Stop other checks if this is not a scene release
    is_scene = await is_scene_release(release_name)
    if not is_scene:
        return SceneCheckResult.false, ()

    # Combine exceptions from verify_release_name() and verify_release_files()
    exceptions = []

    # verify_release_name() can only produce one exception, so it is raised
    try:
        await verify_release_name(content_path, release_name)
    except errors.SceneError as e:
        exceptions.append(e)

    # verify_release_files() can produce multiple exceptions, so it returns them
    exceptions.extend(await verify_release_files(content_path, release_name))
    return is_scene, tuple(exceptions)
