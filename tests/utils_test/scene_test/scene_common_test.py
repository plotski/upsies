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
