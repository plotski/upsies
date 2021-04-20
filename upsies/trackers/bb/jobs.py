"""
:class:`~.base.TrackerJobsBase` subclass
"""

import asyncio
import os
import re

import unidecode

from ... import (__homepage__, __project_name__, __version__, constants,
                 errors, jobs)
from ...utils import (cached_property, fs, http, image, release, string,
                      timestamp, video, webdbs)
from ..base import TrackerJobsBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BbTrackerJobs(TrackerJobsBase):
    @cached_property
    def release_name(self):
        """:class:`~.release.ReleaseName` instance"""
        return release.ReleaseName(self.content_path)

    @property
    def is_movie_release(self):
        return self.release_type_job.choice is release.ReleaseType.movie

    @property
    def is_season_release(self):
        return self.release_type_job.choice is release.ReleaseType.season

    @property
    def is_episode_release(self):
        return self.release_type_job.choice is release.ReleaseType.episode

    @property
    def is_series_release(self):
        return self.release_type_job.choice in (release.ReleaseType.season,
                                                release.ReleaseType.episode)

    def condition_is_movie_release(self):
        return self.is_movie_release

    def condition_is_season_release(self):
        return self.is_season_release

    def condition_is_episode_release(self):
        return self.is_episode_release

    def condition_is_series_release(self):
        return self.is_series_release

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

    promotion = (
        '[align=right][size=1]Shared with '
        f'[url={__homepage__}]{__project_name__} {__version__}[/url]'
        '[/size][/align]'
    )

    # Web DBs

    @cached_property
    def imdb(self):
        """:class:`~.webdbs.imdb.ImdbApi` instance"""
        return webdbs.webdb('imdb')

    @cached_property
    def tvmaze(self):
        """:class:`~.webdbs.imdb.TvmazeApi` instance"""
        return webdbs.webdb('tvmaze')

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

    async def try_webdbs(self, webdbs, method):
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

    # Jobs

    _cli_jobs_map = {
        'movie_title': ('imdb_job', 'movie_title_job'),
        'series_title': ('tvmaze_job', 'series_title_job',),
    }

    @cached_property
    def user_jobs(self):
        """
        Jobs that are singled out by the user (e.g. via a CLI argument) or `None`

        No other jobs should be executed.
        """
        for argument, job_names in self._cli_jobs_map.items():
            if getattr(self.cli_args, argument, None):
                _log.debug('No submission because of argument: %r', argument)
                return [getattr(self, job_name) for job_name in job_names]

    @property
    def submission_ok(self):
        """`False` if any :attr:`user_jobs` are given"""
        if self.user_jobs:
            _log.debug('No submission because of CLI jobs: %r', [j.name for j in self.user_jobs])
            return False
        return super().submission_ok

    @property
    def jobs_after_upload(self):
        """`()` if any :attr:`user_jobs` are given"""
        if self.user_jobs:
            _log.debug('No jobs_after_upload because of CLI jobs: %r', [j.name for j in self.user_jobs])
            return ()
        return super().jobs_after_upload

    @cached_property
    def jobs_before_upload(self):
        # Return all possible jobs and disable/enable them on a condition based
        # on self.is_movie|series_release.
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

    @cached_property
    def release_type_job(self):
        return jobs.dialog.ChoiceJob(
            name='release-type',
            label='Release Type',
            choices=(
                ('Movie', release.ReleaseType.movie),
                ('Season', release.ReleaseType.season),
                ('Episode', release.ReleaseType.episode),
            ),
            focused=self.release_name.type,
            **self.common_job_args,
        )

    # Movie jobs

    @cached_property
    def imdb_job(self):
        """:class:`~.jobs.webdb.SearchWebDbJob` instance"""
        return jobs.webdb.SearchWebDbJob(
            condition=self.condition_is_movie_release,
            content_path=self.content_path,
            db=self.imdb,
            **self.common_job_args,
        )

    @cached_property
    def movie_title_job(self):
        self.imdb_job.signal.register('output', self.movie_title_imdb_id_handler)
        return jobs.dialog.TextFieldJob(
            name='movie-title',
            label='Title',
            condition=self.condition_is_movie_release,
            validator=self.movie_title_validator,
            **self.common_job_args,
        )

    def movie_title_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError(f'Invalid title: {text}')

    def movie_title_imdb_id_handler(self, imdb_id):
        default_text = self.release_name.title_with_aka
        coro = self.get_movie_title(imdb_id)
        task = self.movie_title_job.fetch_text(
            coro=coro,
            default_text=default_text,
            finish_on_success=False,
        )
        self.movie_title_job.add_task(task)

    @cached_property
    def movie_year_job(self):
        self.imdb_job.signal.register('output', self.movie_year_imdb_id_handler)
        return jobs.dialog.TextFieldJob(
            name='movie-year',
            label='Year',
            condition=self.condition_is_movie_release,
            text=self.release_name.year,
            validator=self.movie_year_validator,
            **self.common_job_args,
        )

    def movie_year_validator(self, text):
        # Raises ValueError if not a valid year
        self.release_name.year = text

    def movie_year_imdb_id_handler(self, imdb_id):
        default_text = self.release_name.year
        coro = self.imdb.year(imdb_id)
        task = self.movie_year_job.fetch_text(
            coro=coro,
            default_text=default_text,
            finish_on_success=True,
        )
        self.movie_year_job.add_task(task)

    @cached_property
    def movie_resolution_job(self):
        return self.make_choices_job(
            name='movie-resolution',
            label='Resolution',
            condition=self.condition_is_movie_release,
            autodetect_value=self.release_info_resolution,
            autofinish=True,
            options=(
                ('4320p', '2160p', re.compile(r'4320p')),
                ('2160p', '2160p', re.compile(r'2160p')),
                ('1080p', '1080p', re.compile(r'1080p')),
                ('1080i', '1080i', re.compile(r'1080i')),
                ('720p', '720p', re.compile(r'720p')),
                ('720i', '720i', re.compile(r'720i')),
                ('576p', '480p', re.compile(r'576p')),
                ('576i', '480i', re.compile(r'576i')),
                ('480p', '480p', re.compile(r'480p')),
                ('480i', '480i', re.compile(r'480i')),
                ('SD', 'SD', re.compile(r'SD')),
            ),
        )

    @cached_property
    def movie_source_job(self):
        return self.make_choices_job(
            name='movie-source',
            label='Source',
            condition=self.condition_is_movie_release,
            autodetect_value=self.release_name.source,
            autofinish=True,
            options=(
                ('BluRay', 'BluRay', re.compile('^BluRay')),  # BluRay or BluRay Remux
                # ('BluRay 3D', ' ', re.compile('^ $')),
                # ('BluRay RC', ' ', re.compile('^ $')),
                # ('CAM', ' ', re.compile('^ $')),
                ('DVD5', 'DVD5', re.compile('^DVD5$')),
                ('DVD9', 'DVD9', re.compile('^DVD9$')),
                ('DVDRip', 'DVDRip', re.compile('^DVDRip$')),
                # ('DVDSCR', ' ', re.compile('^ $')),
                ('HD-DVD', 'HD-DVD', re.compile('^HD-DVD$')),
                # ('HDRip', ' ', re.compile('^ $')),
                ('HDTV', 'HDTV', re.compile('^HDTV$')),
                # ('PDTV', ' ', re.compile('^ $')),
                # ('R5', ' ', re.compile('^ $')),
                # ('SDTV', ' ', re.compile('^ $')),
                # ('TC', ' ', re.compile('^ $')),
                # ('TeleSync', ' ', re.compile('^ $')),
                # ('VHSRip', ' ', re.compile('^ $')),
                # ('VODRip', ' ', re.compile('^ $')),
                ('WEB-DL', 'WEB-DL', re.compile('^WEB-DL$')),
                ('WEBRip', 'WebRip', re.compile('^WEBRip$')),
            ),
        )

    @cached_property
    def movie_audio_codec_job(self):
        return self.make_choices_job(
            name='movie-audio-codec',
            label='Audio Codec',
            condition=self.condition_is_movie_release,
            autodetect_value=self.release_info_audio_format,
            autofinish=True,
            options=(
                ('AAC', 'AAC', re.compile(r'^AAC$')),
                ('AC-3', 'AC-3', re.compile(r'^(?:E-|)AC-3$')),   # AC-3, E-AC-3
                ('DTS', 'DTS', re.compile(r'^DTS(?!-HD)')),       # DTS, DTS-ES
                ('DTS-HD', 'DTS-HD', re.compile(r'^DTS-HD\b')),   # DTS-HD, DTS-HD MA
                ('DTS:X', 'DTS:X', re.compile(r'^DTS:X$')),
                ('Dolby Atmos', 'Atmos', re.compile(r'Atmos')),
                ('FLAC', 'FLAC', re.compile(r'^FLAC$')),
                ('MP3', 'MP3', re.compile(r'^MP3$')),
                # ('PCM', 'PCM', re.compile(r'^$')),
                ('TrueHD', 'True-HD', re.compile(r'TrueHD')),
                ('Vorbis', 'Vorbis', re.compile(r'^Vorbis$')),
            ),
        )

    @cached_property
    def movie_video_codec_job(self):
        return self.make_choices_job(
            name='movie-video-codec',
            label='Video Codec',
            condition=self.condition_is_movie_release,
            autodetect_value=self.release_name.video_format,
            autofinish=True,
            options=(
                ('x264', 'x264', re.compile(r'x264')),
                ('x265', 'x265', re.compile(r'x265')),
                ('XviD', 'XVid', re.compile(r'(?i:XviD)')),
                # ('MPEG-2', 'MPEG-2', re.compile(r'')),
                # ('WMV-HD', 'WMV-HD', re.compile(r'')),
                # ('DivX', 'DivX', re.compile(r'')),
                ('H.264', 'H.264', re.compile(r'H.264')),
                ('H.265', 'H.265', re.compile(r'H.265')),
                # ('VC-1', 'VC-1', re.compile(r'')),
            ),
        )

    @cached_property
    def movie_container_job(self):
        return self.make_choices_job(
            name='movie-container',
            label='Container',
            condition=self.condition_is_movie_release,
            autodetect_value=fs.file_extension(video.first_video(self.content_path)),
            autofinish=True,
            options=(
                ('AVI', 'AVI', re.compile(r'(?i:AVI)')),
                ('MKV', 'MKV', re.compile('(?i:MKV)')),
                ('MP4', 'MP4', re.compile(r'(?i:MP4)')),
                ('TS', 'TS', re.compile(r'(?i:TS)')),
                ('VOB', 'VOB', re.compile(r'(?i:VOB)')),
                ('WMV', 'WMV', re.compile(r'(?i:WMV)')),
                ('m2ts', 'm2ts', re.compile(r'(?i:m2ts)')),
            ),
        )

    @cached_property
    def movie_release_info_job(self):
        return jobs.dialog.TextFieldJob(
            name='movie-release-info',
            label='Release Info',
            condition=self.condition_is_movie_release,
            text=self.get_movie_release_info(),
            **self.common_job_args,
        )

    @cached_property
    def movie_poster_job(self):
        """Re-upload poster from IMDb to :attr:`~.TrackerJobsBase.image_host`"""
        return jobs.custom.CustomJob(
            name='movie-poster',
            label='Poster',
            condition=self.condition_is_movie_release,
            worker=self.movie_get_poster_url,
            **self.common_job_args,
        )

    async def movie_get_poster_url(self, poster_job):
        return await self.get_poster_url(poster_job, self.get_movie_poster_url)

    @cached_property
    def movie_tags_job(self):
        self.imdb_job.signal.register('output', self.movie_tags_imdb_id_handler)
        return jobs.dialog.TextFieldJob(
            name='movie-tags',
            label='Tags',
            condition=self.condition_is_movie_release,
            validator=self.movie_tags_validator,
            **self.common_job_args,
        )

    def movie_tags_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError(f'Invalid tags: {text}')

    def movie_tags_imdb_id_handler(self, imdb_id):
        coro = self.get_tags(self.imdb, imdb_id)
        task = self.movie_tags_job.fetch_text(
            coro=coro,
            finish_on_success=True,
        )
        self.movie_tags_job.add_task(task)

    @cached_property
    def movie_description_job(self):
        self.imdb_job.signal.register('output', self.movie_description_imdb_id_handler)
        return jobs.dialog.TextFieldJob(
            name='movie-description',
            label='Description',
            condition=self.condition_is_movie_release,
            validator=self.movie_description_validator,
            **self.common_job_args,
        )

    def movie_description_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError(f'Invalid description: {text}')

    def movie_description_imdb_id_handler(self, imdb_id):
        coro = self.get_description(self.imdb, imdb_id)
        task = self.movie_description_job.fetch_text(
            coro=coro,
            finish_on_success=True,
        )
        self.movie_description_job.add_task(task)

    # Series jobs

    @cached_property
    def tvmaze_job(self):
        """:class:`~.jobs.webdb.SearchWebDbJob` instance"""
        return jobs.webdb.SearchWebDbJob(
            condition=self.condition_is_series_release,
            content_path=self.content_path,
            db=self.tvmaze,
            **self.common_job_args,
        )

    @cached_property
    def series_title_job(self):
        self.tvmaze_job.signal.register('output', self.series_title_tvmaze_id_handler)
        return jobs.dialog.TextFieldJob(
            name='series-title',
            label='Title',
            condition=self.condition_is_series_release,
            validator=self.series_title_validator,
            **self.common_job_args,
        )

    def series_title_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError(f'Invalid title: {text}')
        unknown = ', '.join(u.lower() for u in re.findall(r'UNKNOWN_([A-Z_]+)', text))
        if unknown:
            raise ValueError(f'Failed to autodetect: {unknown}')

    def series_title_tvmaze_id_handler(self, tvmaze_id):
        coro = self.get_series_title_and_release_info(tvmaze_id)
        default_text = self.release_name.title_with_aka_and_year
        task = self.series_title_job.fetch_text(
            coro=coro,
            default_text=default_text,
            finish_on_success=False,
        )
        self.series_title_job.add_task(task)

    @cached_property
    def series_poster_job(self):
        """Re-upload poster from TVmaze to :attr:`~.TrackerJobsBase.image_host`"""
        return jobs.custom.CustomJob(
            name='series-poster',
            label='Poster',
            condition=self.condition_is_series_release,
            worker=self.series_get_poster_url,
            **self.common_job_args,
        )

    async def series_get_poster_url(self, poster_job):
        return await self.get_poster_url(poster_job, self.get_series_poster_url)

    @cached_property
    def series_tags_job(self):
        self.tvmaze_job.signal.register('output', self.series_tags_tvmaze_id_handler)
        return jobs.dialog.TextFieldJob(
            name='series-tags',
            label='Tags',
            condition=self.condition_is_series_release,
            validator=self.series_tags_validator,
            **self.common_job_args,
        )

    def series_tags_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError(f'Invalid tags: {text}')

    def series_tags_tvmaze_id_handler(self, tvmaze_id):
        coro = self.get_tags(self.tvmaze, tvmaze_id)
        task = self.series_tags_job.fetch_text(
            coro=coro,
            finish_on_success=True,
        )
        self.series_tags_job.add_task(task)

    @cached_property
    def series_description_job(self):
        self.tvmaze_job.signal.register('output', self.series_description_tvmaze_id_handler)
        return jobs.dialog.TextFieldJob(
            name='series-description',
            label='Description',
            condition=self.condition_is_series_release,
            validator=self.series_description_validator,
            **self.common_job_args,
        )

    def series_description_validator(self, text):
        text = text.strip()
        if not text:
            raise ValueError(f'Invalid description: {text}')

    def series_description_tvmaze_id_handler(self, tvmaze_id):
        coro = self.get_description(self.tvmaze, tvmaze_id)
        task = self.series_description_job.fetch_text(
            coro=coro,
            finish_on_success=True,
        )
        self.series_description_job.add_task(task)

    # Release Info

    @property
    def release_info_subtitles(self):
        subtitle_tracks = video.tracks(self.content_path).get('Text', ())
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
            return self.release_name.source

    @property
    def release_info_remux(self):
        if 'Remux' in self.release_name.source:
            return 'REMUX'

    @property
    def release_info_resolution(self):
        # Move/TV Rule 3.6.1 - Encodes with a stored resolution less than 700px
        #                      AND a height less than 460px should be labelled
        #                      "SD"
        if video.width(self.content_path) < 700 and video.height(self.content_path) < 460:
            return 'SD'

        # Movie Rule 3.6.2 - 576p PAL encodes with a stored resolution of at
        #                    least 700px wide and/or 560px tall should be
        #                    labelled "480p" with "576p PAL" noted in the
        #                    Release Info field
        # We also apply this to series releases by using this property in
        # get_series_title_and_release_info().
        if self.release_name.resolution == '576p' and video.frame_rate(self.content_path) == 25:
            return '576p PAL'

        return self.release_name.resolution

    @property
    def release_info_proper(self):
        if 'Proper' in self.release_name.edition:
            return 'PROPER'

    @property
    def release_info_hdr10(self):
        if video.is_hdr10(self.content_path):
            return 'HDR10'

    @property
    def release_info_10bit(self):
        if video.bit_depth(self.content_path) == '10' and not self.release_info_hdr10:
            return '10-bit'

    @property
    def release_info_dual_audio(self):
        if video.has_dual_audio(self.content_path):
            return 'Dual Audio'

    @property
    def release_info_audio_format(self):
        audio_format = self.release_name.audio_format
        # "E-AC-3 Atmos" and "TrueHD Atmos" -> "Atmos"
        if 'Atmos' in audio_format:
            return 'Atmos'
        return audio_format

    # Metadata generators

    async def get_movie_title(self, imdb_id):
        await self.release_name.fetch_info(imdb_id)
        return self.release_name.title_with_aka

    async def get_series_title_and_release_info(self, tvmaze_id):
        imdb_id = await self.tvmaze.imdb_id(tvmaze_id)
        if imdb_id:
            await self.release_name.fetch_info(imdb_id)

        title = [self.release_name.title_with_aka]
        if self.release_name.year_required:
            title.append(f'({self.release_name.year})')

        # "Season x"
        if self.is_season_release:
            title.append(f'- Season {self.season or "UNKNOWN_SEASON"}')

        # "SxxEyy"
        elif self.is_episode_release:
            title.append(str(self.release_name.episodes))

        # "[Source / VideoCodec / AudioCodec / Container / Resolution( / ...)]"
        info = [
            self.release_info_remux,
            self.release_info_source,
            self.release_name.video_format,
            self.release_info_10bit,
            self.release_info_audio_format,
            fs.file_extension(video.first_video(self.content_path)).upper(),
            self.release_info_proper,
            self.release_info_resolution,
            self.release_info_hdr10,
            self.release_info_dual_audio,
            self.release_info_commentary,
            self.release_info_subtitles,
        ]
        info_string = ' / '.join(i for i in info if i)
        return ' '.join(title) + f' [{info_string}]'

    async def get_poster_url(self, poster_job, poster_url_getter):
        # Get original poster URL (e.g. "http://imdb.com/...jpg")
        poster_job.info = 'Waiting for ID'
        poster_url = await poster_url_getter()
        if not poster_url:
            self.error('Failed to find poster')
        else:
            poster_job.info = f'Downloading poster: {poster_url}'
            poster_path = os.path.join(poster_job.home_directory, 'poster.bb.jpg')
            try:
                await http.download(poster_url, poster_path)
            except errors.RequestError as e:
                self.error(f'Poster download failed: {e}')
            else:
                if not os.path.exists(poster_path) or not os.path.getsize(poster_path) > 0:
                    self.error(f'Poster download failed: {poster_url}')
                else:
                    # Resize poster
                    try:
                        resized_poster_path = image.resize(poster_path, width=300)
                    except errors.ImageResizeError as e:
                        self.error(f'Poster resizing failed: {e}')
                    else:
                        _log.debug('Poster resized: %r', resized_poster_path)
                        # Upload poster to self.image_host
                        poster_job.info = f'Uploading poster to {self.image_host.name}'
                        try:
                            real_poster_url = await self.image_host.upload(resized_poster_path)
                        except errors.RequestError as e:
                            self.error(f'Poster upload failed: {e}')
                        else:
                            poster_job.info = ''
                            poster_job.send(real_poster_url)

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

    async def get_tags(self, webdb, id):
        def normalize_tags(strings):
            normalized = []
            for s in strings:
                s = (
                    s
                    .lower()
                    .replace(' ', '.')
                    .replace('-', '.')
                    .replace('\'', '.')
                )
                s = re.sub(r'\.+', '.', s)  # Dedup "."
                s = unidecode.unidecode(s)  # Replace non-ASCII
                normalized.append(s)
            return normalized

        def assemble(*sequences):
            return ','.join(
                item
                for seq in sequences
                for item in seq
            )

        # Gather tags
        tags = list(await webdb.keywords(id))
        if self.is_movie_release:
            tags.extend(await webdb.directors(id))
        elif self.is_series_release:
            tags.extend(await webdb.creators(id))
        tags.extend(await webdb.cast(id))

        # Replace spaces, non-ASCII characters, etc
        tags = normalize_tags(tags)

        # Maximum length of concatenated tags is 200 characters
        tags_string = assemble(tags)
        while len(tags_string) > 200:
            del tags[-1]
            tags_string = assemble(tags)

        return tags_string

    def get_movie_release_info(self):
        info = []

        # Rule 3.6.2 - 576p PAL encodes with a stored resolution of at least
        #              700px wide and/or 560px tall should be labelled "480p"
        #              with "576p PAL" noted in the Release Info field
        if self.release_info_resolution == '576p PAL':
            info.append(self.release_info_resolution)

        info.extend((
            self.release_info_remux,
            self.release_info_proper,
        ))

        for name in fs.file_and_parent(self.content_path):
            match = re.search(r'[ \.](\d+)th[ \.]Anniversary[ \.]', name)
            if match:
                info.append(f'{match.group(1)}th Anniversary Edition')

            if re.search(r'[ \.](?i:4k[ \.]REMASTER)', name):
                info.append('4k Remaster')
            elif re.search(r'[ \.](?i:remastered)[ \.]', name):
                info.append('Remastered')

        for ed, ed_ in (('DC', "Director's Cut"),
                        ('Extended', 'Extended Edition'),
                        ('Uncensored', 'Uncut'),
                        ('Uncut', 'Uncut'),
                        ('Unrated', 'Unrated'),
                        ('Criterion', 'Criterion Collection'),
                        ('Special', 'Special Edition'),
                        ('Limited', 'Limited')):
            if ed in self.release_name.edition:
                info.append(ed_)

        info.extend((
            self.release_info_dual_audio,
            self.release_info_hdr10,
            self.release_info_10bit,
            self.release_info_commentary,
            self.release_info_subtitles,
        ))

        return ' / '.join(i for i in info if i)

    async def get_description(self, webdb, id):
        info_table = await asyncio.gather(
            self.format_description_webdbs(),
            self.format_description_year(),
            self.format_description_status(),
            self.format_description_countries(),
            self.format_description_runtime(),
            self.format_description_directors(),
            self.format_description_creators(),
            self.format_description_cast(),
        )
        info_table_string = '\n'.join(str(item) for item in info_table
                                      if item is not None)
        parts = [
            await self.format_description_summary() or '',
            f'[quote]{info_table_string}[/quote]',
        ]

        if self.is_series_release:
            parts.append(await self.format_description_series_screenshots())
            parts.append(await self.format_description_series_mediainfo())

        parts.append(self.promotion)
        return ''.join(parts)

    async def format_description_summary(self):
        summary = await self.try_webdbs((self.tvmaze, self.imdb), 'summary')
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
                else:
                    year = await self.tvmaze.year(tvmaze_id)

        if year:
            return f'[b]Year[/b]: {year}'

    async def format_description_status(self):
        tvmaze_id = await self.get_tvmaze_id()
        if tvmaze_id:
            status = await self.tvmaze.status(tvmaze_id)
            if status == 'Ended':
                return f'[b]Status[/b]: {status}'

    async def format_description_countries(self):
        countries = await self.try_webdbs((self.tvmaze, self.imdb), 'countries')
        if countries:
            return (f'[b]Countr{"ies" if len(countries) > 1 else "y"}[/b]: '
                    + ', '.join(countries))

    async def format_description_runtime(self):
        if self.is_movie_release or self.is_episode_release:
            runtime = video.duration(self.content_path)
        elif self.is_season_release:
            # Return average runtime
            filepaths = fs.file_list(
                self.content_path,
                extensions=constants.VIDEO_FILE_EXTENSIONS,
            )
            if len(filepaths) >= 5:
                # Ignore first and last episode as they are often longer
                filepaths = filepaths[1:-1]
            runtime = sum(video.duration(f) for f in filepaths) / len(filepaths)
        else:
            return None
        return f'[b]Runtime[/b]: {timestamp.pretty(runtime)}'

    async def format_description_directors(self):
        directors = await self.try_webdbs((self.imdb, self.tvmaze), 'directors')
        if directors:
            directors_links = [
                f'[url={director.url}]{director}[/url]' if director.url else director
                for director in directors
            ]
            return (f'[b]Director{"s" if len(directors) > 1 else ""}[/b]: '
                    + ', '.join(directors_links))

    async def format_description_creators(self):
        creators = await self.try_webdbs((self.tvmaze, self.imdb), 'creators')
        if creators:
            creators_links = [
                f'[url={creator.url}]{creator}[/url]' if creator.url else creator
                for creator in creators
            ]
            return (f'[b]Creator{"s" if len(creators) > 1 else ""}[/b]: '
                    + ', '.join(creators_links))

    async def format_description_cast(self):
        actors = await self.try_webdbs((self.tvmaze, self.imdb), 'cast')
        if actors:
            actors_links = [
                f'[url={actor.url}]{actor}[/url]' if actor.url else actor
                for actor in actors
            ]
            return (f'[b]Actor{"s" if len(actors) > 1 else ""}[/b]: '
                    + ', '.join(actors_links))

    async def format_description_series_screenshots(self):
        screenshots_bbcode_parts = []  # Spacer
        await self.upload_screenshots_job.wait()
        screenshot_urls = self.get_job_output(self.upload_screenshots_job)
        for url in screenshot_urls:
            screenshots_bbcode_parts.append(f'[img={url}]')
        screenshots_bbcode = '\n\n'.join(screenshots_bbcode_parts)
        return (
            '[quote]\n'
            f'[align=center]{screenshots_bbcode}[/align]\n'
            '[/quote]'
        )

    async def format_description_series_mediainfo(self):
        await self.mediainfo_job.wait()
        mediainfo = self.get_job_output(self.mediainfo_job, slice=0)
        return f'[mediainfo]{mediainfo}[/mediainfo]\n'

    # Web form data

    def get_job_output(self, job, slice=slice(None, None)):
        if not job.is_finished:
            raise RuntimeError(f'Unfinished job: {job.name}')
        try:
            return job.output[slice]
        except IndexError:
            raise RuntimeError(f'Job finished with insufficient output: {job.name}: {job.output}')

    def get_job_attribute(self, job, attribute):
        if not job.is_finished:
            raise RuntimeError(f'Unfinished job: {job.name}')
        else:
            return getattr(job, attribute)

    @property
    def torrent_filepath(self):
        return self.get_job_output(self.create_torrent_job, slice=0)

    @property
    def post_data(self):
        _log.debug('Is scene release: %r', self.scene_check_job.is_scene_release)
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
                'desc': self.get_job_output(self.movie_description_job, slice=0),
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
                'type': 'TV',
                'title': self.get_job_output(self.series_title_job, slice=0),
                'tags': self.get_job_output(self.series_tags_job, slice=0),
                'desc': self.get_job_output(self.series_description_job, slice=0),
                'image': self.get_job_output(self.series_poster_job, slice=0),
            }
            if self.scene_check_job.is_scene_release:
                post_data['scene'] = '1'
            return post_data

        else:
            raise RuntimeError(f'Weird release type: {self.release_type_job.choice}')

    @property
    def post_data_screenshot_urls(self):
        urls = self.get_job_output(self.upload_screenshots_job)
        return {f'screenshot{i}': url for i, url in enumerate(urls, start=1)}

    # Other stuff

    def make_choices_job(self, name, label, autodetect_value, options,
                         condition=None, autofinish=False):
        """
        Return :class:`~.jobs.dialog.ChoiceJob` instance

        :param name: See :class:`~.jobs.dialog.ChoiceJob`
        :param label: See :class:`~.jobs.dialog.ChoiceJob`
        :param autodetect_value: Autodetected choice
        :param options: Sequence of `(label, value, regex)` tuples. `label` is
            presented to the user and `value` is available via
            :attr:`~.jobs.dialog.ChoiceJob.choice` when this job is
            finished. The first `regex` that matches `autodetect_value` is
            visually marked as "autodetected" for the user.
        :param condition: See ``condition`` for :class:`~.base.JobBase`
        :param bool autofinish: Whether to choose the autodetected value with no
            user-interaction
        """
        focused = None
        choices = []
        for text, value, regex in options:
            if not focused and regex.search(autodetect_value):
                choices.append((f'{text} (autodetected)', value))
                focused = choices[-1]
                autofinish = autofinish and True
            else:
                choices.append((text, value))

        job = jobs.dialog.ChoiceJob(
            name=name,
            label=label,
            condition=condition,
            choices=choices,
            focused=focused,
            **self.common_job_args,
        )
        if autofinish and focused:
            job.choice = focused
        return job
