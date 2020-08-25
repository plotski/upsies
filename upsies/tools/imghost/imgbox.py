import json
import os

import pyimgbox

from ... import errors
from ...utils import fs
from . import _common

import logging  # isort:skip
_log = logging.getLogger(__name__)


class Uploader:
    def __init__(self, thumb_width=300):
        self._thumb_width = thumb_width
        self._gallery = pyimgbox.Gallery(thumb_width=thumb_width,
                                         square_thumbs=False,
                                         comments_enabled=False)

    def upload(self, image_path):
        info = self._get_info_from_cache(image_path)
        if not info:
            if not self._gallery.created:
                self._gallery.create()
                _log.debug('Creating gallery: %r', self._gallery)
            info = self._upload(image_path)
            _log.debug('Upload %r: %r', image_path, info)
            self._cache_info(image_path, info)
        else:
            _log.debug('Got info for %r from cache: %r', image_path, info)
        return _common.UploadedImage(**info)

    def _upload(self, image_path):
        # Gallery.add() is an iterator, but we only upload a single image so we
        # can just return instead of yielding.
        for submission in self._gallery.add(image_path):
            _log.debug('Submission: %r', submission)
            if not submission['success']:
                raise errors.RequestError(submission['error'])
            else:
                return {
                    'url': submission.image_url,
                    'thumbnail_url': submission.thumbnail_url,
                    'edit_url': submission.edit_url,
                }

    def _get_info_from_cache(self, image_path):
        cache_path = self._cache_file(image_path)
        if os.path.exists(cache_path):
            _log.debug('Already uploaded: %s', image_path)
            try:
                with open(cache_path, 'r') as f:
                    return json.loads(f.read())
            except (OSError, ValueError):
                _log.debug('Deleting malformed or inaccessible cache file: %r', cache_path)
                os.remove(cache_path)

    def _cache_info(self, image_path, info):
        cache_file = self._cache_file(image_path)
        try:
            with open(cache_file, 'w') as f:
                f.write(json.dumps(info, indent=4) + '\n')
        except (OSError, TypeError, ValueError) as e:
            raise RuntimeError(f'Unable to write cache {cache_file}: {info}: {e}')

    @staticmethod
    def _cache_file(image_path):
        # FIXME: Max file name length is ususally 255 bytes. We use 200 to
        # account for multibyte characters. That's not very resilient.
        filename = image_path[-200:].replace('/', '_') + '.urls.json'
        return os.path.join(fs.tmpdir(), filename)
