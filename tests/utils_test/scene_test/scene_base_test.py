from unittest.mock import Mock, call

import pytest

from upsies.utils.release import ReleaseInfo
from upsies.utils.scene import base, predb
from upsies.utils.types import SceneCheckResult


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
async def test_search_delegates_query(testdb, mocker):
    query_mock = Mock(search=AsyncMock(return_value=['foo', 'bar', 'baz']))
    cache_mock = 'mock cache value'
    results = await testdb.search(query=query_mock, cache=cache_mock)
    assert query_mock.search.call_args_list == [call(testdb._search, cache=cache_mock)]
    assert results == ['foo', 'bar', 'baz']


@pytest.mark.parametrize(
    argnames='release_name, exp_return_value',
    argvalues=(
        # Movie: Abbreviated file in properly named directory
        ('Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', SceneCheckResult.true),
        ('Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/ly-dellmdm1080p.mkv', SceneCheckResult.true),
        ('dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity/ly-dellmdm1080p.mkv', SceneCheckResult.true),

        # Movie: Properly named file
        ('Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', SceneCheckResult.true),

        # Movie: Properly named file in properly named directory
        ('Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', SceneCheckResult.true),

        # Movie: Abbreviated file without properly named parent directory
        ('path/to/ly-dellmdm1080p.mkv', SceneCheckResult.unknown),

        # Movie: Properly named file in lower-case
        ('dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity.mkv', SceneCheckResult.true),

        # Series: Scene released season pack
        ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT', SceneCheckResult.true),
        ('bored.to.death.s01.720p.bluray.x264-ingot', SceneCheckResult.true),
        ('Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv', SceneCheckResult.true),
        ('bored.to.death.s01.720p.bluray.x264-ingot.mkv', SceneCheckResult.true),

        # Series: Scene released single episodes
        ('Justified.S04E01.720p.BluRay.x264-REWARD', SceneCheckResult.true),
        ('Justified.S04E99.720p.BluRay.x264-REWARD', SceneCheckResult.false),
        ('Justified.S04.720p.BluRay.x264-REWARD', SceneCheckResult.true),
        ('Justified.S02.720p.BluRay.x264-REWARD', SceneCheckResult.false),  # REWARD only released S01 + S04
        ('Justified.720p.BluRay.x264-REWARD', SceneCheckResult.true),

        # Non-scene release
        ('Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', SceneCheckResult.false),
        ('Damnation.S01.720p.AMZN.WEB-DL.DDP5.1.H.264-AJP69', SceneCheckResult.false),
        ('Damnation.S01E03.One.Penny.720p.AMZN.WEB-DL.DD+5.1.H.264-AJP69.mkv', SceneCheckResult.false),
    ),
)
@pytest.mark.asyncio
async def test_is_scene_release(release_name, exp_return_value, store_response):
    release = ReleaseInfo(release_name)
    assert await predb.PreDbApi().is_scene_release(release) is exp_return_value
