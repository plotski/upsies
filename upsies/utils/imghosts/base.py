"""
Base class for image uploaders
"""

import abc
import copy
import json
import os

from ... import constants
from .. import fs
from . import common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImageHostBase(abc.ABC):
    """
    Base class for image uploaders

    :param str cache_directory: Where to store URLs in JSON files; defaults to
        :attr:`.constants.CACHE_DIRPATH`
    :param dict config: User configuration
    """

    def __init__(self, cache_directory=None, config=None):
        self.cache_directory = cache_directory if cache_directory else constants.CACHE_DIRPATH
        self._config = copy.deepcopy(self.default_config)
        if config is not None:
            self._config.update(config.items())

    @property
    @abc.abstractmethod
    def name(self):
        """Name of the image hosting service"""

    @property
    def cache_directory(self):
        """Path to directory where upload info is cached"""
        return self._cache_dir

    @cache_directory.setter
    def cache_directory(self, directory):
        self._cache_dir = directory

    @property
    def config(self):
        """
        User configuration

        This is a deep copy of :attr:`default_config` that is updated with the
        `config` argument from initialization.
        """
        return self._config

    @property
    @abc.abstractmethod
    def default_config(self):
        """Default user configuration as a dictionary"""

    async def upload(self, image_path, cache=True):
        """
        Upload image to gallery

        :param str image_path: Path to image file
        :param bool cache: Whether to attempt to get the image URL from cache or
            cache it

        :raise RequestError: if the upload fails

        :return: :class:`~.imghost.common.UploadedImage`
        """
        info = self._get_info_from_cache(image_path) if cache else {}
        if not info:
            info = await self._upload(image_path)
            _log.debug('Uploaded %r: %r', image_path, info)
            self._store_info_to_cache(image_path, info)
        if 'url' not in info:
            raise RuntimeError(f'Missing "url" key in {info}')
        return common.UploadedImage(**info)

    @abc.abstractmethod
    async def _upload(self, image_path):
        """
        Upload a single image

        :param str image_path: Path to an image file

        :return: Dictionary that must contain an "url" key
        """

    def _get_info_from_cache(self, image_path):
        cache_file = self._cache_file(image_path)
        if os.path.exists(cache_file):
            _log.debug('Already uploaded: %s', cache_file)
            try:
                with open(cache_file, 'r') as f:
                    return json.loads(f.read())
            except (OSError, ValueError):
                # We'll overwrite the corrupted cache file later
                pass

    def _store_info_to_cache(self, image_path, info):
        cache_file = self._cache_file(image_path)
        try:
            json_string = json.dumps(info, indent=4) + '\n'
        except (TypeError, ValueError) as e:
            raise RuntimeError(f'Unable to write cache {cache_file}: {e}')

        try:
            fs.mkdir(fs.dirname(cache_file))
            with open(cache_file, 'w') as f:
                f.write(json_string)
        except (OSError, TypeError, ValueError) as e:
            msg = e.strerror if getattr(e, 'strerror', None) else e
            raise RuntimeError(f'Unable to write cache {cache_file}: {msg}')

    def _cache_file(self, image_path):
        # If image is in our cache_directory, the image's file name makes it
        # unique. This is usually the case when we're uploading screenshots. If
        # image is not in our cache_directory, use the absolute path as a unique
        # identifier.
        if fs.dirname(image_path) == self.cache_directory:
            image_path = os.path.basename(image_path)
        else:
            image_path = os.path.abspath(image_path)
        # Max file name length is ususally 255 bytes
        filename = fs.sanitize_filename(image_path[-200:]) + f'.{self.name}.json'
        return os.path.join(self.cache_directory, filename)
