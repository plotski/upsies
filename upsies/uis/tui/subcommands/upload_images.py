"""
Upload images to image hosting service
"""

from .... import jobs, utils
from .. import argtypes
from .base import CommandBase


class upload_images(CommandBase):
    """Upload images to image hosting service"""

    names = ('upload-images', 'ui')

    arguments = {
        'IMAGEHOST': {
            'type': argtypes.IMAGEHOST,
            'help': ('Case-insensitive name of image hosting service\n'
                     'Supported services: ' + ', '.join(argtypes.IMGHOST_NAMES)),
        },
        'IMAGE': {
            'nargs': '+',
            'help': 'Path to image file',
        },
    }

    @utils.cached_property
    def jobs(self):
        return (
            jobs.imghost.ImageHostJob(
                ignore_cache=self.args.ignore_cache,
                imghost=utils.imghosts.imghost(
                    name=self.args.IMAGEHOST,
                    **self.config['imghosts'][self.args.IMAGEHOST],
                ),
                enqueue=self.args.IMAGE,
            ),
        )
