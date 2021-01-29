"""
Create screenshots from video file and optionally upload them
"""

from .... import constants, jobs, utils
from .base import CommandBase


class screenshots(CommandBase):
    """Create screenshots from video file and optionally upload them"""

    names = ('screenshots', 'ss')

    argument_definitions = {
        'CONTENT': {'help': 'Path to release content'},
        ('--timestamps', '-t'): {
            'nargs': '+',
            'default': (),
            'type': utils.types.timestamp,
            'metavar': 'TIMESTAMP',
            'help': 'Space-separated list of [[HH:]MM:]SS strings',
        },
        ('--number', '-n'): {
            'type': utils.types.integer,
            'help': 'How many screenshots to make in total',
            'default': 0,
        },
        ('--upload-to', '-u'): {
            'type': utils.types.imghost,
            'metavar': 'IMAGEHOST',
            'help': ('Case-insensitive name of image hosting service\n'
                     'Supported services: ' + ', '.join(constants.IMGHOST_NAMES)),
        },
    }

    @utils.cached_property
    def screenshots_job(self):
        return jobs.screenshots.ScreenshotsJob(
            home_directory=utils.fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            timestamps=self.args.timestamps,
            count=self.args.number,
        )

    @utils.cached_property
    def upload_screenshots_job(self):
        if self.args.upload_to:
            imghost_job = jobs.imghost.ImageHostJob(
                home_directory=utils.fs.projectdir(self.args.CONTENT),
                ignore_cache=self.args.ignore_cache,
                imghost=utils.imghosts.imghost(
                    name=self.args.upload_to,
                    **self.config['imghosts'][self.args.upload_to],
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
            self.screenshots_job.signal.register('finished', imghost_job.finalize)
            return imghost_job

    @utils.cached_property
    def jobs(self):
        return (
            self.screenshots_job,
            self.upload_screenshots_job,
        )
