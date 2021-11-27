"""
Base class for image uploaders
"""

import abc
import collections
import copy
import os

from ... import __project_name__, constants, errors
from .. import configfiles, fs, image
from . import common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ImageHostBase(abc.ABC):
    """
    Base class for image uploaders

    :param str cache_directory: Where to cache URLs; defaults to
        :attr:`.constants.DEFAULT_CACHE_DIRECTORY`
    :param options: User configuration options for this image host,
        e.g. authentication details, thumbnail size, etc
    :type options: :class:`dict`-like
    """

    def __init__(self, cache_directory=None, options=None):
        self._options = copy.deepcopy(self.default_config)
        self._options.update()
        if options is not None:
            self._options.update(options)
        self._cache_dir = cache_directory if cache_directory else constants.DEFAULT_CACHE_DIRECTORY

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # This method is called for each subclass. This hack allows us to
        # overload `default_config` in subclasses without caring about common
        # defaults, e.g. subclasses don't need to have "thumb_width" in their
        # `default_config`, but it will exist anyway.
        cls.default_config = {
            **cls.default_config_common,
            **cls.default_config,
        }

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

    default_config_common = {
        'thumb_width': configfiles.config_value(
            value=0,
            description=(
                'Thumbnail width in pixels or 0 for no thumbnail. '
                'Trackers may ignore this option and use a hardcoded thumbnail width.'
            ),
        ),
    }
    """Default user configuration for all subclasses"""

    default_config = {}
    """
    Default user configuration for a subclass

    This always contains :attr:`default_config_common`.
    """

    argument_definitions = {}
    """CLI argument definitions (see :attr:`.CommandBase.argument_definitions`)"""

    description = ''
    """Any documentation, for example how to get an API key"""

    async def upload(self, image_path, cache=True):
        """
        Upload image file

        :param image_path: Path to image file
        :param bool cache: Whether to attempt to get the image URL from cache

        :raise RequestError: if the upload fails

        :return: :class:`~.imghost.common.UploadedImage`
        """
        if 'apikey' in self.options and not self.options['apikey']:
            raise errors.RequestError(
                'You must configure an API key first. Run '
                f'"{__project_name__} upload-images {self.name} --help" '
                'for more information.'
            )

        info = {
            'url': await self._get_image_url(image_path, cache=cache),
        }

        thumb_width = self.options['thumb_width']
        if thumb_width:
            try:
                thumbnail_path = image.resize(
                    image_path,
                    width=thumb_width,
                    target_directory=self.cache_directory,
                )
            except errors.ImageResizeError as e:
                raise errors.RequestError(e)
            else:
                info['thumbnail_url'] = await self._get_image_url(thumbnail_path, cache=cache)

        return common.UploadedImage(**info)

    async def _get_image_url(self, image_path, cache=True):
        url = self._get_url_from_cache(image_path) if cache else None
        if not url:
            try:
                url = await self._upload_image(image_path)
            except errors.RequestError as e:
                raise errors.RequestError(e)
            else:
                _log.debug('Uploaded %r: %r', image_path, url)
                self._store_url_to_cache(image_path, url)
        else:
            _log.debug('Got URL from cache: %r: %r', image_path, url)
        return url

    @abc.abstractmethod
    async def _upload_image(self, image_path):
        """Upload `image_path` and return URL to the image file"""

    def _get_url_from_cache(self, image_path):
        cache_file = self._cache_file(image_path)
        if os.path.exists(cache_file):
            _log.debug('Already uploaded: %s', cache_file)
            try:
                with open(cache_file, 'r') as f:
                    return f.read().strip()
            except OSError:
                # We'll try to overwrite the bad cache file later
                pass

    def _store_url_to_cache(self, image_path, url):
        cache_file = self._cache_file(image_path)
        try:
            fs.mkdir(fs.dirname(cache_file))
            with open(cache_file, 'w') as f:
                f.write(url)
        except OSError as e:
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
        filename = fs.sanitize_filename(image_path[-200:]) + f'.{self.name}.url'

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
        if cache_id is not None:
            return as_str(cache_id)

    @property
    def cache_id(self):
        """
        Information that makes an upload unique, aside from the file path

        If this returns `None`, the file path is unique enough. Otherwise, the
        return value should be a string, dictionary, sequence or anything with a
        readable and unique string representation.
        """
        return None
