import asyncio
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.utils import ReleaseType
from upsies.utils.release_info import ReleaseName


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


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_tracks_is_called_during_instantiation(ReleaseInfo_mock, mocker):
    mocker.patch.object(asyncio.get_event_loop(), 'run_in_executor')
    rn = ReleaseName('path/to/something')
    assert asyncio.get_event_loop().run_in_executor.call_args_list == [
        call(None, rn._tracks),
    ]

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='raised_exception, exp_exception, exp_message',
    argvalues=(
        (None, None, None),
        (errors.ContentError('no such file'), None, None),
        (RuntimeError('Argh'), RuntimeError, 'Argh'),
    ),
    ids=lambda v: repr(v),
)
def test_tracks_raises(ReleaseInfo_mock, raised_exception, exp_exception, exp_message, mocker):
    mocker.patch.object(asyncio.get_event_loop(), 'run_in_executor')
    mocker.patch('upsies.utils.video.tracks', side_effect=raised_exception)
    rn = ReleaseName('path/to/something')
    if exp_exception:
        with pytest.raises(exp_exception, match=rf'^{exp_message}$'):
            rn._tracks()


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_str(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with patch.object(rn, 'format') as format_mock:
        format_mock.return_value = 'Pretty Release Name'
        assert str(rn) == 'Pretty Release Name'
        format_mock.call_args_list == [call()]

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_len(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert len(rn) == 17

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='attr',
    argvalues=tuple(ReleaseName('')),
)
def test_getitem(ReleaseInfo_mock, attr):
    ReleaseInfo_mock.return_value = {attr: 'mock value', 'type': ReleaseType.movie}
    rn = ReleaseName('path/to/something')
    if not attr.startswith('_'):
        rn[attr]
    with pytest.raises(KeyError, match=r"^'format'$"):
        rn['format']
    with pytest.raises(TypeError, match=r"^Not a string: 123$"):
        rn[123]


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_usage_as_dictionary_in_str_format(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {
        'type': ReleaseType.movie,
        'title': 'The Foo',
        'year': '1998',
        'source': 'BluRay',
        'resolution': '1080p',
        'audio_codec': 'AC3',
        'audio_channels': '5.1',
        'video_codec': 'x264',
        'group': 'ASDF',
    }
    rn = ReleaseName('path/to/something')
    fmt = '{title} ({year}) {audio_format} {video_format} {source}-{group}'
    assert fmt.format(**rn) == 'The Foo (1998) AC3 x264 BluRay-ASDF'


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_type_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').type is ReleaseType.movie
    ReleaseInfo_mock.return_value = {'type': ReleaseType.series}
    assert ReleaseName('path/to/something').type is ReleaseType.series
    ReleaseInfo_mock.return_value = {'type': ReleaseType.season}
    assert ReleaseName('path/to/something').type is ReleaseType.season
    ReleaseInfo_mock.return_value = {'type': ReleaseType.episode}
    assert ReleaseName('path/to/something').type is ReleaseType.episode
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').type is ReleaseType.unknown

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='value, exp_value',
    argvalues=(
        ('movie', ReleaseType.movie),
        ('series', ReleaseType.series),
        ('season', ReleaseType.season),
        ('episode', ReleaseType.episode),
        ('', ReleaseType.unknown),
        (ReleaseType.movie, ReleaseType.movie),
        (ReleaseType.series, ReleaseType.series),
        (ReleaseType.season, ReleaseType.season),
        (ReleaseType.episode, ReleaseType.episode),
        (ReleaseType.unknown, ReleaseType.unknown),
    ),
)
def test_type_setter_with_valid_value(ReleaseInfo_mock, value, exp_value):
    rn = ReleaseName('path/to/something')
    rn.type = value
    assert rn.type is exp_value

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_type_setter_with_invalid_value(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(ValueError, match=r"^'asdf' is not a valid ReleaseType$"):
        rn.type = 'asdf'


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo'}
    assert ReleaseName('path/to/something').title == 'The Foo'
    ReleaseInfo_mock.return_value = {'title': 'The Bar'}
    assert ReleaseName('path/to/something').title == 'The Bar'

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.title != 'The Baz'
    rn.title = 'The Baz'
    assert rn.title == 'The Baz'


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_aka_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': ''}
    assert ReleaseName('path/to/something').title_aka == ''
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'The Bar'}
    assert ReleaseName('path/to/something').title_aka == 'The Bar'
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'The Foo'}
    assert ReleaseName('path/to/something').title_aka == ''

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_aka_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.title_aka != 'The Baz'
    rn.title_aka = 'The Baz'
    assert rn.title_aka == 'The Baz'
    rn.title = 'The Baz'
    assert rn.title_aka == ''


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_year_getter_with_movie(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'year': '2000', 'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').year == '2000'
    ReleaseInfo_mock.return_value = {'year': '', 'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').year == 'UNKNOWN_YEAR'
    ReleaseInfo_mock.return_value = {'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').year == 'UNKNOWN_YEAR'

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize('type', (ReleaseType.series, ReleaseType.season, ReleaseType.episode))
def test_year_getter_with_series(ReleaseInfo_mock, type):
    ReleaseInfo_mock.return_value = {'year': '2000', 'type': type}
    assert ReleaseName('path/to/something').year == '2000'
    ReleaseInfo_mock.return_value = {'year': '', 'type': type}
    assert ReleaseName('path/to/something').year == ''
    ReleaseInfo_mock.return_value = {'type': type}
    assert ReleaseName('path/to/something').year == ''

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_year_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.year == ''
    rn.year = '1999'
    assert rn.year == '1999'
    with pytest.raises(TypeError, match=r'^Not a number: \(2, 0, 2, 0\)$'):
        rn.year = (2, 0, 2, 0)
    with pytest.raises(ValueError, match=r'^Invalid year: 123$'):
        rn.year = '123'

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, year_required, year, exp_year',
    argvalues=(
        (ReleaseType.movie, False, '1234', '1234'),
        (ReleaseType.movie, False, '', 'UNKNOWN_YEAR'),
        (ReleaseType.movie, True, '1234', '1234'),
        (ReleaseType.movie, True, '', 'UNKNOWN_YEAR'),
        (ReleaseType.series, False, '1234', '1234'),
        (ReleaseType.series, False, '', ''),
        (ReleaseType.series, True, '1234', '1234'),
        (ReleaseType.series, True, '', 'UNKNOWN_YEAR'),
        (ReleaseType.season, False, '1234', '1234'),
        (ReleaseType.season, False, '', ''),
        (ReleaseType.season, True, '1234', '1234'),
        (ReleaseType.season, True, '', 'UNKNOWN_YEAR'),
        (ReleaseType.episode, False, '1234', '1234'),
        (ReleaseType.episode, False, '', ''),
        (ReleaseType.episode, True, '1234', '1234'),
        (ReleaseType.episode, True, '', 'UNKNOWN_YEAR'),
        (ReleaseType.unknown, False, '1234', '1234'),
        (ReleaseType.unknown, False, '', ''),
        (ReleaseType.unknown, True, '1234', '1234'),
        (ReleaseType.unknown, True, '', 'UNKNOWN_YEAR'),
    ),
)
def test_year_required(ReleaseInfo_mock, type, year_required, year, exp_year):
    ReleaseInfo_mock.return_value = {'year': year, 'type': type}
    rn = ReleaseName('path/to/something')
    assert rn.year_required is False
    rn.year_required = year_required
    assert rn.year == exp_year


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, season, exp_season',
    argvalues=(
        (ReleaseType.movie, '3', ''),
        (ReleaseType.movie, '', ''),
        (ReleaseType.series, '3', '3'),
        (ReleaseType.series, '', 'UNKNOWN_SEASON'),
        (ReleaseType.season, '3', '3'),
        (ReleaseType.season, '', 'UNKNOWN_SEASON'),
        (ReleaseType.episode, '3', '3'),
        (ReleaseType.episode, '', 'UNKNOWN_SEASON'),
        (ReleaseType.unknown, '3', '3'),
        (ReleaseType.unknown, '', ''),
    ),
)
def test_season_getter(ReleaseInfo_mock, type, season, exp_season):
    ReleaseInfo_mock.return_value = {'season': season, 'type': type}
    assert ReleaseName('path/to/something').season == exp_season

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, season, exp_season',
    argvalues=(
        (ReleaseType.movie, '3', ''),
        (ReleaseType.movie, 3, ''),
        (ReleaseType.movie, '', ''),
        (ReleaseType.series, '3', '3'),
        (ReleaseType.series, 3, '3'),
        (ReleaseType.series, '', 'UNKNOWN_SEASON'),
        (ReleaseType.season, '3', '3'),
        (ReleaseType.season, 3, '3'),
        (ReleaseType.season, '', 'UNKNOWN_SEASON'),
        (ReleaseType.episode, '3', '3'),
        (ReleaseType.episode, 3, '3'),
        (ReleaseType.episode, '', 'UNKNOWN_SEASON'),
        (ReleaseType.unknown, '3', '3'),
        (ReleaseType.unknown, 3, '3'),
        (ReleaseType.unknown, '', ''),
    ),
)
def test_season_setter_with_valid_value(ReleaseInfo_mock, type, season, exp_season):
    rn = ReleaseName('path/to/something')
    rn.type = type
    rn.season = season
    assert rn.season == exp_season

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_season_setter_with_invalid_type(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(TypeError, match=r'^Invalid season: \(1, 2, 3\)$'):
        rn.season = (1, 2, 3)
    with pytest.raises(TypeError, match=r"^Invalid season: 1.3$"):
        rn.season = 1.3

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_season_setter_with_invalid_value(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(ValueError, match=r"^Invalid season: 'foo'$"):
        rn.season = 'foo'
    with pytest.raises(ValueError, match=r"^Invalid season: -1$"):
        rn.season = -1


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episode, exp_episode',
    argvalues=(
        (ReleaseType.movie, '3', ''),
        (ReleaseType.movie, ['1', '2'], ''),
        (ReleaseType.movie, '', ''),
        (ReleaseType.series, '3', '3'),
        (ReleaseType.series, ['1', '2'], ['1', '2']),
        (ReleaseType.series, '', ''),
        (ReleaseType.season, '3', '3'),
        (ReleaseType.season, ['1', '2'], ['1', '2']),
        (ReleaseType.season, '', ''),
        (ReleaseType.episode, '3', '3'),
        (ReleaseType.episode, ['1', '2'], ['1', '2']),
        (ReleaseType.episode, '', ''),
        (ReleaseType.unknown, '3', '3'),
        (ReleaseType.unknown, ['1', '2'], ['1', '2']),
        (ReleaseType.unknown, '', ''),
    ),
)
def test_episode_getter(ReleaseInfo_mock, type, episode, exp_episode):
    ReleaseInfo_mock.return_value = {'episode': episode, 'type': type}
    assert ReleaseName('path/to/something').episode == exp_episode
    ReleaseInfo_mock.return_value = {'episode': episode, 'type': type, 'season': '1'}
    assert ReleaseName('path/to/something').episode == exp_episode

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episode, exp_episode',
    argvalues=(
        (ReleaseType.movie, '3', ''),
        (ReleaseType.movie, 3, ''),
        (ReleaseType.movie, [1, '2'], ''),
        (ReleaseType.movie, '', ''),
        (ReleaseType.series, '3', '3'),
        (ReleaseType.series, 3, '3'),
        (ReleaseType.series, [1, '2'], ['1', '2']),
        (ReleaseType.series, '', ''),
        (ReleaseType.season, '3', '3'),
        (ReleaseType.season, 3, '3'),
        (ReleaseType.season, [1, '2'], ['1', '2']),
        (ReleaseType.season, '', ''),
        (ReleaseType.episode, '3', '3'),
        (ReleaseType.episode, 3, '3'),
        (ReleaseType.episode, [1, '2'], ['1', '2']),
        (ReleaseType.episode, '', ''),
        (ReleaseType.unknown, '3', '3'),
        (ReleaseType.unknown, 3, '3'),
        (ReleaseType.unknown, [1, '2'], ['1', '2']),
        (ReleaseType.unknown, '', ''),
    ),
)
def test_episode_setter_with_valid_value(ReleaseInfo_mock, type, episode, exp_episode):
    rn = ReleaseName('path/to/something')
    rn.type = type
    assert rn.episode == ''
    rn.episode = episode
    assert rn.episode == exp_episode

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_episode_setter_with_invalid_type(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(TypeError, match=r"^Invalid episode: 1.3$"):
        rn.episode = 1.3

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_episode_setter_with_invalid_value(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(ValueError, match=r"^Invalid episode: 'foo'$"):
        rn.episode = 'foo'
    with pytest.raises(ValueError, match=r"^Invalid episode: -1$"):
        rn.episode = -1


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episode_title, exp_episode_title',
    argvalues=(
        (ReleaseType.movie, 'Something', ''),
        (ReleaseType.movie, '', ''),
        (ReleaseType.series, 'Something', ''),
        (ReleaseType.series, '', ''),
        (ReleaseType.season, 'Something', ''),
        (ReleaseType.season, '', ''),
        (ReleaseType.episode, 'Something', 'Something'),
        (ReleaseType.episode, '', ''),
        (ReleaseType.unknown, 'Something', ''),
        (ReleaseType.unknown, '', ''),
    ),
)
def test_episode_title_getter(ReleaseInfo_mock, type, episode_title, exp_episode_title):
    ReleaseInfo_mock.return_value = {'episode_title': episode_title, 'type': type}
    rn = ReleaseName('path/to/something')
    assert rn.episode_title == exp_episode_title
    rn.type = ReleaseType.episode
    assert rn.episode_title == episode_title

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize('episode_title, exp_episode_title', (('Foo', 'Foo'), (123, '123')))
def test_episode_title_setter(ReleaseInfo_mock, episode_title, exp_episode_title):
    rn = ReleaseName('path/to/something')
    rn.type = ReleaseType.episode
    rn.episode_title = episode_title
    assert rn.episode_title == exp_episode_title


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_service_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'service': 'FOO'}
    assert ReleaseName('path/to/something').service == 'FOO'

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_service_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.service == ''
    rn.service = 'FOO'
    assert rn.service == 'FOO'
    rn.service = 256
    assert rn.service == '256'


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_edition_getter_returns_same_list_with_no_edition(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.edition is rn.edition
    assert isinstance(rn.edition, list)

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_edition_getter_returns_same_list_with_given_edition(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'edition': ['DC', 'Unrated']}
    rn = ReleaseName('path/to/something')
    assert rn.edition == ['DC', 'Unrated']
    assert rn.edition is rn.edition
    assert isinstance(rn.edition, list)

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='edition, exp_edition',
    argvalues=(
        (('DC',), ['DC']),
        ((1, 2, 3), ['1', '2', '3']),
    ),
)
def test_edition_setter(ReleaseInfo_mock, edition, exp_edition):
    rn = ReleaseName('path/to/something')
    rn.edition = edition
    assert rn.edition == exp_edition
    assert rn.edition is rn.edition


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='source, exp_source',
    argvalues=(
        ('WEB-DL', 'WEB-DL'),
        ('', 'UNKNOWN_SOURCE'),
    ),
)
def test_source_getter(ReleaseInfo_mock, source, exp_source):
    ReleaseInfo_mock.return_value = {'source': source}
    assert ReleaseName('path/to/something').source == exp_source

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='source, exp_source',
    argvalues=(
        ('BluRay', 'BluRay'),
        ('', 'UNKNOWN_SOURCE'),
        (123, '123'),
    ),
)
def test_source_setter(ReleaseInfo_mock, source, exp_source):
    rn = ReleaseName('path/to/something')
    rn.source = source
    assert rn.source == exp_source


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@patch('upsies.utils.video.resolution')
def test_resolution_getter_prefers_mediainfo(resolution_mock, ReleaseInfo_mock):
    resolution_mock.return_value = '720p'
    ReleaseInfo_mock.return_value = {'resolution': '1080p'}
    assert ReleaseName('path/to/something').resolution == '720p'
    assert resolution_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@patch('upsies.utils.video.resolution')
def test_resolution_getter_defaults_to_guess(resolution_mock, ReleaseInfo_mock):
    resolution_mock.return_value = None
    ReleaseInfo_mock.return_value = {'resolution': '1080p'}
    assert ReleaseName('path/to/something').resolution == '1080p'
    assert resolution_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@patch('upsies.utils.video.resolution')
def test_resolution_getter_defaults_to_placeholder(resolution_mock, ReleaseInfo_mock):
    resolution_mock.return_value = None
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').resolution == 'UNKNOWN_RESOLUTION'
    assert resolution_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_resolution_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.resolution == 'UNKNOWN_RESOLUTION'
    rn.resolution = '1080p'
    assert rn.resolution == '1080p'
    rn.resolution = ''
    assert rn.resolution == 'UNKNOWN_RESOLUTION'
    rn.resolution = 1080
    assert rn.resolution == '1080'


@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.audio_format')
def test_audio_format_getter_prefers_mediainfo(audio_format_mock, ReleaseInfo_mock):
    audio_format_mock.return_value = 'AC3'
    ReleaseInfo_mock.return_value = {'audio_codec': 'DD+'}
    assert ReleaseName('path/to/something').audio_format == 'AC3'
    assert audio_format_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.audio_format')
def test_audio_format_getter_defaults_to_guess(audio_format_mock, ReleaseInfo_mock):
    audio_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_codec': 'DD+'}
    assert ReleaseName('path/to/something').audio_format == 'DD+'
    assert audio_format_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.audio_format')
def test_audio_format_getter_defaults_to_placeholder(audio_format_mock, ReleaseInfo_mock):
    audio_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_codec': ''}
    assert ReleaseName('path/to/something').audio_format == 'UNKNOWN_AUDIO_FORMAT'
    assert audio_format_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
def test_audio_format_setter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {}
    rn = ReleaseName('path/to/something')
    assert rn.audio_format == 'UNKNOWN_AUDIO_FORMAT'
    rn.audio_format = 'AC3'
    assert rn.audio_format == 'AC3'
    rn.audio_format = ''
    assert rn.audio_format == 'UNKNOWN_AUDIO_FORMAT'
    rn.audio_format = 'DD+'
    assert rn.audio_format == 'DD+'


@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.audio_channels')
def test_audio_channels_getter_prefers_mediainfo(audio_channels_mock, ReleaseInfo_mock):
    audio_channels_mock.return_value = '5.1'
    ReleaseInfo_mock.return_value = {'audio_channels': '7.1'}
    assert ReleaseName('path/to/something').audio_channels == '5.1'
    assert audio_channels_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.audio_channels')
def test_audio_channels_getter_defaults_to_guess(audio_channels_mock, ReleaseInfo_mock):
    audio_channels_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_channels': '7.1'}
    assert ReleaseName('path/to/something').audio_channels == '7.1'
    assert audio_channels_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.audio_channels')
def test_audio_channels_getter_defaults_to_empty_string(audio_channels_mock, ReleaseInfo_mock):
    audio_channels_mock.return_value = None
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').audio_channels == ''
    assert audio_channels_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
def test_audio_channels_setter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {}
    rn = ReleaseName('path/to/something')
    assert rn.audio_channels == ''
    rn.audio_channels = '2.0'
    assert rn.audio_channels == '2.0'
    rn.audio_channels = ''
    assert rn.audio_channels == ''
    rn.audio_channels = 2.0
    assert rn.audio_channels == '2.0'


@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.video_format')
def test_video_format_getter_prefers_mediainfo(video_format_mock, ReleaseInfo_mock):
    video_format_mock.return_value = 'x264'
    ReleaseInfo_mock.return_value = {'video_codec': 'x265'}
    assert ReleaseName('path/to/something').video_format == 'x264'
    assert video_format_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.video_format')
def test_video_format_getter_defaults_to_guess(video_format_mock, ReleaseInfo_mock):
    video_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'video_codec': 'x265'}
    assert ReleaseName('path/to/something').video_format == 'x265'
    assert video_format_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
@patch('upsies.utils.video.video_format')
def test_video_format_getter_defaults_to_placeholder(video_format_mock, ReleaseInfo_mock):
    video_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').video_format == 'UNKNOWN_VIDEO_FORMAT'
    assert video_format_mock.call_args_list == [call('path/to/something')]

@patch('upsies.utils.release_info.ReleaseInfo')
def test_video_format_setter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {}
    rn = ReleaseName('path/to/something')
    assert rn.video_format == 'UNKNOWN_VIDEO_FORMAT'
    rn.video_format = 'x265'
    assert rn.video_format == 'x265'
    rn.video_format = ''
    assert rn.video_format == 'UNKNOWN_VIDEO_FORMAT'
    rn.video_format = 264
    assert rn.video_format == '264'


@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_group_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'group': 'ASDF'}
    assert ReleaseName('path/to/something').group == 'ASDF'
    ReleaseInfo_mock.return_value = {'release_group': ''}
    assert ReleaseName('path/to/something').group == 'NOGROUP'
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').group == 'NOGROUP'

@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_group_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.group == 'NOGROUP'
    rn.group = 'ASDF'
    assert rn.group == 'ASDF'
    rn.group = ''
    assert rn.group == 'NOGROUP'
    rn.group = 123
    assert rn.group == '123'


@patch('upsies.utils.release_info.ReleaseName._tracks')
@pytest.mark.parametrize(
    argnames='audio_tracks, exp_value',
    argvalues=(
        ([{'Title': 'Something'}, {'Title': 'Commentary with Foo Bar'}], True),
        ([{'Title': 'COMMENTARY'}, {'Title': 'Something'}], True),
        ([{'Title': 'Something'}], False),
        ([], False),
    ),
    ids=lambda v: str(v),
)
def test_has_commentary_getter(tracks_mock, audio_tracks, exp_value):
    tracks_mock.return_value = {'Audio': audio_tracks}
    rn = ReleaseName('path/to/something')
    assert rn.has_commentary is exp_value
    assert rn._guess['has_commentary'] is exp_value

def test_has_commentary_setter():
    rn = ReleaseName('path/to/something')
    assert rn.has_commentary is False
    assert rn._guess['has_commentary'] is False
    rn.has_commentary = 'yes'
    assert rn._guess['has_commentary'] is True


@patch('upsies.utils.webdbs.imdb.ImdbApi')
@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='guessed_type, imdb_type, exp_type',
    argvalues=(
        (ReleaseType.movie, ReleaseType.movie, ReleaseType.movie),
        (ReleaseType.movie, ReleaseType.season, ReleaseType.season),
        (ReleaseType.movie, ReleaseType.episode, ReleaseType.episode),
        (ReleaseType.movie, ReleaseType.unknown, ReleaseType.movie),
        (ReleaseType.season, ReleaseType.movie, ReleaseType.movie),
        (ReleaseType.season, ReleaseType.season, ReleaseType.season),
        (ReleaseType.season, ReleaseType.episode, ReleaseType.episode),
        (ReleaseType.season, ReleaseType.unknown, ReleaseType.season),
        # For episodes, we trust guessed type more than IMDb
        (ReleaseType.episode, ReleaseType.movie, ReleaseType.episode),
        (ReleaseType.episode, ReleaseType.season, ReleaseType.episode),
        (ReleaseType.episode, ReleaseType.episode, ReleaseType.episode),
        (ReleaseType.episode, ReleaseType.unknown, ReleaseType.episode),
    ),
)
def test_update_attributes(ReleaseInfo_mock, ImdbApi_mock, guessed_type, imdb_type, exp_type):
    id_mock = '12345'
    gather_mock = {
        'type': imdb_type,
        'title_original': 'Le Foo',
        'title_english': 'The Foo',
        'year': '2010',
    }
    ImdbApi_mock.return_value.gather = AsyncMock(return_value=gather_mock)
    ReleaseInfo_mock.return_value = {'type': guessed_type}
    rn = ReleaseName('path/to/something')
    assert rn.type == guessed_type
    run_async(rn._update_attributes(id_mock))
    assert rn.title == 'Le Foo'
    assert rn.title_aka == 'The Foo'
    assert rn.year == '2010'
    assert rn.type == exp_type
    assert ImdbApi_mock.return_value.gather.call_args_list == [
        call(id_mock, 'type', 'title_english', 'title_original', 'year'),
    ]


_unique_titles = (Mock(title='The Foo'), Mock(title='The Bar'))
_same_titles = (Mock(title='The Foo'), Mock(title='The Foo'))

@patch('upsies.utils.webdbs.imdb.ImdbApi')
@patch('upsies.utils.release_info.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, results, exp_year_required',
    argvalues=(
        (ReleaseType.movie, _unique_titles, False),
        (ReleaseType.movie, _same_titles, False),
        (ReleaseType.season, _unique_titles, False),
        (ReleaseType.season, _same_titles, True),
        (ReleaseType.episode, _unique_titles, False),
        (ReleaseType.episode, _same_titles, True),
    ),
)
def test_update_year_required(ReleaseInfo_mock, ImdbApi_mock, type, results, exp_year_required):
    ImdbApi_mock.return_value.search = AsyncMock(return_value=results)
    ReleaseInfo_mock.return_value = {'type': type, 'title': 'The Foo'}
    rn = ReleaseName('path/to/something')
    assert rn.year_required is False
    run_async(rn._update_year_required())
    assert rn.year_required is exp_year_required
