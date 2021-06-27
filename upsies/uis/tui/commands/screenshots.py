"""
Create screenshots from video file and optionally upload them
"""

from .... import jobs, utils
from .base import CommandBase


class screenshots(CommandBase):
    """Create screenshots from video file and optionally upload them"""

    names = ('screenshots', 'ss')

    argument_definitions = {
        'CONTENT': {
            'type': utils.argtypes.content,
            'help': 'Path to release content',
        },
        ('--timestamps', '-t'): {
            'nargs': '+',
            'default': (),
            'type': utils.argtypes.timestamp,
            'metavar': 'TIMESTAMP',
            'help': 'Space-separated list of [[HH:]MM:]SS strings',
        },
        ('--number', '-n'): {
            'type': utils.argtypes.integer,
            'help': 'How many screenshots to make in total',
            'default': 0,
        },
        ('--upload-to', '-u'): {
            'type': utils.argtypes.imghost,
            'metavar': 'IMAGEHOST',
            'help': ('Case-insensitive name of image hosting service\n'
                     'Supported services: ' + ', '.join(utils.imghosts.imghost_names())),
        },
        ('--output-directory', '-o'): {
            'default': '',  # Current working directory
            'metavar': 'PATH',
            'help': 'Directory where screenshots are put (created on demand)',
        },
    }

    @utils.cached_property
    def screenshots_job(self):
        return jobs.screenshots.ScreenshotsJob(
            home_directory=self.args.output_directory,
            cache_directory=self.cache_directory,
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            timestamps=self.args.timestamps,
            count=self.args.number,
        )

    @utils.cached_property
    def upload_screenshots_job(self):
        if self.args.upload_to:
            imghost_job = jobs.imghost.ImageHostJob(
                home_directory=self.home_directory,
                cache_directory=self.cache_directory,
                ignore_cache=self.args.ignore_cache,
                imghost=utils.imghosts.imghost(
                    name=self.args.upload_to,
                    config=self.config['imghosts'][self.args.upload_to],
                ),
            )
            # Timestamps are calculated in a subprocess, we have to wait for
            # that until we can set the number of expected screenhots.
            self.screenshots_job.signal.register(
                'timestamps',
                lambda timestamps: imghost_job.set_images_total(len(timestamps)),
            )
            # Pass ScreenshotsJob's output to ImageHostJob input.
            self.screenshots_job.signal.register('output', imghost_job.enqueue)
            # Tell imghost_job to finish the current upload and then finish.
            self.screenshots_job.signal.register('finished', lambda _: imghost_job.finalize())
            return imghost_job

    @utils.cached_property
    def jobs(self):
        return (
            self.screenshots_job,
            self.upload_screenshots_job,
        )
