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
def test_assert_not_abbreviated_filename(filename, should_raise):
    exp_msg = re.escape(
        f'Provide parent directory of abbreviated scene file: {filename}'
    )
    if should_raise:
        with pytest.raises(errors.SceneError, match=rf'^{exp_msg}$'):
            verify.assert_not_abbreviated_filename(filename)
        with pytest.raises(errors.SceneError, match=rf'^{exp_msg}$'):
            verify.assert_not_abbreviated_filename(f'path/to/{filename}')
    else:
        verify.assert_not_abbreviated_filename(filename)
        verify.assert_not_abbreviated_filename(f'path/to/{filename}')


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

        # Ignore resolution for DVDRip
        ('The.Fall.Guy.S02.480p.DVDRip.XviD.AAC-nodlabs', SceneCheckResult.true),

        # Non-scene release
        ('Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', SceneCheckResult.false),
        ('Damnation.S01.720p.AMZN.WEB-DL.DDP5.1.H.264-AJP69', SceneCheckResult.false),
        ('Damnation.S01E03.One.Penny.720p.AMZN.WEB-DL.DD+5.1.H.264-AJP69.mkv', SceneCheckResult.false),
    ),
)
@pytest.mark.asyncio
async def test_is_scene_release(release_name, exp_return_value, store_response):
    assert await verify.is_scene_release(release_name) is exp_return_value
    assert await verify.is_scene_release(ReleaseInfo(release_name)) is exp_return_value

@pytest.mark.asyncio
async def test_is_scene_release_with_no_needed_keys(mocker):
    mocker.patch('upsies.utils.scene.verify._predb.search', AsyncMock(return_value=('a', 'b')))
    mocker.patch('upsies.utils.scene.common.get_needed_keys', Mock(return_value=()))
    assert await verify.is_scene_release('Some.Release-NAME') is SceneCheckResult.unknown


@pytest.mark.parametrize(
    argnames='release_name, exp_return_value',
    argvalues=(
        # Looking for single-file release when original release was single-file
        ('Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         {'ly-dellmdm1080p.mkv': {'release_name': 'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
                                  'file_name': 'ly-dellmdm1080p.mkv',
                                  'size': 7044061767,
                                  'crc': 'B59CE234'}}),

        # Looking for multi-file release when original release was multi-file
        ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
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
           'crc': '7B822E59'}}),

        # Looking for multi-file release when original releases where single-file
        ('Fawlty.Towers.S01.720p.BluRay.x264-SHORTBREHD',
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
           'size': 1559556862, 'crc': '9FAB6E5F'}}),

        # Looking for single episode from multi-file release
        ('Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
         {'Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv':
          {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
           'file_name': 'Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
           'size': 138052914,
           'crc': 'E4E41C29'}}),

        # Looking for single non-episode file from multi-file release
        ('Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT',
         {'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv':
          {'release_name': 'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
           'file_name': 'Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
           'size': 779447228,
           'crc': '8C8C0AE7'}}),

        # # Non-scene release
        ('Foo.2015.1080p.Bluray.DD5.1.x264-DON.mkv', {}),
    ),
)
@pytest.mark.asyncio
async def test_release_files(release_name, exp_return_value, store_response):
    assert await verify.release_files(release_name) == exp_return_value


@pytest.mark.parametrize(
    argnames='content_path, release_name, exp_exception',
    argvalues=(
        # Abbreviated file in properly named directory
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         errors.SceneError('Provide parent directory of abbreviated scene file: ly-dellmdm1080p.mkv')),

        # Abbreviated file in non-release directory
        ('path/to/ly-dellmdm1080p.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         errors.SceneError('Provide parent directory of abbreviated scene file: ly-dellmdm1080p.mkv')),

        # Non-scene release
        ('path/to/Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv',
         'Rampart.2011.1080p.Bluray.DD5.1.x264-DON',
         errors.SceneError('Not a scene release: Rampart.2011.1080p.Bluray.DD5.1.x264-DON')),

        # Properly named directory
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         None),

        # Properly named file
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         None),

        # Renamed
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.X264-LiViDiTY',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         errors.SceneRenamedError(original_name='Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
                                  existing_name='Dellamorte.Dellamore.1994.1080p.BluRay.X264-LiViDiTY')),

        # File from release
        ('path/to/side.effects.2013.720p.bluray.x264-sparks.mkv',
         'Side.Effects.2013.720p.BluRay.x264-SPARKS',
         None),

        # Renamed file from release
        ('path/to/side.effects.2013.720p.bluray.x264-SPARKS.mkv',
         'Side.Effects.2013.720p.BluRay.x264-SPARKS',
         errors.SceneRenamedError(original_name='Side.Effects.2013.720p.BluRay.x264-SPARKS',
                                  existing_name='side.effects.2013.720p.bluray.x264-SPARKS.mkv')),

        # Multi-file release
        ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         (),),

        # Renamed multi-file release
        ('path/to/Bored.to.Death.S01.Extras.720p.BluRay.x264-iNGOT',
         'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         errors.SceneRenamedError(original_name='Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
                                  existing_name='Bored.to.Death.S01.Extras.720p.BluRay.x264-iNGOT')),

        # Single file from multi-file release
        ('path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
         'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         None),
    ),
)
@pytest.mark.asyncio
async def test_verify_release_name(content_path, release_name, exp_exception, store_response):
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await verify.verify_release_name(content_path, release_name)
    else:
        await verify.verify_release_name(content_path, release_name)


@pytest.mark.parametrize(
    argnames='content_path, release_name, file_sizes, exp_exceptions',
    argvalues=(
        # Abbreviated file in properly named directory
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', 7044061767),),
         (errors.SceneError('Provide parent directory of abbreviated scene file: ly-dellmdm1080p.mkv'),)),

        # Abbreviated file in non-release directory
        ('path/to/ly-dellmdm1080p.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/ly-dellmdm1080p.mkv', 7044061767),),
         (errors.SceneError('Provide parent directory of abbreviated scene file: ly-dellmdm1080p.mkv'),)),

        # Non-scene release
        ('path/to/Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv',
         'Rampart.2011.1080p.Bluray.DD5.1.x264-DON',
         (('path/to/Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', 7793811601),),
         (errors.SceneError('Not a scene release: Rampart.2011.1080p.Bluray.DD5.1.x264-DON'),)),

        # Abbreviated file in properly named directory with correct size
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', 7044061767),),
         ()),

        # Abbreviated file in properly named directory with wrong size
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY/ly-dellmdm1080p.mkv', 123),),
         (errors.SceneFileSizeError(filename='ly-dellmdm1080p.mkv',
                                    original_size=7044061767, existing_size=123),)),

        # Properly named file with correct size
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', 7044061767),),
         ()),

        # Properly named file with wrong size
        ('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv', 123),),
         (errors.SceneFileSizeError(filename='Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY.mkv',
                                    original_size=7044061767, existing_size=123),)),

        # Renamed file with correct size
        ('path/to/dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv', 7044061767),),
         ()),

        # Renamed file with wrong size
        ('path/to/dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv',
         'Dellamorte.Dellamore.1994.1080p.BluRay.x264-LiViDiTY',
         (('path/to/dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv', 123),),
         (errors.SceneFileSizeError(filename='dellamorte.dellamore.1994.1080p.bluray.x264-lividity.mkv',
                                    original_size=7044061767, existing_size=123),)),

        # Missing scene release info
        # (I think this was released with wrong episode order.)
        ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS',
         'The.Fall.S02.720p.BluRay.x264-7SinS',
         (('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e01-720p.mkv', 2340971701),
          ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e02-720p.mkv', 2345872861),
          ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e03-720p.mkv', 2345958712),
          ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e04-720p.mkv', 2346136836),
          ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e05-720p.mkv', 123),  # No info about this one
          ('path/to/The.Fall.S02.720p.BluRay.x264-7SinS/7s-tf-s02e06-720p.mkv', 3517999979)),
         (errors.SceneFileSizeError(filename='7s-tf-s02e02-720p.mkv',
                                    original_size=2345872860, existing_size=2345872861),
          errors.SceneMissingInfoError('7s-tf-s02e05-720p.mkv'),
          errors.SceneFileSizeError(filename='7s-tf-s02e06-720p.mkv',
                                    original_size=3517999978, existing_size=3517999979))),

        # Multi-file release
        ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         (('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv', 518652629),
          ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv', 779447228),
          ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E03.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv', 30779540),
          ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv', 138052913),
          ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E08.Deleted.Scene.1.720p.BluRay.x264-iNGOT.mkv', 68498554),
          ('path/to/Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E08.Deleted.Scene.2.720p.BluRay.x264-iNGOT.mkv', 45583011),),
         (errors.SceneFileSizeError(filename='Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv',
                                    original_size=138052914, existing_size=138052913),)),

        # Single file from multi-file release
        ('path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
         'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         (('path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv', 779447228),),
         (),),
        ('path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
         'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         (('path/to/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv', 779447229),),
         (errors.SceneFileSizeError(filename='Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv',
                                    original_size=779447228, existing_size=779447229),)),

        # Renamed single file from multi-file release
        ('path/to/Bored.to.Death.S01.MAKING.OF.720p.BluRay.x264-iNGOT.mkv',
         'Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT',
         (('path/to/Bored.to.Death.S01.MAKING.OF.720p.BluRay.x264-iNGOT.mkv', 779447228),),
         (errors.SceneMissingInfoError('Bored.to.Death.S01.MAKING.OF.720p.BluRay.x264-iNGOT.mkv'),),),
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
        side_effect=errors.SceneError('nope'),
    ))
    is_scene_release_mock = mocker.patch('upsies.utils.scene.verify.is_scene_release', AsyncMock())
    verify_release_name_mock = mocker.patch('upsies.utils.scene.verify.verify_release_name', AsyncMock())
    verify_release_files_mock = mocker.patch('upsies.utils.scene.verify.verify_release_files', AsyncMock())
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.unknown
    assert exceptions == (errors.SceneError('nope'),)
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
            errors.SceneFileSizeError('foo', 123, 456),
            errors.SceneFileSizeError('bar', 100, 200),
        ),
    ))
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (
        errors.SceneFileSizeError('foo', 123, 456),
        errors.SceneFileSizeError('bar', 100, 200),
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
            errors.SceneFileSizeError('foo', 123, 456),
            errors.SceneFileSizeError('bar', 100, 200),
        ),
    ))
    is_scene, exceptions = await verify.verify_release('mock/path', 'Mock.Release')
    assert is_scene is SceneCheckResult.true
    assert exceptions == (
        errors.SceneRenamedError(original_name='foo', existing_name='bar'),
        errors.SceneFileSizeError('foo', 123, 456),
        errors.SceneFileSizeError('bar', 100, 200),
    )
    assert assert_not_abbreviated_filename_mock.call_args_list == [call('mock/path')]
    assert is_scene_release_mock.call_args_list == [call('Mock.Release')]
    assert verify_release_name_mock.call_args_list == [call('mock/path', 'Mock.Release')]
    assert verify_release_files_mock.call_args_list == [call('mock/path', 'Mock.Release')]
