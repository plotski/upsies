"""
:class:`~.base.TrackerJobsBase` subclass for movie submissions
"""

import re

import unidecode

from ... import jobs
from ...utils import cached_property, fs, video
from .base import BbTrackerJobsBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class MovieBbTrackerJobs(BbTrackerJobsBase):
    @cached_property
    def jobs_before_upload(self):
        return (
            self.imdb_job,
            self.title_job,
            self.year_job,
            self.resolution_job,
            self.source_job,
            self.audio_codec_job,
            self.video_codec_job,
            self.container_job,
            self.release_info_job,
            self.tags_job,
            self.description_job,
            # self.create_torrent_job,
            # self.screenshots_job,
        )

    @cached_property
    def title_job(self):
        def validator(text):
            text = text.strip()
            if not text:
                raise ValueError(f'Invalid title: {text}')

        return jobs.dialog.TextFieldJob(
            name='movie-title',
            label='Title',
            validator=validator,
            **self.common_job_args,
        )

    async def generate_title(self, id):
        await self.release_name.fetch_info(id)
        return self.release_name.title_with_aka

    @cached_property
    def year_job(self):
        def validator(text):
            # Raises ValueError if not a valid year
            self.release_name.year = text

        return jobs.dialog.TextFieldJob(
            name='movie-year',
            label='Year',
            text=self.release_name.year,
            validator=validator,
            **self.common_job_args,
        )

    async def generate_year(self, id):
        await self.release_name.fetch_info(id)
        return self.release_name.year

    @cached_property
    def resolution_job(self):
        return self.make_choices_job(
            name='movie-resolution',
            label='Resolution',
            autodetect_value=self.release_name.resolution,
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
    def source_job(self):
        _log.debug('source: %r', self.release_name.source)
        return self.make_choices_job(
            name='movie-source',
            label='Source',
            autodetect_value=self.release_name.source,
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
    def audio_codec_job(self):
        return self.make_choices_job(
            name='movie-audio-codec',
            label='Audio Codec',
            autodetect_value=self.release_name.audio_format,
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
    def video_codec_job(self):
        return self.make_choices_job(
            name='movie-video-codec',
            label='Video Codec',
            autodetect_value=self.release_name.video_format,
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
    def container_job(self):
        return self.make_choices_job(
            name='movie-container',
            label='Container',
            autodetect_value=fs.file_extension(video.first_video(self.content_path)),
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
    def release_info_job(self):
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

        return jobs.dialog.TextFieldJob(
            name='movie-release-info',
            label='Release Info',
            text=' / '.join(info),
            **self.common_job_args,
        )

    @cached_property
    def tags_job(self):
        def validator(text):
            text = text.strip()
            if not text:
                raise ValueError(f'Invalid tags: {text}')

        return jobs.dialog.TextFieldJob(
            name='movie-tags',
            label='Tags',
            validator=validator,
            **self.common_job_args,
        )

    async def generate_tags(self, id):
        def normalize_tags(strings):
            normalized = []
            for string in strings:
                string = (
                    string
                    .lower()
                    .replace(' ', '.')
                    .replace('-', '.')
                    .replace('\'', '.')
                )
                string = re.sub(r'\.+', '.', string)  # Dedup "."
                string = unidecode.unidecode(string)  # Replace non-ASCII
                normalized.append(string)
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

    @cached_property
    def description_job(self):
        def validator(text):
            text = text.strip()
            if not text:
                raise ValueError(f'Invalid description: {text}')

        return jobs.dialog.TextFieldJob(
            name='movie-description',
            label='Description',
            validator=validator,
            **self.common_job_args,
        )

    async def generate_description(self, id):
        info = await self.imdb.gather(id, 'title_original', 'title_english', 'year', 'url')
        _log.debug('info: %r', info)
        lines = []

        lines.append('[b]Title[/b]: {title_original}'.format(**info))
        if info['title_english']:
            lines.append('[b]Also Known As[/b]: {title_english}'.format(**info))
        lines.append('[b]Year[/b]: {year}'.format(**info))
        lines.append('[b]Link[/b]: [url={url}]IMDb[/url]'.format(**info))
        # lines.append('[b]IMDb Rating[/b]: {rating}'.format(**info))
        return '\n'.join(lines)

    def handle_imdb_id(self, id):
        self.add_background_task(self.update_text_field_job(
            job=self.title_job,
            text_getter_coro=self.generate_title(id),
            finish_on_success=False,
            default_text=self.release_name.title_with_aka,
        ))

        self.add_background_task(self.update_text_field_job(
            job=self.year_job,
            text_getter_coro=self.generate_year(id),
            finish_on_success=True,
            default_text=self.release_name.year,
        ))

        self.add_background_task(self.update_text_field_job(
            job=self.tags_job,
            text_getter_coro=self.generate_tags(id),
            finish_on_success=True,
        ))

        self.add_background_task(self.update_text_field_job(
            job=self.description_job,
            text_getter_coro=self.generate_description(id),
            finish_on_success=True,
        ))

    @property
    def torrent_filepath(self):
        return self.create_torrent_job.output[0]

    @property
    def post_data(self):
        return {
            'type': "Movies",
            'title': self.title_job.output[0],
            'year': self.year_job.output[0],
            'source': self.source_job.choice,
            'video_codec': self.video_codec_job.choice,
            'audio_codec': self.audio_codec_job.choice,
            'container': self.container_job.choice,
            'resolution': self.resolution_job.choice,
            'remaster_title': self.release_info_job.output[0],
            'tags': self.tags_job.output[0],
            'desc': self.description_job.output[0],
        }
