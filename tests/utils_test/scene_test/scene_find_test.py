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
    argnames='release, exp_keywords, exp_group, exp_episodes',
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
            ('The', 'Foo', '2004', '720p', 'BluRay', 'x264'),
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
            ('The', 'Foo', 'S01E01E02', '720p', 'BluRay', 'x264'),
            'ASDF',
            {'1': ('1', '2')},
        ),
    ),
    ids=lambda v: str(v),
)
def test_SceneQuery_from_release(release, exp_keywords, exp_group, exp_episodes):
    query = find.SceneQuery.from_release(release)
    assert query.keywords == exp_keywords
    assert query.group == exp_group
    assert query.episodes == exp_episodes


@pytest.mark.parametrize('cache, exp_cache', ((True, True), (False, False)))
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
async def test_SceneQuery_search_calls_given_coroutine_function(keywords, exp_keywords, cache, exp_cache):
    query = find.SceneQuery(*keywords, group='baz')
    search = AsyncMock(return_value=('20', 'C', '1', 'b'))
    results = await query.search(search, cache=cache)
    assert results == ['1', '20', 'b', 'C']
    assert search.call_args_list == [call(exp_keywords, group='baz', cache=exp_cache)]

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
        ({'1': ()}, ['X.S01E01.x264-ASDF', 'X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF']),
        ({'2': ()}, ['X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': ('2',)}, ['X.S01E02.x264-ASDF']),
        ({'2': ('1', '3')}, ['X.S02E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': ('1',), '2': ('3',)}, ['X.S01E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
    ),
)
@pytest.mark.asyncio
async def test_SceneQuery_handle_results(episodes, exp_matches):
    query = find.SceneQuery(episodes=episodes)
    search = AsyncMock(return_value=[
        'X.2015.x264-ASDF',
        'X.S01E01.x264-ASDF',
        'X.S01E02.x264-ASDF',
        'X.S01E03.x264-ASDF',
        'X.S02E01.x264-ASDF',
        'X.S02E02.x264-ASDF',
        'X.S02E03.x264-ASDF',
    ])
    results = await query.search(search)
    if exp_matches == 'ALL':
        assert results == search.return_value
    else:
        assert results == exp_matches


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
