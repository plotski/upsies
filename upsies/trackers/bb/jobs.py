"""
Concrete :class:`~.base.TrackerJobsBase` subclass for bB
"""

import asyncio
import os
import re

import unidecode

from ... import __homepage__, __project_name__, __version__, errors, jobs
from ...utils import cached_property, fs, http, image, release, string, video
from ..base import TrackerJobsBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BbTrackerJobs(TrackerJobsBase):
    @cached_property
    def release_name(self):
        """:class:`~.release.ReleaseName` instance"""
        return release.ReleaseName(self.content_path)

    @property
    def release_type(self):
        """:class:`~.types.ReleaseType` enum"""
        return self.release_type_job.choice

    @property
    def is_movie_release(self):
        return self.release_type is release.ReleaseType.movie

    @property
    def is_season_release(self):
        return self.release_type is release.ReleaseType.season

    @property
    def is_episode_release(self):
        return self.release_type is release.ReleaseType.episode

    @property
    def is_series_release(self):
        return self.release_type in (release.ReleaseType.season,
                                     release.ReleaseType.episode)

    @property
    def season(self):
        """Season number or `None`"""
        match = re.search(r'S0*(\d+)', self.release_name.episodes)
        if match:
            return int(match.group(1))

    @property
    def episode(self):
        """Episode number or `None`"""
        match = re.search(r'E0*(\d+)', self.release_name.episodes)
        if match:
            return int(match.group(1))

    # Web DBs

    async def get_imdb_id(self):
        """Return IMDb ID by any means possible, default to `None`"""
        if self.imdb_job.is_enabled:
            await self.imdb_job.wait()
            if self.imdb_job.output:
                return self.imdb_job.output[0]
        else:
            tvmaze_id = await self.get_tvmaze_id()
            if tvmaze_id:
                return await self.tvmaze.imdb_id(tvmaze_id)

    async def get_tvmaze_id(self):
        """Return TVmaze ID by any means possible, default to `None`"""
        if self.tvmaze_job.is_enabled:
            await self.tvmaze_job.wait()
            if self.tvmaze_job.output:
                return self.tvmaze_job.output[0]

    async def try_webdbs(self, webdbs, method, default=None):
        """
        Try to run `method` on each item in `webdbs` and return the first truthy
        return value

        :params webdbs: Sequence of :class:`~.webdbs.base.WebDbApiBase`
            instances
        :params str method: Name of a method of any item in `webdbs`

        Before calling `method`, an attempt is made to get the DB's ID by
        calling the ``get_<webdb.name>_id`` method. If that fails, the next DB
        is tried. If an ID is returned, it is passed to `method`.

        :return: The first truthy return value of `method`
        """
        for webdb in webdbs:
            id_getter = getattr(self, f'get_{webdb.name}_id')
            id = await id_getter()
            if id:
                result_getter = getattr(webdb, method)
                result = await result_getter(id)
                if result:
                    return result
        try:
            # Default to return value from final webdb, e.g. empty string, empty
            # list, etc (these wouldn't be returned above, they are falsy)
            return result
        except NameError:
            # Return default if we couldn't get an ID for any webdb
            return default

    # Jobs

    @cached_property
    def jobs_before_upload(self):
        # Turn generic jobs from parent class into conditional jobs.
        all_release_types = (release.ReleaseType.movie, release.ReleaseType.series, release.ReleaseType.episode)
        generic_job_attributes = ('mediainfo_job', 'scene_check_job', 'create_torrent_job',
                                  'screenshots_job', 'upload_screenshots_job',
                                  'add_torrent_job', 'copy_torrent_job')
        for job_attr in generic_job_attributes:
            job = getattr(self, job_attr)
            if job is not None:
                job.condition = self.make_job_condition(job_attr, *all_release_types)

        # Return all possible jobs and disable/enable them via JobBase's
        # "condition" argument.
        return (
            # Generic jobs
            self.release_type_job,
            self.mediainfo_job,
            self.create_torrent_job,
            self.screenshots_job,
            self.upload_screenshots_job,
            self.scene_check_job,

            # Movie jobs
            self.imdb_job,
            self.movie_title_job,
            self.movie_year_job,
            self.movie_resolution_job,
            self.movie_source_job,
            self.movie_audio_codec_job,
            self.movie_video_codec_job,
            self.movie_container_job,
            self.movie_release_info_job,
            self.movie_poster_job,
            self.movie_tags_job,
            self.movie_description_job,

            # Series jobs
            self.tvmaze_job,
            self.series_title_job,
            self.series_poster_job,
            self.series_tags_job,
            self.series_description_job,
        )

    def make_job_condition(self, job_attr, *release_types):
        """
        Return :attr:`~.base.JobBase.condition` for jobs

        :param str job_attr: Name of the job attribute this condition is for
        """
        def condition():
            if self.release_type in release_types:
                # Job is appropriate for release type
                isolated_jobs = self.isolated_jobs
                if not isolated_jobs:
                    # No jobs where singled out via CLI arguments or other
                    # means; all appropriate jobs are enabled
                    return True
                elif job_attr in isolated_jobs:
                    # This particular job was singled out by the user;
                    # all other jobs are disabled
                    return True
            return False

        return condition

    @property
    def isolated_jobs(self):
        """
        Sequence of attribute names (e.g. "movie_poster_job") that were singled out
        by the user, e.g. with a CLI argument
        """
        if self.is_movie_release:
            if self.options.get('only_description', False):
                return ('imdb_job', 'movie_description_job')
            elif self.options.get('only_poster', False):
                return ('imdb_job', 'movie_poster_job')
            elif self.options.get('only_release_info', False):
                return ('movie_release_info_job',)
            elif self.options.get('only_tags', False):
                return ('imdb_job', 'movie_tags_job')
            elif self.options.get('only_title', False):
                return ('imdb_job', 'movie_title_job')

        elif self.is_series_release:
            if self.options.get('only_description', False):
                return ('tvmaze_job', 'mediainfo_job', 'screenshots_job',
                        'upload_screenshots_job', 'series_description_job')
            elif self.options.get('only_poster', False):
                return ('tvmaze_job', 'series_poster_job')
            elif self.options.get('only_title', False) or self.options.get('only_release_info', False):
                # Series title and release_info are combined
                return ('tvmaze_job', 'series_title_job')
            elif self.options.get('only_tags', False):
                return ('tvmaze_job', 'series_tags_job')

        return ()

    @cached_property
    def release_type_job(self):
        return jobs.dialog.ChoiceJob(
            name=self.get_job_name('release-type'),
            label='Release Type',
            choices=(
                ('Movie', release.ReleaseType.movie),
                ('Season', release.ReleaseType.season),
                ('Episode', release.ReleaseType.episode),
            ),
            focused=self.release_name.type,
            callbacks={
                'output': self.handle_release_type_selected,
            },
            **self.common_job_args,
        )

    def handle_release_type_selected(self, _):
        if self.release_type_job.choice:
            self.imdb_job.query.type = self.release_type_job.choice

    # Movie jobs

    @cached_property
    def imdb_job(self):
        """:class:`~.jobs.webdb.WebDbSearchJob` instance"""
        imdb_job = super().imdb_job
        imdb_job.condition = self.make_job_condition('imdb_job', release.ReleaseType.movie)
        imdb_job.no_id_ok = True
        return imdb_job

    @cached_property
    def movie_title_job(self):
        self.imdb_job.signal.register('finished', self.fill_in_movie_title)
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('movie-title'),
            label='Title',
            condition=self.make_job_condition('movie_title_job', release.ReleaseType.movie),
            validator=self.movie_title_validator,
            **self.common_job_args,
        )

    def movie_title_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError('Failed to autodetect title')

    def fill_in_movie_title(self, job_):
        task = self.movie_title_job.fetch_text(
            coro=self.get_movie_title(),
            default_text=self.release_name.title_with_aka,
            finish_on_success=False,
        )
        self.movie_title_job.add_task(task)

    @cached_property
    def movie_year_job(self):
        self.imdb_job.signal.register('finished', self.fill_in_movie_year)
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('movie-year'),
            label='Year',
            condition=self.make_job_condition('movie_year_job', release.ReleaseType.movie),
            validator=self.movie_year_validator,
            **self.common_job_args,
        )

    def movie_year_validator(self, text):
        # Raise ValueError if not a valid year
        self.release_name.year = text
        # release_name.year is now "UNKNOWN_YEAR" if year is required but not known
        if self.release_name.year == 'UNKNOWN_YEAR':
            raise ValueError('Failed to autodetect year')

    def fill_in_movie_year(self, job_):
        task = self.movie_year_job.fetch_text(
            coro=self.get_movie_year(),
            default_text=self.release_name.year,
            finish_on_success=True,
        )
        self.movie_year_job.add_task(task)

    @cached_property
    def movie_resolution_job(self):
        return self.make_choice_job(
            name=self.get_job_name('movie-resolution'),
            label='Resolution',
            condition=self.make_job_condition('movie_resolution_job', release.ReleaseType.movie),
            autodetected=self.release_info_resolution,
            autofinish=True,
            options=(
                {'label': '4320p', 'value': '2160p', 'regex': re.compile(r'4320p')},
                {'label': '2160p', 'value': '2160p', 'regex': re.compile(r'2160p')},
                {'label': '1080p', 'value': '1080p', 'regex': re.compile(r'1080p')},
                {'label': '1080i', 'value': '1080i', 'regex': re.compile(r'1080i')},
                {'label': '720p', 'value': '720p', 'regex': re.compile(r'720p')},
                {'label': '720i', 'value': '720i', 'regex': re.compile(r'720i')},
                {'label': '576p', 'value': '480p', 'regex': re.compile(r'576p')},
                {'label': '576i', 'value': '480i', 'regex': re.compile(r'576i')},
                {'label': '540p', 'value': '480p', 'regex': re.compile(r'540p')},
                {'label': '540i', 'value': '480i', 'regex': re.compile(r'540i')},
                {'label': '480p', 'value': '480p', 'regex': re.compile(r'480p')},
                {'label': '480i', 'value': '480i', 'regex': re.compile(r'480i')},
                {'label': 'SD', 'value': 'SD', 'regex': re.compile(r'SD')},
            ),
        )

    @cached_property
    def movie_source_job(self):
        return self.make_choice_job(
            name=self.get_job_name('movie-source'),
            label='Source',
            condition=self.make_job_condition('movie_source_job', release.ReleaseType.movie),
            autodetected=self.release_name.source,
            autofinish=True,
            options=(
                {'label': 'BluRay', 'value': 'BluRay', 'regex': re.compile('BluRay')},  # [Hybrid] BluRay [Remux]
                {'label': 'DVD5', 'value': 'DVD5', 'regex': re.compile('^DVD5$')},
                {'label': 'DVD9', 'value': 'DVD9', 'regex': re.compile('^DVD9$')},
                {'label': 'DVDRip', 'value': 'DVDRip', 'regex': re.compile('^DVDRip$')},
                {'label': 'HD-DVD', 'value': 'HD-DVD', 'regex': re.compile('^HD-DVD$')},
                {'label': 'HDTV', 'value': 'HDTV', 'regex': re.compile('^HDTV$')},
                {'label': 'WEB-DL', 'value': 'WEB-DL', 'regex': re.compile('^WEB-DL$')},
                {'label': 'WEBRip', 'value': 'WebRip', 'regex': re.compile('^WEBRip$')},
                # I don't know if guessit supports these
                {'label': 'BluRay 3D', 'value': 'BluRay 3D'},
                {'label': 'BluRay RC', 'value': 'BluRay RC'},
                {'label': 'CAM', 'value': 'CAM'},
                {'label': 'DVDSCR', 'value': 'DVDSCR'},
                {'label': 'HDRip', 'value': 'HDRip'},
                {'label': 'PDTV', 'value': 'PDTV'},
                {'label': 'R5', 'value': 'R5'},
                {'label': 'SDTV', 'value': 'SDTV'},
                {'label': 'TC', 'value': 'TC'},
                {'label': 'TeleSync', 'value': 'TeleSync'},
                {'label': 'VHSRip', 'value': 'VHSRip'},
                {'label': 'VODRip', 'value': 'VODRip'},
            ),
        )

    @cached_property
    def movie_audio_codec_job(self):
        return self.make_choice_job(
            name=self.get_job_name('movie-audio-codec'),
            label='Audio Codec',
            condition=self.make_job_condition('movie_audio_codec_job', release.ReleaseType.movie),
            autodetected=self.release_info_audio_format,
            autofinish=True,
            options=(
                {'label': 'AAC', 'value': 'AAC', 'regex': re.compile(r'^AAC$')},
                {'label': 'AC-3', 'value': 'AC-3', 'regex': re.compile(r'^(?:E-|)AC-3$')},   # AC-3, E-AC-3
                {'label': 'DTS', 'value': 'DTS', 'regex': re.compile(r'^DTS(?!-HD)')},       # DTS, DTS-ES
                {'label': 'DTS-HD', 'value': 'DTS-HD', 'regex': re.compile(r'^DTS-HD\b')},   # DTS-HD, DTS-HD MA
                {'label': 'DTS:X', 'value': 'DTS:X', 'regex': re.compile(r'^DTS:X$')},
                {'label': 'Dolby Atmos', 'value': 'Dolby Atmos', 'regex': re.compile(r'Atmos')},
                {'label': 'FLAC', 'value': 'FLAC', 'regex': re.compile(r'^FLAC$')},
                {'label': 'MP3', 'value': 'MP3', 'regex': re.compile(r'^MP3$')},
                # {'label': 'PCM', 'value': 'PCM', 'regex': re.compile(r'^$')},
                {'label': 'TrueHD', 'value': 'True-HD', 'regex': re.compile(r'TrueHD')},
                {'label': 'Vorbis', 'value': 'Vorbis', 'regex': re.compile(r'^Vorbis$')},
            ),
        )

    @cached_property
    def movie_video_codec_job(self):
        return self.make_choice_job(
            name=self.get_job_name('movie-video-codec'),
            label='Video Codec',
            condition=self.make_job_condition('movie_video_codec_job', release.ReleaseType.movie),
            autodetected=self.release_name.video_format,
            autofinish=True,
            options=(
                {'label': 'x264', 'value': 'x264', 'regex': re.compile(r'x264')},
                {'label': 'x265', 'value': 'x265', 'regex': re.compile(r'x265')},
                {'label': 'XviD', 'value': 'XVid', 'regex': re.compile(r'(?i:XviD)')},
                # {'label': 'MPEG-2', 'value': 'MPEG-2', 'regex': re.compile(r'')},
                # {'label': 'WMV-HD', 'value': 'WMV-HD', 'regex': re.compile(r'')},
                # {'label': 'DivX', 'value': 'DivX', 'regex': re.compile(r'')},
                {'label': 'H.264', 'value': 'H.264', 'regex': re.compile(r'H.264')},
                {'label': 'H.265', 'value': 'H.265', 'regex': re.compile(r'H.265')},
                # {'label': 'VC-1', 'value': 'VC-1', 'regex': re.compile(r'')},
            ),
        )

    @cached_property
    def movie_container_job(self):
        # Get file extension from largest file
        files = sorted(fs.file_list(self.content_path), key=fs.file_size)
        autodetected_extension = fs.file_extension(files[-1])
        return self.make_choice_job(
            name=self.get_job_name('movie-container'),
            label='Container',
            condition=self.make_job_condition('movie_container_job', release.ReleaseType.movie),
            autodetected=autodetected_extension,
            autofinish=True,
            options=(
                {'label': 'AVI', 'value': 'AVI', 'regex': re.compile(r'^(?i:avi)$')},
                {'label': 'MKV', 'value': 'MKV', 'regex': re.compile('^(?i:mkv)$')},
                {'label': 'MP4', 'value': 'MP4', 'regex': re.compile(r'^(?i:mp4)$')},
                {'label': 'TS', 'value': 'TS', 'regex': re.compile(r'^(?i:ts)$')},
                {'label': 'VOB', 'value': 'VOB', 'regex': re.compile(r'^(?i:vob)$')},
                {'label': 'WMV', 'value': 'WMV', 'regex': re.compile(r'^(?i:wmv)$')},
                {'label': 'm2ts', 'value': 'm2ts', 'regex': re.compile(r'^(?i:m2ts|mts)$')},
            ),
        )

    @cached_property
    def movie_release_info_job(self):
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('movie-release-info'),
            label='Release Info',
            condition=self.make_job_condition('movie_release_info_job', release.ReleaseType.movie),
            text=self.get_movie_release_info(),
            **self.common_job_args,
        )

    @cached_property
    def movie_poster_job(self):
        """Re-upload poster from IMDb to :attr:`~.TrackerJobsBase.image_host`"""
        return jobs.custom.CustomJob(
            name=self.get_job_name('movie-poster'),
            label='Poster',
            condition=self.make_job_condition('movie_poster_job', release.ReleaseType.movie),
            worker=self.movie_get_poster_url,
            catch=(errors.RequestError,),
            **self.common_job_args,
        )

    async def movie_get_poster_url(self, poster_job):
        return await self.get_resized_poster_url(poster_job, self.get_movie_poster_url)

    @cached_property
    def movie_tags_job(self):
        self.imdb_job.signal.register('finished', self.fill_in_movie_tags)
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('movie-tags'),
            label='Tags',
            condition=self.make_job_condition('movie_tags_job', release.ReleaseType.movie),
            validator=self.movie_tags_validator,
            normalizer=self.normalize_tags,
            **self.common_job_args,
        )

    def movie_tags_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError('Failed to generate tags (use --tags)')

    def fill_in_movie_tags(self, job_):
        task = self.movie_tags_job.fetch_text(
            coro=self.get_tags(),
            finish_on_success=True,
        )
        self.movie_tags_job.add_task(task)

    @cached_property
    def movie_description_job(self):
        self.imdb_job.signal.register('finished', self.fill_in_movie_description)
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('movie-description'),
            label='Description',
            condition=self.make_job_condition('movie_description_job', release.ReleaseType.movie),
            validator=self.movie_description_validator,
            **self.common_job_args,
        )

    def movie_description_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError('Failed to generate description (use --description)')

    def fill_in_movie_description(self, job_):
        task = self.movie_description_job.fetch_text(
            coro=self.get_description(),
            finish_on_success=True,
        )
        self.movie_description_job.add_task(task)

    # Series jobs

    @cached_property
    def tvmaze_job(self):
        """:class:`~.jobs.webdb.WebDbSearchJob` instance"""
        tvmaze_job = super().tvmaze_job
        tvmaze_job.condition = self.make_job_condition(
            'tvmaze_job',
            release.ReleaseType.season,
            release.ReleaseType.episode,
        )
        tvmaze_job.no_id_ok = True
        return tvmaze_job

    @cached_property
    def series_title_job(self):
        self.tvmaze_job.signal.register('finished', self.fill_in_series_title)
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('series-title'),
            label='Title',
            condition=self.make_job_condition('series_title_job', release.ReleaseType.season, release.ReleaseType.episode),
            validator=self.series_title_validator,
            **self.common_job_args,
        )

    def series_title_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError('Failed to generate title')
        unknown = ', '.join(u.lower() for u in re.findall(r'UNKNOWN_([A-Z_]+)', text))
        if unknown:
            raise ValueError(f'Failed to autodetect: {unknown}')

    def fill_in_series_title(self, job_):
        task = self.series_title_job.fetch_text(
            coro=self.get_series_title_and_release_info(),
            default_text=self.release_name.title_with_aka_and_year,
            finish_on_success=False,
        )
        self.series_title_job.add_task(task)

    @cached_property
    def series_poster_job(self):
        """Re-upload poster from TVmaze to :attr:`~.TrackerJobsBase.image_host`"""
        return jobs.custom.CustomJob(
            name=self.get_job_name('series-poster'),
            label='Poster',
            condition=self.make_job_condition('series_poster_job', release.ReleaseType.season, release.ReleaseType.episode),
            worker=self.series_get_poster_url,
            catch=(errors.RequestError,),
            **self.common_job_args,
        )

    async def series_get_poster_url(self, poster_job):
        return await self.get_resized_poster_url(poster_job, self.get_series_poster_url)

    @cached_property
    def series_tags_job(self):
        self.tvmaze_job.signal.register('finished', self.fill_in_series_tags)
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('series-tags'),
            label='Tags',
            condition=self.make_job_condition('series_tags_job', release.ReleaseType.season, release.ReleaseType.episode),
            validator=self.series_tags_validator,
            normalizer=self.normalize_tags,
            **self.common_job_args,
        )

    def series_tags_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError('Failed to generate tags (use --tags)')

    def fill_in_series_tags(self, job_):
        task = self.series_tags_job.fetch_text(
            coro=self.get_tags(),
            finish_on_success=True,
        )
        self.series_tags_job.add_task(task)

    @cached_property
    def series_description_job(self):
        self.tvmaze_job.signal.register('finished', self.fill_in_series_description)
        return jobs.dialog.TextFieldJob(
            name=self.get_job_name('series-description'),
            label='Description',
            condition=self.make_job_condition('series_description_job', release.ReleaseType.season, release.ReleaseType.episode),
            validator=self.series_description_validator,
            **self.common_job_args,
        )

    def series_description_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError('Failed to generate description (use --description)')

    def fill_in_series_description(self, job_):
        task = self.series_description_job.fetch_text(
            coro=self.get_description(),
            finish_on_success=True,
        )
        self.series_description_job.add_task(task)

    # Release Info

    @property
    def release_info_subtitles(self):
        subtitle_tracks = video.tracks(self.content_path, default={}).get('Text', ())
        if subtitle_tracks:
            subtitle_languages = [track.get('Language') for track in subtitle_tracks]
            if 'en' in subtitle_languages:
                return 'w. Subtitles'

    @property
    def release_info_commentary(self):
        if self.release_name.has_commentary:
            return 'w. Commentary'

    @property
    def release_info_source(self):
        if self.release_name.source == 'WEBRip':
            return 'WebRip'
        else:
            return string.remove_suffix(self.release_name.source, 'Remux').strip()

    @property
    def release_info_remux(self):
        if 'Remux' in self.release_name.source:
            return 'REMUX'

    @property
    def release_info_resolution(self):
        # Move/TV Rule 3.6.1 - Encodes with a stored resolution less than 700px
        #                      AND a height less than 460px should be labelled
        #                      "SD"
        width = video.width(self.content_path, default=0)
        height = video.height(self.content_path, default=0)
        if 1 < width < 700 and 1 < height < 460:
            return 'SD'

        # Movie Rule 3.6.2 - 576p PAL encodes with a stored resolution of at
        #                    least 700px wide and/or 560px tall should be
        #                    labelled "480p" with "576p PAL" noted in the
        #                    Release Info field
        # We also apply this to series releases by using this property in
        # get_series_title_and_release_info().
        resolution = self.release_name.resolution
        frame_rate = video.frame_rate(self.content_path, default=0)
        if resolution == '576p' and frame_rate == 25:
            return '576p PAL'

        return self.release_name.resolution

    @property
    def release_info_576p_PAL(self):
        """Return "576p PAL" if release is 576p and PAL or `None`"""
        if self.release_info_resolution == '576p PAL':
            return '576p PAL'

    @property
    def release_info_proper(self):
        if 'Proper' in self.release_name.edition:
            return 'PROPER'

    @property
    def release_info_repack(self):
        if 'Repack' in self.release_name.edition:
            return 'REPACK'

    @property
    def release_info_hdr_format(self):
        hdr_format = video.hdr_format(self.content_path, default=None)
        if hdr_format:
            return hdr_format

    @property
    def release_info_10bit(self):
        if video.bit_depth(self.content_path, default=None) == 10:
            return '10-bit'

    @property
    def release_info_dual_audio(self):
        if video.has_dual_audio(self.content_path, default=False):
            return 'Dual Audio'

    @property
    def release_info_audio_format(self):
        audio_format = self.release_name.audio_format
        # "E-AC-3 Atmos" and "TrueHD Atmos" -> "Atmos"
        if 'Atmos' in audio_format:
            return 'Atmos'
        return audio_format

    @property
    def release_info_uncensored(self):
        if 'Uncensored' in self.release_name.edition:
            return 'Uncensored'

    @property
    def release_info_uncut(self):
        if 'Uncut' in self.release_name.edition:
            return 'Uncut'

    @property
    def release_info_unrated(self):
        if 'Unrated' in self.release_name.edition:
            return 'Unrated'

    @property
    def release_info_remastered(self):
        if '4k Remastered' in self.release_name.edition:
            return '4k Remaster'
        elif '4k Restored' in self.release_name.edition:
            return '4k Restored'
        elif 'Remastered' in self.release_name.edition:
            return 'Remastered'
        elif 'Restored' in self.release_name.edition:
            return 'Restored'

    @property
    def release_info_open_matte(self):
        if 'Open Matte' in self.release_name.edition:
            return 'Open Matte'

    @property
    def release_info_directors_cut(self):
        if "Director's Cut" in self.release_name.edition:
            return "Director's Cut"

    @property
    def release_info_theatrical_cut(self):
        if 'Theatrical Cut' in self.release_name.edition:
            return 'Theatrical Cut'

    @property
    def release_info_imax(self):
        if 'IMAX' in self.release_name.edition:
            return 'IMAX'

    @property
    def release_info_extended_edition(self):
        if 'Extended Cut' in self.release_name.edition:
            return 'Extended Edition'

    @property
    def release_info_anniversary_edition(self):
        for name in fs.file_and_parent(self.content_path):
            match = re.search(rf'(?i:{release.DELIM}(?:(\d+)th{release.DELIM}|)Anniversary{release.DELIM})', name)
            if match:
                if match.group(1):
                    return f'{match.group(1)}th Anniversary Edition'
                else:
                    return 'Anniversary Edition'

    @property
    def release_info_criterion_edition(self):
        if 'Criterion Collection' in self.release_name.edition:
            return 'Criterion Edition'

    @property
    def release_info_special_edition(self):
        if 'Special Edition' in self.release_name.edition:
            return 'Special Edition'

    @property
    def release_info_limited_edition(self):
        if 'Limited' in self.release_name.edition:
            return 'Limited'

    @property
    def release_info_2in1(self):
        if '2in1' in self.release_name.edition:
            return '2in1'

    # Metadata generators

    async def get_movie_title(self):
        imdb_id = await self.get_imdb_id()
        if imdb_id:
            await self.release_name.fetch_info(imdb_id=imdb_id)
            return self.release_name.title_with_aka

    async def get_movie_year(self):
        imdb_id = await self.get_imdb_id()
        if imdb_id:
            await self.release_name.fetch_info(imdb_id=imdb_id)
            return self.release_name.year

    async def get_series_title_and_release_info(self):
        imdb_id = await self.get_imdb_id()
        if imdb_id:
            await self.release_name.fetch_info(imdb_id=imdb_id)

        title = [self.release_name.title_with_aka]
        if self.release_name.year_required:
            title.append(f'({self.release_name.year})')

        # "Season x"
        if self.is_season_release:
            title.append(f'- Season {self.season or "UNKNOWN_SEASON"}')

        # "SxxEyy"
        elif self.is_episode_release:
            if self.release_name.date:
                # Episodes may have a date (e.g. "2001-03-24") instead of the
                # usual "SxxEyy" string
                title.append(str(self.release_name.date))
            else:
                # Use "SxxEyy" string or default to "UNKNOWN_EPISODE"
                title.append(str(self.release_name.episodes))

        info = [
            # [Source / VideoCodec / AudioCodec / Container / Resolution]
            self.release_info_source,
            self.release_name.video_format,
            self.release_info_audio_format,
            fs.file_extension(video.first_video(self.content_path)).upper(),
            self.release_info_resolution,

            # Scene tags
            self.release_info_proper,
            self.release_info_repack,

            # Special formats
            self.release_info_remux,
            self.release_info_10bit,
            self.release_info_hdr_format,

            # Editions
            self.release_info_uncensored,
            self.release_info_uncut,
            self.release_info_unrated,
            self.release_info_remastered,
            self.release_info_directors_cut,
            self.release_info_theatrical_cut,
            self.release_info_imax,
            self.release_info_extended_edition,
            self.release_info_anniversary_edition,
            self.release_info_criterion_edition,
            self.release_info_special_edition,
            self.release_info_limited_edition,
            self.release_info_2in1,

            # Features
            self.release_info_open_matte,
            self.release_info_dual_audio,
            self.release_info_commentary,
            self.release_info_subtitles,
        ]
        info_string = ' / '.join(i for i in info if i)
        return ' '.join(title) + f' [{info_string}]'

    async def get_resized_poster_url(self, poster_job, poster_url_getter):
        poster_path = await self.get_poster_file(poster_job, poster_url_getter)
        if not poster_path:
            self.error('Provide a poster file or URL with the --poster option.')
        else:
            # Resize poster
            try:
                resized_poster_path = image.resize(
                    image_file=poster_path,
                    target_directory=poster_job.home_directory,
                    width=300,
                )
            except errors.ImageResizeError as e:
                self.error(f'Poster resizing failed: {e}')
            else:
                _log.debug('Poster resized: %r', resized_poster_path)
                # Upload poster to self.image_host
                poster_job.info = f'Uploading poster to {self.image_host.name}'
                try:
                    return await self.image_host.upload(resized_poster_path)
                except errors.RequestError as e:
                    self.error(f'Poster upload failed: {e}')
                finally:
                    poster_job.info = ''

    async def get_poster_file(self, poster_job, poster_url_getter):
        if self.options.get('poster'):
            # Get custom poster from user (e.g. CLI argument)
            if re.search(r'^[a-z]+://', self.options['poster']):
                # Poster argument is URL
                poster_url = self.options['poster']
            else:
                # Poster is file path
                return self.options['poster']
        else:
            # Get poster URL from webdb
            poster_url = await poster_url_getter()

        if not poster_url:
            self.error('Failed to find poster URL (use --poster)')
        else:
            # Download poster
            poster_job.info = f'Downloading poster: {poster_url}'
            poster_path = os.path.join(poster_job.home_directory, 'poster.bb.jpg')
            try:
                await http.download(poster_url, poster_path)
            except errors.RequestError as e:
                self.error(f'Poster download failed: {e}')
            else:
                return poster_path

    async def get_movie_poster_url(self):
        imdb_id = await self.get_imdb_id()
        if imdb_id:
            poster_url = await self.imdb.poster_url(imdb_id)
            _log.debug('Poster URL for %r: %r', imdb_id, poster_url)
            return poster_url

    async def get_series_poster_url(self):
        tvmaze_id = await self.get_tvmaze_id()
        if tvmaze_id:
            poster_url = await self.tvmaze.poster_url(tvmaze_id, season=self.season)
            _log.debug('Poster URL for %r: %r', tvmaze_id, poster_url)
            return poster_url

    def get_movie_release_info(self):
        info = (
            # Scene tags
            self.release_info_proper,
            self.release_info_repack,

            # Special formats
            self.release_info_remux,
            self.release_info_576p_PAL,
            self.release_info_10bit,
            self.release_info_hdr_format,

            # Editions
            self.release_info_uncensored,
            self.release_info_uncut,
            self.release_info_unrated,
            self.release_info_remastered,
            self.release_info_directors_cut,
            self.release_info_theatrical_cut,
            self.release_info_imax,
            self.release_info_extended_edition,
            self.release_info_anniversary_edition,
            self.release_info_criterion_edition,
            self.release_info_special_edition,
            self.release_info_limited_edition,
            self.release_info_2in1,

            # Features
            self.release_info_open_matte,
            self.release_info_dual_audio,
            self.release_info_commentary,
            self.release_info_subtitles,
        )
        return ' / '.join(i for i in info if i)

    async def get_tags(self):
        if self.options.get('tags', ()):
            # Get custom tags from user (e.g. CLI argument)
            tags_list = self.options['tags'].split(',')

        else:
            # Get custom tags from webdb

            # For movies, TVmaze ID is None and tvmaze is ignored.
            # For series, IMDb might have information TVmaze is missing.
            webdbs = (self.tvmaze, self.imdb)

            # Gather tags
            tags_list = list(await self.try_webdbs(webdbs, 'genres', default=()))
            if self.is_movie_release:
                tags_list.extend(await self.try_webdbs(webdbs, 'directors', default=()))
            elif self.is_series_release:
                tags_list.extend(await self.try_webdbs(webdbs, 'creators', default=()))
            tags_list.extend(await self.try_webdbs(webdbs, 'cast', default=()))

        return self.normalize_tags(tags_list)

    _tags_translation = {
        re.compile('^sci.?fi$'): 'science.fiction',
    }

    def normalize_tags(self, tags):
        if isinstance(tags, str):
            tags = tags.split(',')

        allowed_characters = (
            string.group('ascii_lowercase')
            + string.group('digits')
            + '.'
        )

        # Replace spaces, non-ASCII characters, etc
        normalized = []
        for tag in tags:
            tag = (
                str(tag)
                .strip()
                .lower()
                .replace(' ', '.')
                .replace('-', '.')
                .replace("'", '')
            )
            tag = re.sub(r'\.+', '.', tag)  # Dedup "."
            tag = unidecode.unidecode(tag)  # Translate exotic characters to ASCII
            tag = ''.join(c for c in tag    # Remove remaining non-ASCII characters
                          if c in allowed_characters)
            for regex, replacement in self._tags_translation.items():
                if regex.search(tag):
                    tag = replacement
                    break
            tag = tag.strip(',.')           # Remove leading/trailing tag/space separators
            normalized.append(tag)

        def join_tags(tags):
            return ','.join(str(tag) for tag in tags if tag)

        # Maximum length of concatenated tags is 200 characters
        tags_string = join_tags(normalized)
        while len(tags_string) > 200:
            del normalized[-1]
            tags_string = join_tags(normalized)

        return tags_string

    async def get_description(self):
        parts = []

        if self.options.get('description', ''):
            # Custom description
            if os.path.exists(self.options['description']):
                try:
                    with open(self.options['description'], mode='r', encoding='utf-8') as f:
                        parts.append(f.read())
                except OSError as e:
                    msg = e.strerror if e.strerror else str(e)
                    self.error(f'Failed to read {self.options["description"]}: {msg}')
                    return ''
            else:
                parts.append(self.options['description'])

        else:
            async def extend_parts(*coros, sep='', fmt='{text}'):
                info_table = await asyncio.gather(*coros)
                text = sep.join(
                    str(item) for item in info_table
                    if item is not None
                )
                if text:
                    parts.append(fmt.format(text=text))

            # Summary
            await extend_parts(self.format_description_summary())

            # Table-like quote block with details
            await extend_parts(
                self.format_description_webdbs(),
                self.format_description_year(),
                self.format_description_status(),
                self.format_description_countries(),
                self.format_description_runtime(),
                self.format_description_directors(),
                self.format_description_creators(),
                self.format_description_cast(),
                sep='\n',
                fmt='[quote]{text}[/quote]',
            )

            # Season and episode description also contains screenshots and
            # mediainfo
            if self.is_series_release:
                await extend_parts(
                    self.format_description_series_screenshots(),
                    self.format_description_series_mediainfo(),
                )

        return ''.join(parts).strip()

    async def format_description_summary(self):
        summary = await self.try_webdbs((self.tvmaze, self.imdb), 'summary', default='')
        if summary:
            summary = '[quote]' + summary
            if self.is_episode_release and self.season and self.episode:
                ep_summary = await self.format_description_episode_summary()
                if ep_summary:
                    summary += f'\n\n{ep_summary}'
            summary += '[/quote]'
            return summary

    async def format_description_episode_summary(self):
        tvmaze_id = await self.get_tvmaze_id()
        if tvmaze_id:
            try:
                episode = await self.tvmaze.episode(
                    id=tvmaze_id,
                    season=self.season,
                    episode=self.episode,
                )
            except errors.RequestError:
                pass
            else:
                summary = (
                    f'[url={episode["url"]}]{episode["title"]}[/url]',
                    ' - ',
                    f'Season {episode["season"]}, Episode {episode["episode"]}',
                    f' - [size=2]{episode["date"]}[/size]' if episode.get('date') else '',
                    f'\n\n[spoiler]\n{episode["summary"]}[/spoiler]' if episode.get('summary') else '',
                )
                return ''.join(summary)

    async def format_description_webdbs(self):
        parts = []

        async def append_line(webdb, id):
            url = await webdb.url(id)
            line = [f'[b]{webdb.label}[/b]: [url={url}]{id}[/url]']
            rating = await webdb.rating(id)
            if rating:
                rating_stars = ''.join((
                    '[color=#ffff00]',
                    string.star_rating(rating, max_rating=webdb.rating_max),
                    '[/color]',
                ))
                line.append(f'{rating}/{int(webdb.rating_max)} {rating_stars}')
            parts.append(' | '.join(line))

        imdb_id = await self.get_imdb_id()
        if imdb_id:
            await append_line(self.imdb, imdb_id)

        tvmaze_id = await self.get_tvmaze_id()
        if tvmaze_id:
            await append_line(self.tvmaze, tvmaze_id)

        return '\n'.join(parts)

    async def format_description_year(self):
        year = None
        try:
            if self.is_movie_release:
                imdb_id = await self.get_imdb_id()
                if imdb_id:
                    year = await self.imdb.year(imdb_id)

            elif self.is_series_release:
                tvmaze_id = await self.get_tvmaze_id()
                if tvmaze_id:
                    if self.season:
                        episode = await self.tvmaze.episode(id=tvmaze_id, season=self.season, episode=1)
                        if episode.get('date'):
                            year = episode['date'].split('-')[0]
                    if not year:
                        year = await self.tvmaze.year(tvmaze_id)
        except errors.RequestError:
            pass
        else:
            if year:
                return f'[b]Year[/b]: {year}'

    async def format_description_status(self):
        tvmaze_id = await self.get_tvmaze_id()
        if tvmaze_id:
            status = await self.tvmaze.status(tvmaze_id)
            if status == 'Ended':
                return f'[b]Status[/b]: {status}'

    async def format_description_countries(self):
        countries = await self.try_webdbs((self.tvmaze, self.imdb), 'countries', default=())
        if countries:
            return (f'[b]Countr{"ies" if len(countries) > 1 else "y"}[/b]: '
                    + ', '.join(countries))

    async def format_description_runtime(self):
        def format_runtime(minutes):
            if minutes > 60:
                hours = minutes // 60
                minutes = minutes - ((minutes // 60) * 60)
                if minutes:
                    return f'{hours}h{minutes}m'
                else:
                    return f'{hours}h'
            else:
                return f'{minutes}m'

        runtimes = await self.try_webdbs((self.imdb, self.tvmaze), 'runtimes', default=())
        if len(runtimes) == 1:
            runtime = tuple(runtimes.values())[0]
            return f'[b]Runtime[/b]: {format_runtime(runtime)}'
        elif len(runtimes) > 1:
            parts = []
            for cut, minutes in runtimes.items():
                part = f'{format_runtime(minutes)}'
                if cut != 'default':
                    part += f' ({cut})'
                parts.append(part)
            return f'[b]Runtimes[/b]: {", ".join(parts)}'

    @staticmethod
    def _format_person(person):
        if hasattr(person, 'url') and person.url:
            return f'[url={person.url}]{person}[/url]'
        else:
            return str(person)

    async def format_description_directors(self):
        directors = await self.try_webdbs((self.imdb, self.tvmaze), 'directors', default=())
        if directors:
            directors_links = [self._format_person(director) for director in directors]
            return (f'[b]Director{"s" if len(directors) > 1 else ""}[/b]: '
                    + ', '.join(directors_links))

    async def format_description_creators(self):
        creators = await self.try_webdbs((self.tvmaze, self.imdb), 'creators', default=())
        if creators:
            creators_links = [self._format_person(creator) for creator in creators]
            return (f'[b]Creator{"s" if len(creators) > 1 else ""}[/b]: '
                    + ', '.join(creators_links))

    async def format_description_cast(self):
        actors = await self.try_webdbs((self.tvmaze, self.imdb), 'cast')
        if actors:
            actors_links = [self._format_person(actor) for actor in actors]
            return ('[b]Cast[/b]: ' + ', '.join(actors_links))

    async def format_description_series_screenshots(self):
        await self.upload_screenshots_job.wait()
        screenshot_urls = self.get_job_output(self.upload_screenshots_job)
        screenshots_bbcode_parts = [
            f'[img={url}]'
            for url in screenshot_urls
        ]
        screenshots_bbcode = '\n\n'.join(screenshots_bbcode_parts)
        if screenshots_bbcode:
            return (
                '[quote]\n'
                f'[align=center]{screenshots_bbcode}[/align]\n'
                '[/quote]'
            )

    async def format_description_series_mediainfo(self):
        await self.mediainfo_job.wait()
        mediainfo = self.get_job_output(self.mediainfo_job, slice=0)
        if mediainfo:
            return f'[mediainfo]{mediainfo}[/mediainfo]'

    # Web form data

    @property
    def submission_ok(self):
        """
        `False` if :attr:`isolated_jobs` is truthy, parent implementation
        otherwise
        """
        if self.isolated_jobs:
            return False
        else:
            return super().submission_ok

    @property
    def torrent_filepath(self):
        return self.get_job_output(self.create_torrent_job, slice=0)

    @property
    def post_data(self):
        if self.is_movie_release:
            post_data = {
                'submit': 'true',
                'type': 'Movies',
                'title': self.get_job_output(self.movie_title_job, slice=0),
                'year': self.get_job_output(self.movie_year_job, slice=0),
                'source': self.get_job_attribute(self.movie_source_job, 'choice'),
                'videoformat': self.get_job_attribute(self.movie_video_codec_job, 'choice'),
                'audioformat': self.get_job_attribute(self.movie_audio_codec_job, 'choice'),
                'container': self.get_job_attribute(self.movie_container_job, 'choice'),
                'resolution': self.get_job_attribute(self.movie_resolution_job, 'choice'),
                'remaster_title': self.get_job_output(self.movie_release_info_job, slice=0),
                'tags': self.get_job_output(self.movie_tags_job, slice=0),
                'desc': self.post_data_description,
                'release_desc': self.get_job_output(self.mediainfo_job, slice=0),
                'image': self.get_job_output(self.movie_poster_job, slice=0),
            }
            post_data.update(self.post_data_screenshot_urls)
            if self.get_job_attribute(self.scene_check_job, 'is_scene_release'):
                post_data['scene'] = '1'
            return post_data

        elif self.is_series_release:
            post_data = {
                'submit': 'true',
                'type': 'Anime' if self.options['anime'] else 'TV',
                'title': self.get_job_output(self.series_title_job, slice=0),
                'tags': self.get_job_output(self.series_tags_job, slice=0),
                'desc': self.post_data_description,
                'image': self.get_job_output(self.series_poster_job, slice=0),
            }
            if self.get_job_attribute(self.scene_check_job, 'is_scene_release'):
                post_data['scene'] = '1'
            return post_data

        else:
            raise RuntimeError(f'Weird release type: {self.release_type!r}')

    @property
    def post_data_screenshot_urls(self):
        urls = self.get_job_output(self.upload_screenshots_job)
        return {f'screenshot{i}': url for i, url in enumerate(urls, start=1)}

    @property
    def post_data_description(self):
        parts = []

        if self.is_movie_release:
            # Screenshots and mediainfo are submitted separately
            parts.append(self.get_job_output(self.movie_description_job, slice=0))

        elif self.is_series_release:
            parts.append(self.get_job_output(self.series_description_job, slice=0))

        # Append self promotion below. A closing [/quote] tag automatically
        # renders a newline. Otherwise, we must add a newline character.
        if parts and not parts[-1].endswith(('[/quote]', '\n')):
            parts.append('\n')
        parts.append(self.promotion)

        return ''.join(parts)

    promotion = (
        '[align=right][size=1]Shared with '
        f'[url={__homepage__}]{__project_name__} {__version__}[/url]'
        '[/size][/align]'
    )
