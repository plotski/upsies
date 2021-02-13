from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils import scene
from upsies.utils.release import ReleaseInfo
from upsies.utils.types import SceneCheckResult


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_scenedbs(mocker):
    existing_scenedbs = (Mock(), Mock(), Mock())
    submodules_mock = mocker.patch('upsies.utils.scene.submodules')
    subclasses_mock = mocker.patch('upsies.utils.scene.subclasses', return_value=existing_scenedbs)
    assert scene.scenedbs() == existing_scenedbs
    assert submodules_mock.call_args_list == [call('upsies.utils.scene')]
    assert subclasses_mock.call_args_list == [call(scene.SceneDbApiBase, submodules_mock.return_value)]


def test_scenedb_returns_ClientApiBase_instance(mocker):
    existing_scenedbs = (Mock(), Mock(), Mock())
    existing_scenedbs[0].configure_mock(name='foo')
    existing_scenedbs[1].configure_mock(name='bar')
    existing_scenedbs[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.scene.scenedbs', return_value=existing_scenedbs)
    assert scene.scenedb('bar', x=123) is existing_scenedbs[1].return_value
    assert existing_scenedbs[1].call_args_list == [call(x=123)]

def test_scenedb_fails_to_find_scenedb(mocker):
    existing_scenedbs = (Mock(), Mock(), Mock())
    existing_scenedbs[0].configure_mock(name='foo')
    existing_scenedbs[1].configure_mock(name='bar')
    existing_scenedbs[2].configure_mock(name='baz')
    mocker.patch('upsies.utils.scene.scenedbs', return_value=existing_scenedbs)
    with pytest.raises(ValueError, match='^Unsupported scene release database: bam$'):
        scene.scenedb('bam', x=123)
    for c in existing_scenedbs:
        assert c.call_args_list == []


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
        ('Justified.720p.BluRay.x264-REWARD', SceneCheckResult.unknown),

        # Non-scene release
        ('Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', SceneCheckResult.false),
        ('Damnation.S01.720p.AMZN.WEB-DL.DDP5.1.H.264-AJP69', SceneCheckResult.false),
        ('Damnation.S01E03.One.Penny.720p.AMZN.WEB-DL.DD+5.1.H.264-AJP69.mkv', SceneCheckResult.false),
    ),
)
@pytest.mark.asyncio
async def test_is_scene_release(release_name, exp_return_value, store_response):
    assert await scene.is_scene_release(release_name) is exp_return_value
    assert await scene.is_scene_release(ReleaseInfo(release_name)) is exp_return_value
