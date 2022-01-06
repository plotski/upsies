import re
from unittest.mock import Mock, call

import pytest

from upsies import constants, errors
from upsies.utils import release
from upsies.utils.scene import find


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def make_db_class(name, exception):
    _name = name

    class MockSceneDb:
        name = _name
        calls = []

        async def search(self, *args, **kwargs):
            self.calls.append(call(*args, **kwargs))
            if exception:
                raise exception
            else:
                return f'{name} search results'

    return MockSceneDb()


@pytest.mark.parametrize(
    argnames='query, exp_query',
    argvalues=(
        ('path/to/release', find.SceneQuery.from_string('path/to/release')),
        (release.ReleaseInfo('release name'), find.SceneQuery.from_release(release.ReleaseInfo('release name'))),
        (('some', 'thing', 'else'), ('some', 'thing', 'else')),
    ),
)
@pytest.mark.asyncio
async def test_search_finds_query_results_directly(query, exp_query, mocker):
    mock_results = 'mock results'
    mock_dbs = ('mock db 1', 'mock db 2')
    mock_only_existing_releases = 'mock only existing releases'
    multisearch_mock = mocker.patch('upsies.utils.scene.find._multisearch', AsyncMock(return_value=mock_results))

    results = await find.search(query, mock_dbs, only_existing_releases=mock_only_existing_releases)
    assert results == mock_results
    assert multisearch_mock.call_args_list == [call(mock_dbs, exp_query, mock_only_existing_releases)]

@pytest.mark.parametrize(
    argnames='query, exp_first_query, exp_perform_episode_searches',
    argvalues=(
        (find.SceneQuery('mock query'), find.SceneQuery('mock query'), False),
        (release.ReleaseInfo('release name'), find.SceneQuery.from_release(release.ReleaseInfo('release name')), False),
        ('mock query', find.SceneQuery('mock query'), True),
    ),
)
@pytest.mark.asyncio
async def test_search_finds_results_from_generated_episodes(query, exp_first_query, exp_perform_episode_searches, mocker):
    # find.search() is memoized
    find.search.clear_cache()

    mock_dbs = ('mock db 1', 'mock db 2')
    mock_episode_queries = (
        find.SceneQuery('mock episode query 1'),
        find.SceneQuery('mock episode query 2'),
    )
    mock_episode_results = (['mock episode result 1', 'mock episode result 2'],
                            ['mock episode result 3', 'mock episode result 4'])
    mock_only_existing_releases = 'mock only existing releases'
    generate_episode_queries_mock = mocker.patch(
        'upsies.utils.scene.find._generate_episode_queries',
        return_value=mock_episode_queries,
    )
    multisearch_mock = mocker.patch('upsies.utils.scene.find._multisearch', AsyncMock(
        side_effect=(
            (),                    # First query yields no results
        ) + mock_episode_results,  # The actual results

    ))

    if exp_perform_episode_searches:
        exp_results = [result
                       for results in mock_episode_results
                       for result in results]
    else:
        exp_results = None

    results = await find.search(query, mock_dbs, only_existing_releases=mock_only_existing_releases)
    assert results == exp_results

    if exp_perform_episode_searches:
        assert multisearch_mock.call_args_list == [
            call(mock_dbs, exp_first_query, mock_only_existing_releases),
            call(mock_dbs, mock_episode_queries[0], mock_only_existing_releases),
            call(mock_dbs, mock_episode_queries[1], mock_only_existing_releases),
        ]
        assert generate_episode_queries_mock.call_args_list == [
            call(query),
        ]
    else:
        assert multisearch_mock.call_args_list == [
            call(mock_dbs, exp_first_query, mock_only_existing_releases),
        ]
        assert generate_episode_queries_mock.call_args_list == []


@pytest.mark.parametrize(
    argnames='dbs, exp_results, exp_exception, exp_queried_db_names',
    argvalues=(
        (
            (make_db_class(name='foo', exception=None),
             make_db_class(name='bar', exception=None)),
            'foo search results',
            None,
            ['foo'],
        ),
        (
            (make_db_class(name='foo', exception=errors.RequestError('foo is down')),
             make_db_class(name='bar', exception=None)),
            'bar search results',
            None,
            ['foo', 'bar'],
        ),
        (
            (make_db_class(name='foo', exception=errors.RequestError('foo is down')),
             make_db_class(name='bar', exception=errors.RequestError('bar is down'))),
            None,
            errors.RequestError('All queries failed: foo is down, bar is down'),
            ['foo', 'bar'],
        ),
        (
            (),
            [],
            None,
            [],
        ),
    ),
)
@pytest.mark.asyncio
async def test_multisearch(dbs, exp_results, exp_exception, exp_queried_db_names, mocker):
    mocker.patch('upsies.utils.scene.scenedb', side_effect=dbs)

    db_order = [db.name for db in dbs]
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await find._multisearch(db_order, 'mock query', only_existing_releases='mock bool')
    else:
        results = await find._multisearch(db_order, 'mock query', only_existing_releases='mock bool')
        assert results == exp_results

    db_map = {db.name: db for db in dbs}
    for db_name in exp_queried_db_names:
        db = db_map[db_name]
        assert db.calls == [call('mock query', only_existing_releases='mock bool')]


@pytest.mark.parametrize(
    argnames='path, files, exp_queries, exp_file_list_called',
    argvalues=(
        ('Foo.2000.WEB-DL.H.264', ('a', 'b', 'c'), (), False),
        ('Foo.S01E01.WEB-DL.H.264', ('a', 'b', 'c'), (), False),
        (
            'Foo.S01.WEB-DL.H.264',
            ('foo.s01e01.mkv', 'foo.s01e02.mkv', 'foo.s01e03.mkv'),
            (
                find.SceneQuery.from_string('foo.s01e01.mkv'),
                find.SceneQuery.from_string('foo.s01e02.mkv'),
                find.SceneQuery.from_string('foo.s01e03.mkv'),
            ),
            True,
        ),
        (
            'Foo.S01.WEB-DL.H.264',
            ('stupid-filenames01e01.mkv', 'stupid-filenames01e02.mkv', 'stupid-filenames01e03.mkv'),
            (),
            True,
        ),
    ),
    ids=lambda v: str(v),
)
def test_generate_episode_queries(path, files, exp_queries, exp_file_list_called, mocker):
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=files)
    queries = tuple(find._generate_episode_queries(path))
    assert queries == exp_queries
    if exp_file_list_called:
        assert file_list_mock.call_args_list == [
            call(path, extensions=constants.VIDEO_FILE_EXTENSIONS),
        ]
    else:
        assert file_list_mock.call_args_list == []


@pytest.mark.parametrize(
    argnames='raised_by_ReleaseInfo, raised_by_from_release, exp_exception',
    argvalues=(
        (None, None, None),
        (errors.ContentError('bad release name'), None, errors.SceneError('bad release name')),
        (None, errors.ContentError('something something'), errors.SceneError('something something')),
    ),
)
def test_SceneQuery_from_string(raised_by_ReleaseInfo, raised_by_from_release, exp_exception, mocker):
    ReleaseInfo_mock = mocker.patch('upsies.utils.release.ReleaseInfo', side_effect=raised_by_ReleaseInfo)
    from_release_mock = mocker.patch('upsies.utils.scene.find.SceneQuery.from_release', side_effect=raised_by_from_release)

    if exp_exception:
        with pytest.raises(errors.SceneError, match=rf'^{re.escape(str(exp_exception))}$'):
            find.SceneQuery.from_string('foo')
    else:
        query = find.SceneQuery.from_string('foo')
        assert query.keywords == from_release_mock.return_value.keywords
        assert query.group == from_release_mock.return_value.group
        assert query.episodes == from_release_mock.return_value.episodes

    assert ReleaseInfo_mock.call_args_list == [call('foo', strict=True)]
    if not raised_by_ReleaseInfo:
        assert from_release_mock.call_args_list == [call(ReleaseInfo_mock.return_value)]
    else:
        assert from_release_mock.call_args_list == []


@pytest.mark.parametrize(
    argnames='video_codec, exp_keyword',
    argvalues=(
        ('H.264', 'H264'),
        ('H.265', 'H265'),
        ('h.264', 'h264'),
        ('h.265', 'h265'),
    ),
)
def test_SceneQuery_from_release_normalizes_h26x(video_codec, exp_keyword, mocker):
    mocker.patch('upsies.utils.scene.common.get_needed_keys', return_value=('video_codec',))
    query = find.SceneQuery.from_release({'video_codec': video_codec})
    assert query.keywords == (exp_keyword,)

@pytest.mark.parametrize(
    argnames='source, exp_keyword',
    argvalues=(
        ('WEB-DL', 'WEB'),
        ('WEB', 'WEB'),
        ('WEBRip', 'WEBRip'),
    ),
)
def test_SceneQuery_from_release_normalizes_webdl(source, exp_keyword, mocker):
    mocker.patch('upsies.utils.scene.common.get_needed_keys', return_value=('source',))
    query = find.SceneQuery.from_release({'source': source})
    assert query.keywords == (exp_keyword,)

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
                'episodes': {},
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
                'source': 'WEB-DL',
                'video_codec': 'x264',
                'group': 'ASDF',
                'episodes': {'1': ('1', '2')},
            },
            ('title', 'source', 'group'),
            ('The', 'Foo', 'WEB'),
            'ASDF',
            {'1': ('1', '2')},
        ),
    ),
    ids=lambda v: str(v),
)
def test_SceneQuery_from_release_separates_group_and_episodes(release, needed_keys, exp_keywords, exp_group, exp_episodes, mocker):
    mocker.patch('upsies.utils.scene.common.get_needed_keys', return_value=needed_keys)
    query = find.SceneQuery.from_release(release)
    assert query.keywords == exp_keywords
    assert query.group == exp_group
    assert query.episodes == exp_episodes

@pytest.mark.parametrize(
    argnames='episodes, exp_keyword',
    argvalues=(
        ({'1': ('2',)}, 'S01E02'),
        ({'1': ('2', '3')}, None),
        ({'1': ()}, None),
        ({'1': ('2',), '3': ()}, None),
        ({'1': ('2',), '3': ('4',)}, None),
    ),
)
def test_SceneQuery_from_release_includes_single_episodes_only(episodes, exp_keyword, mocker):
    mocker.patch('upsies.utils.scene.common.get_needed_keys', return_value=('episodes',))
    query = find.SceneQuery.from_release({'episodes': episodes})
    if exp_keyword is None:
        assert query.keywords == ()
    else:
        assert query.keywords == (exp_keyword,)


@pytest.mark.parametrize('group', (None, 'ASDF'))
@pytest.mark.parametrize('episodes', ({}, {'1': ('2', '3', '4')}))
@pytest.mark.parametrize(
    argnames='keywords, exp_keywords',
    argvalues=(
        ([' foo ', ' bar  baz'], ('foo', 'bar', 'baz')),
        ([' foo ', ' bar - baz'], ('foo', 'bar', 'baz')),
        ([' foo ', ' S01 ', 'bar'], ('foo', 'bar')),
        ([' foo ', ' S01S02 ', 'bar'], ('foo', 'bar')),
        ([' foo ', ' S01E10 ', 'bar'], ('foo', 'S01E10', 'bar')),
        ([' foo ', ' S01E10E11 ', 'bar'], ('foo', 'S01E10E11', 'bar')),
        ([' foo ', ' S01E10E11S02E12E13 ', 'bar'], ('foo', 'S01E10E11S02E12E13', 'bar')),
        ([' foo ', ' S01 S02E10E11 ', 'bar'], ('foo', 'S02E10E11', 'bar')),
    ),
    ids=lambda v: str(v),
)
def test_SceneQuery_init(keywords, exp_keywords, group, episodes, mocker):
    query = find.SceneQuery(*keywords, group=group, episodes=episodes)
    assert query.keywords == exp_keywords
    assert query.episodes == episodes
    assert query.group == group


@pytest.mark.parametrize(
    argnames='only_existing_releases, exp_only_existing_releases',
    argvalues=(
        (None, True),
        (True, True),
        (False, False),
    ),
)
@pytest.mark.asyncio
async def test_SceneQuery_search(only_existing_releases, exp_only_existing_releases, mocker):
    query = find.SceneQuery('this', 'that', group='ASDF')
    mocker.patch.object(query, '_handle_results')
    search_coro_func = AsyncMock(return_value=('foo', 'bar', 'baz'))

    return_value = await query.search(search_coro_func, only_existing_releases=only_existing_releases)

    assert return_value is query._handle_results.return_value
    assert query._handle_results.call_args_list == [
        call(('foo', 'bar', 'baz'), exp_only_existing_releases)
    ]


@pytest.mark.parametrize(
    argnames='episodes, exp_matches',
    argvalues=(
        ({}, 'ALL'),
        ({'1': []}, ['X.S01.x264-ASDF']),
        ({'2': []}, ['X.S02.x264-ASDF']),
        ({'1': [], '2': []}, ['X.S01.x264-ASDF', 'X.S02.x264-ASDF']),
        ({'': ['2', '3']}, ['X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'': ['2'], '2': ['1']}, ['X.S01E02.x264-ASDF', 'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ['2']}, ['X.S01E02.x264-ASDF']),
        ({'2': ['1', '3']}, ['X.S02E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': ['1'], '2': ['3']}, ['X.S01E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': [], '2': ['2']}, ['X.S01.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ['2'], '2': []}, ['X.S01E02.x264-ASDF', 'X.S02.x264-ASDF']),
        ({'3': []}, []),
        ({'': ['4']}, []),
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
        ({'1': []}, ['X.S01E01.x264-ASDF', 'X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF']),
        ({'2': []}, ['X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': [], '2': []}, ['X.S01E01.x264-ASDF', 'X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF',
                              'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'': ['2', '3']}, ['X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'': ['2'], '2': ['1']}, ['X.S01E02.x264-ASDF', 'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ['2']}, ['X.S01E02.x264-ASDF']),
        ({'2': ['1', '3']}, ['X.S02E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': ['1'], '2': ['3']}, ['X.S01E01.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'1': [], '2': ['2']}, ['X.S01E01.x264-ASDF', 'X.S01E02.x264-ASDF', 'X.S01E03.x264-ASDF', 'X.S02E02.x264-ASDF']),
        ({'1': ['2'], '2': []}, ['X.S01E02.x264-ASDF', 'X.S02E01.x264-ASDF', 'X.S02E02.x264-ASDF', 'X.S02E03.x264-ASDF']),
        ({'3': []}, []),
        ({'': ['4']}, []),
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


@pytest.mark.parametrize(
    argnames='episode, exp_season_pack',
    argvalues=(
        ('X.S01.1080p.BluRay.x264-ASDF', 'X.S01.1080p.BluRay.x264-ASDF'),
        ('X.S01E01.1080p.BluRay.x264-ASDF', 'X.S01.1080p.BluRay.x264-ASDF'),
        ('X.S01E01.Episode.Title.1080p.BluRay.x264-ASDF', 'X.S01.1080p.BluRay.x264-ASDF'),
        ('X.S01E01.Episode.Title.1080i.BluRay.x264-ASDF', 'X.S01.1080i.BluRay.x264-ASDF'),
        ('X.S01E01.Episode.Title.DVDRip.x264-ASDF', 'X.S01.DVDRip.x264-ASDF'),
        ('X.S01E01.Episode.Title.REPACK.720p.BluRay.x264-ASDF', 'X.S01.REPACK.720p.BluRay.x264-ASDF'),
        ('X.S01E01.Episode.Title.PROPER.720p.BluRay.x264-ASDF', 'X.S01.PROPER.720p.BluRay.x264-ASDF'),
        ('X.S01E01.Episode.Title.DUTCH.DVDRip.x264-ASDF', 'X.S01.DUTCH.DVDRip.x264-ASDF'),
        ('X.S01E01.Episode.Title.iNTERNAL.DVDRip.x264-ASDF', 'X.S01.iNTERNAL.DVDRip.x264-ASDF'),
        ('X.S01E01.Episode.Title.REAL.DVDRip.x264-ASDF', 'X.S01.REAL.DVDRip.x264-ASDF'),
        ('X.S01E01.French.DVDRip.x264-ASDF', 'X.S01.French.DVDRip.x264-ASDF'),
        ('X.S01E01.Episode.Title.German.DL.DVDRip.x264-ASDF', 'X.S01.German.DL.DVDRip.x264-ASDF'),
        ('X.S01E01E02.Episode.Title.German.DL.DVDRip.x264-ASDF', 'X.S01.German.DL.DVDRip.x264-ASDF'),
    ),
)
def test_SceneQuery_create_season_pack_name(episode, exp_season_pack):
    season_pack = find.SceneQuery._create_season_pack_name(episode)
    assert season_pack == exp_season_pack


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
    argnames='query1, query2, exp_return_value',
    argvalues=(
        (
            find.SceneQuery('foo', 'bar', group='GRP', episodes={'1': ('2', '3')}),
            find.SceneQuery('foo', 'bar', group='GRP', episodes={'1': ('2', '3')}),
            True,
        ),
        (
            find.SceneQuery('foo', 'bar', group='GRP', episodes={'1': ()}),
            find.SceneQuery('foo', 'bar', group='GRP', episodes={'1': ()}),
            True,
        ),
        (
            find.SceneQuery('foo', 'bar', group='GRP'),
            find.SceneQuery('foo', 'bar', group='GRP'),
            True,
        ),
        (
            find.SceneQuery('foo', 'bar'),
            find.SceneQuery('foo', 'bar'),
            True,
        ),
        (
            find.SceneQuery(),
            find.SceneQuery(),
            True,
        ),
        (
            find.SceneQuery('foo', 'bar', group='GR_'),
            find.SceneQuery('foo', 'bar', group='GRP'),
            False,
        ),
        (
            find.SceneQuery('foo', 'bar', episodes={'1': ()}),
            find.SceneQuery('foo', 'bar', episodes={'2': ()}),
            False,
        ),
        (
            find.SceneQuery('foo', 'bar', episodes={'1': ('2',)}),
            find.SceneQuery('foo', 'bar', episodes={'1': ('3',)}),
            False,
        ),
        (
            find.SceneQuery('foo', 'bar', episodes={'1': ('2',)}),
            find.SceneQuery('foo', 'bar', episodes={'1': ('2', '3')}),
            False,
        ),
        (
            find.SceneQuery('foo', 'bar'),
            find.SceneQuery('foo', 'baz'),
            False,
        ),
        (
            find.SceneQuery('foo', 'bar'),
            'not a SceneQuery object',
            NotImplemented,
        ),
    )
)
def test_SceneQuery_equality(query1, query2, exp_return_value):
    assert query1.__eq__(query2) is exp_return_value
    assert query2.__eq__(query1) is exp_return_value
    if exp_return_value is NotImplemented:
        assert query1.__ne__(query2) is NotImplemented
        assert query2.__ne__(query1) is NotImplemented
    else:
        assert query1.__ne__(query2) is not bool(exp_return_value)
        assert query2.__ne__(query1) is not bool(exp_return_value)
