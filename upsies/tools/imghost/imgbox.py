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


# @functools.lru_cache(maxsize=None)
# def upload(*image_paths, thumb_size=300):
#     image_paths = list(image_paths)
#     submissions = {}

#     cache_files = {img : _cache_file(img) for img in image_paths}
#     _log.debug('Cache files: %r', cache_files)
#     for img,cache in cache_files.items():
#         if os.path.exists(cache):
#             _log.debug('Already uploaded: %s', img)
#             try:
#                 with open(cache, 'r') as f:
#                     info = json.loads(f.read())
#             except (OSError, ValueError):
#                 _log.debug('Deleting malformed or inaccessible cache file: %r', cache)
#                 os.remove(cache)
#             else:
#                 yield _common.UploadedImage(**info)
#                 image_paths.remove(img)

#     _log.debug('Loaded cached submissions: %r', subsmissions)
#     _log.debug('Remaining image paths: %r', image_paths)

#     gallery = pyimgbox.Gallery(thumb_width=thumb_size,
#                                square_thumbs=False,
#                                comments_enabled=False)
#     gallery.create()
#     for submission in gallery.add(*image_paths):
#         _log.debug('Submission: %r', submission)
#         info = {
#             'url': submission.image_url,
#             'thumbnail_url': submission.thumbnail_url,
#             'edit_url': submission.edit_url,
#         }
#         _log.debug('info: %r', info)
#         with open(cache_file, 'w') as f:
#             f.write(json.dumps(info, indent=4) + '\n')
#         yield _common.UploadedImage(**info)


# @functools.lru_cache(maxsize=None)
# def upload(image_path, thumb_size=300):
#     cache_file = _cache_file(image_path)
#     _log.debug('Cache file for %r: %r', image_path, cache_file)

#     if os.path.exists(cache_file):
#         _log.debug('Already uploaded: %s', image_path)
#         try:
#             with open(cache_file, 'r') as f:
#                 info = json.loads(f.read())
#         except (OSError, ValueError):
#             _log.debug('Deleting malformed cache file: %r', cache_file)
#             os.remove(cache_file)
#         else:
#             return _common.UploadedImage(**info)

#     gallery = pyimgbox.Gallery(thumb_width=thumb_size,
#                                square_thumbs=False,
#                                comments_enabled=False)
#     gallery.create()
#     # Gallery.add() is an iterator, but we only upload a single image
#     for submission in gallery.add(image_path):
#         _log.debug('Submission: %r', submission)
#         info = {
#             'url': submission.image_url,
#             'thumbnail_url': submission.thumbnail_url,
#             'edit_url': submission.edit_url,
#         }
#         _log.debug('info: %r', info)
#         with open(cache_file, 'w') as f:
#             f.write(json.dumps(info, indent=4) + '\n')
#         return _common.UploadedImage(**info)


# def _cache_file(path):
#     # FIXME: Max file name length is ususally 255 bytes. We use 200 to account
#     # for multibyte characters.
#     filename = path[-200:].replace('/', '_') + '.urls'
#     return os.path.join(fs.tmpdir(), filename)
