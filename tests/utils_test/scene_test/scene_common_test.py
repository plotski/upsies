import re
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.release import Episodes
from upsies.utils.scene import common


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_SceneQuery_from_string(mocker):
    ReleaseInfo_mock = mocker.patch('upsies.utils.release.ReleaseInfo')
    from_release_mock = mocker.patch('upsies.utils.scene.common.SceneQuery.from_release')
    query = common.SceneQuery.from_string('foo')
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
    query = common.SceneQuery.from_release(release)
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
    query = common.SceneQuery(*keywords, group='baz')
    search = AsyncMock(return_value=('20', 'C', '1', 'b'))
    results = await query.search(search, cache=cache)
    assert results == ['1', '20', 'b', 'C']
    assert search.call_args_list == [call(exp_keywords, group='baz', cache=exp_cache)]

@pytest.mark.asyncio
async def test_SceneQuery_search_handles_RequestError():
    query = common.SceneQuery('foo', 'bar', group='baz')
    search = AsyncMock(side_effect=errors.RequestError('no'))
    with pytest.raises(errors.SceneError, match=r'^no$'):
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
    query = common.SceneQuery(episodes=episodes)
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
    query = common.SceneQuery('foo bar', ' - ', 'baz', '', '  ', 21)
    assert query.keywords == ('foo', 'bar', 'baz', '21')


def test_SceneQuery_group():
    query = common.SceneQuery(group='ASDF')
    assert query.group == 'ASDF'


def test_SceneQuery_episodes():
    query = common.SceneQuery(episodes={'5': ('10',)})
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
    assert repr(common.SceneQuery(*keywords, **kwargs)) == exp_repr


@pytest.mark.parametrize(
    argnames='filename, should_raise',
    argvalues=(
        ('group-thetitle.1080p.bluray.x264.mkv', True),
        ('group-the.title.2016.720p.bluray.x264.mkv', True),
        ('group-thetitle720.mkv', True),
        ('group-the-title-720p.mkv', True),
        ('group-thetitle-720p.mkv', True),
        ('group-ttl-s02e01-720p.mkv', True),
        ('group-the.title.1984.720p.mkv', True),
        ('group-the.title.720p.mkv', True),
        ('group-ttl.720p.mkv', True),
        ('group-title.mkv', True),
        ('title-1080p-group.mkv', True),
        ('group-the_title_x264_bluray.mkv', True),
        ('ttl.720p-group.mkv', True),
        ('title.2017.720p.bluray.x264-group.mkv', False),
        ('asdf.mkv', False),
    ),
)
def test_assert_not_abbreviated_filename(filename, should_raise):
    exp_msg = re.escape(
        f'Provide parent directory of abbreviated scene file: {filename}'
    )
    if should_raise:
        with pytest.raises(errors.SceneError, match=rf'^{exp_msg}$'):
            common.assert_not_abbreviated_filename(filename)
        with pytest.raises(errors.SceneError, match=rf'^{exp_msg}$'):
            common.assert_not_abbreviated_filename(f'path/to/{filename}')
    else:
        common.assert_not_abbreviated_filename(filename)
        common.assert_not_abbreviated_filename(f'path/to/{filename}')
