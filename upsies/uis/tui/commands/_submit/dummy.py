import random

from ..... import jobs as _jobs
from .....utils import cache, fs, pipe
from . import SubmitCommandBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class submit(SubmitCommandBase):
    @cache.property
    def jobs_before_upload(self):
        return (
            self.create_torrent_job,
            self.screenshots_job,
            self.upload_screenshots_job,
            self.mediainfo_job,
            self.imdb_job,
            self.release_name_job,
            self.choice_prompt_job,
        )

    @cache.property
    def jobs_after_upload(self):
        return (
            self.add_torrent_job,
            self.copy_torrent_job,
        )

    @cache.property
    def screenshots_job(self):
        return _jobs.screenshots.ScreenshotsJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            # TODO: Add --number and --timestamps arguments
        )

    @cache.property
    def upload_screenshots_job(self):
        imghost_job = _jobs.imghost.ImageHostJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            imghost_name='dummy',
            images_total=self.screenshots_job.screenshots_total,
        )
        pipe.Pipe(
            sender=self.screenshots_job,
            receiver=imghost_job,
        )
        return imghost_job

    @cache.property
    def mediainfo_job(self):
        return _jobs.mediainfo.MediainfoJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
        )

    @cache.property
    def imdb_job(self):
        job = _jobs.search.SearchDbJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
            db='imdb',
        )
        job.on_output(self.release_name_job.fetch_info)
        return job

    @cache.property
    def release_name_job(self):
        return _jobs.release_name.ReleaseNameJob(
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.CONTENT,
        )

    @cache.property
    def choice_prompt_job(self):
        return _jobs.prompt.ChoiceJob(
            name='category',
            label='Category',
            homedir=fs.projectdir(self.args.CONTENT),
            ignore_cache=self.args.ignore_cache,
            choices=('Foo', 'Bar', 'Baz'),
            focused=random.choice(('Foo', 'Bar', 'Baz')),
        )
