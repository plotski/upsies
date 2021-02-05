from unittest.mock import Mock, call

import pytest

from upsies.utils import release
from upsies.utils.types import ReleaseType


def test_getting_known_key(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    mocker.patch.object(ri, '_get_title', Mock(return_value='Mocked Title'))
    for _ in range(3):
        assert ri['title'] == 'Mocked Title'
    assert ri._get_title.call_args_list == [call()]

def test_getting_unknown_key(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        ri['foo']


def test_setting_known_key(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    assert ri['title'] == 'foo'
    ri['title'] = ''
    assert ri['title'] == ''

def test_setting_unknown_key(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        ri['foo'] = 'bar'
    assert 'foo' not in ri


def test_deleting_unknown_key(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        del ri['foo']

def test_deleting_known_key(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    assert ri['title'] == 'foo'
    del ri['title']
    assert ri['title'] == 'foo'


def test_iter(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    assert set(ri) == {
        'type',
        'title',
        'aka',
        'year',
        'episodes',
        'episode_title',
        'edition',
        'resolution',
        'service',
        'source',
        'audio_codec',
        'audio_channels',
        'video_codec',
        'group',
        'has_commentary',
    }

def test_len(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    assert len(ri) == 15


def test_repr():
    ri = release.ReleaseInfo('path/to/foo.mkv')
    assert repr(ri) == "ReleaseInfo('path/to/foo.mkv')"


@pytest.mark.parametrize(
    argnames=('release_name', 'exp_params'),
    argvalues=(
        ('The Foo S01 foo bar baz', 'foo bar baz'),
        ('The Foo S01E01 foo bar baz', 'foo bar baz'),
        ('The Foo S01E01E02 foo bar baz', 'foo bar baz'),
        ('The Foo S01E01E02E03 foo bar baz', 'foo bar baz'),
        ('The Foo Season 1 foo bar baz', 'foo bar baz'),
        ('The Foo Season1 foo bar baz', 'foo bar baz'),
        ('The Foo Season 1 Episode 1 foo bar baz', 'foo bar baz'),
        ('The Foo Season 1 Episode 1 Episode 2 foo bar baz', 'foo bar baz'),
        ('The Foo Season1 Episode1 foo bar baz', 'foo bar baz'),
        ('The Foo Season1 Episode1 Episode2 foo bar baz', 'foo bar baz'),
        ('The Foo foo bar baz', 'The Foo foo bar baz'),
    ),
    ids=lambda v: str(v),
)
def test_release_name_params(release_name, exp_params):
    for name, exp in ((release_name, exp_params),
                      (release_name.replace(' ', '.'), exp_params.replace(' ', '.'))):
        for path in (f'path/to/{name}.mkv', f'path/to/{name}/asdf.mkv'):
            print(repr(path), repr(exp))
            info = release.ReleaseInfo(path)
            assert info.release_name_params == exp

def test_release_name_params_default():
    assert release.ReleaseInfo('path/to/Foo.mkv').release_name_params == 'Foo'
    assert release.ReleaseInfo('Foo.mkv').release_name_params == 'Foo'
    assert release.ReleaseInfo('Foo').release_name_params == 'Foo'


def assert_info(release_name,
                type=ReleaseType.unknown, title='', aka='', year='', episodes={},
                edition=[], resolution='', service='', source='',
                audio_codec='', audio_channels='', video_codec='', group='', has_commentary=False):
    # Test space- and dot-separated release name
    for rn in (release_name, release_name.replace(' ', '.')):
        # Test release name in file and in parent directory name
        for path in (f'foo/{rn}.mkv', f'{rn}/foo.mkv'):
            info = release.ReleaseInfo(path)
            assert info['type'] == type
            assert info['title'] == title
            assert info['aka'] == aka
            assert info['year'] == year
            assert info['episodes'] == episodes
            assert info['edition'] == edition
            assert info['resolution'] == resolution
            assert info['service'] == service
            assert info['source'] == source
            assert info['audio_codec'] == audio_codec
            assert info['audio_channels'] == audio_channels
            assert info['video_codec'] == video_codec
            assert info['group'] == group
            assert info['has_commentary'] == has_commentary


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo 2000 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo S01E04 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '', 'episodes': {'1': ('4',)},
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo S01 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.season, 'title': 'The Foo', 'year': '', 'episodes': {'1': ()},
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.season, 'title': 'The Foo', 'year': '2000', 'episodes': {'1': ()},
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01E02 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '2000', 'episodes': {'1': ('2',)},
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01E01E02 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '2000', 'episodes': {'1': ('1', '2')},
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
))
def test_type_and_year_season_and_episode(release_name, expected):
    assert_info(release_name, **expected)


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984', 'year': '1984',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 2000 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984', 'year': '2000',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
))
def test_title_and_year(release_name, expected):
    assert_info(release_name, **expected)


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo - The Bar 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo - The Bar', 'year': '1984',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('The Foo - The Bar - The Baz 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo - The Bar - The Baz', 'year': '1984',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 AKA Nineteen Eighty-Four 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984', 'aka': 'Nineteen Eighty-Four', 'year': '1984',
      'resolution': '1080p', 'service': '',
      'source': 'BluRay', 'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 - Foo AKA Nineteen Eighty-Four 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984 - Foo', 'aka': 'Nineteen Eighty-Four', 'year': '1984',
      'resolution': '1080p', 'service': '',
      'source': 'BluRay', 'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('Foo - Bar AKA Baz 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'Foo - Bar', 'aka': 'Baz', 'year': '',
      'resolution': '1080p', 'service': '',
      'source': 'BluRay', 'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
))
def test_title_and_alternative_title(release_name, expected):
    assert_info(release_name, **expected)


edition_samples = (
    ('The Foo 2000 EXTENDED 1080p BluRay DTS x264-ASDF', {'edition': ['Extended']}),
    ('The Foo 2000 DC Uncut 1080p BluRay DTS x264-ASDF', {'edition': ["DC", 'Uncut']}),
    ('The Foo 2000 1080p Hybrid Uncut BluRay DTS x264-ASDF', {'edition': ['Uncut'],
                                                              'source': 'Hybrid BluRay'}),
    ('The Foo 2000 1080p Hybrid Unrated DC BluRay DTS x264-ASDF', {'edition': ['Unrated', 'DC'],
                                                                   'source': 'Hybrid BluRay'}),
    ('The Foo Extended 2000 1080p Hybrid Uncut BluRay DTS x264-ASDF', {'edition': ['Extended', 'Uncut'],
                                                                       'source': 'Hybrid BluRay'}),
)
@pytest.mark.parametrize('release_name, exp_values', edition_samples)
def test_edition(release_name, exp_values):
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
                'resolution': '1080p', 'source': 'BluRay',
                'audio_codec': 'DTS', 'video_codec': 'x264', 'group': 'ASDF'}
    expected.update(exp_values)
    assert_info(release_name, **expected)


source_samples = (
    ('DVDRip', 'DVDRip'), ('dvdrip', 'DVDRip'), ('dvd rip', 'DVDRip'), ('DVDRip hybrid', 'Hybrid DVDRip'),
    ('BluRay', 'BluRay'), ('bluray', 'BluRay'), ('Blu-ray', 'BluRay'),
    ('Blu-ray Hybrid REMUX', 'Hybrid BluRay Remux'), ('Ultra HD Blu-ray', 'BluRay'),
    ('WEB-DL', 'WEB-DL'), ('WEBDL', 'WEB-DL'), ('web-dl', 'WEB-DL'), ('webdl', 'WEB-DL'),
    ('WEBRip', 'WEBRip'), ('WEBRIP', 'WEBRip'), ('web-rip', 'WEBRip'), ('webrip', 'WEBRip'),
    ('WEB-DL Remux', 'WEB-DL'), ('Remux WEB-DL', 'WEB-DL'), ('WEBRip Remux', 'WEBRip'), ('Remux WEBRip', 'WEBRip'),
    ('WEB', 'WEB'), ('Web', 'WEB'), ('web', 'WEB'),
    ('DVD', 'DVD'), ('DVD9', 'DVD9'), ('DVD5', 'DVD5'),
    # TODO: Blu-ray images. guessit doesn't support it. Can we just look for
    #       "AVC" and "video_codec=H.264"?
)
@pytest.mark.parametrize('source, exp_source', source_samples)
def test_source(source, exp_source):
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984',
                'resolution': '1080p', 'service': '', 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}
    assert_info(release_name, **expected)


source_from_encoder_samples = (
    ('WEB', 'x264', 'WEBRip'),
    ('Web', 'x265', 'WEBRip'),
    ('web', 'H.264', 'WEB-DL'),
    ('WEB', 'H.265', 'WEB-DL'),
    ('WEB', '', 'WEB'),
)
@pytest.mark.parametrize('source, video_format, exp_source', source_from_encoder_samples)
def test_source_from_encoder(source, video_format, exp_source, mocker):
    mocker.patch('upsies.utils.video.video_format', Mock(return_value=video_format))
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984',
                'resolution': '1080p', 'service': '', 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}
    assert_info(release_name, **expected)


extended_source_samples = (
    ('BluRay REMUX', 'BluRay Remux'),
    ('remux BluRay', 'BluRay Remux'),
    ('Hybrid BluRay', 'Hybrid BluRay'),
    ('BluRay hybrid', 'Hybrid BluRay'),
    ('HYBRID BluRay REMUX', 'Hybrid BluRay Remux'),
    ('Bluray hybrid remux', 'Hybrid BluRay Remux'),
    ('Blu-Ray REMUX hybrid', 'Hybrid BluRay Remux'),
    ('remux BluRay Hybrid', 'Hybrid BluRay Remux'),
)
@pytest.mark.parametrize('source, exp_source', extended_source_samples)
def test_extended_source(source, exp_source):
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984',
                'resolution': '1080p', 'service': '', 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}
    assert_info(release_name, **expected)


service_samples = (
    ('NF', 'NF'), ('Netflix', 'NF'),
    ('AMZN', 'AMZN'), ('Amazon', 'AMZN'),
    ('APTV', 'APTV'),
    ('BBC', 'BBC'),
    ('HBO', 'HBO'),
    ('HMAX', 'HMAX'),
    ('HULU', 'HULU'), ('Hulu', 'HULU'),
    ('iT', 'iT'), ('iTunes', 'iT'),
    ('VUDU', 'VUDU'),
    ('CRKL', 'CRKL'),
)
@pytest.mark.parametrize('service, service_abbrev', service_samples)
def test_service_is_abbreviated(service, service_abbrev):
    release_name = f'The Foo S10 1080p {service} WEB-DL AAC H.264-ASDF'
    expected = {'type': ReleaseType.season, 'title': 'The Foo', 'year': '', 'episodes': {'10': ()},
                'resolution': '1080p', 'service': service_abbrev, 'source': 'WEB-DL',
                'audio_codec': 'AAC', 'audio_channels': '', 'video_codec': 'H.264', 'group': 'ASDF'}
    assert_info(release_name, **expected)


audio_codec_samples = (
    ('DD', 'DD'), ('AC3', 'DD'), ('AC-3', 'DD'),
    ('DD+', 'DD+'), ('DDP', 'DD+'), ('EAC3', 'DD+'), ('E-AC3', 'DD+'), ('E-AC-3', 'DD+'),
    ('DD+ Atmos', 'DD+ Atmos'), ('DDP Atmos', 'DD+ Atmos'),
    ('TrueHD', 'TrueHD'), ('Dolby TrueHD', 'TrueHD'),
    ('TrueHD Atmos', 'TrueHD Atmos'), ('Dolby TrueHD Atmos', 'TrueHD Atmos'),
    ('DTS', 'DTS'),
    ('AAC', 'AAC'),
    ('FLAC', 'FLAC'),
    ('MP3', 'MP3'),
    (None, ''),
)
@pytest.mark.parametrize('audio_codec, audio_codec_abbrev', audio_codec_samples)
def test_audio_codec_is_abbreviated(audio_codec, audio_codec_abbrev):
    release_name = f'The Foo S04 1080p WEB-DL {audio_codec} H.264-ASDF'
    expected = {'type': ReleaseType.season, 'title': 'The Foo', 'year': '', 'episodes': {'4': ()},
                'resolution': '1080p', 'source': 'WEB-DL',
                'audio_codec': audio_codec_abbrev, 'audio_channels': '',
                'video_codec': 'H.264', 'group': 'ASDF'}
    assert_info(release_name, **expected)


audio_channels_samples = (
    ('MP3', 'MP3', ''),
    ('FLAC 1.0', 'FLAC', '1.0'),
    ('AAC2.0', 'AAC', '2.0'),
    ('AAC 2.0', 'AAC', '2.0'),
    ('DD5.1', 'DD', '5.1'),
    ('DD 5.1', 'DD', '5.1'),
    ('Dolby Digital 7.1', 'DD', '7.1'),
)
@pytest.mark.parametrize('audio, audio_codec, audio_channels', audio_channels_samples)
def test_audio_channels(audio, audio_codec, audio_channels):
    release_name = f'The Foo 2000 1080p WEB-DL {audio} H.264-ASDF'
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
                'resolution': '1080p', 'source': 'WEB-DL',
                'audio_codec': audio_codec, 'audio_channels': audio_channels,
                'video_codec': 'H.264', 'group': 'ASDF'}
    assert_info(release_name, **expected)


video_codec_samples = (
    ('The Foo 2000 1080p DTS H.264-ASDF', {'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 1080p DTS x264-ASDF', {'video_codec': 'x264', 'group': 'ASDF'}),
    ('The Foo 2000 1080p DTS H.265-ASDF', {'video_codec': 'H.265', 'group': 'ASDF'}),
    ('The Foo 2000 1080p DTS x265-ASDF', {'video_codec': 'x265', 'group': 'ASDF'}),
    ('The Foo 2000 1080p DTS H.264', {'video_codec': 'H.264', 'group': ''}),
    ('The Foo 2000 1080p DTS x264', {'video_codec': 'x264', 'group': ''}),
    ('The Foo 2000 1080p DTS H.265', {'video_codec': 'H.265', 'group': ''}),
    ('The Foo 2000 1080p DTS x265', {'video_codec': 'x265', 'group': ''}),
)
@pytest.mark.parametrize('release_name, exp_values', video_codec_samples)
def test_video_codec(release_name, exp_values):
    expected = {**{'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
                   'resolution': '1080p', 'audio_codec': 'DTS'},
                **exp_values}
    assert_info(release_name, **expected)


group_samples = (
    ('The Foo 2000 1080p DTS x264-ASDF', 'ASDF'),
    ('The Foo 2000 1080p DTS x264-AsdF', 'AsdF'),
    ('The Foo 2000 1080p DTS x264-A-F', 'A-F'),
)
@pytest.mark.parametrize('release_name, group', group_samples)
def test_group(release_name, group):
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
                'resolution': '1080p',
                'audio_codec': 'DTS', 'video_codec': 'x264', 'group': group}
    assert_info(release_name, **expected)


@pytest.mark.parametrize(
    argnames='release_name, exp_value',
    argvalues=(
        ('The Foo 2000 1080p Plus Comm DTS x264-ASDF', True),
        ('The Foo 2000 1080p Comm DTS x264-ASDF', False),
        ('The Foo 2000 1080p Commentary DTS x264-ASDF', True),
        ('The Foo 2000 1080p DTS x264-ASDF', False),
    ),
)
def test_has_commentary(release_name, exp_value):
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
                'resolution': '1080p', 'audio_codec': 'DTS', 'video_codec': 'x264',
                'group': 'ASDF', 'has_commentary': exp_value}
    assert_info(release_name, **expected)
    ri = release.ReleaseInfo(release_name)
    ri['has_commentary'] = ''
    assert ri['has_commentary'] is False
    ri['has_commentary'] = 1
    assert ri['has_commentary'] is True
    ri['has_commentary'] = None
    assert ri['has_commentary'] is exp_value


def test_path():
    assert release.ReleaseInfo('path/to/foo').path == 'path/to/foo'


@pytest.mark.parametrize('path, exp_release_name', (
    ('Foo.2017.720p.BluRay.x264-ASDF/asdf-foo.2017.720p.bluray.x264.mkv',
     'Foo 2017 720p BluRay x264-ASDF'),
    ('Bar.Bar.2013.720p.BluRay.x264-ASDF/asdf-barbar.mkv',
     'Bar Bar 2013 720p BluRay x264-ASDF'),
    ('path/to/Baz.2009.720p.BluRay.x264-ASDF/asdf-720p-baz.mkv',
     'Baz 2009 720p BluRay x264-ASDF'),
    ('QuuX.2005.1080p.BluRay.x264-ASD/asd-q_u_u_x_x264_bluray.mkv',
     'QuuX 2005 1080p BluRay x264-ASD'),
    ('foo/foo.bar.1994.1080p.blu-ray.x264-baz.mkv',
     'foo bar 1994 1080p BluRay x264-baz'),
))
def test_abbreviated_scene_filename(path, exp_release_name):
    ri = release.ReleaseInfo(path)
    release_name = '{title} {year} {resolution} {source} {video_codec}-{group}'.format(**ri)
    assert release_name == exp_release_name


@pytest.mark.parametrize('release_name, expected', (
    ('The Collector 2009 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Collector', 'year': '2009',
      'resolution': '1080p', 'source': 'BluRay', 'audio_codec': 'DTS', 'group': 'ASDF',
      'edition': []}),
    ('The Collector Collector 2009 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Collector', 'year': '2009',
      'resolution': '1080p', 'source': 'BluRay', 'audio_codec': 'DTS', 'group': 'ASDF',
      'edition': ['Collector']}),
))
def test_special_case(release_name, expected):
    assert_info(release_name, **expected)
