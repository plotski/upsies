"""
Upload images to image hosting service
"""

from .... import jobs, utils
from .base import CommandBase


class upload_images(CommandBase):
    """Upload images to image hosting service"""

    names = ('upload-images', 'ui')

    argument_definitions = {}

    subcommand_name = 'IMGHOST'
    subcommands = {
        imghost.name: {
            'description': imghost.description,
            'cli': {
                # Default arguments for all image hosts
                **{
                    'IMAGE': {
                        'nargs': '+',
                        'help': 'Path to image file',
                    },
                    ('--thumb-width', '-t'): {
                        'help': 'Thumbnail width in pixels',
                        'type': utils.argtypes.integer,
                        'default': None,
                    },
                },
                # Custom arguments defined by image host
                **imghost.argument_definitions,
            },
        }
        for imghost in utils.imghosts.imghosts()
    }

    @utils.cached_property
    def imghost_name(self):
        """Lower-case image host name"""
        return self.args.subcommand.lower()

    @utils.cached_property
    def imghost_options(self):
        """
        Relevant section in image host configuration file combined with CLI
        arguments where CLI arguments take precedence unless their value is
        `None`
        """
        return self.get_options('imghosts', self.imghost_name)

    @utils.cached_property
    def jobs(self):
        return (
            jobs.imghost.ImageHostJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                imghost=utils.imghosts.imghost(
                    name=self.imghost_name,
                    options=self.imghost_options,
                ),
                enqueue=self.args.IMAGE,
            ),
        )
