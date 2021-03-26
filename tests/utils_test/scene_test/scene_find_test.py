from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.release import Episodes
from upsies.utils.scene import find


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_SceneQuery_from_string(mocker):
    ReleaseInfo_mock = mocker.patch('upsies.utils.release.ReleaseInfo')
    from_release_mock = mocker.patch('upsies.utils.scene.find.SceneQuery.from_release')
    query = find.SceneQuery.from_string('foo')
    assert ReleaseInfo_mock.call_args_list == [call('foo', strict=True)]
    assert from_release_mock.call_args_list == [call(ReleaseInfo_mock.return_value)]
    assert query.keywords == from_release_mock.return_value.keywords
    assert query.group == from_release_mock.return_value.group
    assert query.episodes == from_release_mock.return_value.episodes


@pytest.mark.parametrize(
    argnames='release, needed_keys, exp_keywords, exp_group, exp_episodes',
    argvalues=(
        (
            {
                'title': 'The Foo',
                'year': '2004',
                'resolution': '720p',
                'source': 'BluRay',
                'video_codec': 'x264',
                'group': 'ASDF',
                'episodes': Episodes({}),
            },
            ('title', 'episodes', 'resolution'),
            ('The', 'Foo', '720p'),
            'ASDF',
            {},
        ),
        (
            {
                'title': 'The Foo',
                'year': '',
                'resolution': '720p',
                'source': 'BluRay',
                'video_codec': 'x264',
                'group': 'ASDF',
                'episodes': Episodes({'1': ('1', '2')}),
            },
            ('title', 'source', 'group'),
            ('The', 'Foo', 'BluRay'),
            'ASDF',
            {'1': ('1', '2')},
        ),
    ),
    ids=lambda v: str(v),
)
def test_SceneQuery_from_release(release, needed_keys, exp_keywords, exp_group, exp_episodes, mocker):
    mocker.patch('upsies.utils.scene.common.get_needed_keys', return_value=needed_keys)
    query = find.SceneQuery.from_release(release)
    assert query.keywords == exp_keywords
    assert query.group == exp_group
    assert query.episodes == exp_episodes


@pytest.mark.parametrize(
    argnames='keywords, exp_keywords',
    argvalues=(
        (('foo', 'bar'), ('foo', 'bar')),
        (('foo', 'S01', 'bar'), ('foo', 'bar')),
        (('foo', 'S01E2', 'bar'), ('foo', 'bar')),
        (('foo', 'E3E04S01E2', 'bar'), ('foo', 'bar')),
    ),
)
@pytest.mark.asyncio
async def test_SceneQuery_search_calls_given_coroutine_function(keywords, exp_keywords):
    query = find.SceneQuery(*keywords, group='baz')
    search = AsyncMock(return_value=('20', 'C', '1', 'b'))
    results = await query.search(search)
    assert results == ['1', '20', 'b', 'C']
    assert search.call_args_list == [call(exp_keywords, group='baz')]

@pytest.mark.asyncio
async def test_SceneQuery_search_raises_RequestError():
    query = find.SceneQuery('foo', 'bar', group='baz')
    search = AsyncMock(side_effect=errors.RequestError('no'))
    with pytest.raises(errors.RequestError, match=r'^no$'):
        await query.search(search)


@pytest.mark.parametrize(
    argnames='episodes, exp_matches',
    argvalues=(
        ({}, 'ALL'),
        ({'1': ()}, ['X.S01.x264-ASDF']),
        ({'2': ()}, ['X.S02.x264-ASDF']),
        ({'1': (), '2': ()}, ['X.S01.x264-ASDF', 'X.S02.x264-ASDF']),
        ({'': ('2', '3')}, ['X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'': ('2',), '2': ('1',)}, ['X.S01E02.x264-ASDF', 'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ('2',)}, ['X.S01E02.x264-ASDF']),
        ({'2': ('1', '3')}, ['X.S02E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': ('1',), '2': ('3',)}, ['X.S01E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': (), '2': ('2',)}, ['X.S01.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ('2',), '2': ()}, ['X.S01E02.x264-ASDF', 'X.S02.x264-ASDF']),
        ({'3': ()}, []),
        ({'': ('4',)}, []),
    ),
    ids=lambda v: str(v),
)
def test_SceneQuery_handle_results_without_only_existing_releases(episodes, exp_matches):
    query = find.SceneQuery(episodes=episodes)
    results = [
        'X.2015.x264-ASDF',
        'X.S01E01.x264-ASDF',
        'X.S01E02.x264-ASDF',
        'X.S01E03.x264-ASDF',
        'X.S02E01.x264-ASDF',
        'X.S02E02.x264-ASDF',
        'X.S02E03.x264-ASDF',
    ]
    handled_results = query._handle_results(results, only_existing_releases=False)
    if exp_matches == 'ALL':
        assert handled_results == results
    else:
        assert handled_results == exp_matches

@pytest.mark.parametrize(
    argnames='episodes, exp_matches',
    argvalues=(
        ({}, 'ALL'),
        ({'1': ()}, ['X.S01E01.x264-ASDF', 'X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF']),
        ({'2': ()}, ['X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': (), '2': ()}, ['X.S01E01.x264-ASDF', 'X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF',
                              'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'': ('2', '3')}, ['X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'': ('2',), '2': ('1',)}, ['X.S01E02.x264-ASDF', 'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ('2',)}, ['X.S01E02.x264-ASDF']),
        ({'2': ('1', '3')}, ['X.S02E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': ('1',), '2': ('3',)}, ['X.S01E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': (), '2': ('2',)}, ['X.S01E01.x264-ASDF', 'X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ('2',), '2': ()}, ['X.S01E02.x264-ASDF', 'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'3': ()}, []),
        ({'': ('4',)}, []),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_SceneQuery_handle_results_with_only_existing_releases(episodes, exp_matches):
    query = find.SceneQuery(episodes=episodes)
    results = [
        'X.2015.x264-ASDF',
        'X.S01E01.x264-ASDF',
        'X.S01E02.x264-ASDF',
        'X.S01E03.x264-ASDF',
        'X.S02E01.x264-ASDF',
        'X.S02E02.x264-ASDF',
        'X.S02E03.x264-ASDF',
    ]
    handled_results = query._handle_results(results, only_existing_releases=True)
    if exp_matches == 'ALL':
        assert handled_results == results
    else:
        assert handled_results == exp_matches


def test_SceneQuery_keywords():
    query = find.SceneQuery('foo bar', ' - ', 'baz', '', '  ', 21)
    assert query.keywords == ('foo', 'bar', 'baz', '21')


def test_SceneQuery_group():
    query = find.SceneQuery(group='ASDF')
    assert query.group == 'ASDF'


def test_SceneQuery_episodes():
    query = find.SceneQuery(episodes={'5': ('10',)})
    assert query.episodes == {'5': ('10',)}


@pytest.mark.parametrize(
    argnames='keywords, group, episodes, exp_repr',
    argvalues=(
        (('foo', 'bar', 'baz'), '', {}, "SceneQuery('foo', 'bar', 'baz')"),
        ((), 'ASDF', {}, "SceneQuery(group='ASDF')"),
        ((), '', {'2': ('3', '4', '5')}, "SceneQuery(episodes={'2': ('3', '4', '5')})"),
    )
)
def test_SceneQuery_repr(keywords, group, episodes, exp_repr):
    kwargs = {}
    if group:
        kwargs['group'] = group
    if episodes:
        kwargs['episodes'] = episodes
    assert repr(find.SceneQuery(*keywords, **kwargs)) == exp_repr


@pytest.mark.parametrize(
    argnames='keywords1, keywords2, group1, group2, episodes1, episodes2, exp_equality',
    argvalues=(
        (('foo', 'bar',), ('foo', 'bar',), 'GRP', 'GRP', {1: ()}, {1: ()}, True),
        (('foo', 'bar',), ('foo', 'baz',), 'GRP', 'GRP', {1: ()}, {1: ()}, False),
        (('foo', 'bar',), ('foo', 'bar',), 'GP', 'GRP', {1: ()}, {1: ()}, False),
        (('foo', 'bar',), ('foo', 'bar',), 'GRP', 'GRP', {1: (3,)}, {1: (4,)}, False),
        (('foo', 'bar',), ('foo', 'bar',), 'GRP', 'GRP', {}, {}, True),
        (('foo', 'bar',), ('foo', 'bar',), '', '', {}, {}, True),
        ((), (), '', '', {}, {}, True),
    )
)
def test_equality(keywords1, keywords2, group1, group2, episodes1, episodes2, exp_equality):
    a = find.SceneQuery(keywords1, group=group1, episodes=episodes1)
    b = find.SceneQuery(keywords2, group=group2, episodes=episodes2)
    assert (a == b) is exp_equality
