"""
:class:`~.base.TrackerJobsBase` subclass
"""

import os
import re

import unidecode

from ... import __homepage__, __project_name__, __version__, jobs
from ...utils import (cached_property, fs, http, release, string, timestamp,
                      video, webdbs)
from ..base import TrackerJobsBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class BbTrackerJobs(TrackerJobsBase):
    # Web DBs

    @cached_property
    def imdb(self):
        """:class:`~.webdbs.imdb.ImdbApi` instance"""
        return webdbs.webdb('imdb')

    @cached_property
    def tvmaze(self):
        """:class:`~.webdbs.imdb.TvmazeApi` instance"""
        return webdbs.webdb('tvmaze')

    @cached_property
    def release_name(self):
        """:class:`~.release.ReleaseName` instance"""
        return release.ReleaseName(self.content_path)

    @property
    def is_movie_release(self):
        return self.release_type_job.choice is release.ReleaseType.movie

    @property
    def is_series_release(self):
        return self.release_type_job.choice in (release.ReleaseType.series,
                                                release.ReleaseType.episode)

    # Generic jobs

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
            condition=lambda: self.is_movie_release,
            content_path=self.content_path,
            db=self.imdb,
            **self.common_job_args,
        )

    @cached_property
    def movie_title_job(self):
        def validator(text):
            text = text.strip()
            if not text:
                raise ValueError(f'Invalid title: {text}')

        def handle_imdb_id(imdb_id):
            self.movie_title_job.add_task(
                self.movie_title_job.fetch_text(
                    coro=self.get_title(imdb_id),
                    default_text=self.release_name.title_with_aka,
                    finish_on_success=False,
                )
            )

        self.imdb_job.signal.register('output', handle_imdb_id)

        return jobs.dialog.TextFieldJob(
            name='movie-title',
            label='Title',
            condition=lambda: self.is_movie_release,
            validator=validator,
            **self.common_job_args,
        )

    @cached_property
    def movie_year_job(self):
        def validator(text):
            # Raises ValueError if not a valid year
            self.release_name.year = text

        def handle_imdb_id(imdb_id):
            self.movie_year_job.add_task(
                self.movie_year_job.fetch_text(
                    coro=self.get_year(imdb_id),
                    default_text=self.release_name.year,
                    finish_on_success=True,
                )
            )

        self.imdb_job.signal.register('output', handle_imdb_id)

        return jobs.dialog.TextFieldJob(
            name='movie-year',
            label='Year',
            condition=lambda: self.is_movie_release,
            text=self.release_name.year,
            validator=validator,
            **self.common_job_args,
        )

    @cached_property
    def movie_resolution_job(self):
        return self.make_choices_job(
            name='movie-resolution',
            label='Resolution',
            condition=lambda: self.is_movie_release,
            autodetect_value=self.release_name.resolution,
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
                ('SD', 'SD', re.compile(r'')),
            ),
        )

    @cached_property
    def movie_source_job(self):
        _log.debug('source: %r', self.release_name.source)
        return self.make_choices_job(
            name='movie-source',
            label='Source',
            condition=lambda: self.is_movie_release,
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
            condition=lambda: self.is_movie_release,
            autodetect_value=self.release_name.audio_format,
            autofinish=True,
            options=(
                ('AAC', 'AAC', re.compile(r'^AAC$')),
                ('AC-3', 'AC-3', re.compile(r'^DD\+?$')),                   # DD, DD+, not DD+ Atmos
                ('DTS', 'DTS', re.compile(r'^DTS(?!-HD)')),                 # DTS, DTS-ES
                ('DTS-HD', 'DTS-HD', re.compile(r'^DTS-HD\b')),             # DTS-HD, DTS-HD MA
                ('DTS:X', 'DTS:X', re.compile(r'^DTS:X$')),
                ('Dolby Atmos', 'Dolby Atmos', re.compile(r'^DD\+ Atmos')),
                ('FLAC', 'FLAC', re.compile(r'^FLAC$')),
                ('MP3', 'MP3', re.compile(r'^MP3$')),
                # ('PCM', 'PCM', re.compile(r'^$')),
                ('TrueHD', 'True-HD', re.compile(r'TrueHD')),               # TrueHD, TrueHD Atmos
                ('Vorbis', 'Vorbis', re.compile(r'^Vorbis$')),
            ),
        )

    @cached_property
    def movie_video_codec_job(self):
        return self.make_choices_job(
            name='movie-video-codec',
            label='Video Codec',
            condition=lambda: self.is_movie_release,
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
            condition=lambda: self.is_movie_release,
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
            condition=lambda: self.is_movie_release,
            text=self.get_movie_release_info(),
            **self.common_job_args,
        )

    @cached_property
    def movie_poster_job(self):
        """Re-upload poster from IMDb to :attr:`~.TrackerJobsBase.image_host`"""
        async def get_poster(poster_job):
            return await self.get_poster_url(poster_job, self.get_movie_poster_url)

        return jobs.custom.CustomJob(
            name='movie-poster',
            label='Poster',
            condition=lambda: self.is_movie_release,
            worker=get_poster,
            **self.common_job_args,
        )

    @cached_property
    def movie_tags_job(self):
        def validator(text):
            text = text.strip()
            if not text:
                raise ValueError(f'Invalid tags: {text}')

        def handle_imdb_id(id):
            self.movie_tags_job.add_task(
                self.movie_tags_job.fetch_text(
                    coro=self.get_movie_tags(id),
                    finish_on_success=True,
                )
            )

        self.imdb_job.signal.register('output', handle_imdb_id)

        return jobs.dialog.TextFieldJob(
            name='movie-tags',
            label='Tags',
            condition=lambda: self.is_movie_release,
            validator=validator,
            **self.common_job_args,
        )
    @cached_property
    def movie_description_job(self):
        def validator(text):
            text = text.strip()
            if not text:
                raise ValueError(f'Invalid description: {text}')

        def handle_imdb_id(id):
            self.movie_description_job.add_task(
                self.movie_description_job.fetch_text(
                    coro=self.get_movie_description(id),
                    finish_on_success=True,
                )
            )

        self.imdb_job.signal.register('output', handle_imdb_id)

        return jobs.dialog.TextFieldJob(
            name='movie-description',
            label='Description',
            condition=lambda: self.is_movie_release,
            validator=validator,
            **self.common_job_args,
        )

    # Metadata generators

    async def get_title(self, imdb_id):
        await self.release_name.fetch_info(imdb_id)
        return self.release_name.title_with_aka

    async def get_year(self, imdb_id):
        await self.release_name.fetch_info(imdb_id)
        return self.release_name.year

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
                self.error('Poster download failed: {e}')
            else:
                if not os.path.exists(poster_path) or not os.path.getsize(poster_path) > 0:
                    self.error('Poster download failed: {poster_url}')
                else:
                    # Upload poster to self.image_host
                    poster_job.info = f'Uploading poster to {self.image_host.name}'
                    real_poster_url = await self.image_host.upload(poster_path)
                    poster_job.info = ''
                    poster_job.send(real_poster_url)

    async def get_movie_poster_url(self):
        await self.imdb_job.wait()
        imdb_id = self.imdb_job.output[0]
        poster_url = await self.imdb.poster_url(imdb_id)
        _log.debug('Poster URL for %r: %r', imdb_id, poster_url)
        return poster_url

    async def get_series_poster_url(self):
        await self.tvmaze_job.wait()
        tvmaze_id = self.tvmaze_job.output[0]
        poster_url = await self.tvmaze.poster_url(tvmaze_id)
        _log.debug('Poster URL for %r: %r', tvmaze_id, poster_url)
        return poster_url

    async def get_movie_tags(self, id):
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

        genres = await self.imdb.keywords(id)
        directors = await self.imdb.directors(id)
        cast = await self.imdb.cast(id)
        tags = sum((
            normalize_tags(genres),
            normalize_tags(directors),
            normalize_tags(cast),
        ), start=[])

        # Maximum length of concatenated tags is 200 characters
        tags_string = assemble(tags)
        while len(tags_string) > 200:
            del tags[-1]
            tags_string = assemble(tags)

        return tags_string

    def get_movie_release_info(self):
        info = []

        if 'Remux' in self.release_name.source:
            info.append('REMUX')

        if 'Proper' in self.release_name.edition:
            info.append('Proper')

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

        if video.has_dual_audio(self.content_path):
            info.append('Dual Audio')

        if video.has_hdr10(self.content_path):
            info.append('HDR10')
        elif video.bit_depth(self.content_path) == '10':
            info.append('10-bit')

        if self.release_name.has_commentary:
            info.append('Commentary')

        subtitle_tracks = video.tracks(self.content_path).get('Text', ())
        if subtitle_tracks:
            subtitle_languages = [track.get('Language') for track in subtitle_tracks]
            if 'en' in subtitle_languages:
                info.append('Subtitles')

        return ' / '.join(info)

    async def get_movie_description(self, id):
        info = await self.imdb.gather(id, 'cast', 'countries', 'directors',
                                      'rating', 'summary', 'url', 'year')
        _log.debug('info: %r', info)
        lines = ['[b]IMDb[/b]: [url={url}]{id}[/url]'.format(**info)]

        # Rating
        if info['rating'] is not None:
            info['rating_stars'] = ''.join((
                '[color=#ffff00]',
                string.star_rating(info['rating']),
                '[/color]',
            ))
            lines.append('[b]Rating[/b]: {rating}/10 {rating_stars}'.format(**info))

        # Main info
        if info['countries']:
            countries = ', '.join(info['countries'])
            if len(info['countries']) == 1:
                lines.append(f'[b]Country[/b]: {countries}')
            elif len(info['countries']) >= 2:
                lines.append(f'[b]Countries[/b]: {countries}')

        lines.append(f'[b]Runtime[/b]: {timestamp.pretty(video.duration(self.content_path))}')

        # Director(s)
        if info['directors']:
            directors = [f'[url={director.url}]{director}[/url]'
                         for director in info['directors']]
            lines.append(f'[b]Direcor{"s" if len(directors) > 1 else ""}[/b]: '
                         f'{", ".join(directors)}')

        # Actors
        if info['cast']:
            actors = [f'[url={actor.url}]{actor}[/url]'
                      for actor in info['cast'][:10]]
            lines.append(f'[b]Cast[/b]: {", ".join(actors)}')

        # Link to project
        promotion = (
            '[align=right][size=1]Shared with '
            f'[url={__homepage__}]{__project_name__} {__version__}[/url]'
            '[/size][/align]'
        )

        return ''.join((
            '[quote]{summary}[/quote]'.format(**info),
            '[quote]' + '\n'.join(lines) + '[/quote]',
            promotion,
        ))

    # Web form data

    @property
    def torrent_filepath(self):
        if self.create_torrent_job.output:
            return self.create_torrent_job.output[0]
        else:
            raise RuntimeError('Torrent is not ready yet')

    @property
    def post_data(self):
        if self.is_movie_release:
            post_data = {
                'submit': 'true',
                'type': 'Movies',
                'title': self.movie_title_job.output[0],
                'year': self.movie_year_job.output[0],
                'source': self.movie_source_job.choice,
                'videoformat': self.movie_video_codec_job.choice,
                'audioformat': self.movie_audio_codec_job.choice,
                'container': self.movie_container_job.choice,
                'resolution': self.movie_resolution_job.choice,
                'remaster_title': self.movie_release_info_job.output[0],
                'tags': self.movie_tags_job.output[0],
                'desc': self.movie_description_job.output[0],
                'release_desc': self.mediainfo_job.output[0],
                'image': self.movie_poster_job.output[0],
            }
            post_data.update(self.post_data_screenshot_urls)
            if self.scene_check_job.is_scene_release:
                post_data['scene'] = '1'
            return post_data

        elif self.is_series_release:
            self.error('TV series are not supported yet.')
        else:
            raise RuntimeError(f'Weird release type: {self.release_type_job.choice}')

    @property
    def post_data_screenshot_urls(self):
        urls = self.upload_screenshots_job.output
        if not urls:
            raise RuntimeError('Screeenshots not uploaded yet')
        else:
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
            visually marked as "auto-detected" for the user.
        :param condition: See ``condition`` for :class:`~.base.JobBase`
        :param bool autofinish: Whether to choose the autodetected value with no
            user-interaction
        """
        focused = None
        choices = []
        for text, value, regex in options:
            if not focused and regex.search(autodetect_value):
                choices.append((f'{text} (auto-detected)', value))
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
