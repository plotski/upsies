from unittest.mock import Mock, call, patch

import pytest

from upsies.utils import guessit


# guessit() is memoized so we must clear its cache before every test.
@pytest.fixture(autouse=True)
def clear_guessit_cache():
    guessit.guessit.cache_clear()


@patch('upsies.utils.guessit._guessit')
def test_return_value_is_regular_dict(guessit_mock):
    guessit_mock.guessit.return_value = (('type', 'movie'),)
    guess = guessit.guessit('path/to/foo.mkv')
    assert type(guess) is dict
    assert guess == {'type': 'movie'}
    assert guessit_mock.guessit.call_args_list == [call('path/to/foo.mkv')]

@patch('upsies.utils.guessit._guessit')
def test_turn_other_field_into_list(guessit_mock):
    guessit_mock.guessit.return_value = {'type': 'movie', 'other': 'Rip'}
    guess = guessit.guessit('path/to/foo.mkv')
    assert guess['other'] == ['Rip']

@patch('upsies.utils.guessit._guessit')
def test_preserve_other_field_as_list(guessit_mock):
    guessit_mock.guessit.return_value = {'other': 'info'}
    guessit_mock.guessit.return_value = {'other': ['more', 'info']}
    guess = guessit.guessit('path/to/foo.mkv')
    assert guess['other'] == ['more', 'info']


def assert_guess(release_name,
                 type=None, title=None, aka=None, year=None, season=None, episode=None,
                 edition=None, screen_size=None, streaming_service=None, source=None,
                 audio_codec=None, audio_channels=None, video_codec=None, group=None):
    # Test space- and dot-separated release name
    for rn in (release_name, release_name.replace(' ', '.')):
        # Test release name in file and in parent directory name
        for path in (f'{rn}.mkv', f'{rn}/foo.mkv'):
            guess = guessit.guessit(path)
            assert guess['type'] == type
            assert guess['title'] == title
            assert guess.get('aka') == aka
            assert guess.get('year') == year
            assert guess.get('season') == season
            assert guess.get('episode') == episode
            assert guess.get('edition') == edition
            assert guess.get('screen_size') == screen_size
            assert guess.get('streaming_service') == streaming_service
            assert guess.get('source') == source
            assert guess.get('audio_codec') == audio_codec
            assert guess.get('audio_channels') == audio_channels
            assert guess.get('video_codec') == video_codec


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo 2000 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': 'movie', 'title': 'The Foo', 'year': '2000', 'season': None, 'episode': None,
      'screen_size': '1080p', 'streaming_service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo S01E04 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': 'episode', 'title': 'The Foo', 'year': None, 'season': '1', 'episode': '4',
      'screen_size': '1080p', 'streaming_service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo S01 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': 'season', 'title': 'The Foo', 'year': None, 'season': '1', 'episode': None,
      'screen_size': '1080p', 'streaming_service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': 'season', 'title': 'The Foo', 'year': '2000', 'season': '1', 'episode': None,
      'screen_size': '1080p', 'streaming_service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01E02 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': 'episode', 'title': 'The Foo', 'year': '2000', 'season': '1', 'episode': '2',
      'screen_size': '1080p', 'streaming_service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
    ('The Foo 2000 S01E01E02 1080p NF WEB-DL AAC2.0 H.264-ASDF',
     {'type': 'episode', 'title': 'The Foo', 'year': '2000', 'season': '1', 'episode': ['1', '2'],
      'screen_size': '1080p', 'streaming_service': 'NF', 'source': 'WEB-DL',
      'audio_codec': 'AAC', 'audio_channels': '2.0', 'video_codec': 'H.264', 'group': 'ASDF'}),
))
def test_type_and_year_season_and_episode(release_name, expected):
    assert_guess(release_name, **expected)


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo 1984 1080p BluRay DTS-ASDF',
     {'type': 'movie', 'title': 'The Foo', 'year': '1984', 'season': None, 'episode': None,
      'screen_size': '1080p', 'streaming_service': None, 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}),
    ('1984 1984 1080p BluRay DTS-ASDF',
     {'type': 'movie', 'title': '1984', 'year': '1984', 'season': None, 'episode': None,
      'screen_size': '1080p', 'streaming_service': None, 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}),
    ('1984 2000 1080p BluRay DTS-ASDF',
     {'type': 'movie', 'title': '1984', 'year': '2000', 'season': None, 'episode': None,
      'screen_size': '1080p', 'streaming_service': None, 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}),
))
def test_title_and_year(release_name, expected):
    assert_guess(release_name, **expected)


@pytest.mark.parametrize('release_name, expected', (
    ('The Foo - The Bar 1984 1080p BluRay DTS-ASDF',
     {'type': 'movie', 'title': 'The Foo - The Bar', 'year': '1984', 'season': None, 'episode': None,
      'screen_size': '1080p', 'streaming_service': None, 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}),
    ('The Foo - The Bar - The Baz 1984 1080p BluRay DTS-ASDF',
     {'type': 'movie', 'title': 'The Foo - The Bar - The Baz', 'year': '1984', 'season': None, 'episode': None,
      'screen_size': '1080p', 'streaming_service': None, 'source': 'BluRay',
      'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}),
    ('1984 AKA Nineteen Eighty-Four 1984 1080p BluRay DTS-ASDF',
     {'type': 'movie', 'title': '1984', 'aka': 'Nineteen Eighty-Four', 'year': '1984',
      'season': None, 'episode': None, 'screen_size': '1080p', 'streaming_service': None,
      'source': 'BluRay', 'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}),
    ('1984 - Foo AKA Nineteen Eighty-Four 1984 1080p BluRay DTS-ASDF',
     {'type': 'movie', 'title': '1984 - Foo', 'aka': 'Nineteen Eighty-Four', 'year': '1984',
      'season': None, 'episode': None, 'screen_size': '1080p', 'streaming_service': None,
      'source': 'BluRay', 'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}),
))
def test_title_and_alternative_title(release_name, expected):
    assert_guess(release_name, **expected)


source_samples = (
    ('DVDRip', 'DVDRip'), ('dvdrip', 'DVDRip'), ('dvd rip', 'DVDRip'),
    ('BluRay', 'BluRay'), ('bluray', 'BluRay'), ('Blu-ray', 'BluRay'), ('Ultra HD Blu-ray', 'BluRay'),
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
    expected = {'type': 'movie', 'title': 'The Foo', 'year': '1984', 'season': None, 'episode': None,
                'screen_size': '1080p', 'streaming_service': None, 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}
    assert_guess(release_name, **expected)


source_from_encoder_samples = (
    ('WEB', 'x264', 'WEBRip'),
    ('Web', 'x265', 'WEBRip'),
    ('web', 'H.264', 'WEB-DL'),
    ('WEB', 'H.265', 'WEB-DL'),
    ('WEB', None, 'WEB'),
)
@pytest.mark.parametrize('source, video_format, exp_source', source_from_encoder_samples)
def test_source_from_encoder(source, video_format, exp_source, mocker):
    mocker.patch('upsies.tools.mediainfo.video_format', Mock(return_value=video_format))
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': 'movie', 'title': 'The Foo', 'year': '1984', 'season': None, 'episode': None,
                'screen_size': '1080p', 'streaming_service': None, 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}
    assert_guess(release_name, **expected)


extended_source_samples = (
    ('BluRay REMUX', 'BluRay Remux'), ('remux BluRay', 'BluRay Remux'),
    ('Hybrid BluRay', 'Hybrid BluRay'), ('BluRay hybrid', 'Hybrid BluRay'),
    ('HYBRID BluRay REMUX', 'Hybrid BluRay Remux'), ('BluRay hybrid remux', 'Hybrid BluRay Remux'),
)
@pytest.mark.parametrize('source, exp_source', extended_source_samples)
def test_extended_source(source, exp_source):
    release_name = f'The Foo 1984 1080p {source} DTS-ASDF'
    expected = {'type': 'movie', 'title': 'The Foo', 'year': '1984', 'season': None, 'episode': None,
                'screen_size': '1080p', 'streaming_service': None, 'source': exp_source,
                'audio_codec': 'DTS', 'audio_channels': None, 'group': 'ASDF'}
    assert_guess(release_name, **expected)


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
def test_streaming_service_is_abbreviated(service, service_abbrev):
    release_name = f'The Foo S10 1080p {service} WEB-DL AAC H.264-ASDF'
    expected = {'type': 'season', 'title': 'The Foo', 'year': None, 'season': '10', 'episode': None,
                'screen_size': '1080p', 'streaming_service': service_abbrev, 'source': 'WEB-DL',
                'audio_codec': 'AAC', 'audio_channels': None, 'video_codec': 'H.264', 'group': 'ASDF'}
    assert_guess(release_name, **expected)


audio_codec_samples = (
    ('DD+', 'DD+'), ('DDP', 'DD+'), ('EAC3', 'DD+'),
    ('DD', 'DD'), ('DD', 'DD'),
    ('DD+ Atmos', 'DD+ Atmos'), ('DDP Atmos', 'DD+ Atmos'),
    ('TrueHD', 'TrueHD'), ('Dolby TrueHD', 'TrueHD'),
    ('TrueHD Atmos', 'TrueHD Atmos'), ('Dolby TrueHD Atmos', 'TrueHD Atmos'),
    ('DTS', 'DTS'),
    ('AAC', 'AAC'),
    ('FLAC', 'FLAC'),
    ('MP3', 'MP3'),
)

@pytest.mark.parametrize('audio_codec, audio_codec_abbrev', audio_codec_samples)
def test_audio_codec_is_abbreviated(audio_codec, audio_codec_abbrev):
    release_name = f'The Foo S10 1080p WEB-DL {audio_codec} H.264-ASDF'
    expected = {'type': 'season', 'title': 'The Foo', 'year': None, 'season': '10', 'episode': None,
                'screen_size': '1080p', 'source': 'WEB-DL',
                'audio_codec': audio_codec_abbrev, 'audio_channels': None, 'video_codec': 'H.264', 'group': 'ASDF'}
    assert_guess(release_name, **expected)


video_codec_samples = (
    ('The Foo 2000 1080p DTS H.264-ASDF', 'H.264'),
    ('The Foo 2000 1080p DTS x264-ASDF', 'x264'),
    ('The Foo 2000 1080p DTS H.265-ASDF', 'H.265'),
    ('The Foo 2000 1080p DTS x265-ASDF', 'x265'),
)

@pytest.mark.parametrize('release_name, video_codec', video_codec_samples)
def test_video_codec(release_name, video_codec):
    expected = {'type': 'movie', 'title': 'The Foo', 'year': '2000',
                'screen_size': '1080p',
                'audio_codec': 'DTS', 'video_codec': video_codec, 'group': 'ASDF'}
    assert_guess(release_name, **expected)


edition_samples = (
    ('The Foo 2000 EXTENDED 1080p DTS x264-ASDF', ['Extended']),
    ('The Foo 2000 DC Uncut 1080p DTS x264-ASDF', ["Director's Cut", 'Uncut']),
)

@pytest.mark.parametrize('release_name, edition', edition_samples)
def test_edition(release_name, edition):
    expected = {'type': 'movie', 'title': 'The Foo', 'year': '2000',
                'edition': edition, 'screen_size': '1080p',
                'audio_codec': 'DTS', 'video_codec': 'x264', 'group': 'ASDF'}
    assert_guess(release_name, **expected)
