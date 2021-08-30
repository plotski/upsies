import asyncio
import re
import time
from unittest.mock import Mock, PropertyMock, call, patch

import pytest

from upsies.utils.release import Episodes, ReleaseName
from upsies.utils.types import ReleaseType


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def run_async(awaitable):
    return asyncio.get_event_loop().run_until_complete(awaitable)


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_name_argument(ReleaseInfo_mock, mocker):
    rn = ReleaseName('path/to/something', name='the real something')
    assert ReleaseInfo_mock.call_args_list == [call('the real something')]
    assert rn._info is ReleaseInfo_mock.return_value


def test_set_release_info(mocker):
    mocker.patch('upsies.utils.video.audio_format', return_value='DTS')
    rn = ReleaseName('path/to/Foo Season 1 1080p BluRay DTS-ASDF/Foo S01E02 Uncut x264.mkv')
    assert str(rn) == 'Foo S01E02 1080p BluRay Uncut DTS x264-ASDF'
    rn.set_release_info('path/to/Bar Season 2 720p Limited WEBDL FLAC-AsdF/Bar S02E03 x265.mkv')
    assert str(rn) == 'Bar S02E03 720p WEB-DL Limited DTS x265-AsdF'


@patch('upsies.utils.release.ReleaseInfo', Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='path, name, translate, exp_repr',
    argvalues=(
        ('path/to/something', None, None,
         "ReleaseName('path/to/something')"),
        ('path/to/something', 'The Name', None,
         "ReleaseName('path/to/something', name='The Name')"),
        ('path/to/something', 'The Name', {'foo': 'bar'},
         "ReleaseName('path/to/something', name='The Name', translate={'foo': 'bar'})"),
        ('path/to/something', None, {'foo': 'bar'},
         "ReleaseName('path/to/something', translate={'foo': 'bar'})"),
    ),
)
def test_repr(path, name, translate, exp_repr):
    rn = ReleaseName(path=path, name=name, translate=translate)
    assert repr(rn) == exp_repr


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_str(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with patch.object(rn, 'format') as format_mock:
        format_mock.return_value = 'Pretty Release Name'
        assert str(rn) == 'Pretty Release Name'
        format_mock.call_args_list == [call()]

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_len(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert len(rn) == 21

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
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


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
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


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_type_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').type is ReleaseType.movie
    ReleaseInfo_mock.return_value = {'type': ReleaseType.season}
    assert ReleaseName('path/to/something').type is ReleaseType.season
    ReleaseInfo_mock.return_value = {'type': ReleaseType.episode}
    assert ReleaseName('path/to/something').type is ReleaseType.episode
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').type is ReleaseType.unknown

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='value, exp_value',
    argvalues=(
        ('movie', ReleaseType.movie),
        ('season', ReleaseType.season),
        ('episode', ReleaseType.episode),
        ('', ReleaseType.unknown),
        (ReleaseType.movie, ReleaseType.movie),
        (ReleaseType.season, ReleaseType.season),
        (ReleaseType.episode, ReleaseType.episode),
        (ReleaseType.unknown, ReleaseType.unknown),
    ),
)
def test_type_setter_with_valid_value(ReleaseInfo_mock, value, exp_value):
    rn = ReleaseName('path/to/something')
    rn.type = value
    assert rn.type is exp_value

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_type_setter_with_invalid_value(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    with pytest.raises(ValueError, match=r"^'asdf' is not a valid ReleaseType$"):
        rn.type = 'asdf'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo'}
    assert ReleaseName('path/to/something').title == 'The Foo'
    ReleaseInfo_mock.return_value = {'title': 'The Bar'}
    assert ReleaseName('path/to/something').title == 'The Bar'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.title != 'The Baz'
    rn.title = 'The Baz'
    assert rn.title == 'The Baz'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'Bar', 'year': '2015'}
    translation = {
        'title': {
            re.compile(r'o+'): r'00',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    rn.year_required = True
    assert rn.title == 'The F00'
    assert rn.title_aka == 'Bar'
    assert rn.title_with_aka == 'The F00 AKA Bar'
    assert rn.title_with_aka_and_year == 'The F00 AKA Bar 2015'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_aka_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': ''}
    assert ReleaseName('path/to/something').title_aka == ''
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'The Bar'}
    assert ReleaseName('path/to/something').title_aka == 'The Bar'
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'The Foo'}
    assert ReleaseName('path/to/something').title_aka == ''

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_aka_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.title_aka != 'The Baz'
    rn.title_aka = 'The Baz'
    assert rn.title_aka == 'The Baz'
    rn.title = 'The Baz'
    assert rn.title_aka == ''

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_aka_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'Bar', 'year': '2015'}
    translation = {
        'title_aka': {
            re.compile(r'(\w+)r'): r'R-\1',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    rn.year_required = True
    assert rn.title == 'The Foo'
    assert rn.title_aka == 'R-Ba'
    assert rn.title_with_aka == 'The Foo AKA R-Ba'
    assert rn.title_with_aka_and_year == 'The Foo AKA R-Ba 2015'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_with_aka(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': ''}
    assert ReleaseName('path/to/something').title_with_aka == 'The Foo'
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'The Bar'}
    assert ReleaseName('path/to/something').title_with_aka == 'The Foo AKA The Bar'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_with_aka_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'Bar', 'year': '2015'}
    translation = {
        'title_with_aka': {
            re.compile(r' +AKA +'): r': ',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    rn.year_required = True
    assert rn.title == 'The Foo'
    assert rn.title_aka == 'Bar'
    assert rn.title_with_aka == 'The Foo: Bar'
    assert rn.title_with_aka_and_year == 'The Foo: Bar 2015'


@pytest.mark.parametrize(
    argnames='release_info, year_required, exp_title_with_aka_and_year',
    argvalues=(
        ({'title': 'The Foo', 'aka': '', 'year': '2015'}, True, 'The Foo 2015'),
        ({'title': 'The Foo', 'aka': '', 'year': '2015'}, False, 'The Foo'),
        ({'title': 'The Foo', 'aka': 'The Bar', 'year': '2015'}, False, 'The Foo AKA The Bar'),
        ({'title': 'The Foo', 'aka': 'The Bar', 'year': '2015'}, True, 'The Foo AKA The Bar 2015'),
        ({'title': 'The Foo', 'aka': 'The Bar', 'year': ''}, False, 'The Foo AKA The Bar'),
        ({'title': 'The Foo', 'aka': 'The Bar', 'year': ''}, True, 'The Foo AKA The Bar UNKNOWN_YEAR'),
    ),
    ids=lambda v: str(v),
)
@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_with_aka_and_year(ReleaseInfo_mock, release_info, year_required, exp_title_with_aka_and_year):
    ReleaseInfo_mock.return_value = release_info
    rn = ReleaseName('path/to/something')
    rn.year_required = year_required
    assert rn.title_with_aka_and_year == exp_title_with_aka_and_year

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_title_with_aka_and_year_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'title': 'The Foo', 'aka': 'Bar', 'year': '2015'}
    translation = {
        'title_with_aka_and_year': {
            re.compile(r'(.*) (\d+)'): r'"\1" \2',
            re.compile(r'(\d+)'): r'(\1)',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    rn.year_required = True
    assert rn.title == 'The Foo'
    assert rn.title_aka == 'Bar'
    assert rn.title_with_aka == 'The Foo AKA Bar'
    assert rn.title_with_aka_and_year == '"The Foo AKA Bar" (2015)'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_year_getter_with_movie(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'year': '2000', 'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').year == '2000'
    ReleaseInfo_mock.return_value = {'year': '', 'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').year == 'UNKNOWN_YEAR'
    ReleaseInfo_mock.return_value = {'type': ReleaseType.movie}
    assert ReleaseName('path/to/something').year == 'UNKNOWN_YEAR'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize('type', (ReleaseType.season, ReleaseType.episode))
def test_year_getter_with_series(ReleaseInfo_mock, type):
    ReleaseInfo_mock.return_value = {'year': '2000', 'type': type}
    assert ReleaseName('path/to/something').year == '2000'
    ReleaseInfo_mock.return_value = {'year': '', 'type': type}
    assert ReleaseName('path/to/something').year == ''
    ReleaseInfo_mock.return_value = {'type': type}
    assert ReleaseName('path/to/something').year == ''

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='year, exp_year',
    argvalues=(
        ('1880', '1880'),
        ('1990', '1990'),
        ('2015', '2015'),
        (time.strftime('%Y'), time.strftime('%Y')),
        (int(time.strftime('%Y')) + 1, str(int(time.strftime('%Y')) + 1)),
        (int(time.strftime('%Y')) + 2, str(int(time.strftime('%Y')) + 2)),
        ('', ''),
        (None, ''),
    ),
)
def test_year_setter_with_valid_year(ReleaseInfo_mock, year, exp_year):
    rn = ReleaseName('path/to/something')
    assert rn.year == ''
    rn.year = year
    assert rn.year == exp_year

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='year, exp_exception, exp_message',
    argvalues=(
        ([], TypeError, 'Not a number: []'),
        ('foo', ValueError, 'Invalid year: foo'),
        ('1879', ValueError, 'Invalid year: 1879'),
        (int(time.strftime('%Y')) + 3, ValueError, f'Invalid year: {int(time.strftime("%Y")) + 3}'),
    ),
)
def test_year_setter_with_invalid_year(ReleaseInfo_mock, year, exp_exception, exp_message):
    rn = ReleaseName('path/to/something')
    assert rn.year == ''
    with pytest.raises(exp_exception, match=rf'^{re.escape(exp_message)}$'):
        rn.year = year

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_year_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'year': '2012'}
    translation = {
        'year': {
            re.compile(r'(\d+)'): r'\1 CE',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.year == '2012 CE'
    rn.year = '1995'
    assert rn.year == '1995 CE'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, year_required, year, exp_year',
    argvalues=(
        (ReleaseType.movie, False, '1234', '1234'),
        (ReleaseType.movie, False, '', 'UNKNOWN_YEAR'),
        (ReleaseType.movie, True, '1234', '1234'),
        (ReleaseType.movie, True, '', 'UNKNOWN_YEAR'),
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
    if type is ReleaseType.movie:
        assert rn.year_required is True
    else:
        assert rn.year_required is False
    rn.year_required = year_required
    assert rn.year_required is year_required
    assert rn.year == exp_year


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episodes, exp_string',
    argvalues=(
        (ReleaseType.movie, Episodes({}), ''),
        (ReleaseType.movie, Episodes({3: ()}), ''),
        (ReleaseType.movie, Episodes({3: (1, 2), 4: ()}), ''),
        (ReleaseType.movie, Episodes({3: (1, 2), 4: (3, 4)}), ''),

        (ReleaseType.season, Episodes({}), 'UNKNOWN_SEASON'),
        (ReleaseType.season, Episodes({3: ()}), 'S03'),
        (ReleaseType.season, Episodes({3: (), 4: ()}), 'S03S04'),
        (ReleaseType.season, Episodes({3: (1, 2), 4: ()}), 'S03E01E02S04'),
        (ReleaseType.season, Episodes({3: (1, 2), 4: (3, 4)}), 'S03E01E02S04E03E04'),

        (ReleaseType.episode, Episodes({}), 'UNKNOWN_EPISODE'),
        (ReleaseType.episode, Episodes({3: ()}), 'UNKNOWN_EPISODE'),
        (ReleaseType.episode, Episodes({3: (), 4: ()}), 'UNKNOWN_EPISODE'),
        (ReleaseType.episode, Episodes({3: (1, 2), 4: ()}), 'S03E01E02S04'),
        (ReleaseType.episode, Episodes({3: (1, 2), 4: (3, 4)}), 'S03E01E02S04E03E04'),

        (ReleaseType.unknown, Episodes({}), ''),
        (ReleaseType.unknown, Episodes({3: ()}), 'S03'),
        (ReleaseType.unknown, Episodes({3: (), 4: ()}), 'S03S04'),
        (ReleaseType.unknown, Episodes({3: (1, 2), 4: ()}), 'S03E01E02S04'),
        (ReleaseType.unknown, Episodes({3: (1, 2), 4: (3, 4)}), 'S03E01E02S04E03E04'),
    ),
)
def test_episodes_getter(ReleaseInfo_mock, type, episodes, exp_string):
    ReleaseInfo_mock.return_value = {'episodes': episodes, 'type': type}
    assert ReleaseName('path/to/something').episodes == exp_string

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, value, exp_episodes',
    argvalues=(
        (ReleaseType.movie, 'foo.S03S04.bar', ''),
        (ReleaseType.movie, '3', ''),
        (ReleaseType.movie, 3, ''),
        (ReleaseType.movie, (3, '4'), ''),
        (ReleaseType.movie, {3: (1, 2), '4': ()}, ''),
        (ReleaseType.movie, '', ''),
        (ReleaseType.season, 'foo.S03S04.bar', 'S03S04'),
        (ReleaseType.season, 'foo.S03E10.bar', 'S03E10'),
        (ReleaseType.season, '3', 'S03'),
        (ReleaseType.season, 3, 'S03'),
        (ReleaseType.season, (3, '4'), 'S03S04'),
        (ReleaseType.season, {3: (1, 2), '4': ()}, 'S03E01E02S04'),
        (ReleaseType.season, '', 'UNKNOWN_SEASON'),
        (ReleaseType.episode, 'foo.S03S04.bar', 'UNKNOWN_EPISODE'),
        (ReleaseType.episode, 'foo.S03E10.bar', 'S03E10'),
        (ReleaseType.episode, 'foo.S03E10E11.bar', 'S03E10E11'),
        (ReleaseType.episode, '3', 'UNKNOWN_EPISODE'),
        (ReleaseType.episode, 3, 'UNKNOWN_EPISODE'),
        (ReleaseType.episode, (3, '4'), 'UNKNOWN_EPISODE'),
        (ReleaseType.episode, {3: (1, 2), '4': ()}, 'S03E01E02S04'),
        (ReleaseType.episode, '', 'UNKNOWN_EPISODE'),
        (ReleaseType.unknown, 'foo.S03S04.bar', 'S03S04'),
        (ReleaseType.unknown, 'foo.S03E10.bar', 'S03E10'),
        (ReleaseType.unknown, 'foo.S03E10E11.bar', 'S03E10E11'),
        (ReleaseType.unknown, '3', 'S03'),
        (ReleaseType.unknown, 3, 'S03'),
        (ReleaseType.unknown, (3, '4'), 'S03S04'),
        (ReleaseType.unknown, {3: (1, 2), '4': ()}, 'S03E01E02S04'),
        (ReleaseType.unknown, '', ''),
    ),
)
def test_episodes_setter_with_valid_value(ReleaseInfo_mock, type, value, exp_episodes):
    rn = ReleaseName('path/to/something')
    rn.type = type
    rn.episodes = value
    assert rn.episodes == exp_episodes

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_episodes_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'episodes': Episodes({3: ()})}
    translation = {
        'episodes': {
            re.compile(r'S0*'): r'Season ',
            re.compile(r'E0*'): r', Episode ',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.episodes == 'Season 3'
    rn.episodes = 'S03E12'
    assert rn.episodes == 'Season 3, Episode 12'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, episode_title, exp_episode_title',
    argvalues=(
        (ReleaseType.movie, 'Something', ''),
        (ReleaseType.movie, '', ''),
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

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize('episode_title, exp_episode_title', (('Foo', 'Foo'), (123, '123')))
def test_episode_title_setter(ReleaseInfo_mock, episode_title, exp_episode_title):
    rn = ReleaseName('path/to/something')
    rn.type = ReleaseType.episode
    rn.episode_title = episode_title
    assert rn.episode_title == exp_episode_title

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_episode_title_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'episode_title': 'This Episode', 'type': ReleaseType.episode}
    translation = {
        'episode_title': {
            re.compile(r'(?i:this)'): r'That',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.episode_title == 'That Episode'
    rn.episode_title = 'foo'
    assert rn.episode_title == 'foo'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_service_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'service': 'FOO'}
    assert ReleaseName('path/to/something').service == 'FOO'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_service_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.service == ''
    rn.service = 'FOO'
    assert rn.service == 'FOO'
    rn.service = 256
    assert rn.service == '256'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_service_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'service': 'Asdf'}
    translation = {
        'service': {
            re.compile(r'Asdf'): r'ASDF',
            re.compile(r'(.*)TV'): r'Tee\1Vee',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.service == 'ASDF'
    rn.service = 'AsdfTV'
    assert rn.service == 'TeeASDFVee'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_edition_getter_returns_same_list_with_no_edition(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.edition is rn.edition
    assert isinstance(rn.edition, list)

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_edition_getter_returns_same_list_with_given_edition(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'edition': ['DC', 'Unrated']}
    rn = ReleaseName('path/to/something')
    assert rn.edition == ['DC', 'Unrated']
    assert rn.edition is rn.edition
    assert isinstance(rn.edition, list)

@patch('upsies.utils.release.ReleaseInfo', Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='edition_list, has_dual_audio, exp_edition',
    argvalues=(
        ([], True, ['Dual Audio']),
        ([], False, []),
        (['Dual Audio'], True, ['Dual Audio']),
        (['Dual Audio'], False, []),
        (['Dual Audio', 'Dual Audio'], False, []),
    ),
)
def test_edition_getter_autodetects_dual_audio(edition_list, has_dual_audio, exp_edition, mocker):
    rn = ReleaseName('path/to/something')
    rn._info['edition'] = edition_list
    mocker.patch.object(type(rn), 'has_dual_audio', PropertyMock(return_value=has_dual_audio))
    # Ensure "Dual Audio" is only appended once
    for _ in range(3):
        assert rn.edition == exp_edition

@patch('upsies.utils.release.ReleaseInfo', Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='edition_list, hdr_format, exp_edition',
    argvalues=(
        ([], 'HDR', ['HDR']),
        (['HDR'], 'HDR', ['HDR']),
        (['HDR10'], 'HDR', ['HDR']),
        (['HDR'], 'HDR10', ['HDR10']),
        (['HDR10'], 'HDR10', ['HDR10']),
        (['HDR10', 'HDR10'], 'HDR10', ['HDR10']),
    ),
)
def test_edition_getter_autodetects_hdr_format(edition_list, hdr_format, exp_edition, mocker):
    rn = ReleaseName('path/to/something')
    rn._info['edition'] = edition_list
    mocker.patch.object(type(rn), 'hdr_format', PropertyMock(return_value=hdr_format))
    # Ensure HDR format is only appended once
    for _ in range(3):
        assert rn.edition == exp_edition

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
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

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_edition_is_translated(ReleaseInfo_mock, mocker):
    ReleaseInfo_mock.return_value = {'edition': ['foo', 'bar', 'baz']}
    rn = ReleaseName('path/to/something')
    translation = {
        'edition': {
            re.compile(r'o+'): r'00',
            re.compile(r'b(\w+)'): r'\1F',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.edition == ['f00', 'arF', 'azF']
    rn.edition = ('noo', 'nar', 'naz')
    assert rn.edition == ['n00', 'nar', 'naz']


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
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

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
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

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_source_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'source': 'Blu-Ray'}
    translation = {
        'source': {
            re.compile(r'-'): r'',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.source == 'BluRay'
    rn.source = 'asdf'
    assert rn.source == 'asdf'
    rn.source = 'WEB-DL'
    assert rn.source == 'WEBDL'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@patch('upsies.utils.video.resolution')
def test_resolution_getter_prefers_mediainfo(resolution_mock, ReleaseInfo_mock):
    resolution_mock.return_value = '720p'
    ReleaseInfo_mock.return_value = {'resolution': '1080p'}
    assert ReleaseName('path/to/something').resolution == '720p'
    assert resolution_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@patch('upsies.utils.video.resolution')
def test_resolution_getter_defaults_to_guess(resolution_mock, ReleaseInfo_mock):
    resolution_mock.return_value = None
    ReleaseInfo_mock.return_value = {'resolution': '1080p'}
    assert ReleaseName('path/to/something').resolution == '1080p'
    assert resolution_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@patch('upsies.utils.video.resolution')
def test_resolution_getter_defaults_to_placeholder(resolution_mock, ReleaseInfo_mock):
    resolution_mock.return_value = None
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').resolution == 'UNKNOWN_RESOLUTION'
    assert resolution_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_resolution_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.resolution == 'UNKNOWN_RESOLUTION'
    rn.resolution = '1080p'
    assert rn.resolution == '1080p'
    rn.resolution = ''
    assert rn.resolution == 'UNKNOWN_RESOLUTION'
    rn.resolution = 1080
    assert rn.resolution == '1080'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@patch('upsies.utils.video.resolution')
def test_resolution_is_translated(resolution_mock, ReleaseInfo_mock):
    resolution_mock.return_value = None
    ReleaseInfo_mock.return_value = {'resolution': '1080i'}
    translation = {
        'resolution': {
            re.compile(r'(\d+)i'): r'\1I',
            re.compile(r'x'): r':',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.resolution == '1080I'
    rn.resolution = 'asdf'
    assert rn.resolution == 'asdf'
    rn.resolution = '1080x1920'
    assert rn.resolution == '1080:1920'


@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_format')
def test_audio_format_getter_prefers_mediainfo(audio_format_mock, ReleaseInfo_mock):
    audio_format_mock.return_value = 'AC3'
    ReleaseInfo_mock.return_value = {'audio_codec': 'DD+'}
    assert ReleaseName('path/to/something').audio_format == 'AC3'
    assert audio_format_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_format')
def test_audio_format_getter_defaults_to_guess(audio_format_mock, ReleaseInfo_mock):
    audio_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_codec': 'DD+'}
    assert ReleaseName('path/to/something').audio_format == 'DD+'
    assert audio_format_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_format')
def test_audio_format_getter_defaults_to_placeholder(audio_format_mock, ReleaseInfo_mock):
    audio_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_codec': ''}
    assert ReleaseName('path/to/something').audio_format == 'UNKNOWN_AUDIO_FORMAT'
    assert audio_format_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
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

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_format')
def test_audio_format_is_translated(audio_format_mock, ReleaseInfo_mock):
    audio_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_codec': 'fooo'}
    translation = {
        'audio_format': {
            re.compile(r'\w(o+)'): r'b\1',
            re.compile(r'oo'): r'00',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.audio_format == 'b00o'
    rn.audio_format = 'asdf'
    assert rn.audio_format == 'asdf'
    rn.audio_format = 'noooo'
    assert rn.audio_format == 'b0000'


@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_channels')
def test_audio_channels_getter_prefers_mediainfo(audio_channels_mock, ReleaseInfo_mock):
    audio_channels_mock.return_value = '5.1'
    ReleaseInfo_mock.return_value = {'audio_channels': '7.1'}
    assert ReleaseName('path/to/something').audio_channels == '5.1'
    assert audio_channels_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_channels')
def test_audio_channels_getter_defaults_to_guess(audio_channels_mock, ReleaseInfo_mock):
    audio_channels_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_channels': '7.1'}
    assert ReleaseName('path/to/something').audio_channels == '7.1'
    assert audio_channels_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_channels')
def test_audio_channels_getter_defaults_to_empty_string(audio_channels_mock, ReleaseInfo_mock):
    audio_channels_mock.return_value = None
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').audio_channels == ''
    assert audio_channels_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
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

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.audio_channels')
def test_audio_channels_is_translated(audio_channels_mock, ReleaseInfo_mock):
    audio_channels_mock.return_value = None
    ReleaseInfo_mock.return_value = {'audio_channels': '5.1'}
    translation = {'audio_channels': {re.compile(r'\.'): r':'}}
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.audio_channels == '5:1'
    rn.audio_channels = 'asdf'
    assert rn.audio_channels == 'asdf'
    rn.audio_channels = '2.0'
    assert rn.audio_channels == '2:0'


@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.video_format')
def test_video_format_getter_prefers_mediainfo(video_format_mock, ReleaseInfo_mock):
    video_format_mock.return_value = 'x264'
    ReleaseInfo_mock.return_value = {'video_codec': 'x265'}
    assert ReleaseName('path/to/something').video_format == 'x264'
    assert video_format_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.video_format')
def test_video_format_getter_defaults_to_guess(video_format_mock, ReleaseInfo_mock):
    video_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'video_codec': 'x265'}
    assert ReleaseName('path/to/something').video_format == 'x265'
    assert video_format_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.video_format')
def test_video_format_getter_defaults_to_placeholder(video_format_mock, ReleaseInfo_mock):
    video_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').video_format == 'UNKNOWN_VIDEO_FORMAT'
    assert video_format_mock.call_args_list == [call('path/to/something', default=None)]

@patch('upsies.utils.release.ReleaseInfo')
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

@patch('upsies.utils.release.ReleaseInfo')
@patch('upsies.utils.video.video_format')
def test_video_format_is_translated(video_format_mock, ReleaseInfo_mock):
    video_format_mock.return_value = None
    ReleaseInfo_mock.return_value = {'video_codec': 'x264'}
    translation = {
        'video_format': {
            re.compile(r'x(\d+)'): r'H.\1',
            re.compile(r'H\.?'): r'Harry',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.video_format == 'Harry264'
    rn.video_format = 'asdf'
    assert rn.video_format == 'asdf'
    rn.video_format = 'H265'
    assert rn.video_format == 'Harry265'


@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_group_getter(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'group': 'ASDF'}
    assert ReleaseName('path/to/something').group == 'ASDF'
    ReleaseInfo_mock.return_value = {'release_group': ''}
    assert ReleaseName('path/to/something').group == 'NOGROUP'
    ReleaseInfo_mock.return_value = {}
    assert ReleaseName('path/to/something').group == 'NOGROUP'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_group_setter(ReleaseInfo_mock):
    rn = ReleaseName('path/to/something')
    assert rn.group == 'NOGROUP'
    rn.group = 'ASDF'
    assert rn.group == 'ASDF'
    rn.group = ''
    assert rn.group == 'NOGROUP'
    rn.group = 123
    assert rn.group == '123'

@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
def test_group_is_translated(ReleaseInfo_mock):
    ReleaseInfo_mock.return_value = {'group': 'A-SDF'}
    translation = {
        'group': {
            re.compile(r'-'): r'_',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.group == 'A_SDF'
    rn.group = 'F-o-o'
    assert rn.group == 'F_o_o'


@pytest.mark.parametrize(
    argnames='path_exists, has_commentary, release_info, exp_value',
    argvalues=(
        ('path_exists', True, {'has_commentary': True}, True),
        ('path_exists', True, {'has_commentary': False}, True),

        ('path_exists', False, {'has_commentary': True}, False),
        ('path_exists', False, {'has_commentary': False}, False),

        ('path_exists', None, {'has_commentary': True}, False),
        ('path_exists', None, {'has_commentary': False}, False),

        ('path_does_not_exist', True, {'has_commentary': True}, True),
        ('path_does_not_exist', True, {'has_commentary': False}, False),

        ('path_does_not_exist', False, {'has_commentary': True}, True),
        ('path_does_not_exist', False, {'has_commentary': False}, False),

        ('path_does_not_exist', None, {'has_commentary': True}, True),
        ('path_does_not_exist', None, {'has_commentary': False}, False),
    ),
    ids=lambda v: str(v),
)
def test_has_commentary(path_exists, has_commentary, release_info, exp_value, mocker):
    mocker.patch(
        'upsies.utils.video.has_commentary',
        Mock(return_value=has_commentary),
    )
    mocker.patch(
        'upsies.utils.release.ReleaseInfo',
        Mock(return_value=release_info),
    )
    mocker.patch(
        'os.path.exists',
        Mock(return_value=True if path_exists == 'path_exists' else False),
    )
    rn = ReleaseName('path/to/something')
    assert rn.has_commentary is exp_value
    rn.has_commentary = ''
    assert rn.has_commentary is False
    rn.has_commentary = 1
    assert rn.has_commentary is True
    rn.has_commentary = None
    assert rn.has_commentary is exp_value


@pytest.mark.parametrize(
    argnames='path_exists, has_dual_audio, release_info, exp_value',
    argvalues=(
        ('path_exists', True, {'edition': ['Dual Audio']}, True),
        ('path_exists', True, {'edition': []}, True),

        ('path_exists', False, {'edition': ['Dual Audio']}, False),
        ('path_exists', False, {'edition': []}, False),

        ('path_exists', None, {'edition': ['Dual Audio']}, False),
        ('path_exists', None, {'edition': []}, False),

        ('path_does_not_exist', True, {'edition': ['Dual Audio']}, True),
        ('path_does_not_exist', True, {'edition': []}, False),

        ('path_does_not_exist', False, {'edition': ['Dual Audio']}, True),
        ('path_does_not_exist', False, {'edition': []}, False),

        ('path_does_not_exist', None, {'edition': ['Dual Audio']}, True),
        ('path_does_not_exist', None, {'edition': []}, False),
    ),
    ids=lambda v: str(v),
)
def test_has_dual_audio(path_exists, has_dual_audio, release_info, exp_value, mocker):
    mocker.patch(
        'upsies.utils.video.has_dual_audio',
        Mock(return_value=has_dual_audio),
    )
    mocker.patch(
        'upsies.utils.release.ReleaseInfo',
        Mock(return_value=release_info),
    )
    mocker.patch(
        'os.path.exists',
        Mock(return_value=True if path_exists == 'path_exists' else False),
    )
    rn = ReleaseName('path/to/something')
    assert rn.has_dual_audio is exp_value
    rn.has_dual_audio = ''
    assert rn.has_dual_audio is False
    rn.has_dual_audio = 1
    assert rn.has_dual_audio is True
    rn.has_dual_audio = None
    assert rn.has_dual_audio is exp_value


@pytest.mark.parametrize(
    argnames='path_exists, hdr_format, release_info, exp_value',
    argvalues=(
        ('path_does_not_exist', 'Dolby Vision', {'edition': ['HDR10']}, 'HDR10'),
        ('path_exists', 'Dolby Vision', {'edition': ['HDR10']}, 'Dolby Vision'),
        ('path_exists', None, {'edition': ['HDR10']}, 'HDR10'),
        ('path_exists', None, {'edition': ['HDR10', 'Dolby Vision', 'HDR', 'HDR10+']}, 'Dolby Vision'),
        ('path_exists', None, {'edition': ['HDR10', 'HDR10+', 'HDR']}, 'HDR10+'),
        ('path_exists', None, {'edition': ['HDR', 'HDR10']}, 'HDR10'),
        ('path_exists', None, {'edition': ['HDR']}, 'HDR'),
        ('path_exists', None, {'edition': []}, None),
    ),
    ids=lambda v: str(v),
)
def test_hdr_format(path_exists, hdr_format, release_info, exp_value, mocker):
    mocker.patch('upsies.utils.video.hdr_format', Mock(return_value=hdr_format))
    mocker.patch('upsies.utils.release.ReleaseInfo', Mock(return_value=release_info))
    mocker.patch(
        'os.path.exists',
        Mock(return_value=True if path_exists == 'path_exists' else False),
    )
    rn = ReleaseName('path/to/something')
    assert rn.hdr_format == exp_value
    rn.hdr_format = ''
    assert rn.hdr_format == ''
    for hdr_format in ('HDR10', 'Dolby Vision'):
        rn.hdr_format = hdr_format
        assert rn.hdr_format == hdr_format
    rn.hdr_format = None
    assert rn.hdr_format == exp_value

def test_hdr_format_is_set_to_invalid_value(mocker):
    mocker.patch('upsies.utils.video.hdr_formats', ('foo', 'bar'))
    rn = ReleaseName('path/to/something')
    for hdr_format in ('foo', 'bar'):
        rn.hdr_format = hdr_format
        assert rn.hdr_format == hdr_format
    with pytest.raises(ValueError, match=r"^Unknown HDR format: 'baz'$"):
        rn.hdr_format = 'baz'

def test_hdr_format_is_translated(mocker):
    mocker.patch('upsies.utils.release.ReleaseInfo', Mock(return_value={'edition': ['HDR10']}))
    translation = {
        'hdr_format': {
            re.compile(r'(?i:hdr)'): r'ABC',
        },
    }
    rn = ReleaseName('path/to/something', translate=translation)
    assert rn.hdr_format == 'ABC10'
    rn.hdr_format = 'Dolby Vision'
    assert rn.hdr_format == 'Dolby Vision'
    rn.hdr_format = 'HDR10+'
    assert rn.hdr_format == 'ABC10+'


@pytest.mark.parametrize('release_type', tuple(ReleaseType), ids=lambda v: repr(v))
def test_is_complete_handles_all_ReleaseTypes(release_type):
    rn = ReleaseName('path/to/something')
    rn.type = release_type
    assert rn.is_complete is False

@pytest.mark.parametrize(
    argnames='release_name, release_type, needed_attrs',
    argvalues=(
        ('The Foo 1998 1080p BluRay DTS x264-ASDF', ReleaseType.movie, ReleaseName._needed_attrs[ReleaseType.movie]),
        ('The Foo S03 1080p BluRay DTS x264-ASDF', ReleaseType.season, ReleaseName._needed_attrs[ReleaseType.season]),
        ('The Foo S03E04 1080p BluRay DTS x264-ASDF', ReleaseType.episode, ReleaseName._needed_attrs[ReleaseType.episode]),
    ),
    ids=lambda v: str(v),
)
def test_is_complete(release_name, release_type, needed_attrs):
    rn = ReleaseName(release_name)
    rn.type = release_type
    assert rn.is_complete is True
    for attr in needed_attrs:
        value = getattr(rn, attr)
        setattr(rn, attr, '')
        assert rn.type is release_type
        assert rn.is_complete is False
        setattr(rn, attr, value)
        assert rn.is_complete is True


@pytest.mark.parametrize('callback', (None, Mock()))
@pytest.mark.parametrize(
    argnames='guessed_type, found_type, exp_type',
    argvalues=(
        (ReleaseType.movie, ReleaseType.season, ReleaseType.season),
    ),
)
@pytest.mark.asyncio
async def test_fetch_info(guessed_type, found_type, exp_type, callback, mocker):
    rn = ReleaseName('Foo 2000 1080p BluRay DTS x264-ASDF')
    rn.type = guessed_type

    async def update_attributes(id):
        await asyncio.sleep(0.1)
        rn.type = found_type

    async def update_year_required():
        assert rn.type == found_type

    mocker.patch.object(rn, '_update_attributes', update_attributes)
    mocker.patch.object(rn, '_update_year_required', update_year_required)
    return_value = await rn.fetch_info('mock id', callback=callback)
    assert return_value is rn
    assert rn.type == exp_type
    if callback:
        assert callback.call_args_list == [call(rn)]


@patch('upsies.utils.webdbs.imdb.ImdbApi')
@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
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
        'year': '',
    }
    ImdbApi_mock.return_value.gather = AsyncMock(return_value=gather_mock)
    ReleaseInfo_mock.return_value = {'type': guessed_type}
    rn = ReleaseName('path/to/something')
    assert rn.type == guessed_type
    run_async(rn._update_attributes(id_mock))
    assert rn.title == 'Le Foo'
    assert rn.title_aka == 'The Foo'
    if exp_type is ReleaseType.movie:
        assert rn.year == 'UNKNOWN_YEAR'
    else:
        assert rn.year == ''
    assert rn.type == exp_type
    assert ImdbApi_mock.return_value.gather.call_args_list == [
        call(id_mock, 'type', 'title_english', 'title_original', 'year'),
    ]


@patch('upsies.utils.webdbs.imdb.ImdbApi')
@patch('upsies.utils.release.ReleaseInfo', new_callable=lambda: Mock(return_value={}))
@pytest.mark.parametrize(
    argnames='type, results, exp_year_required',
    argvalues=(
        (ReleaseType.movie, (Mock(title='The Foo'), Mock(title='the bar')), True),
        (ReleaseType.movie, (Mock(title='The Foo'), Mock(title='the föö')), True),
        (ReleaseType.season, (Mock(title='The Foo'), Mock(title='the bar')), None),
        (ReleaseType.season, (Mock(title='The Foo'), Mock(title='the föö')), True),
        (ReleaseType.episode, (Mock(title='The Foo'), Mock(title='the bar')), None),
        (ReleaseType.episode, (Mock(title='The Foo'), Mock(title='the föö')), True),
    ),
    ids=lambda v: str(v),
)
def test_update_year_required(ReleaseInfo_mock, ImdbApi_mock, type, results, exp_year_required):
    ImdbApi_mock.return_value.search = AsyncMock(return_value=results)
    ReleaseInfo_mock.return_value = {'type': type, 'title': 'The Foo'}
    rn = ReleaseName('path/to/something')
    orig_year_required = rn.year_required
    if type is ReleaseType.movie:
        assert rn.year_required is True
    else:
        assert rn.year_required is False
    run_async(rn._update_year_required())
    if exp_year_required is None:
        assert rn.year_required is orig_year_required
    else:
        assert rn.year_required is exp_year_required
