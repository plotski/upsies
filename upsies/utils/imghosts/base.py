"""
Base class for image uploaders
"""

import abc
import collections
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
    :param options: User configuration options for this image host,
        e.g. authentication details, thumbnail size, etc
    :type options: :class:`dict`-like
    """

    def __init__(self, cache_directory=None, options=None):
        self._options = copy.deepcopy(self.default_config)
        if options is not None:
            self._options.update(options)
        self.cache_directory = cache_directory if cache_directory else constants.CACHE_DIRPATH

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
    def options(self):
        """
        Configuration options provided by the user

        This is the :class:`dict`-like object from the initialization argument
        of the same name.
        """
        return self._options

    default_config = {}
    """Default user configuration"""

    argument_definitions = {}
    """CLI argument definitions (see :attr:`.CommandBase.argument_definitions`)"""

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
        # If image_path is in our cache_directory, the image's file name makes
        # it unique. This is usually the case when we're uploading
        # screenshots. If image is not in our cache_directory, use the absolute
        # path as a unique identifier.
        if fs.dirname(image_path) == self.cache_directory:
            image_path = fs.basename(image_path)
        else:
            image_path = os.path.abspath(image_path)

        # Make cache file even more unique, e.g. imgbox only has one thumbnail
        # size per uploaded image, so if we want a different thumbnail size, we
        # need to upload again.
        cache_id = self._get_cache_id_as_string()
        if cache_id:
            image_path += f'.{cache_id}'

        # Max file name length is usually 255 bytes
        filename = fs.sanitize_filename(image_path[-200:]) + f'.{self.name}.json'

        return os.path.join(self.cache_directory, filename)

    def _get_cache_id_as_string(self):
        def as_str(obj):
            if isinstance(obj, collections.abc.Mapping):
                return ','.join(f'{as_str(k)}={as_str(v)}' for k,v in obj.items())
            elif isinstance(obj, str):
                return str(obj)
            elif isinstance(obj, collections.abc.Sequence):
                return ','.join(as_str(i) for i in obj)
            else:
                return str(obj)

        cache_id = self.cache_id
        if cache_id is None:
            cache_id = self.options
        return as_str(cache_id)

    @property
    def cache_id(self):
        """Information that makes an upload unique, aside from the file path"""
        return None
