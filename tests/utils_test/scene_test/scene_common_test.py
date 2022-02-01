import pytest

from upsies.utils.scene import common
from upsies.utils.types import ReleaseType


@pytest.mark.parametrize(
    argnames='source, irrelevant_keys',
    argvalues=(
        ('BluRay', ()),
        ('DVDRip', ('resolution')),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.parametrize(
    argnames='release_info, exp_keys',
    argvalues=(
        ({'type': ReleaseType.movie}, ('title', 'year', 'resolution', 'source', 'video_codec', 'group')),
        ({'type': ReleaseType.season}, ('title', 'episodes', 'resolution', 'source', 'video_codec', 'group')),
        ({'type': ReleaseType.episode}, ('title', 'episodes', 'resolution', 'source', 'video_codec', 'group')),
        ({'type': None}, ()),
        ({'type': 'something weird'}, ()),
    ),
    ids=lambda v: str(v),
)
def test_get_needed_keys(release_info, exp_keys, source, irrelevant_keys):
    release_info['source'] = source
    exp_keys = tuple(k for k in exp_keys if k not in irrelevant_keys)
    assert common.get_needed_keys(release_info) == exp_keys


@pytest.mark.parametrize(
    argnames='release_name, exp_season_pack',
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
        ('X.S01E03-E04.Episode.Title.German.DL.DVDRip.x264-ASDF', 'X.S01.German.DL.DVDRip.x264-ASDF'),
    ),
)
def test_get_season_pack_name(release_name, exp_season_pack):
    season_pack = common.get_season_pack_name(release_name)
    assert season_pack == exp_season_pack
