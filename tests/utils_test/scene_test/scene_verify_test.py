import os
import re
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.release import ReleaseInfo
from upsies.utils.scene import verify
from upsies.utils.types import SceneCheckResult


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


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
        ('GR0up1080pAsDf.mkv', True),
        ('title.2017.720p.bluray.x264-group.mkv', False),
        ('asdf.mkv', False),
    ),
)
def test_assert_not_abbreviated_filename_and_is_abbreviated_filename(filename, should_raise):
    exp_msg = re.escape(f'Abbreviated scene file name is verboten: {filename}')
    if should_raise:
        with pytest.raises(errors.SceneAbbreviatedFilenameError, match=rf'^{exp_msg}$'):
            verify.assert_not_abbreviated_filename(filename)
        with pytest.raises(errors.SceneAbbreviatedFilenameError, match=rf'^{exp_msg}$'):
            verify.assert_not_abbreviated_filename(f'path/to/{filename}')

        assert verify.is_abbreviated_filename(filename)
        assert verify.is_abbreviated_filename(f'path/to/{filename}')
    else:
        verify.assert_not_abbreviated_filename(filename)
        verify.assert_not_abbreviated_filename(f'path/to/{filename}')

        assert not verify.is_abbreviated_filename(filename)
        assert not verify.is_abbreviated_filename(f'path/to/{filename}')


@pytest.mark.parametrize(
    argnames='release_name, exp_return_value',
    argvalues=(
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', SceneCheckResult.true,
            id='Movie: Properly named file',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY.mkv', SceneCheckResult.true,
            id='Movie: Properly named file',
        ),
        pytest.param(
            'dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity.mkv', SceneCheckResult.true,
            id='Movie: Properly named file',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', SceneCheckResult.true,
            id='Movie: Properly named file in properly named directory',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', SceneCheckResult.true,
            id='Movie: Properly named file in properly named directory',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY.mkv', SceneCheckResult.true,
            id='Movie: Properly named file in properly named directory',
        ),

        pytest.param(
            'path/to/ly-dellmdm1080p.mkv', SceneCheckResult.unknown,
            id='Movie: Abbreviated file without usably named parent directory',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', SceneCheckResult.true,
            id='Movie: Abbreviated file in usably named directory',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/ly-dellmdm1080p.mkv', SceneCheckResult.true,
            id='Movie: Abbreviated file in usably named directory',
        ),
        pytest.param(
            'dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity/ly-dellmdm1080p.mkv', SceneCheckResult.true,
            id='Movie: Abbreviated file in usably named directory',
        ),

        pytest.param(
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT', SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),
        pytest.param(
            'bored.to.death.s01.720p.bluray.x264-ingot', SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),
        pytest.param(
            'Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv', SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),
        pytest.param(
            'bored.to.death.s01.720p.bluray.x264-ingot.mkv', SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),

        pytest.param(
            'Justified.S04E01.720p.BluRay.x264-REWARD', SceneCheckResult.true,
            id='Series: Scene released single episodes',
        ),

        pytest.param(
            'Justified.S04E99.720p.BluRay.x264-REWARD', SceneCheckResult.false,
            id='Series: Scene released single episodes',
        ),

        pytest.param(
            'Justified.S04.720p.BluRay.x264-REWARD', SceneCheckResult.true,
            id='Series: Scene released single episodes',
        ),

        pytest.param(
            'Justified.S02.720p.BluRay.x264-REWARD', SceneCheckResult.false,
            id='Series: Missing season from scene group',
        ),

        pytest.param(
            'Justified.720p.BluRay.x264-REWARD', SceneCheckResult.unknown,
            id='Series: Not enough information in release name',
        ),

        pytest.param(
            'Friends.S10.1080p.BluRay.x264-TENEIGHTY', SceneCheckResult.true,
            id='Series: Lots of seasons and episodes',
        ),

        pytest.param(
            'The.Fall.Guy.S02.480p.DVDRip.XviD.AAC-nodlabs', SceneCheckResult.true,
            id='Resolution is ignored for DVDRip',
        ),

        pytest.param(
            'Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', SceneCheckResult.false,
            id='Non-scene movie release',
        ),

        pytest.param(
            'Damnation.S01.720p.AMZN.WEB-DL.DDP5.1.H.264-AJP69', SceneCheckResult.false,
            id='Non-scene season release',
        ),

        pytest.param(
            'Damnation.S01E03.One.Penny.720p.AMZN.WEB-DL.DD+5.1.H.264-AJP69.mkv', SceneCheckResult.false,
            id='Non-scene episode release',
        ),
    ),
)
@pytest.mark.asyncio
async def test_is_scene_release(release_name, exp_return_value, store_response):
    assert await verify.is_scene_release(release_name) is exp_return_value
    assert await verify.is_scene_release(ReleaseInfo(release_name)) is exp_return_value

@pytest.mark.asyncio
async def test_is_scene_release_with_insufficient_needed_keys(mocker):
    mocker.patch('upsies.utils.scene.find.search', AsyncMock(return_value=('a', 'b')))
    mocker.patch('upsies.utils.scene.common.get_needed_keys', Mock(
        return_value=('year', 'resolution'),
    ))
    assert await verify.is_scene_release('Title.2015-ASDF') is SceneCheckResult.unknown
    assert await verify.is_scene_release('Title.1080p-ASDF') is SceneCheckResult.unknown

@pytest.mark.asyncio
async def test_is_scene_release_with_no_needed_keys(mocker):
    mocker.patch('upsies.utils.scene.find.search', AsyncMock(return_value=('a', 'b')))
    mocker.patch('upsies.utils.scene.common.get_needed_keys', Mock(return_value=()))
    assert await verify.is_scene_release('Some.Release-NAME') is SceneCheckResult.unknown


@pytest.mark.parametrize(
    argnames='release_name, exp_return_value',
    argvalues=(
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            {'ly-dellmdm1080p.mkv': {'release_name': 'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
                                     'file_name': 'ly-dellmdm1080p.mkv',
                                     'size': 7044061767,
                                     'crc': 'B59CE234'}},
            id='Looking for single-file release when original release was single-file',
        ),

        pytest.param(
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            {'Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv',
              'size': 518652629,
              'crc': '497277ED'},
             'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
              'size': 779447228,
              'crc': '8C8C0AE7'},
             'Bored.to.Death.S01E03.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01E03.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
              'size': 30779540,
              'crc': '0ECBEBE8'},
             'Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
              'size': 138052914,
              'crc': 'E4E41C29'},
             'Bored.to.Death.S01E08.Deleted.Scene.1.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01E08.Deleted.Scene.1.720p.BluRay.x264-iNGOT.mkv',
              'size': 68498554,
              'crc': '085C6946'},
             'Bored.to.Death.S01E08.Deleted.Scene.2.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01E08.Deleted.Scene.2.720p.BluRay.x264-iNGOT.mkv',
              'size': 45583011,
              'crc': '7B822E59'}},
            id='Looking for multi-file release when original release was multi-file',
        ),

        pytest.param(
            'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD',
            {'Fawlty.Towers.S01E01.720p.BluRay.x264-SHORTBREHD.mkv':
             {'release_name': 'Fawlty.Towers.S01E01.720p.BluRay.x264-SHORTBREHD',
              'file_name': 'Fawlty.Towers.S01E01.720p.BluRay.x264-SHORTBREHD.mkv',
              'size': 1559430969, 'crc': 'B334CBEA'},
             'Fawlty.Towers.S01E02.720p.BluRay.x264-SHORTBREHD.mkv':
             {'release_name': 'Fawlty.Towers.S01E02.720p.BluRay.x264-SHORTBREHD',
              'file_name': 'Fawlty.Towers.S01E02.720p.BluRay.x264-SHORTBREHD.mkv',
              'size': 1168328357, 'crc': '156FDC0E'},
             'Fawlty.Towers.S01E03.720p.BluRay.x264-SHORTBREHD.mkv':
             {'release_name': 'Fawlty.Towers.S01E03.720p.BluRay.x264-SHORTBREHD',
              'file_name': 'Fawlty.Towers.S01E03.720p.BluRay.x264-SHORTBREHD.mkv',
              'size': 1559496197, 'crc': '5EAAAEC3'},
             'Fawlty.Towers.S01E04.720p.BluRay.x264-SHORTBREHD.mkv':
             {'release_name': 'Fawlty.Towers.S01E04.720p.BluRay.x264-SHORTBREHD',
              'file_name': 'Fawlty.Towers.S01E04.720p.BluRay.x264-SHORTBREHD.mkv',
              'size': 1560040644, 'crc': '4AAB7B8F'},
             'Fawlty.Towers.S01E05.720p.BluRay.x264-SHORTBREHD.mkv':
             {'release_name': 'Fawlty.Towers.S01E05.720p.BluRay.x264-SHORTBREHD',
              'file_name': 'Fawlty.Towers.S01E05.720p.BluRay.x264-SHORTBREHD.mkv',
              'size': 1559747905, 'crc': '40A2568C'},
             'Fawlty.Towers.S01E06.720p.BluRay.x264-SHORTBREHD.mkv':
             {'release_name': 'Fawlty.Towers.S01E06.720p.BluRay.x264-SHORTBREHD',
              'file_name': 'Fawlty.Towers.S01E06.720p.BluRay.x264-SHORTBREHD.mkv',
              'size': 1559556862, 'crc': '9FAB6E5F'}},
            id='Looking for multi-file release when original releases where single-file',
        ),

        pytest.param(
            'Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
            {'Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
              'size': 138052914,
              'crc': 'E4E41C29'}},
            id='Looking for single episode from multi-file release',
        ),

        pytest.param(
            'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT',
            {'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv':
             {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
              'file_name': 'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
              'size': 779447228,
              'crc': '8C8C0AE7'}},
            id='Looking for single non-episode file from multi-file release',
        ),

        pytest.param(
            'Foo.2015.1080p.Bluray.DD5.1.x264-DON.mkv',
            {},
            id='Non-scene release',
        ),
    ),
)
@pytest.mark.asyncio
async def test_release_files(release_name, exp_return_value, store_response):
    assert await verify.release_files(release_name) == exp_return_value


@pytest.mark.parametrize('parent_path', ('', 'path/to'))
@pytest.mark.parametrize(
    argnames='content_path, release_name, exp_exception',
    argvalues=(
        pytest.param(
            'Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv',
            'Rampart.2011.1080p.Bluray.DD5.1.x264-DON',
            errors.SceneError('Not a scene release: Rampart.2011.1080p.Bluray.DD5.1.x264-DON'),
            id='[MOVIE] Non-scene release',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            None,
            id='[MOVIE RELEASE] Properly named directory',
        ),

        pytest.param(
            f'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY{os.sep}',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            None,
            id='[MOVIE RELEASE] Properly named directory with trailing os.sep',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            None,
            id='[MOVIE RELEASE] Properly named file from abbreviated file name',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            errors.SceneRenamedError(original_name='Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
                                     existing_name='Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY'),
            id='[MOVIE RELEASE] Renamed release name',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            None,
            id='[MOVIE] Abbreviated file in properly named directory',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/ly-dellmdm1080p.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            errors.SceneRenamedError(original_name='Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
                                     existing_name='Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/ly-dellmdm1080p.mkv'),
            id='[MOVIE] Abbreviated file in renamed directory',
        ),

        pytest.param(
            'side.effects.2013.720p.bluray.x264-sparks.mkv',
            'Side.Effects.2013.720p.BluRay.x264-SPARKS',
            None,
            id='[MOVIE] File from release',
        ),

        pytest.param(
            'side.effects.2013.720p.bluray.x264-SPARKS.mkv',
            'Side.Effects.2013.720p.BluRay.x264-SPARKS',
            errors.SceneRenamedError(original_name='side.effects.2013.720p.bluray.x264-sparks.mkv',
                                     existing_name='side.effects.2013.720p.bluray.x264-SPARKS.mkv'),
            id='[MOVIE] Renamed file from release',
        ),

        pytest.param(
            'Friends.S10.1080p.BluRay.x264-TENEIGHTY/',
            'Friends.S10.1080p.BluRay.x264-TENEIGHTY',
            None,
            id='[SEASON] Abbreviated file names; properly named season directory',
        ),

        pytest.param(
            'Friends.S10.1080p.Blu-ray.x264-TENEIGHTY/',
            'Friends.S10.1080p.BluRay.x264-TENEIGHTY',
            errors.SceneRenamedError(original_name='Friends.S10.1080p.BluRay.x264-TENEIGHTY',
                                     existing_name='Friends.S10.1080p.Blu-ray.x264-TENEIGHTY'),
            id='[SEASON] Abbreviated file names; renamed season directory',
        ),

        pytest.param(
            'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD/',
            'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD',
            None,
            id='[SEASON] Normal file names; properly named season directory',
        ),

        pytest.param(
            'Fawlty.Towers.S01.720p.Blu-ray.x264-SHORTBREHD/',
            'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD',
            errors.SceneRenamedError(original_name='Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD',
                                     existing_name='Fawlty.Towers.S01.720p.Blu-ray.x264-SHORTBREHD'),
            id='[SEASON] Normal file names; properly named season directory',
        ),

        pytest.param(
            'Friends.S10.1080p.BluRay.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
            'Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY',
            None,
            id='[EPISODE] Abbreviated file name in properly named season directory',
        ),

        pytest.param(
            'Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
            'Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY',
            None,
            id='[EPISODE] Abbreviated file name in properly named episode directory',
        ),

        pytest.param(
            'Friends.S10E17E18.1080p.Blu-ray.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
            'Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY',
            errors.SceneRenamedError(original_name='Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
                                     existing_name='Friends.S10E17E18.1080p.Blu-ray.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv'),
            id='[EPISODE] Abbreviated file name in renamed episode directory',
        ),

        pytest.param(
            'Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY/teneighty-friends.s10e17e18.mkv',
            'Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY',
            errors.SceneRenamedError(original_name='Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
                                     existing_name='Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY/teneighty-friends.s10e17e18.mkv'),
            id='[EPISODE] Renamed abbreviated file name in properly episode directory',
        ),

        pytest.param(
            'Friends.S10E17E18.1080p.Blu-ray.x264-TENEIGHTY/teneighty-friends.s10e17e18.mkv',
            'Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY',
            errors.SceneRenamedError(original_name='Friends.S10E17E18.1080p.BluRay.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
                                     existing_name='Friends.S10E17E18.1080p.Blu-ray.x264-TENEIGHTY/teneighty-friends.s10e17e18.mkv'),
            id='[EPISODE] Renamed abbreviated file name in renamed episode directory',
        ),

        pytest.param(
            'Fawlty.Towers.S01E06.720p.BluRay.x264-SHORTBREHD.mkv',
            'Fawlty.Towers.S01E06.720p.BluRay.x264-SHORTBREHD',
            None,
            id='[EPISODE] Normal file name',
        ),

        pytest.param(
            'Fawlty.Towers.S01E06.720p.Blu-ray.x264-SHORTBREHD.mkv',
            'Fawlty.Towers.S01E06.720p.BluRay.x264-SHORTBREHD',
            errors.SceneRenamedError(original_name='Fawlty.Towers.S01E06.720p.BluRay.x264-SHORTBREHD.mkv',
                                     existing_name='Fawlty.Towers.S01E06.720p.Blu-ray.x264-SHORTBREHD.mkv'),
            id='[EPISODE] Normal renamed file name',
        ),

        pytest.param(
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            None,
            id='[EXTRAS] Multi-file release',
        ),

        pytest.param(
            'Bored.to.Death.S01.Extras.720p.BluRay.x264-iNGOT',
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            errors.SceneRenamedError(original_name='Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
                                     existing_name='Bored.to.Death.S01.Extras.720p.BluRay.x264-iNGOT'),
            id='[EXTRAS] Renamed multi-file release',
        ),

        pytest.param(
            'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            None,
            id='[EXTRAS] Single file from multi-file release',
        ),
    ),
)
@pytest.mark.asyncio
async def test_verify_release_name(content_path, release_name, exp_exception, parent_path, store_response):
    full_content_path = os.path.join(parent_path, content_path)
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await verify.verify_release_name(full_content_path, release_name)
    else:
        await verify.verify_release_name(full_content_path, release_name)


@pytest.mark.parametrize(
    argnames='content_path, release_name, file_sizes, exp_exceptions',
    argvalues=(
        pytest.param(
            'path/to/Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv',
            'Rampart.2011.1080p.Bluray.DD5.1.x264-DON',
            (('path/to/Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', 7793811601),),
            (errors.SceneError('Not a scene release: Rampart.2011.1080p.Bluray.DD5.1.x264-DON'),),
            id='Non-scene release',
        ),

        pytest.param(
            'path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', 7044061767),),
            (),
            id='Abbreviated file in properly named directory with correct size',
        ),

        pytest.param(
            'path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', 123),),
            (errors.SceneFileSizeError(filename='ly-dellmdm1080p.mkv', original_size=7044061767, existing_size=123),),
            id='Abbreviated file in properly named directory with wrong size',
        ),

        pytest.param(
            'path/to/ly-dellmdm1080p.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/ly-dellmdm1080p.mkv', 7044061767),),
            (),
            id='Abbreviated file in non-release directory with correct size',
        ),

        pytest.param(
            'path/to/ly-dellmdm1080p.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/ly-dellmdm1080p.mkv', 123),),
            (errors.SceneFileSizeError(filename='ly-dellmdm1080p.mkv', original_size=7044061767, existing_size=123),),
            id='Abbreviated file in non-release directory with wrong size',
        ),

        pytest.param(
            'path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', 7044061767),),
            (),
            id='Properly named file with correct size',
        ),

        pytest.param(
            'path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', 123),),
            (errors.SceneFileSizeError(filename='Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
                                       original_size=7044061767, existing_size=123),),
            id='Properly named file with wrong size',
        ),

        pytest.param(
            'path/to/dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity.mkv', 7044061767),),
            (),
            id='Renamed file with correct size',
        ),

        pytest.param(
            'path/to/dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv',
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (('path/to/dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv', 123),),
            (errors.SceneFileSizeError(filename='dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv',
                                       original_size=7044061767, existing_size=123),),
            id='Renamed file with wrong size',
        ),

        pytest.param(
            'path/to/The.Fall.S02.720p.BluRay.x264-7SinS',
            'The.Fall.S02.720p.BluRay.x264-7SinS',
            (('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e01-720p.mkv', 2340971701),
             ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e02-720p.mkv', 2345872861),
             ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e03-720p.mkv', 2345958712),
             ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e04-720p.mkv', 2346136836),
             ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e05-720p.mkv', 123),  # No info about this one
             ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e06-720p.mkv', 3517999979)),
            (errors.SceneFileSizeError(filename='7s-tf-s02e02-720p.mkv', original_size=2345872860, existing_size=2345872861),
             errors.SceneMissingInfoError('7s-tf-s02e05-720p.mkv'),
             errors.SceneFileSizeError(filename='7s-tf-s02e06-720p.mkv', original_size=3517999978, existing_size=3517999979)),
            id='Missing scene release info / wrong episode order in release',
        ),

        pytest.param(
            'path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            (('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv', 518652629),
             ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv', 779447228),
             ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E03.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv', 30779540),
             ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv', 138052913),
             ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E08.Deleted.Scene.1.720p.BluRay.x264-iNGOT.mkv', 68498554),
             ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E08.Deleted.Scene.2.720p.BluRay.x264-iNGOT.mkv', 45583011),),
            (errors.SceneFileSizeError(filename='Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
                                       original_size=138052914, existing_size=138052913),),
            id='Multi-file release',
        ),

        pytest.param(
            'path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            (('path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv', 779447228),),
            (),
            id='Single file from multi-file release',
        ),

        pytest.param(
            'path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            (('path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv', 779447229),),
            (errors.SceneFileSizeError(filename='Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
                                       original_size=779447228, existing_size=779447229),),
            id='Single file from multi-file release',
        ),

        pytest.param(
            'path/to/Bored.to.Death.S01.MAKING.OF.720p.BluRay.x264-iNGOT.mkv',
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            (('path/to/Bored.to.Death.S01.MAKING.OF.720p.BluRay.x264-iNGOT.mkv', 779447228),),
            (errors.SceneMissingInfoError('Bored.to.Death.S01.MAKING.OF.720p.BluRay.x264-iNGOT.mkv'),),
            id='Renamed single file from multi-file release',
        ),
    ),
)
@pytest.mark.asyncio
async def test_verify_release_files(content_path, release_name, file_sizes, exp_exceptions, tmp_path, store_response):
    for filepath, filesize in file_sizes:
        parent = tmp_path / os.path.dirname(filepath)
        if not parent.exists():
            parent.mkdir(parents=True)
        f = (tmp_path / filepath).open('wb')
        f.truncate(filesize)  # Sparse file
        f.close()
        assert os.path.getsize(tmp_path / filepath) == filesize

    exceptions = await verify.verify_release_files(str(tmp_path / content_path), release_name)
    assert exceptions == exp_exceptions


@pytest.mark.asyncio
async def test_verify_release_gets_abbreviated_scene_file_name(mocker):
    assert_not_abbreviated_filename_mock = mocker.patch('upsies.utils.scene.verify.assert_not_abbreviated_filename', Mock(
        side_effect=errors.SceneAbbreviatedFilenameError('nope'),
    ))
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock())
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock())
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock())
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.unknown
    assert exceptions == (errors.SceneAbbreviatedFilenameError('nope'),)
    assert assert_not_abbreviated_filename_mock.call_args_list == [call('mock/path')]
    assert is_scene_release_mock.call_args_list == []
    assert verify_release_name_mock.call_args_list == []
    assert verify_release_files_mock.call_args_list == []

@pytest.mark.asyncio
async def test_verify_release_gets_nonscene_release_name(mocker):
    assert_not_abbreviated_filename_mock = mocker.patch('upsies.utils.scene.verify.assert_not_abbreviated_filename')
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.false,
    ))
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock())
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock())
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.false
    assert exceptions == ()
    assert assert_not_abbreviated_filename_mock.call_args_list == [call('mock/path')]
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == []
    assert verify_release_files_mock.call_args_list == []

@pytest.mark.asyncio
async def test_verify_release_gets_wrong_release_name(mocker):
    assert_not_abbreviated_filename_mock = mocker.patch('upsies.utils.scene.verify.assert_not_abbreviated_filename')
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.true,
    ))
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock(
        side_effect=errors.SceneRenamedError(original_name='foo', existing_name='bar'),
    ))
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock(
        return_value=(),
    ))
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (errors.SceneRenamedError(original_name='foo', existing_name='bar'),)
    assert assert_not_abbreviated_filename_mock.call_args_list == [call('mock/path')]
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == [call('mock/path', 'Mock.Release')]
    assert verify_release_files_mock.call_args_list == [call('mock/path', 'Mock.Release')]

@pytest.mark.asyncio
async def test_verify_release_gets_wrong_release_files(mocker):
    assert_not_abbreviated_filename_mock = mocker.patch('upsies.utils.scene.verify.assert_not_abbreviated_filename')
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.true,
    ))
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock())
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock(
        return_value=(
            errors.SceneFileSizeError('foo', original_size=123, existing_size=456),
            errors.SceneFileSizeError('bar', original_size=100, existing_size=200),
        ),
    ))
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (
        errors.SceneFileSizeError('foo', original_size=123, existing_size=456),
        errors.SceneFileSizeError('bar', original_size=100, existing_size=200),
    )
    assert assert_not_abbreviated_filename_mock.call_args_list == [call('mock/path')]
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == [call('mock/path', 'Mock.Release')]
    assert verify_release_files_mock.call_args_list == [call('mock/path', 'Mock.Release')]

@pytest.mark.asyncio
async def test_verify_release_gets_wrong_release_name_and_files(mocker):
    assert_not_abbreviated_filename_mock = mocker.patch('upsies.utils.scene.verify.assert_not_abbreviated_filename')
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.true,
    ))
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock(
        side_effect=errors.SceneRenamedError(original_name='foo', existing_name='bar'),
    ))
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock(
        return_value=(
            errors.SceneFileSizeError('foo', original_size=123, existing_size=456),
            errors.SceneFileSizeError('bar', original_size=100, existing_size=200),
        ),
    ))
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (
        errors.SceneRenamedError(original_name='foo', existing_name='bar'),
        errors.SceneFileSizeError('foo', original_size=123, existing_size=456),
        errors.SceneFileSizeError('bar', original_size=100, existing_size=200),
    )
    assert assert_not_abbreviated_filename_mock.call_args_list == [call('mock/path')]
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == [call('mock/path', 'Mock.Release')]
    assert verify_release_files_mock.call_args_list == [call('mock/path', 'Mock.Release')]
