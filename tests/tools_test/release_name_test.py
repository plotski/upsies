import asyncio
from unittest.mock import Mock, call, patch

import pytest

from upsies.tools.release_name import ReleaseName


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


def run_async(awaitable):
    return asyncio.get_event_loop().run_until_complete(awaitable)


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_str(guessit_mock):
    rn = ReleaseName('path/to/something')
    with patch.object(rn, 'format') as format_mock:
        format_mock.return_value = 'Pretty Release Name'
        assert str(rn) == 'Pretty Release Name'
        format_mock.call_args_list == [call()]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_len(guessit_mock):
    rn = ReleaseName('path/to/something')
    with patch.object(rn, 'format') as format_mock:
        format_mock.return_value = 'Pretty Release Name'
        assert len(rn) == len('Pretty Release Name')
        format_mock.call_args_list == [call()]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='attr',
    argvalues=(
        'type', 'title', 'title_aka', 'year', 'season', 'episode',
        'episode_title', 'service', 'edition', 'source', 'resolution', 'audio_format',
        'audio_channels', 'video_format', 'group')
)
def test_getitem(guessit_mock, attr):
    guessit_mock.return_value = {attr: 'mock value', 'type': 'movie'}
    rn = ReleaseName('path/to/something')
    if not attr.startswith('_'):
        rn[attr]
    with pytest.raises(KeyError, match=r"^'format'$"):
        assert rn['format']


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_usage_as_dictionary_in_str_format(guessit_mock):
    guessit_mock.return_value = {
        'type': 'movie',
        'title': 'The Foo',
        'year': '1998',
        'source': 'BluRay',
        'resolution': '1080p',
        'audio_codec': 'AC3',
        'audio_channels': '5.1',
        'video_codec': 'x264',
        'release_group': 'ASDF',
    }
    rn = ReleaseName('path/to/something')
    fmt = '{title} ({year}) {audio_format} {video_format} {source}-{group}'
    assert fmt.format(**rn) == 'The Foo (1998) AC3 x264 BluRay-ASDF'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_type_getter(guessit_mock):
    guessit_mock.return_value = {'type': 'movie'}
    assert ReleaseName('path/to/something').type == 'movie'
    guessit_mock.return_value = {'type': 'season'}
    assert ReleaseName('path/to/something').type == 'season'
    guessit_mock.return_value = {}
    assert ReleaseName('path/to/something').type == ''

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='value, exp_value',
    argvalues=(
        ('movie', 'movie'),
        ('season', 'season'),
        ('episode', 'episode'),
        ('', ''),
    ),
)
def test_type_setter_with_valid_value(guessit_mock, value, exp_value):
    rn = ReleaseName('path/to/something')
    rn.type = value
    assert rn.type == exp_value

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_type_setter_with_invalid_value(guessit_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(ValueError, match=r"^Invalid type: 'asdf'$"):
        rn.type = 'asdf'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_title_getter(guessit_mock):
    guessit_mock.return_value = {'title': 'The Foo'}
    assert ReleaseName('path/to/something').title == 'The Foo'
    guessit_mock.return_value = {'title': 'The Bar'}
    assert ReleaseName('path/to/something').title == 'The Bar'

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_title_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.title != 'The Baz'
    rn.title = 'The Baz'
    assert rn.title == 'The Baz'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_title_aka_getter(guessit_mock):
    guessit_mock.return_value = {'title': 'The Foo', 'aka': ''}
    assert ReleaseName('path/to/something').title_aka == ''
    guessit_mock.return_value = {'title': 'The Foo', 'aka': 'The Bar'}
    assert ReleaseName('path/to/something').title_aka == 'The Bar'
    guessit_mock.return_value = {'title': 'The Foo', 'aka': 'The Foo'}
    assert ReleaseName('path/to/something').title_aka == ''

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_title_aka_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.title_aka != 'The Baz'
    rn.title_aka = 'The Baz'
    assert rn.title_aka == 'The Baz'
    rn.title = 'The Baz'
    assert rn.title_aka == ''


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_year_getter_with_movie(guessit_mock):
    guessit_mock.return_value = {'year': '2000', 'type': 'movie'}
    assert ReleaseName('path/to/something').year == '2000'
    guessit_mock.return_value = {'year': '', 'type': 'movie'}
    assert ReleaseName('path/to/something').year == 'UNKNOWN_YEAR'
    guessit_mock.return_value = {'type': 'movie'}
    assert ReleaseName('path/to/something').year == 'UNKNOWN_YEAR'

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize('type', ('season', 'episode'))
def test_year_getter_with_series(guessit_mock, type):
    guessit_mock.return_value = {'year': '2000', 'type': type}
    assert ReleaseName('path/to/something').year == '2000'
    guessit_mock.return_value = {'year': '', 'type': type}
    assert ReleaseName('path/to/something').year == ''
    guessit_mock.return_value = {'type': type}
    assert ReleaseName('path/to/something').year == ''

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_year_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.year == ''
    rn.year = '1999'
    assert rn.year == '1999'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, year_required, year, exp_year',
    argvalues=(
        ('movie', False, '1234', '1234'),
        ('movie', False, '', 'UNKNOWN_YEAR'),
        ('movie', True, '1234', '1234'),
        ('movie', True, '', 'UNKNOWN_YEAR'),
        ('season', False, '1234', '1234'),
        ('season', False, '', ''),
        ('season', True, '1234', '1234'),
        ('season', True, '', 'UNKNOWN_YEAR'),
        ('episode', False, '1234', '1234'),
        ('episode', False, '', ''),
        ('episode', True, '1234', '1234'),
        ('episode', True, '', 'UNKNOWN_YEAR'),
    ),
)
def test_year_required(guessit_mock, type, year_required, year, exp_year):
    guessit_mock.return_value = {'year': year, 'type': type}
    rn = ReleaseName('path/to/something')
    assert rn.year_required is False
    rn.year_required = year_required
    assert rn.year == exp_year


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, season, exp_season',
    argvalues=(
        ('movie', '3', ''),
        ('movie', '', ''),
        ('season', '3', '3'),
        ('season', '', 'UNKNOWN_SEASON'),
        ('episode', '3', '3'),
        ('episode', '', 'UNKNOWN_SEASON'),
    ),
)
def test_season_getter(guessit_mock, type, season, exp_season):
    guessit_mock.return_value = {'season': season, 'type': type}
    assert ReleaseName('path/to/something').season == exp_season

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, season, exp_season',
    argvalues=(
        ('movie', '3', ''),
        ('movie', 3, ''),
        ('movie', '', ''),
        ('season', '3', '3'),
        ('season', 3, '3'),
        ('season', '', 'UNKNOWN_SEASON'),
        ('episode', '3', '3'),
        ('episode', 3, '3'),
        ('episode', '', 'UNKNOWN_SEASON'),
    ),
)
def test_season_setter_with_valid_value(guessit_mock, type, season, exp_season):
    rn = ReleaseName('path/to/something')
    rn.type = type
    rn.season = season
    assert rn.season == exp_season

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_season_setter_with_invalid_type(guessit_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(TypeError, match=r'^Invalid season: \(1, 2, 3\)$'):
        rn.season = (1, 2, 3)
    with pytest.raises(TypeError, match=r"^Invalid season: 1.3$"):
        rn.season = 1.3

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_season_setter_with_invalid_value(guessit_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(ValueError, match=r"^Invalid season: 'foo'$"):
        rn.season = 'foo'
    with pytest.raises(ValueError, match=r"^Invalid season: -1$"):
        rn.season = -1


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episode, exp_episode',
    argvalues=(
        ('movie', '3', ''),
        ('movie', ['1', '2'], ''),
        ('movie', '', ''),
        ('season', '3', '3'),
        ('season', ['1', '2'], ['1', '2']),
        ('season', '', ''),
        ('episode', '3', '3'),
        ('episode', ['1', '2'], ['1', '2']),
        ('episode', '', ''),
    ),
)
def test_episode_getter(guessit_mock, type, episode, exp_episode):
    guessit_mock.return_value = {'episode': episode, 'type': type}
    assert ReleaseName('path/to/something').episode == exp_episode
    guessit_mock.return_value = {'episode': episode, 'type': type, 'season': '1'}
    assert ReleaseName('path/to/something').episode == exp_episode

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episode, exp_episode',
    argvalues=(
        ('movie', '3', ''),
        ('movie', 3, ''),
        ('movie', [1, '2'], ''),
        ('movie', '', ''),
        ('season', '3', '3'),
        ('season', 3, '3'),
        ('season', [1, '2'], ['1', '2']),
        ('season', '', ''),
        ('episode', '3', '3'),
        ('episode', 3, '3'),
        ('episode', [1, '2'], ['1', '2']),
        ('episode', '', ''),
    ),
)
def test_episode_setter_with_valid_value(guessit_mock, type, episode, exp_episode):
    rn = ReleaseName('path/to/something')
    rn.type = type
    assert rn.episode == ''
    rn.episode = episode
    assert rn.episode == exp_episode

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_episode_setter_with_invalid_type(guessit_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(TypeError, match=r"^Invalid episode: 1.3$"):
        rn.episode = 1.3

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_episode_setter_with_invalid_value(guessit_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(ValueError, match=r"^Invalid episode: 'foo'$"):
        rn.episode = 'foo'
    with pytest.raises(ValueError, match=r"^Invalid episode: -1$"):
        rn.episode = -1


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episode_title, exp_episode_title',
    argvalues=(
        ('movie', 'Something', ''),
        ('movie', '', ''),
        ('season', 'Something', ''),
        ('season', '', ''),
        ('episode', 'Something', 'Something'),
        ('episode', '', ''),
    ),
)
def test_episode_title_getter(guessit_mock, type, episode_title, exp_episode_title):
    guessit_mock.return_value = {'episode_title': episode_title, 'type': type}
    assert ReleaseName('path/to/something').episode_title == exp_episode_title

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize('episode_title, exp_episode_title', (('Foo', 'Foo'), (123, '123')))
def test_episode_title_setter(guessit_mock, episode_title, exp_episode_title):
    rn = ReleaseName('path/to/something')
    rn.type = 'episode'
    rn.episode_title = episode_title
    assert rn.episode_title == exp_episode_title


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_service_getter(guessit_mock):
    guessit_mock.return_value = {'streaming_service': 'FOO'}
    assert ReleaseName('path/to/something').service == 'FOO'

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_service_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.service == ''
    rn.service = 'FOO'
    assert rn.service == 'FOO'
    rn.service = 256
    assert rn.service == '256'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_edition_getter_returns_same_list_with_no_edition(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.edition is rn.edition
    assert isinstance(rn.edition, list)

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_edition_getter_returns_same_list_with_given_edition(guessit_mock):
    guessit_mock.return_value = {'edition': ['DC', 'Unrated']}
    rn = ReleaseName('path/to/something')
    assert rn.edition == ['DC', 'Unrated']
    assert rn.edition is rn.edition
    assert isinstance(rn.edition, list)

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='edition, exp_edition',
    argvalues=(
        (('DC',), ['DC']),
        ((1, 2, 3), ['1', '2', '3']),
    ),
)
def test_edition_setter(guessit_mock, edition, exp_edition):
    rn = ReleaseName('path/to/something')
    rn.edition = edition
    assert rn.edition == exp_edition
    assert rn.edition is rn.edition


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='source, exp_source',
    argvalues=(
        ('WEB-DL', 'WEB-DL'),
        ('', 'UNKNOWN_SOURCE'),
    ),
)
def test_source_getter(guessit_mock, source, exp_source):
    guessit_mock.return_value = {'source': source}
    assert ReleaseName('path/to/something').source == exp_source

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='source, exp_source',
    argvalues=(
        ('BluRay', 'BluRay'),
        ('', 'UNKNOWN_SOURCE'),
        (123, '123'),
    ),
)
def test_source_setter(guessit_mock, source, exp_source):
    rn = ReleaseName('path/to/something')
    rn.source = source
    assert rn.source == exp_source


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_resolution_getter_prefers_mediainfo(mediainfo_mock, guessit_mock):
    mediainfo_mock.resolution.return_value = '720p'
    guessit_mock.return_value = {'screen_size': '1080p'}
    assert ReleaseName('path/to/something').resolution == '720p'
    assert mediainfo_mock.resolution.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_resolution_getter_defaults_to_guessit(mediainfo_mock, guessit_mock):
    mediainfo_mock.resolution.return_value = None
    guessit_mock.return_value = {'screen_size': '1080p'}
    assert ReleaseName('path/to/something').resolution == '1080p'
    assert mediainfo_mock.resolution.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_resolution_getter_defaults_to_placeholder(mediainfo_mock, guessit_mock):
    mediainfo_mock.resolution.return_value = None
    guessit_mock.return_value = {}
    assert ReleaseName('path/to/something').resolution == 'UNKNOWN_RESOLUTION'
    assert mediainfo_mock.resolution.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_resolution_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.resolution == 'UNKNOWN_RESOLUTION'
    rn.resolution = '1080p'
    assert rn.resolution == '1080p'
    rn.resolution = ''
    assert rn.resolution == 'UNKNOWN_RESOLUTION'
    rn.resolution = 1080
    assert rn.resolution == '1080'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_audio_format_getter_prefers_mediainfo(mediainfo_mock, guessit_mock):
    mediainfo_mock.audio_format.return_value = 'AC3'
    guessit_mock.return_value = {'audio_codec': 'DD+'}
    assert ReleaseName('path/to/something').audio_format == 'AC3'
    assert mediainfo_mock.audio_format.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_audio_format_getter_defaults_to_guessit(mediainfo_mock, guessit_mock):
    mediainfo_mock.audio_format.return_value = None
    guessit_mock.return_value = {'audio_codec': 'DD+'}
    assert ReleaseName('path/to/something').audio_format == 'DD+'
    assert mediainfo_mock.audio_format.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_audio_format_getter_defaults_to_placeholder(mediainfo_mock, guessit_mock):
    mediainfo_mock.audio_format.return_value = None
    guessit_mock.return_value = {'audio_codec': ''}
    assert ReleaseName('path/to/something').audio_format == 'UNKNOWN_AUDIO_FORMAT'
    assert mediainfo_mock.audio_format.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_audio_format_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.audio_format == 'UNKNOWN_AUDIO_FORMAT'
    rn.audio_format = 'AC3'
    assert rn.audio_format == 'AC3'
    rn.audio_format = ''
    assert rn.audio_format == 'UNKNOWN_AUDIO_FORMAT'
    rn.audio_format = 'DD+'
    assert rn.audio_format == 'DD+'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_audio_channels_getter_prefers_mediainfo(mediainfo_mock, guessit_mock):
    mediainfo_mock.audio_channels.return_value = '5.1'
    guessit_mock.return_value = {'audio_channels': '7.1'}
    assert ReleaseName('path/to/something').audio_channels == '5.1'
    assert mediainfo_mock.audio_channels.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_audio_channels_getter_defaults_to_guessit(mediainfo_mock, guessit_mock):
    mediainfo_mock.audio_channels.return_value = None
    guessit_mock.return_value = {'audio_channels': '7.1'}
    assert ReleaseName('path/to/something').audio_channels == '7.1'
    assert mediainfo_mock.audio_channels.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_audio_channels_getter_defaults_to_empty_string(mediainfo_mock, guessit_mock):
    mediainfo_mock.audio_channels.return_value = None
    guessit_mock.return_value = {}
    assert ReleaseName('path/to/something').audio_channels == ''
    assert mediainfo_mock.audio_channels.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_audio_channels_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.audio_channels == ''
    rn.audio_channels = '2.0'
    assert rn.audio_channels == '2.0'
    rn.audio_channels = ''
    assert rn.audio_channels == ''
    rn.audio_channels = 2.0
    assert rn.audio_channels == '2.0'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_video_format_getter_prefers_mediainfo(mediainfo_mock, guessit_mock):
    mediainfo_mock.video_format.return_value = 'x264'
    guessit_mock.return_value = {'video_codec': 'x265'}
    assert ReleaseName('path/to/something').video_format == 'x264'
    assert mediainfo_mock.video_format.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_video_format_getter_defaults_to_guessit(mediainfo_mock, guessit_mock):
    mediainfo_mock.video_format.return_value = None
    guessit_mock.return_value = {'video_codec': 'x265'}
    assert ReleaseName('path/to/something').video_format == 'x265'
    assert mediainfo_mock.video_format.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@patch('upsies.tools.release_name.mediainfo')
def test_video_format_getter_defaults_to_placeholder(mediainfo_mock, guessit_mock):
    mediainfo_mock.video_format.return_value = None
    guessit_mock.return_value = {}
    assert ReleaseName('path/to/something').video_format == 'UNKNOWN_VIDEO_FORMAT'
    assert mediainfo_mock.video_format.call_args_list == [call('path/to/something')]

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_video_format_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.video_format == 'UNKNOWN_VIDEO_FORMAT'
    rn.video_format = 'x265'
    assert rn.video_format == 'x265'
    rn.video_format = ''
    assert rn.video_format == 'UNKNOWN_VIDEO_FORMAT'
    rn.video_format = 264
    assert rn.video_format == '264'


@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_group_getter(guessit_mock):
    guessit_mock.return_value = {'release_group': 'ASDF'}
    assert ReleaseName('path/to/something').group == 'ASDF'
    guessit_mock.return_value = {'release_group': ''}
    assert ReleaseName('path/to/something').group == 'NOGROUP'
    guessit_mock.return_value = {}
    assert ReleaseName('path/to/something').group == 'NOGROUP'

@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
def test_group_setter(guessit_mock):
    rn = ReleaseName('path/to/something')
    assert rn.group == 'NOGROUP'
    rn.group = 'ASDF'
    assert rn.group == 'ASDF'
    rn.group = ''
    assert rn.group == 'NOGROUP'
    rn.group = 123
    assert rn.group == '123'


@patch('upsies.tools.dbs.imdb')
@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='guessit_type, imdb_type, exp_type',
    argvalues=(
        ('movie', 'movie', 'movie'),
        ('movie', 'season', 'season'),
        ('movie', 'episode', 'episode'),
        ('movie', '', 'movie'),
        ('season', 'movie', 'movie'),
        ('season', 'season', 'season'),
        ('season', 'episode', 'episode'),
        ('season', '', 'season'),
        # For episodes, we trust guessit more than IMDb
        ('episode', 'movie', 'episode'),
        ('episode', 'season', 'episode'),
        ('episode', 'episode', 'episode'),
        ('episode', '', 'episode'),
    ),
)
def test_update_attributes(guessit_mock, imdb_mock, guessit_type, imdb_type, exp_type):
    id_mock = '12345'
    info_mock = {
        'type': imdb_type,
        'title_original': 'Le Foo',
        'title_english': 'The Foo',
        'year': '2010',
    }
    imdb_mock.info = AsyncMock(return_value=info_mock)
    guessit_mock.return_value = {'type': guessit_type}
    rn = ReleaseName('path/to/something')
    assert rn.type == guessit_type
    run_async(rn._update_attributes(id_mock))
    assert rn.title == 'Le Foo'
    assert rn.title_aka == 'The Foo'
    assert rn.year == '2010'
    assert rn.type == exp_type
    assert imdb_mock.info.call_args_list == [
        call(id_mock, imdb_mock.type, imdb_mock.title_english, imdb_mock.title_original, imdb_mock.year),
    ]


_unique_titles = (Mock(title='The Foo'), Mock(title='The Bar'))
_same_titles = (Mock(title='The Foo'), Mock(title='The Foo'))

@patch('upsies.tools.dbs.imdb')
@patch('upsies.utils.guessit.guessit', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, results, exp_year_required',
    argvalues=(
        ('movie', _unique_titles, False),
        ('movie', _same_titles, False),
        ('season', _unique_titles, False),
        ('season', _same_titles, True),
        ('episode', _unique_titles, False),
        ('episode', _same_titles, True),
    ),
)
def test_update_year_required(guessit_mock, imdb_mock, type, results, exp_year_required):
    imdb_mock.search = AsyncMock(return_value=results)
    guessit_mock.return_value = {'type': type, 'title': 'The Foo'}
    rn = ReleaseName('path/to/something')
    assert rn.year_required is False
    run_async(rn._update_year_required())
    assert rn.year_required is exp_year_required
