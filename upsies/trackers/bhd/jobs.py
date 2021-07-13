"""
Concrete :class:`~.base.TrackerJobsBase` subclass for BHD
"""

import io
import os

from ... import jobs
from ...utils import as_groups, cached_property, fs, release
from ..base import TrackerJobsBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BhdTrackerJobs(TrackerJobsBase):
    @cached_property
    def guessed_release_name(self):
        return release.ReleaseName(self.content_path)

    @property
    def approved_release_name(self):
        if self.release_name_job.is_finished and self.release_name_job.output:
            if not hasattr(self, '_approved_release_name'):
                release_name = self.get_job_output(self.release_name_job, slice=0)
                link_path = os.path.join(self.release_name_job.home_directory, release_name)
                file_extension = fs.file_extension(self.content_path)
                if file_extension:
                    link_path += f'.{file_extension}'
                if not os.path.exists(link_path):
                    os.symlink(os.path.abspath(self.content_path), link_path)
                self._approved_release_name = release.ReleaseName(link_path)
            return self._approved_release_name

    movie_types = (release.ReleaseType.movie,)
    series_types = (release.ReleaseType.season, release.ReleaseType.episode)

    def is_movie_type(self, type):
        return type in self.movie_types

    def is_series_type(self, type):
        return type in self.series_types

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
            self.category_job,
            self.imdb_job,
            self.tmdb_job,
            self.release_name_job,
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
            if self.options['description']:
                # Only activate description_job and its dependencies
                return job_attr in ('description_job', 'screenshots_job', 'upload_screenshots_job')
            else:
                return True

        return condition

    @cached_property
    def category_job(self):
        return self.make_choice_job(
            name='category',
            label='Category',
            condition=self.make_job_condition('category_job'),
            autodetected=self.guessed_release_name.type,
            autofinish=False,
            options=(
                {'label': 'Movie', 'value': '1', 'match': self.is_movie_type},
                {'label': 'TV', 'value': '2', 'match': self.is_series_type},
            ),
        )

    @cached_property
    def type_job(self):
        self.release_name_job.signal.register('finished', self.autodetect_type)
        return self.make_choice_job(
            name='type',
            label='Type',
            condition=self.make_job_condition('type_job'),
            autofinish=False,
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

    # Map type_job labels to matchers
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
        if self.approved_release_name:
            approved_release_name = self.approved_release_name
            _log.debug('Approved resolution and source: %r, %r',
                       approved_release_name.resolution, approved_release_name.source)
            for label, is_match in self._autodetect_type_map.items():
                if is_match(approved_release_name):
                    self.type_job.focused = label
                    value = self.type_job.focused[1]
                    self.type_job.set_label(value, f'{label} (autodetected)')
                    break
            else:
                self.type_job.focused = 'Other'

    @cached_property
    def source_job(self):
        self.release_name_job.signal.register('finished', self.autodetect_source)
        return self.make_choice_job(
            name='source',
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

    def autodetect_source(self, release_name_job):
        if self.approved_release_name:
            approved_release_name = self.approved_release_name
            _log.debug('Approved source: %r', approved_release_name.source)
            for label, is_match in self._autodetect_source_map.items():
                if is_match(approved_release_name):
                    # Focus autodetected choice
                    self.source_job.focused = label
                    # Get value of autodetected choice
                    value = self.source_job.focused[1]
                    # Mark autodetected choice
                    self.source_job.set_label(value, f'{label} (autodetected)')
                    # Select autodetected choice (i.e. finish job)
                    self.source_job.choice = value
                    break

    @cached_property
    def description_job(self):
        job = jobs.dialog.TextFieldJob(
            name='description',
            label='Description',
            condition=self.make_job_condition('description_job'),
            read_only=True,
            **self.common_job_args,
        )
        job.add_task(
            job.fetch_text(
                coro=self.generate_screenshots_bbcode(),
                finish_on_success=True,
            )
        )
        return job

    screenshots = 4
    """How many screenshots to make"""

    image_host_config = {
        'imgbox': {'thumb_width': 350},
    }
    """
    Dictionary that maps an image hosting service
    :attr:`~.imghosts.ImageHostBase.name` to keyword arguments for its
    :class:`~.imghosts.ImageHostBase` subclass
    """

    async def generate_screenshots_bbcode(self):
        # Wait until all screenshots are uploaded
        await self.upload_screenshots_job.wait()
        rows = []
        screenshot_groups = as_groups(
            self.upload_screenshots_job.uploaded_images,
            group_sizes=(2, 3),
            default='PLACEHOLDER',
        )
        for screenshots in screenshot_groups:
            cells = []
            for screenshot in screenshots:
                if screenshot != 'PLACEHOLDER':
                    cells.append(f'[url={screenshot}][img]{screenshot.thumbnail_url}[/img][/url]')
            # Space between columns
            rows.append(' '.join(cells))
        # Empty line between rows
        bbcode = '\n\n'.join(rows)
        return f'[center]\n{bbcode}\n[/center]'

    @cached_property
    def tags_job(self):
        job = jobs.dialog.TextFieldJob(
            name='tags',
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
        if 'WEBRip' in self.approved_release_name.source:
            tags.append('WEBRip')
        elif 'WEB-DL' in self.approved_release_name.source:
            tags.append('WEBDL')
        if 'Hybrid' in self.approved_release_name.source:
            tags.append('Hybrid')
        if self.approved_release_name.has_commentary:
            tags.append('Commentary')
        if self.approved_release_name.has_dual_audio:
            tags.append('DualAudio')
        if 'Open Matte' in self.approved_release_name.edition:
            tags.append('OpenMatte')
        if self.get_job_attribute(self.scene_check_job, 'is_scene_release'):
            tags.append('Scene')
        if self.options['personal_rip']:
            tags.append('Personal')

        # TODO: 4kRemaster (waiting for https://github.com/guessit-io/guessit/pull/701)
        # TODO: 2in1 (waiting for https://github.com/guessit-io/guessit/pull/702)
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
        if self.options['description']:
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
        edition = self.approved_release_name.edition
        _log.debug('Approved edition: %r', edition)

        # TODO: Submitting any of the commented edition values produces the
        #       error "Invalid edition value: Field must be a valid edition
        #       value."
        #       "Uncut" and "Unrated" work

        # if 'Collector' in edition:
        #     return 'Collector'
        # # elif 'DC' in edition or 'Director' in edition:
        # #     return 'Director'
        # elif 'Extended' in edition:
        #     return 'Extended'
        # elif 'Limited' in edition:
        #     return 'Limited'
        # elif 'Special' in edition:
        #     return 'Special'
        # elif 'Theatrical' in edition:
        #     return 'Theatrical'
        if 'Uncut' in edition:
            return 'Uncut'
        elif 'Unrated' in edition:
            return 'Unrated'

    @property
    def post_data_pack(self):
        # The TV pack flag for when the torrent contains a complete season.
        # (0 = No TV pack or 1 = TV Pack). Default is 0
        if self.approved_release_name.type is release.ReleaseType.season:
            return '1'
        else:
            return '0'

    @property
    def post_data_sd(self):
        # The SD flag. (0 = Not Standard Definition, 1 = Standard Definition).
        # Default is 0
        try:
            height = int(self.approved_release_name.resolution[:-1])
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
                            with open(nfo_path, 'r') as f:
                                return f.read()
                        except OSError as e:
                            if e.strerror:
                                self.error(e.strerror)
                            else:
                                self.error(e)

    @property
    def post_data_special(self):
        # The TV special flag for when the torrent contains a TV special. (0 =
        # Not a TV special, 1 = TV Special). Default is 0
        if self.approved_release_name.type is release.ReleaseType.episode:
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
