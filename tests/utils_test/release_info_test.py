import re
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils import release
from upsies.utils.types import ReleaseType


@pytest.mark.parametrize(
    argnames='strict, exception, exp_exception',
    argvalues=(
        (False, None, None),
        (False, errors.ContentError('Error!'), None),
        (True, errors.ContentError('Error!'), errors.ContentError('Error!')),
        (True, None, None),
    ),
    ids=lambda v: str(v),
)
def test_strict_argument(strict, exception, exp_exception, mocker):
    mocker.patch('upsies.utils.scene.assert_not_abbreviated_filename', side_effect=exception)
    if exp_exception:
        exp_msg = re.escape(str(exp_exception))
        with pytest.raises(type(exp_exception), match=rf'^{exp_msg}$'):
            release.ReleaseInfo('foo.mkv', strict=strict)
    else:
        ri = release.ReleaseInfo('foo.mkv', strict=strict)
        assert ri['title'] == 'foo'


def test_getting_known_key(mocker):
    ri = release.ReleaseInfo('foo.mkv')
    mocker.patch.object(ri, '_get_title', Mock(return_value='Mocked Title'))
    for _ in range(3):
        assert ri['title'] == 'Mocked Title'
    assert ri._get_title.call_args_list == [call()]

def test_getting_unknown_key():
    ri = release.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        ri['foo']


def test_setting_known_key():
    ri = release.ReleaseInfo('foo.mkv')
    assert ri['title'] == 'foo'
    ri['title'] = ''
    assert ri['title'] == ''

def test_setting_unknown_key():
    ri = release.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        ri['foo'] = 'bar'
    assert 'foo' not in ri


def test_deleting_unknown_key():
    ri = release.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        del ri['foo']

def test_deleting_known_key():
    ri = release.ReleaseInfo('foo.mkv')
    assert ri['title'] == 'foo'
    del ri['title']
    assert ri['title'] == 'foo'


def test_iter():
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

def test_len():
    ri = release.ReleaseInfo('foo.mkv')
    assert len(ri) == 15


def test_repr():
    ri = release.ReleaseInfo('path/to/foo.mkv')
    assert repr(ri) == "ReleaseInfo('path/to/foo.mkv')"


def test_episodes_is_singleton():
    ri = release.ReleaseInfo('foo.mkv')
    episodes_id = id(ri['episodes'])
    ri['episodes'] = {1: (2, 3)}
    assert id(ri['episodes']) == episodes_id


@pytest.mark.parametrize(
    argnames=('release_name', 'exp_params'),
    argvalues=(
        ('The Foo S01 foo bar baz', 'foo bar baz'),
        ('The Foo S01E01 foo bar baz', 'foo bar baz'),
        ('The Foo S01E01E02 foo bar baz', 'foo bar baz'),
        ('The Foo S01E01E02E03 foo bar baz', 'foo bar baz'),
        ('The Foo E9S01E01S03E02 foo bar baz', 'foo bar baz'),
        ('The Foo Season 1 foo bar baz', 'foo bar baz'),
        ('The Foo Season1 foo bar baz', 'foo bar baz'),
        ('The Foo Season 1 Episode 1 foo bar baz', 'foo bar baz'),
        ('The Foo Season 1 Episode 1 Episode 2 foo bar baz', 'foo bar baz'),
        ('The Foo Season 1 Season 2 Episode 1 Episode 2 foo bar baz', 'foo bar baz'),
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
        if '/' not in rn:
            # Test release name in file name and in parent directory name
            paths = (f'foo/{rn}.mkv', f'{rn}/foo.mkv')
        else:
            # Release name is already coming as path and grandparent directory
            # is not used for parsing
            paths = (f'foo/{rn}.mkv',)

        for path in paths:
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
    ('The Foo S01E04S02 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '', 'episodes': {'1': ('4',), '2': ()},
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
    ('The Foo 2000 S01E02S03E04 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '2000',
      'episodes': {'1': ('2',), '3': ('4',)},
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
    ('The Foo 2000 1080p PROPER BluRay DTS x264-ASDF', {'edition': ['Proper']}),
    ('The Foo 2000 Repack 1080p BluRay DTS x264-ASDF', {'edition': ['Repack']}),
    ('The Foo 2000 1080p Repack2 BluRay DTS x264-ASDF', {'edition': ['Repack2']}),
    ('The Foo 2000 1080p Dual Audio BluRay DTS x264-ASDF', {'edition': ['Dual Audio']}),
    ('The Foo 2000 EXTENDED 1080p BluRay DTS x264-ASDF', {'edition': ['Extended']}),
    ('The Foo 2000 DC Uncut 1080p BluRay DTS x264-ASDF', {'edition': ["DC", 'Uncut']}),
    ('The Foo 2000 1080p Hybrid Uncut BluRay DTS x264-ASDF', {'edition': ['Uncut'],
                                                              'source': 'Hybrid BluRay'}),
    ('The Foo 2000 1080p Hybrid Unrated DC BluRay DTS x264-ASDF', {'edition': ['Unrated', 'DC'],
                                                                   'source': 'Hybrid BluRay'}),
    ('The Foo Extended 2000 1080p Hybrid Uncut BluRay DTS x264-ASDF', {'edition': ['Extended', 'Uncut'],
                                                                       'source': 'Hybrid BluRay'}),
    ('The Foo 2000 OM 1080p BluRay DTS x264-ASDF', {'edition': ['Open Matte']}),

    # TODO: Enable this test when guessit supports it (likely after 3.3.1)
    #       https://github.com/guessit-io/guessit/commit/ddf8e772d735bc80940ba3068c5014d79499a618
    # ('The Foo 2000 Open Matte 1080p BluRay DTS x264-ASDF', {'edition': ['Open Matte']}),

    # TODO: Enable this test when guessit supports it.
    #       https://github.com/guessit-io/guessit/pull/697
    # ('The Foo 2000 Criterion Collection 1080p BluRay DTS x264-ASDF', {'edition': ['Criterion'],
    #                                                                   'source': 'BluRay'}),
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
    ('WEB', 'WEB-DL'), ('Web', 'WEB-DL'), ('web', 'WEB-DL'),
    ('DVD', 'DVD'), ('DVD9', 'DVD9'), ('DVD5', 'DVD5'),
    ('DVD Remux', 'DVD Remux'), ('Remux DVD', 'DVD Remux'),
    # An episode title can contain another source and guessit doesn't have a
    # problem with both "WEB" and "Blu-ray" as a source.
    ('WEB-DL tc', 'WEB-DL'), ('BluRay DVD', 'BluRay'),
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


extended_source_samples = (
    ('BluRay REMUX', 'BluRay Remux'),
    ('remux BluRay', 'BluRay Remux'),
    ('DVD Remux', 'DVD Remux'),
    ('DVDRip Remux', 'DVDRip'),
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
    ('DD', 'AC-3'), ('AC3', 'AC-3'), ('AC-3', 'AC-3'),
    ('DD+', 'E-AC-3'), ('DDP', 'E-AC-3'), ('EAC3', 'E-AC-3'), ('E-AC3', 'E-AC-3'), ('E-AC-3', 'E-AC-3'),
    ('Atmos', 'Atmos'), ('DD+ Atmos', 'Atmos'), ('DDP Atmos', 'Atmos'),
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
    ('DD5.1', 'AC-3', '5.1'),
    ('DD 5.1', 'AC-3', '5.1'),
    ('Dolby Digital 7.1', 'AC-3', '7.1'),
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
    ('The Foo 2000 1080p DTS {vc}-ASDF', {'year': '2000', 'resolution': '1080p', 'audio_codec': 'DTS',
                                          'group': 'ASDF', 'type': ReleaseType.movie}),
    ('The Foo 2000 1080p DTS {vc}', {'year': '2000', 'resolution': '1080p', 'audio_codec': 'DTS',
                                     'type': ReleaseType.movie}),
    ('The Foo S03 1080p DTS {vc}-ASDF', {'episodes': {'3': ()}, 'resolution': '1080p', 'audio_codec': 'DTS',
                                         'group': 'ASDF', 'type': ReleaseType.season}),
    ('The Foo S03 1080p DTS {vc}', {'episodes': {'3': ()}, 'resolution': '1080p', 'audio_codec': 'DTS',
                                    'type': ReleaseType.season}),
    ('The Foo S03 {vc}-ASDF', {'episodes': {'3': ()}, 'group': 'ASDF', 'type': ReleaseType.season}),
    ('The Foo S03 {vc}', {'episodes': {'3': ()}, 'type': ReleaseType.season}),
    ('The Foo {vc}-ASDF', {'group': 'ASDF', 'type': ReleaseType.movie}),
    ('The Foo {vc}', {'type': ReleaseType.movie}),
)
@pytest.mark.parametrize('video_codec', ('x264', 'H.264', 'x265', 'H.265'))
@pytest.mark.parametrize('release_name, exp_values', video_codec_samples, ids=lambda v: str(v))
def test_video_codec(release_name, exp_values, video_codec):
    exp_values['video_codec'] = video_codec
    expected = {**{'title': 'The Foo'}, **exp_values}
    assert_info(release_name.format(vc=video_codec), **expected)


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
     'Baz 2009 720p BluRay x264-asdf'),
    ('QuuX.2005.1080p.BluRay.x264-ASD/asd-q_u_u_x_x264_bluray.mkv',
     'QuuX 2005 1080p BluRay x264-ASD'),
    ('foo/foo.bar.1994.1080p.blu-ray.x264-baz.mkv',
     'foo bar 1994 1080p BluRay x264-baz'),
    ('foo/asdf-barbar.mkv',
     'asdf-barbar    -'),
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
    ('xXx 2002 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'xXx', 'year': '2002',
      'resolution': '1080p', 'source': 'BluRay', 'audio_codec': 'DTS', 'group': 'ASDF'}),
    ('path/to/The Foo - Season 01 - DVDRip.x264',
     {'type': ReleaseType.season, 'title': 'The Foo', 'episodes': {'1': ()},
      'source': 'DVDRip', 'video_codec': 'x264'}),
    ('The Foo - Season 02 - DVDRip.x264/Episode 3 - Something.mkv',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'episodes': {'2': ('3',)},
      'source': 'DVDRip', 'video_codec': 'x264'}),
    ('Real.Life.2015.1080p.AMZN.WEB-DL.DDP5.1.H.264-ASDF',
     {'type': ReleaseType.movie, 'title': 'Real', 'year': '2015', 'resolution': '1080p',
      'service': 'AMZN', 'source': 'WEB-DL', 'audio_codec': 'E-AC-3', 'audio_channels': '5.1',
      'video_codec': 'H.264', 'group': 'ASDF'}),
))
def test_special_case(release_name, expected):
    assert_info(release_name, **expected)
