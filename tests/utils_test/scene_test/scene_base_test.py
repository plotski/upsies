from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.release import ReleaseInfo
from upsies.utils.scene import base, predb


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def testdb():
    class TestDb(base.SceneDbApiBase):
        name = 'scn'
        label = 'SCN'
        _search = AsyncMock()

    return TestDb()


@pytest.mark.asyncio
async def test_search_delegates_arguments(testdb, mocker):
    mocker.patch.object(testdb, '_normalize_query', Mock(return_value='mock query'))
    mocker.patch.object(testdb, '_search', AsyncMock(return_value='mock results'))
    mocker.patch.object(testdb, '_normalize_results', Mock(return_value='mock normalized results'))
    results = await testdb.search('foo', group='bar', cache='baz')
    assert testdb._normalize_query.call_args_list == [call(('foo',))]
    assert testdb._search.call_args_list == [call(query='mock query', group='bar', cache='baz')]
    assert testdb._normalize_results.call_args_list == [call('mock results')]
    assert results == 'mock normalized results'

@pytest.mark.asyncio
async def test_search_handles_RequestError(testdb, mocker):
    mocker.patch.object(testdb, '_normalize_query', Mock(return_value='mock query'))
    mocker.patch.object(testdb, '_search', AsyncMock(side_effect=errors.RequestError('no')))
    mocker.patch.object(testdb, '_normalize_results')
    with pytest.raises(errors.SceneError, match=r'^no$'):
        await testdb.search('foo', group='bar', cache='baz')
    assert testdb._normalize_query.call_args_list == [call(('foo',))]
    assert testdb._search.call_args_list == [call(query='mock query', group='bar', cache='baz')]
    assert testdb._normalize_results.call_args_list == []


def test_normalize_query(testdb):
    assert testdb._normalize_query(('foo  bar ', ' baz')) == ['foo', 'bar', 'baz']


def test_normalize_results(testdb):
    assert testdb._normalize_results(('Foo', 'bar', 'BAZ')) == ['bar', 'BAZ', 'Foo']


@pytest.mark.parametrize('group, exp_return_value', (('LiViDiTY', True), ('TayTo', False)))
@pytest.mark.asyncio
async def test_is_scene_group(group, exp_return_value, store_response):
    assert await predb.PreDbApi().is_scene_group(group) is exp_return_value


@pytest.mark.parametrize(
    argnames='release_name, exp_return_value',
    argvalues=(
        # Movie: Abbreviated file in properly named directory
        ('Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', True),
        ('Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/ly-dellmdm1080p.mkv', True),
        ('dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity/ly-dellmdm1080p.mkv', True),

        # Movie: Properly named file
        ('Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', True),

        # Movie: Properly named file in properly named directory
        ('Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', True),

        # Movie: Abbreviated file without properly named parent directory
        ('path/to/ly-dellmdm1080p.mkv', None),

        # Movie: Properly named file in lower-case
        ('dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity.mkv', True),

        # Series: Scene released season pack
        ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT', True),
        ('bored.to.death.s01.720p.bluray.x264-ingot', True),
        ('Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv', True),
        ('bored.to.death.s01.720p.bluray.x264-ingot.mkv', True),

        # Series: Scene released single episodes
        ('Justified.S04E01.720p.BluRay.x264-REWARD', True),
        ('Justified.S04E99.720p.BluRay.x264-REWARD', False),
        ('Justified.S04.720p.BluRay.x264-REWARD', True),
        ('Justified.S02.720p.BluRay.x264-REWARD', False),  # REWARD only released S01 + S04
        ('Justified.720p.BluRay.x264-REWARD', False),

        # Non-scene release
        ('Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', False),
        ('Damnation.S01.720p.AMZN.WEB-DL.DDP5.1.H.264-AJP69', False),
        ('Damnation.S01E03.One.Penny.720p.AMZN.WEB-DL.DD+5.1.H.264-AJP69.mkv', False),
    ),
)
@pytest.mark.asyncio
async def test_is_scene_release(release_name, exp_return_value, store_response):
    release = ReleaseInfo(release_name)
    assert await predb.PreDbApi().is_scene_release(release) is exp_return_value
