import os
import re
from unittest.mock import Mock, call

import pytest

from upsies import constants, errors
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
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264.mkv',
            SceneCheckResult.false,
            id='Movie: NOGROUP',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-NOGROUP.mkv',
            SceneCheckResult.false,
            id='Movie: NOGROUP',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-NoGrp.mkv',
            SceneCheckResult.false,
            id='Movie: NOGROUP',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            SceneCheckResult.true,
            id='Movie: Properly named file',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY.mkv',
            SceneCheckResult.true,
            id='Movie: Properly named file',
        ),
        pytest.param(
            'dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity.mkv',
            SceneCheckResult.true,
            id='Movie: Properly named file',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            SceneCheckResult.true,
            id='Movie: Properly named file in properly named directory',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            SceneCheckResult.true,
            id='Movie: Properly named file in properly named directory',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY.mkv',
            SceneCheckResult.true,
            id='Movie: Properly named file in properly named directory',
        ),

        pytest.param(
            'path/to/ly-dellmdm1080p.mkv',
            SceneCheckResult.unknown,
            id='Movie: Abbreviated file without usably named parent directory',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
            SceneCheckResult.true,
            id='Movie: Abbreviated file in usably named directory',
        ),
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.Blu-ray.x264-LiViDiTY/ly-dellmdm1080p.mkv',
            SceneCheckResult.true,
            id='Movie: Abbreviated file in usably named directory',
        ),
        pytest.param(
            'dellamorte.dellamore.1994.1080p.blu-ray.x264-lividity/ly-dellmdm1080p.mkv',
            SceneCheckResult.true,
            id='Movie: Abbreviated file in usably named directory',
        ),

        pytest.param(
            'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
            SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),
        pytest.param(
            'bored.to.death.s01.720p.bluray.x264-ingot',
            SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),
        pytest.param(
            'Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv',
            SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),
        pytest.param(
            'bored.to.death.s01.720p.bluray.x264-ingot.mkv',
            SceneCheckResult.true,
            id='Series: Scene released season pack',
        ),

        pytest.param(
            'Justified.S04E01.720p.BluRay.x264-REWARD',
            SceneCheckResult.true,
            id='Series: Scene released single episodes',
        ),

        pytest.param(
            'Justified.S04E99.720p.BluRay.x264-REWARD',
            SceneCheckResult.false,
            id='Series: Scene released single episodes',
        ),

        pytest.param(
            'Justified.S04.720p.BluRay.x264-REWARD',
            SceneCheckResult.true,
            id='Series: Scene released single episodes',
        ),

        pytest.param(
            'Justified.S02.720p.BluRay.x264-REWARD',
            SceneCheckResult.false,
            id='Series: Missing season from scene group',
        ),

        pytest.param(
            'Justified.720p.BluRay.x264-REWARD',
            SceneCheckResult.unknown,
            id='Series: Not enough information in release name',
        ),

        pytest.param(
            'Friends.S10.1080p.BluRay.x264-TENEIGHTY',
            SceneCheckResult.true,
            id='Series: Lots of seasons and episodes',
        ),

        pytest.param(
            'The.Fall.Guy.S02.480p.DVDRip.XviD.AAC-nodlabs',
            SceneCheckResult.true,
            id='Resolution is ignored for DVDRip',
        ),

        pytest.param(
            'Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv',
            SceneCheckResult.false,
            id='Non-scene movie release',
        ),

        pytest.param(
            'Damnation.S01.720p.AMZN.WEB-DL.DDP5.1.H.264-AJP69',
            SceneCheckResult.false,
            id='Non-scene season release',
        ),

        pytest.param(
            'Damnation.S01E03.One.Penny.720p.AMZN.WEB-DL.DD+5.1.H.264-AJP69.mkv',
            SceneCheckResult.false,
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
    assert await verify.is_scene_release('Title.2015.x264-ASDF') is SceneCheckResult.unknown
    assert await verify.is_scene_release('Title.1080p.x264-ASDF') is SceneCheckResult.unknown

@pytest.mark.asyncio
async def test_is_scene_release_with_no_needed_keys(mocker):
    mocker.patch('upsies.utils.scene.find.search', AsyncMock(return_value=('a', 'b')))
    mocker.patch('upsies.utils.scene.common.get_needed_keys', Mock(return_value=()))
    assert await verify.is_scene_release('Some.Release.x264-NAME') is SceneCheckResult.unknown


@pytest.mark.parametrize(
    argnames='directory_name, files, exp_return_value',
    argvalues=(
        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            (
                'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
            ),
            False,
            id='Movie as file',
        ),

        pytest.param(
            'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
            (
                'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
            ),
            False,
            id='Movie in directory',
        ),

        pytest.param(
            'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD',
            (
                'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E01.720p.BluRay.x264-SHORTBREHD.mkv',
                'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E02.720p.BluRay.x264-SHORTBREHD.mkv',
                'Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E03.720p.BluRay.x264-SHORTBREHD.mkv',
            ),
            False,
            id='Non-mixed season pack',
        ),

        pytest.param(
            'Drunk.History.S01.720p.HDTV.x264-MiXED',
            (
                'Drunk.History.S01.720p.HDTV.x264-MiXED/drunk.history.s01e01.720p.hdtv.x264-killers.mkv',
                'Drunk.History.S01.720p.HDTV.x264-MiXED/drunk.history.s01e02.720p.hdtv.x264-2hd.mkv',
                'Drunk.History.S01.720p.HDTV.x264-MiXED/drunk.history.s01e03.720p.hdtv.x264.mkv',
                'Drunk.History.S01.720p.HDTV.x264-MiXED/Drunk.History.S01E04.720p.HDTV.x264-EVOLVE.mkv',
            ),
            True,
            id='Season pack with 2 scene groups',
        ),

        pytest.param(
            'Drunk.History.S01.720p.HDTV.x264-MiXED',
            (
                'Drunk.History.S01.720p.HDTV.x264-MiXED/drunk.history.s01e01.720p.hdtv.x264-killers.mkv',
                'Drunk.History.S01.720p.HDTV.x264-MiXED/drunk.history.s01e02.720p.hdtv.x264-2hd.mkv',
                'Drunk.History.S01.720p.HDTV.x264-MiXED/drunk.history.s01e03.720p.hdtv.x264-2hd.mkv',
                'Drunk.History.S01.720p.HDTV.x264-MiXED/Drunk.History.S01E04.720p.HDTV.x264-EVO.mkv',
            ),
            True,
            id='Season pack with 2 scene groups and 1 non-scene group',
        ),

        pytest.param(
            'Drunk.History.S01.720p.HDTV.x264',
            (
                'Drunk.History.S01.720p.HDTV.x264/drunk.history.s01e01.720p.hdtv.x264-killers.mkv',
                'Drunk.History.S01.720p.HDTV.x264/drunk.history.s01e02.720p.hdtv.x264.mkv',
                'Drunk.History.S01.720p.HDTV.x264/Drunk.History.S01E04.720p.HDTV.x264-EVO.mkv',
            ),
            False,
            id='Season pack with 1 scene group and 1 non-scene group and 1 nogroup',
        ),
    ),
)
@pytest.mark.asyncio
async def test_is_mixed_scene_release(directory_name, files, exp_return_value, store_response, tmp_path):
    for filepath in files:
        filepath = tmp_path / filepath
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(f'this is {filepath}')

    directory_path = str(tmp_path / directory_name)
    assert await verify.is_mixed_scene_release(directory_path) == exp_return_value


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
            'Drunk.History.S01.720p.HDTV.x264-2HD',
            {
                'drunk.history.s01e02.720p.hdtv.x264-2hd.mkv': {
                    'release_name': 'Drunk.History.S01E02.720p.HDTV.x264-2HD',
                    'file_name': 'drunk.history.s01e02.720p.hdtv.x264-2hd.mkv',
                    'size': 534364440, 'crc': 'F074DA2A',
                },
                'drunk.history.s01e03.720p.hdtv.x264-2hd.mkv': {
                    'release_name': 'Drunk.History.S01E03.720p.HDTV.x264-2HD',
                    'file_name': 'drunk.history.s01e03.720p.hdtv.x264-2hd.mkv',
                    'size': 525260014, 'crc': 'BBA99EED',
                },
            },
            id='Looking for incomplete season pack',
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
            'Friends.S10.1080p.Blu-ray.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
            'Friends.S10.1080p.BluRay.x264-TENEIGHTY',
            errors.SceneRenamedError(original_name='Friends.S10.1080p.BluRay.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv',
                                     existing_name='Friends.S10.1080p.Blu-ray.x264-TENEIGHTY/teneighty-friendss10e17e18.mkv'),
            id='[EPISODE] Abbreviated file name in renamed season directory',
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
            id='[EPISODE] Renamed abbreviated file name in properly named episode directory',
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

        pytest.param(
            'foo',
            'Wrecked.2011.DiRFiX.LIMITED.FRENCH.720p.BluRay.X264-LOST',
            errors.SceneRenamedError(original_name='Wrecked.2011.DiRFiX.LIMITED.FRENCH.720p.BluRay.X264-LOST',
                                     existing_name='foo'),
            id='Empty release',
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
async def test_verify_release_gets_release_name(mocker):
    _verify_release_mock = mocker.patch('upsies.utils.scene.verify._verify_release', AsyncMock())
    _verify_release_per_file_mock = mocker.patch('upsies.utils.scene.verify._verify_release_per_file', AsyncMock())

    content_path = 'mock/path/to/Mock.Release'
    release_name = 'Mock.Release'
    return_value = await verify.verify_release(content_path, release_name)

    assert return_value is _verify_release_mock.return_value
    assert _verify_release_mock.call_args_list == [call(content_path, release_name)]
    assert _verify_release_per_file_mock.call_args_list == []

@pytest.mark.asyncio
async def test_verify_release_gets_no_release_name_and_finds_no_matching_scene_release(mocker):
    _verify_release_mock = mocker.patch('upsies.utils.scene.verify._verify_release', AsyncMock())
    search_mock = mocker.patch('upsies.utils.scene.find.search', AsyncMock(
        return_value=(),
    ))
    _verify_release_per_file_mock = mocker.patch('upsies.utils.scene.verify._verify_release_per_file', AsyncMock())

    content_path = 'mock/path/to/Mock.Release'
    return_value = await verify.verify_release(content_path)

    assert return_value == (SceneCheckResult.false, ())
    assert search_mock.call_args_list == [call(content_path)]
    assert _verify_release_mock.call_args_list == []
    assert _verify_release_per_file_mock.call_args_list == []

@pytest.mark.asyncio
async def test_verify_release_finds_valid_scene_release(mocker):
    verify_release_results = {
        'The.Foo.2000.x264-AAA': (SceneCheckResult.false, ()),
        'The.Foo.2000.x264-BBB': (SceneCheckResult.unknown, ()),
        'The.Foo.2000.x264-CCC': (SceneCheckResult.true, (errors.SceneRenamedError(original_name='foo', existing_name='bar'),)),
        'The.Foo.2000.x264-DDD': (SceneCheckResult.true, ()),
        'The.Foo.2000.x264-EEE': (SceneCheckResult.true, (errors.SceneFileSizeError('foo', original_size=123, existing_size=456),)),
    }

    _verify_release_mock = mocker.patch('upsies.utils.scene.verify._verify_release', AsyncMock(
        side_effect=tuple(verify_release_results.values()),
    ))
    search_mock = mocker.patch('upsies.utils.scene.find.search', AsyncMock(
        return_value=tuple(verify_release_results.keys()),
    ))
    _verify_release_per_file_mock = mocker.patch('upsies.utils.scene.verify._verify_release_per_file', AsyncMock())

    content_path = 'mock/path/to/Mock.Release'
    return_value = await verify.verify_release(content_path)

    assert return_value == (SceneCheckResult.true, ())
    assert search_mock.call_args_list == [call(content_path)]
    assert _verify_release_mock.call_args_list == [
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-AAA'),
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-BBB'),
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-CCC'),
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-DDD'),
    ]
    assert _verify_release_per_file_mock.call_args_list == []

@pytest.mark.asyncio
async def test_verify_release_finds_only_nonscene_releases(mocker):
    verify_release_results = {
        'The.Foo.2000.x264-AAA': (SceneCheckResult.false, ()),
        'The.Foo.2000.x264-BBB': (SceneCheckResult.unknown, ()),
    }

    _verify_release_mock = mocker.patch('upsies.utils.scene.verify._verify_release', AsyncMock(
        side_effect=tuple(verify_release_results.values()),
    ))
    search_mock = mocker.patch('upsies.utils.scene.find.search', AsyncMock(
        return_value=tuple(verify_release_results.keys()),
    ))
    _verify_release_per_file_mock = mocker.patch('upsies.utils.scene.verify._verify_release_per_file', AsyncMock())

    content_path = 'mock/path/to/Mock.Release'
    return_value = await verify.verify_release(content_path)

    assert return_value is _verify_release_per_file_mock.return_value
    assert search_mock.call_args_list == [call(content_path)]
    assert _verify_release_mock.call_args_list == [
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-AAA'),
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-BBB'),
    ]
    assert _verify_release_per_file_mock.call_args_list == [call(content_path)]

@pytest.mark.asyncio
async def test_verify_release_finds_only_scene_releases_with_exceptions(mocker):
    verify_release_results = {
        'The.Foo.2000.x264-AAA': (SceneCheckResult.true, (errors.SceneRenamedError(original_name='foo', existing_name='bar'),)),
        'The.Foo.2000.x264-BBB': (SceneCheckResult.unknown, ()),
        'The.Foo.2000.x264-CCC': (SceneCheckResult.true, (errors.SceneFileSizeError('foo', original_size=123, existing_size=456),)),
    }

    _verify_release_mock = mocker.patch('upsies.utils.scene.verify._verify_release', AsyncMock(
        side_effect=tuple(verify_release_results.values()),
    ))
    search_mock = mocker.patch('upsies.utils.scene.find.search', AsyncMock(
        return_value=tuple(verify_release_results.keys()),
    ))
    _verify_release_per_file_mock = mocker.patch('upsies.utils.scene.verify._verify_release_per_file', AsyncMock(
        return_value='_verify_release_per_file return value',
    ))

    content_path = 'mock/path/to/Mock.Release'
    return_value = await verify.verify_release(content_path)

    assert return_value == '_verify_release_per_file return value'
    assert search_mock.call_args_list == [call(content_path)]
    assert _verify_release_mock.call_args_list == [
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-AAA'),
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-BBB'),
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-CCC'),
    ]
    assert _verify_release_per_file_mock.call_args_list == [call(content_path)]

@pytest.mark.asyncio
async def test_verify_release_finds_nothing(mocker):
    verify_release_results = {
        'The.Foo.2000.x264-AAA': (SceneCheckResult.false, ()),
        'The.Foo.2000.x264-BBB': (SceneCheckResult.unknown, ()),
    }

    _verify_release_mock = mocker.patch('upsies.utils.scene.verify._verify_release', AsyncMock(
        side_effect=tuple(verify_release_results.values()),
    ))
    search_mock = mocker.patch('upsies.utils.scene.find.search', AsyncMock(
        return_value=tuple(verify_release_results.keys()),
    ))
    _verify_release_per_file_mock = mocker.patch('upsies.utils.scene.verify._verify_release_per_file', AsyncMock(
        return_value='_verify_release_per_file return value',
    ))

    content_path = 'mock/path/to/Mock.Release'
    return_value = await verify.verify_release(content_path)

    assert return_value == '_verify_release_per_file return value'
    assert search_mock.call_args_list == [call(content_path)]
    assert _verify_release_mock.call_args_list == [
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-AAA'),
        call('mock/path/to/Mock.Release', 'The.Foo.2000.x264-BBB'),
    ]
    assert _verify_release_per_file_mock.call_args_list == [call(content_path)]


@pytest.mark.parametrize(
    argnames='mock_data, exp_search_calls, exp_verify_release_calls, exp_is_scene_release, exp_exceptions',
    argvalues=(
        pytest.param(
            {
                'foo.mkv': (
                    {'release_name': 'Foo-AAA', 'is_scene_release': SceneCheckResult.false, 'exceptions': ()},
                    {'release_name': 'Foo-BBB', 'is_scene_release': SceneCheckResult.true, 'exceptions': ()},
                ),
                'bar.mp4': (
                    {'release_name': 'Bar-AAA', 'is_scene_release': SceneCheckResult.true, 'exceptions': ()},
                    {'release_name': 'Bar-BBB', 'is_scene_release': SceneCheckResult.true,
                     'exceptions': (errors.SceneError('never found'),)},
                ),
            },
            [call('foo.mkv'), call('bar.mp4')],
            [call('foo.mkv', 'Foo-AAA'), call('foo.mkv', 'Foo-BBB'), call('bar.mp4', 'Bar-AAA')],
            SceneCheckResult.true,
            (),
            id='Verification is stopped after first match is found',
        ),

        pytest.param(
            {
                'foo.mkv': (
                    {'release_name': 'Foo-AAA', 'is_scene_release': SceneCheckResult.false, 'exceptions': ()},
                    {'release_name': 'Foo-BBB', 'is_scene_release': SceneCheckResult.unknown, 'exceptions': ()},
                ),
                'bar.mp4': (
                    {'release_name': 'Bar-AAA', 'is_scene_release': SceneCheckResult.true, 'exceptions': ()},
                    {'release_name': 'Bar-BBB', 'is_scene_release': SceneCheckResult.true,
                     'exceptions': (errors.SceneError('never found'),)},
                ),
            },
            [call('foo.mkv'), call('bar.mp4')],
            [call('foo.mkv', 'Foo-AAA'), call('foo.mkv', 'Foo-BBB'), call('bar.mp4', 'Bar-AAA')],
            SceneCheckResult.unknown,
            (),
            id='One scene check is unknown',
        ),

        pytest.param(
            {
                'foo.mkv': (
                    {'release_name': 'Foo-AAA', 'is_scene_release': SceneCheckResult.false, 'exceptions': ()},
                    {'release_name': 'Foo-BBB', 'is_scene_release': SceneCheckResult.false, 'exceptions': ()},
                ),
                'bar.mp4': (
                    {'release_name': 'Bar-AAA', 'is_scene_release': SceneCheckResult.false, 'exceptions': ()},
                    {'release_name': 'Bar-BBB', 'is_scene_release': SceneCheckResult.false, 'exceptions': ()},
                ),
            },
            [call('foo.mkv'), call('bar.mp4')],
            [call('foo.mkv', 'Foo-AAA'), call('foo.mkv', 'Foo-BBB'), call('bar.mp4', 'Bar-AAA'), call('bar.mp4', 'Bar-BBB')],
            SceneCheckResult.false,
            (),
            id='All scene checks are false',
        ),

        pytest.param(
            {
                'foo.mkv': (
                    {'release_name': 'Foo-AAA', 'is_scene_release': SceneCheckResult.true, 'exceptions': (errors.SceneError('foo!'),)},
                    {'release_name': 'Foo-BBB', 'is_scene_release': SceneCheckResult.true, 'exceptions': ()},
                ),
                'bar.mp4': (
                    {'release_name': 'Bar-AAA', 'is_scene_release': SceneCheckResult.true, 'exceptions': ()},
                    {'release_name': 'Bar-BBB', 'is_scene_release': SceneCheckResult.true, 'exceptions': ()},
                ),
            },
            [call('foo.mkv'), call('bar.mp4')],
            [call('foo.mkv', 'Foo-AAA'), call('foo.mkv', 'Foo-BBB'), call('bar.mp4', 'Bar-AAA')],
            SceneCheckResult.true,
            (errors.SceneError('foo!'),),
            id='One scene check returns exceptions',
        ),

        pytest.param(
            {
                'foo.mkv': (
                    {'release_name': 'Foo-AAA', 'is_scene_release': SceneCheckResult.true, 'exceptions': (errors.SceneError('foo!'),)},
                    {'release_name': 'Foo-BBB', 'is_scene_release': SceneCheckResult.true, 'exceptions': ()},
                ),
                'bar.mp4': (
                    {'release_name': 'Bar-AAA', 'is_scene_release': SceneCheckResult.false, 'exceptions': ()},
                    {'release_name': 'Bar-BBB', 'is_scene_release': SceneCheckResult.true, 'exceptions': (errors.SceneError('bar!'),)},
                ),
            },
            [call('foo.mkv'), call('bar.mp4')],
            [call('foo.mkv', 'Foo-AAA'), call('foo.mkv', 'Foo-BBB'), call('bar.mp4', 'Bar-AAA'), call('bar.mp4', 'Bar-BBB')],
            SceneCheckResult.true,
            (errors.SceneError('foo!'), errors.SceneError('bar!'), ),
            id='Multiple scene checks return exceptions',
        ),
    ),
)
@pytest.mark.asyncio
async def test__verify_release_per_file_verifies_each_search_result(
    mock_data, exp_search_calls, exp_verify_release_calls,
    exp_is_scene_release, exp_exceptions, mocker
):
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', Mock(
        return_value=mock_data.keys(),
    ))
    search_mock = mocker.patch('upsies.utils.scene.find.search', AsyncMock(
        side_effect=(
            tuple(data['release_name'] for data in datas)
            for datas in mock_data.values()
        )
    ))
    _verify_release_mock = mocker.patch('upsies.utils.scene.verify._verify_release', AsyncMock(
        side_effect=tuple(
            (data['is_scene_release'], data['exceptions'])
            for datas in mock_data.values()
            for data in datas
        )
    ))

    is_scene_release, exceptions = await verify._verify_release_per_file('path/to/content')
    assert is_scene_release == exp_is_scene_release
    assert exceptions == exp_exceptions

    assert file_list_mock.call_args_list == [call('path/to/content', extensions=constants.VIDEO_FILE_EXTENSIONS)]
    assert search_mock.call_args_list == exp_search_calls
    assert _verify_release_mock.call_args_list == exp_verify_release_calls


@pytest.mark.asyncio
async def test__verify_release_gets_nonscene_release_name(mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.false,
    ))
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock())
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock())
    is_scene, exceptions = await verify._verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.false
    assert exceptions == ()
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == []
    assert verify_release_files_mock.call_args_list == []

@pytest.mark.asyncio
async def test__verify_release_gets_wrong_release_name(mocker):
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock(
        return_value=SceneCheckResult.true,
    ))
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock(
        side_effect=errors.SceneRenamedError(original_name='foo', existing_name='bar'),
    ))
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock(
        return_value=(),
    ))
    is_scene, exceptions = await verify._verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (errors.SceneRenamedError(original_name='foo', existing_name='bar'),)
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == [call('mock/path', 'Mock.Release')]
    assert verify_release_files_mock.call_args_list == [call('mock/path', 'Mock.Release')]

@pytest.mark.asyncio
async def test__verify_release_gets_wrong_release_files(mocker):
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
    is_scene, exceptions = await verify._verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (
        errors.SceneFileSizeError('foo', original_size=123, existing_size=456),
        errors.SceneFileSizeError('bar', original_size=100, existing_size=200),
    )
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == [call('mock/path', 'Mock.Release')]
    assert verify_release_files_mock.call_args_list == [call('mock/path', 'Mock.Release')]

@pytest.mark.asyncio
async def test__verify_release_gets_wrong_release_name_and_wrong_files(mocker):
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
    is_scene, exceptions = await verify._verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (
        errors.SceneRenamedError(original_name='foo', existing_name='bar'),
        errors.SceneFileSizeError('foo', original_size=123, existing_size=456),
        errors.SceneFileSizeError('bar', original_size=100, existing_size=200),
    )
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == [call('mock/path', 'Mock.Release')]
    assert verify_release_files_mock.call_args_list == [call('mock/path', 'Mock.Release')]
