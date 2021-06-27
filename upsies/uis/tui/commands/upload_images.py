"""
Upload images to image hosting service
"""

from .... import jobs, utils
from .base import CommandBase


class upload_images(CommandBase):
    """Upload images to image hosting service"""

    names = ('upload-images', 'ui')

    argument_definitions = {
        'IMAGEHOST': {
            'type': utils.argtypes.imghost,
            'help': ('Case-insensitive name of image hosting service\n'
                     'Supported services: ' + ', '.join(utils.imghosts.imghost_names())),
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
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                imghost=utils.imghosts.imghost(
                    name=self.args.IMAGEHOST,
                    config=self.config['imghosts'][self.args.IMAGEHOST],
                ),
                enqueue=self.args.IMAGE,
            ),
        )
