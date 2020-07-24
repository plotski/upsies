from unittest.mock import patch

import pytest

from upsies.tools.release_name import ReleaseName


def assert_attrs(string,
                 exp_type='', exp_title='UNKNOWN_TITLE', exp_year='UNKNOWN_YEAR',
                 exp_season='', exp_episode='', exp_resolution='UNKNOWN_RESOLUTION',
                 exp_service='', exp_source='UNKNOWN_SOURCE',
                 exp_audio_format='UNKNOWN_AUDIO_FORMAT', exp_audio_channels='',
                 exp_video_format='UNKNOWN_VIDEO_FORMAT', exp_group='NOGROUP'):
    for rn in (ReleaseName(string), ReleaseName(string.replace(' ', '.'))):
        assert rn.type == exp_type
        assert rn.title == exp_title
        assert rn.year == exp_year
        assert rn.season == exp_season
        assert rn.episode == exp_episode
        assert rn.resolution == exp_resolution
        assert rn.service == exp_service
        assert rn.source == exp_source
        assert rn.audio_format == exp_audio_format
        assert rn.audio_channels == exp_audio_channels
        assert rn.video_format == exp_video_format
        assert rn.group == exp_group


def test_title():
    assert_attrs('path/to/The Foo.mkv',
                 exp_type='movie',
                 exp_title='The Foo')

title_year_samples = (
    ('The Foo 1984.mkv', 'The Foo', '1984'),
    ('Bar 2000.mkv', 'Bar', '2000'),
    ('1984 1984.mkv', '1984', '1984'),
)

@pytest.mark.parametrize('filepath, exp_title, exp_year', title_year_samples)
def test_title_year(filepath, exp_title, exp_year):
    assert_attrs(filepath,
                 exp_type='movie',
                 exp_title=exp_title,
                 exp_year=exp_year)

@patch('upsies.utils.video.first_video')
def test_title_season(first_video_mock):
    first_video_mock.return_value = 'The Foo S03/The Foo S03E01.mkv'
    assert_attrs('The Foo S03',
                 exp_type='season',
                 exp_title='The Foo',
                 exp_year='',
                 exp_season='3')

def test_title_season_episode():
    assert_attrs('The Foo S03/The Foo S03E04.mkv',
                 exp_type='episode',
                 exp_title='The Foo',
                 exp_year='',
                 exp_season='3',
                 exp_episode='4')

@patch('upsies.utils.video.first_video')
def test_title_year_season(first_video_mock):
    first_video_mock.return_value = 'The Foo S03/The Foo S03E01.mkv'
    assert_attrs('The Foo 2000 S03',
                 exp_type='season',
                 exp_title='The Foo',
                 exp_year='2000',
                 exp_season='3')

def test_title_year_season_episode():
    assert_attrs('The Foo 2000 S03E04.mkv',
                 exp_type='episode',
                 exp_title='The Foo',
                 exp_year='2000',
                 exp_season='3',
                 exp_episode='4')


@patch('upsies.tools.mediainfo.resolution')
def test_resolution_from_file_name(resolution_mock):
    resolution_mock.return_value = None
    assert_attrs('The Foo 2000 1080p.mkv',
                 exp_type='movie',
                 exp_title='The Foo',
                 exp_year='2000',
                 exp_resolution='1080p')

@patch('upsies.tools.mediainfo.resolution')
def test_resolution_from_parent_directory_name(resolution_mock):
    resolution_mock.return_value = None
    assert_attrs('The Foo S03 1080p/The Foo S03E04.mkv',
                 exp_type='episode',
                 exp_title='The Foo',
                 exp_year='',
                 exp_season='3',
                 exp_episode='4',
                 exp_resolution='1080p')

@patch('upsies.tools.mediainfo.resolution')
def test_resolution_from_mediainfo(resolution_mock):
    resolution_mock.return_value = '480p'
    assert_attrs('The Foo 720p S03E04.mkv',
                 exp_type='episode',
                 exp_title='The Foo',
                 exp_year='',
                 exp_season='3',
                 exp_episode='4',
                 exp_resolution='480p')


@patch('upsies.tools.mediainfo.audio_format')
@patch('upsies.tools.mediainfo.audio_channels')
def test_audio_from_file_name(audio_format_mock, audio_channels_mock):
    audio_format_mock.return_value = None
    audio_channels_mock.return_value = None
    assert_attrs('The Foo 2000 1080p DD+ 5.1-ASDF.mkv',
                 exp_type='movie',
                 exp_title='The Foo',
                 exp_year='2000',
                 exp_resolution='1080p',
                 exp_audio_format='DD+',
                 exp_audio_channels='5.1',
                 exp_group='ASDF')

@patch('upsies.tools.mediainfo.audio_format')
@patch('upsies.tools.mediainfo.audio_channels')
def test_audio_from_parent_directory_name(audio_format_mock, audio_channels_mock):
    audio_format_mock.return_value = None
    audio_channels_mock.return_value = None
    assert_attrs('The Foo 2000 1080p DD+ 5.1-ASDF/tf.mkv',
                 exp_type='movie',
                 exp_title='The Foo',
                 exp_year='2000',
                 exp_resolution='1080p',
                 exp_audio_format='DD+',
                 exp_audio_channels='5.1',
                 exp_group='ASDF')

@patch('upsies.tools.mediainfo.audio_channels')
@patch('upsies.tools.mediainfo.audio_format')
def test_audio_from_mediainfo(audio_format_mock, audio_channels_mock):
    audio_format_mock.return_value = 'AAC'
    audio_channels_mock.return_value = '2.0'
    assert_attrs('The Foo 2000 1080p DD+ 5.1-ASDF.mkv',
                 exp_type='movie',
                 exp_title='The Foo',
                 exp_year='2000',
                 exp_resolution='1080p',
                 exp_audio_format='AAC',
                 exp_audio_channels='2.0',
                 exp_group='ASDF')
