import abc
import json
import os

from ...utils import fs
from . import _common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class UploaderBase(abc.ABC):
    """
    Base class for uploading images to image hosting services

    :param int thumb_width: Horizontal width of the thumbnails
    """

    def __init__(self, cache_dir=None):
        self._cache_dir = cache_dir or fs.tmpdir()

    @property
    @abc.abstractmethod
    def name(self):
        """Name of the image hosting service"""
        pass

    def upload(self, image_path):
        """
        Upload image to gallery

        :param str image_path: Path to image file

        :raise RequestError: if the upload fails

        :return: :class:`UploadedImage`
        """
        info = self._get_info_from_cache(image_path)
        if not info:
            info = self._upload(image_path)
            _log.debug('Upload %r: %r', image_path, info)
            self._store_info_to_cache(image_path, info)
        else:
            _log.debug('Got info for %r from cache: %r', image_path, info)
        if 'url' not in info:
            raise RuntimeError(f'Missing "url" key in {info}')
        return _common.UploadedImage(**info)

    @abc.abstractmethod
    def _upload(self, image_path):
        """
        Upload a single image

        :param str image_path: Path to an image file

        :return: Dictionary that must contain an "url" key
        """

    def _get_info_from_cache(self, image_path):
        cache_path = self._cache_file(image_path)
        if os.path.exists(cache_path):
            _log.debug('Already uploaded: %s', image_path)
            try:
                with open(cache_path, 'r') as f:
                    return json.loads(f.read())
            except (OSError, ValueError):
                # We'll overwrite the corrupted cache file later
                pass
                # _log.debug('Deleting malformed or inaccessible cache file: %r', cache_path)
                # os.remove(cache_path)

    def _store_info_to_cache(self, image_path, info):
        cache_file = self._cache_file(image_path)
        try:
            json_string = json.dumps(info, indent=4) + '\n'
        except (TypeError, ValueError) as e:
            raise RuntimeError(f'Unable to write cache {cache_file}: {e}')

        try:
            with open(cache_file, 'w') as f:
                f.write(json_string)
        except (OSError, TypeError, ValueError) as e:
            msg = e.strerror if getattr(e, 'strerror', None) else e
            raise RuntimeError(f'Unable to write cache {cache_file}: {msg}')

    def _cache_file(self, image_path):
        # Max file name length is ususally 255 bytes
        filename = image_path[-200:].replace('/', '_') + f'.{self.name}.json'
        return os.path.join(self._cache_dir, filename)
