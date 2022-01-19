"""
Concrete :class:`~.base.TrackerJobsBase` subclass for BHD
"""

import io
import os
import re

from ... import __homepage__, __project_name__, jobs
from ...utils import as_groups, cached_property, release, string
from ..base import TrackerJobsBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BhdTrackerJobs(TrackerJobsBase):
    release_name_translation = {
        'audio_format': {
            # Don't match against end of string to preserve extensions like
            # "Atmos"
            re.compile(r'^AC-3'): r'DD',
            re.compile(r'^E-AC-3'): r'DDP',
        },
    }

    @cached_property
    def jobs_before_upload(self):
        # Make base class jobs conditional. Custom BHD jobs get their condition
        # in their properties.
        generic_job_attributes = ('imdb_job', 'tmdb_job', 'release_name_job',
                                  'scene_check_job', 'create_torrent_job', 'mediainfo_job',
                                  'screenshots_job', 'upload_screenshots_job',
                                  'add_torrent_job', 'copy_torrent_job')
        for job_attr in generic_job_attributes:
            job = getattr(self, job_attr, None)
            if job:
                job.condition = self.make_job_condition(job_attr)

        return (
            # Background jobs
            self.create_torrent_job,
            self.mediainfo_job,
            self.screenshots_job,
            self.upload_screenshots_job,

            # Interactive jobs
            self.imdb_job,
            self.tmdb_job,
            self.release_name_job,
            self.category_job,
            self.type_job,
            self.source_job,
            self.description_job,
            self.scene_check_job,
            self.tags_job,
        )

    def make_job_condition(self, job_attr):
        """
        Return :attr:`~.base.JobBase.condition` for jobs

        :param str job_attr: Name of the job attribute this condition is for
        """
        def condition():
            isolated_jobs = self.isolated_jobs
            if isolated_jobs:
                return job_attr in isolated_jobs
            else:
                return True

        return condition

    @property
    def isolated_jobs(self):
        """
        Sequence of attribute names (e.g. "imdb_job") that were singled out by the
        user, e.g. with a CLI argument
        """
        if self.options.get('only_description', False):
            # Only activate description_job and its dependencies
            return ('description_job', 'screenshots_job', 'upload_screenshots_job')
        elif self.options.get('only_title', False):
            # Only activate release_name_job and its dependencies
            return ('release_name_job', 'imdb_job')
        else:
            return ()

    @cached_property
    def imdb_job(self):
        imdb_job = super().imdb_job
        imdb_job.signal.register('output', self.handle_imdb_job_output)
        return imdb_job

    def handle_imdb_job_output(self, _):
        user_confirmed_type = self.imdb_job.query.type
        self.tmdb_job.query.type = user_confirmed_type

    @cached_property
    def category_job(self):
        # 'output' signal is only emitted when job succeeds while 'finished'
        # signal is also emitted when job fails (e.g. when Ctrl-c is pressed)
        self.release_name_job.signal.register('output', self.autodetect_category)
        return self.make_choice_job(
            name=self.get_job_name('category'),
            label='Category',
            condition=self.make_job_condition('category_job'),
            options=(
                {'label': 'Movie', 'value': '1'},
                {'label': 'TV', 'value': '2'},
            ),
        )

    _autodetect_category_map = {
        'Movie': lambda release_name: release_name.type is release.ReleaseType.movie,
        'TV': lambda release_name: release_name.type in (release.ReleaseType.season,
                                                         release.ReleaseType.episode)
    }

    def autodetect_category(self, _):
        approved_release_name = self.release_name
        _log.debug('Autodetecting category: Approved release type: %r', approved_release_name.type)
        for label, is_match in self._autodetect_category_map.items():
            if is_match(approved_release_name):
                # Focus autodetected choice
                self.category_job.focused = label
                # Get value of autodetected choice
                value = self.category_job.focused[1]
                # Mark autodetected choice
                self.category_job.set_label(value, f'{label} (autodetected)')
                break

    @cached_property
    def type_job(self):
        # 'output' signal is only emitted when job succeeds while 'finished'
        # signal is also emitted when job fails (e.g. when Ctrl-c is pressed)
        self.release_name_job.signal.register('output', self.autodetect_type)
        return self.make_choice_job(
            name=self.get_job_name('type'),
            label='Type',
            condition=self.make_job_condition('type_job'),
            options=(
                {'label': 'UHD 100', 'value': 'UHD 100'},
                {'label': 'UHD 66', 'value': 'UHD 66'},
                {'label': 'UHD 50', 'value': 'UHD 50'},
                {'label': 'UHD Remux', 'value': 'UHD Remux'},
                {'label': 'BD 50', 'value': 'BD 50'},
                {'label': 'BD 25', 'value': 'BD 25'},
                {'label': 'BD Remux', 'value': 'BD Remux'},
                {'label': '2160p', 'value': '2160p'},
                {'label': '1080p', 'value': '1080p'},
                {'label': '1080i', 'value': '1080i'},
                {'label': '720p', 'value': '720p'},
                {'label': '576p', 'value': '576p'},
                {'label': '540p', 'value': '540p'},
                {'label': 'DVD 9', 'value': 'DVD 9'},
                {'label': 'DVD 5', 'value': 'DVD 5'},
                {'label': 'DVD Remux', 'value': 'DVD Remux'},
                {'label': '480p', 'value': '480p'},
                {'label': 'Other', 'value': 'Other'},
            ),
        )

    _autodetect_type_map = {
        'DVD 9': lambda release_name: release_name.source == 'DVD9',
        'DVD 5': lambda release_name: release_name.source == 'DVD5',
        'DVD Remux': lambda release_name: release_name.source == 'DVD Remux',
        '2160p': lambda release_name: release_name.resolution == '2160p',
        '1080p': lambda release_name: release_name.resolution == '1080p',
        '1080i': lambda release_name: release_name.resolution == '1080i',
        '720p': lambda release_name: release_name.resolution == '720p',
        '576p': lambda release_name: release_name.resolution == '576p',
        '540p': lambda release_name: release_name.resolution == '540p',
        '480p': lambda release_name: release_name.resolution == '480p',
    }

    def autodetect_type(self, _):
        approved_release_name = self.release_name
        _log.debug('Autodetecting type: Approved resolution: %r', approved_release_name.resolution)
        _log.debug('Autodetecting type: Approved source: %r', approved_release_name.source)
        for label, is_match in self._autodetect_type_map.items():
            if is_match(approved_release_name):
                # Focus autodetected choice
                self.type_job.focused = label
                # Get value of autodetected choice
                value = self.type_job.focused[1]
                # Mark autodetected choice
                self.type_job.set_label(value, f'{label} (autodetected)')
                # Select autodetected choice (i.e. finish job and don't prompt user)
                self.type_job.choice = value
                break
        else:
            self.type_job.focused = 'Other'

    @cached_property
    def source_job(self):
        # 'output' signal is only emitted when job succeeds while 'finished'
        # signal is also emitted when job fails (e.g. when Ctrl-c is pressed)
        self.release_name_job.signal.register('output', self.autodetect_source)
        return self.make_choice_job(
            name=self.get_job_name('source'),
            label='Source',
            condition=self.make_job_condition('source_job'),
            options=(
                {'label': 'Blu-ray', 'value': 'Blu-ray'},
                {'label': 'HD-DVD', 'value': 'HD-DVD'},
                {'label': 'WEB', 'value': 'WEB'},
                {'label': 'HDTV', 'value': 'HDTV'},
                {'label': 'DVD', 'value': 'DVD'},
            ),
        )

    # Map type_job labels to matchers
    _autodetect_source_map = {
        'Blu-ray': lambda release_name: 'BluRay' in release_name.source,
        'HD-DVD': lambda release_name: 'HD-DVD' in release_name.source,
        'WEB': lambda release_name: 'WEB' in release_name.source,
        'HDTV': lambda release_name: 'HDTV' in release_name.source,
        'DVD': lambda release_name: 'DVD' in release_name.source,
    }

    def autodetect_source(self, _):
        approved_release_name = self.release_name
        _log.debug('Autodetecting source: Approved source: %r', approved_release_name.source)
        for label, is_match in self._autodetect_source_map.items():
            if is_match(approved_release_name):
                # Focus autodetected choice
                self.source_job.focused = label
                # Get value of autodetected choice
                value = self.source_job.focused[1]
                # Mark autodetected choice
                self.source_job.set_label(value, f'{label} (autodetected)')
                # Select autodetected choice (i.e. finish job and don't prompt user)
                self.source_job.choice = value
                break

    @cached_property
    def description_job(self):
        job = jobs.dialog.TextFieldJob(
            name=self.get_job_name('description'),
            label='Description',
            condition=self.make_job_condition('description_job'),
            read_only=True,
            **self.common_job_args,
        )
        job.add_task(
            job.fetch_text(
                coro=self.generate_description(),
                finish_on_success=True,
            )
        )
        return job

    image_host_config = {
        'common': {'thumb_width': 350},
    }

    async def generate_description(self):
        # Wait until all screenshots are uploaded
        await self.upload_screenshots_job.wait()
        rows = []
        screenshot_groups = as_groups(
            self.upload_screenshots_job.uploaded_images,
            group_sizes=(2,),
            default=None,
        )
        for screenshots in screenshot_groups:
            cells = []
            for screenshot in screenshots:
                if screenshot is not None:
                    if screenshot.thumbnail_url is None:
                        raise RuntimeError(f'No thumbnail for {screenshot}')
                    cells.append(f'[url={screenshot}][img]{screenshot.thumbnail_url}[/img][/url]')
            # Space between columns
            rows.append('   '.join(cells))
        screenshots = '[center]\n' + '\n\n'.join(rows) + '\n[/center]'
        promotion = (
            '[right][size=1]'
            f'Shared with [url={__homepage__}]{__project_name__}[/url]'
            '[/size][/right]'
        )
        return screenshots + '\n\n' + promotion

    @cached_property
    def tags_job(self):
        job = jobs.dialog.TextFieldJob(
            name=self.get_job_name('tags'),
            label='Tags',
            condition=self.make_job_condition('tags_job'),
            read_only=True,
            **self.common_job_args,
        )
        job.add_task(
            job.fetch_text(
                coro=self.autodetect_tags(),
                finish_on_success=True,
            )
        )
        return job

    async def autodetect_tags(self):
        await self.release_name_job.wait()
        await self.scene_check_job.wait()

        # Any additional tags separated by comma(s). (Commentary, 2in1, Hybrid,
        # OpenMatte, 2D3D, WEBRip, WEBDL, 3D, 4kRemaster, DualAudio, EnglishDub,
        # Personal, Scene, DigitalExtras, Extras)
        tags = []
        if 'WEBRip' in self.release_name.source:
            tags.append('WEBRip')
        elif 'WEB-DL' in self.release_name.source:
            tags.append('WEBDL')
        if 'Hybrid' in self.release_name.source:
            tags.append('Hybrid')
        if self.release_name.has_commentary:
            tags.append('Commentary')
        if self.release_name.has_dual_audio:
            tags.append('DualAudio')
        if 'Open Matte' in self.release_name.edition:
            tags.append('OpenMatte')
        if '2in1' in self.release_name.edition:
            tags.append('2in1')
        if '4k Remastered' in self.release_name.edition:
            tags.append('4kRemaster')
        if self.get_job_attribute(self.scene_check_job, 'is_scene_release'):
            tags.append('Scene')
        if self.options['personal_rip']:
            tags.append('Personal')

        # TODO: 2D3D
        # TODO: 3D
        # TODO: EnglishDub
        # TODO: DigitalExtras
        # TODO: Extras

        return '\n'.join(tags)

    @property
    def submission_ok(self):
        """
        `False` if :attr:`~.TrackerJobsBase.options` prevents submission for any
        reason, parent class implementation otherwise
        """
        if self.isolated_jobs:
            return False
        else:
            return super().submission_ok

    @property
    def post_data(self):
        return {
            'name': self.get_job_output(self.release_name_job, slice=0),
            'category_id': self.get_job_attribute(self.category_job, 'choice'),
            'type': self.get_job_attribute(self.type_job, 'choice'),
            'source': self.get_job_attribute(self.source_job, 'choice'),
            'imdb_id': self.get_job_output(self.imdb_job, slice=0),
            'tmdb_id': self.get_job_output(self.tmdb_job, slice=0).split('/')[1],
            'description': self.get_job_output(self.description_job, slice=0),
            'edition': self.post_data_edition,
            'custom_edition': self.options['custom_edition'],
            'tags': ','.join(self.get_job_output(self.tags_job, slice=0).split('\n')),
            'nfo': self.post_data_nfo,
            'pack': self.post_data_pack,
            'sd': self.post_data_sd,
            'special': self.post_data_special,
            'anon': '1' if self.options['anonymous'] else '0',
            'live': '0' if self.options['draft'] else '1',
        }

    @cached_property
    def post_data_edition(self):
        # The edition of the uploaded release. (Collector, Director, Extended,
        # Limited, Special, Theatrical, Uncut or Unrated)
        edition = self.release_name.edition
        _log.debug('Approved edition: %r', edition)
        if "Collector's Edition" in edition:
            return 'Collector'
        elif "Director's Cut" in edition:
            return 'Director'
        elif 'Extended Cut' in edition:
            return 'Extended'
        elif 'Limited' in edition:
            return 'Limited'
        elif 'Special Edition' in edition:
            return 'Special'
        elif 'Theatrical Cut' in edition:
            return 'Theatrical'
        elif 'Uncut' in edition or 'Uncensored' in edition:
            return 'Uncut'
        elif 'Unrated' in edition:
            return 'Unrated'

    @property
    def post_data_pack(self):
        # The TV pack flag for when the torrent contains a complete season.
        # (0 = No TV pack or 1 = TV Pack). Default is 0
        if self.release_name.type is release.ReleaseType.season:
            return '1'
        else:
            return '0'

    @property
    def post_data_sd(self):
        # The SD flag. (0 = Not Standard Definition, 1 = Standard Definition).
        # Default is 0
        try:
            height = int(self.release_name.resolution[:-1])
        except ValueError:
            return '0'
        else:
            return '1' if height < 720 else '0'

    max_nfo_size = 500_000

    @property
    def post_data_nfo(self):
        # The NFO of the torrent as string.
        if os.path.isdir(self.content_path):
            for entry in os.listdir(self.content_path):
                if entry.lower().endswith('.nfo'):
                    nfo_path = os.path.join(self.content_path, entry)
                    # Limit size to 500kB
                    if os.path.getsize(nfo_path) <= self.max_nfo_size:
                        try:
                            with open(nfo_path, 'rb') as f:
                                return string.autodecode(f.read())
                        except OSError as e:
                            self.error(e.strerror if e.strerror else str(e))

    @property
    def post_data_special(self):
        # The TV special flag for when the torrent contains a TV special. (0 =
        # Not a TV special, 1 = TV Special). Default is 0
        if self.release_name.type is release.ReleaseType.episode:
            if self.options['special']:
                return '1'
        return '0'

    # TODO
    # @property
    # def post_data_region(self):
    #     # The region in which the disc was released. Only for discs! (AUS,
    #     # CAN, CEE, CHN, ESP, EUR, FRA, GBR, GER, HKG, ITA, JPN, KOR, NOR,
    #     # NLD, RUS, TWN or USA)

    @property
    def torrent_filepath(self):
        return self.get_job_output(self.create_torrent_job, slice=0)

    @property
    def mediainfo_filehandle(self):
        mediainfo = self.get_job_output(self.mediainfo_job, slice=0)
        return io.BytesIO(bytes(mediainfo, 'utf-8'))
