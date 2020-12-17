from unittest.mock import Mock, call

import pytest

from upsies.utils import ReleaseType, release_info


def test_getting_known_key(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    mocker.patch.object(ri, '_get_title', Mock(return_value='Mocked Title'))
    for _ in range(3):
        assert ri['title'] == 'Mocked Title'
    assert ri._get_title.call_args_list == [call()]

def test_getting_unknown_key(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        ri['foo']


def test_setting_known_key(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    assert ri['title'] == 'foo'
    ri['title'] = ''
    assert ri['title'] == ''

def test_setting_unknown_key(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        ri['foo'] = 'bar'
    assert 'foo' not in ri


def test_deleting_unknown_key(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    with pytest.raises(KeyError, match=r"^'foo'$"):
        del ri['foo']

def test_deleting_known_key(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    assert ri['title'] == 'foo'
    del ri['title']
    assert ri['title'] == 'foo'


def test_iter(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    assert set(ri) == {
        'type',
        'title',
        'aka',
        'year',
        'season',
        'episode',
        'episode_title',
        'edition',
        'resolution',
        'service',
        'source',
        'audio_codec',
        'audio_channels',
        'video_codec',
        'group',
    }

def test_len(mocker):
    ri = release_info.ReleaseInfo('foo.mkv')
    assert len(ri) == 15


def assert_info(release_name,
                type=ReleaseType.unknown, title='', aka='', year='', season='', episode='',
                edition=[], resolution='', service='', source='',
                audio_codec='', audio_channels='', video_codec='', group=''):
    # Test space- and dot-separated release name
    for rn in (release_name, release_name.replace(' ', '.')):
        # Test release name in file and in parent directory name
        for path in (f'foo/{rn}.mkv', f'{rn}/foo.mkv'):
            info = release_info.ReleaseInfo(path)
            assert info['type'] == type
            assert info['title'] == title
            assert info['aka'] == aka
            assert info['year'] == year
            assert info['season'] == season
            assert info['episode'] == episode
            assert info['edition'] == edition
            assert info['resolution'] == resolution
            assert info['service'] == service
            assert info['source'] == source
            assert info['audio_codec'] == audio_codec
            assert info['audio_channels'] == audio_channels
            assert info['video_codec'] == video_codec
            assert info['group'] == group


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo 2000 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000', 'season': '', 'episode': '',
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo S01E04 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '', 'season': '1', 'episode': '4',
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo S01 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.season, 'title': 'The Foo', 'year': '', 'season': '1', 'episode': '',
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.season, 'title': 'The Foo', 'year': '2000', 'season': '1', 'episode': '',
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01E02 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '2000', 'season': '1', 'episode': '2',
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01E01E02 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': ReleaseType.episode, 'title': 'The Foo', 'year': '2000', 'season': '1', 'episode': ['1', '2'],
      'resolution': '1080p', 'service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
))
def test_type_and_year_season_and_episode(release_name, expected):
    assert_info(release_name, **expected)


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984', 'season': '', 'episode': '',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984', 'year': '1984', 'season': '', 'episode': '',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 2000 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984', 'year': '2000', 'season': '', 'episode': '',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
))
def test_title_and_year(release_name, expected):
    assert_info(release_name, **expected)


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo - The Bar 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo - The Bar', 'year': '1984', 'season': '', 'episode': '',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('The Foo - The Bar - The Baz 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': 'The Foo - The Bar - The Baz', 'year': '1984', 'season': '', 'episode': '',
      'resolution': '1080p', 'service': '', 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 AKA Nineteen Eighty-Four 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984', 'aka': 'Nineteen Eighty-Four', 'year': '1984',
      'season': '', 'episode': '', 'resolution': '1080p', 'service': '',
      'source': 'BluRay', 'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
    ('1984 - Foo AKA Nineteen Eighty-Four 1984 1080p BluRay DTS-ASDF',
     {'type': ReleaseType.movie, 'title': '1984 - Foo', 'aka': 'Nineteen Eighty-Four', 'year': '1984',
      'season': '', 'episode': '', 'resolution': '1080p', 'service': '',
      'source': 'BluRay', 'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}),
))
def test_title_and_alternative_title(release_name, expected):
    assert_info(release_name, **expected)


source_samples = (
    ('DVDRip', 'DVDRip'), ('dvdrip', 'DVDRip'), ('dvd rip', 'DVDRip'), ('DVDRip hybrid', 'Hybrid DVDRip'),
    ('BluRay', 'BluRay'), ('bluray', 'BluRay'), ('Blu-ray', 'BluRay'),
    ('Blu-ray Hybrid REMUX', 'Hybrid BluRay Remux'), ('Ultra HD Blu-ray', 'BluRay'),
    ('WEB-DL', 'WEB-DL'), ('WEBDL', 'WEB-DL'), ('web-dl', 'WEB-DL'), ('webdl', 'WEB-DL'),
    ('WEBRip', 'WEBRip'), ('WEBRIP', 'WEBRip'), ('web-rip', 'WEBRip'), ('webrip', 'WEBRip'),
    ('WEB', 'WEB'), ('Web', 'WEB'), ('web', 'WEB'),
    ('DVD', 'DVD'), ('DVD9', 'DVD9'), ('DVD5', 'DVD5'),
    # TODO: Blu-ray images. guessit doesn't support it. Can we just look for
    #       "AVC" and "video_codec=H.264"?
)
@pytest.mark.parametrize('source, exp_source', source_samples)
def test_source(source, exp_source):
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984', 'season': '', 'episode': '',
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
    mocker.patch('upsies.utils.mediainfo.video_format', Mock(return_value=video_format))
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984', 'season': '', 'episode': '',
                'resolution': '1080p', 'service': '', 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}
    assert_info(release_name, **expected)


extended_source_samples = (
    ('BluRay REMUX', 'BluRay Remux'), ('remux BluRay', 'BluRay Remux'),
    ('Hybrid BluRay', 'Hybrid BluRay'), ('BluRay hybrid', 'Hybrid BluRay'),
    ('HYBRID BluRay REMUX', 'Hybrid BluRay Remux'), ('BluRay hybrid remux', 'Hybrid BluRay Remux'),
)
@pytest.mark.parametrize('source, exp_source', extended_source_samples)
def test_extended_source(source, exp_source):
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '1984', 'season': '', 'episode': '',
                'resolution': '1080p', 'service': '', 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': '', 'group': 'ASDF'}
    assert_info(release_name, **expected)


service_samples = (
    ('NF', 'NF'), ('Netflix', 'NF'),
    ('AMZN', 'AMZN'), ('Amazon', 'AMZN'),
    ('APTV', 'APTV'),
    ('BBC', 'BBC'),
    ('DSNP', 'DSNP'), ('DNSP', 'DSNP'), ('Disney', 'DSNP'),
    ('HBO', 'HBO'),
    ('HMAX', 'HMAX'),
    ('HULU', 'HULU'), ('Hulu', 'HULU'),
    ('IT', 'IT'), ('iTunes', 'IT'),
    ('VUDU', 'VUDU'),
)
@pytest.mark.parametrize('service, service_abbrev', service_samples)
def test_service_is_abbreviated(service, service_abbrev):
    release_name = f'The Foo S10 1080p {service} WEB-DL AAC H.264-ASDF'
    expected = {'type': ReleaseType.season, 'title': 'The Foo', 'year': '', 'season': '10', 'episode': '',
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
    release_name = f'The Foo S10 1080p WEB-DL {audio_codec} H.264-ASDF'
    expected = {'type': ReleaseType.season, 'title': 'The Foo', 'year': '', 'season': '10', 'episode': '',
                'resolution': '1080p', 'source': 'WEB-DL',
                'audio_codec': audio_codec_abbrev, 'audio_channels': '', 'video_codec': 'H.264', 'group': 'ASDF'}
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
    release_name = f'The Foo S10 1080p WEB-DL {audio} H.264-ASDF'
    expected = {'type': ReleaseType.season, 'title': 'The Foo', 'year': '', 'season': '10', 'episode': '',
                'resolution': '1080p', 'source': 'WEB-DL',
                'audio_codec': audio_codec, 'audio_channels': audio_channels, 'video_codec': 'H.264', 'group': 'ASDF'}
    assert_info(release_name, **expected)


video_codec_samples = (
    ('The Foo 2000 1080p DTS H.264-ASDF', 'H.264'),
    ('The Foo 2000 1080p DTS x264-ASDF', 'x264'),
    ('The Foo 2000 1080p DTS H.265-ASDF', 'H.265'),
    ('The Foo 2000 1080p DTS x265-ASDF', 'x265'),
)
@pytest.mark.parametrize('release_name, video_codec', video_codec_samples)
def test_video_codec(release_name, video_codec):
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
                'resolution': '1080p',
                'audio_codec': 'DTS', 'video_codec': video_codec, 'group': 'ASDF'}
    assert_info(release_name, **expected)


edition_samples = (
    ('The Foo 2000 EXTENDED 1080p DTS x264-ASDF', ['Extended']),
    ('The Foo 2000 DC Uncut 1080p DTS x264-ASDF', ["Director's Cut", 'Uncut']),
)
@pytest.mark.parametrize('release_name, edition', edition_samples)
def test_edition(release_name, edition):
    expected = {'type': ReleaseType.movie, 'title': 'The Foo', 'year': '2000',
                'edition': edition, 'resolution': '1080p',
                'audio_codec': 'DTS', 'video_codec': 'x264', 'group': 'ASDF'}
    assert_info(release_name, **expected)
