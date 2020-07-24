import pytest

from upsies.tools.dbs import tvmaze
from upsies.tools.dbs.tvmaze import _info


@pytest.mark.asyncio
async def test_summary(store_request_cache):
    assert 'Attack of the Clones' in await tvmaze.summary('563')
    assert 'Revenge of the Sith' in await tvmaze.summary('563')

@pytest.mark.asyncio
async def test_year(store_request_cache):
    assert await tvmaze.year('563') == '2008'

title_test_cases = (
    ('35256', 'Something in the Rain', 'Bap Jal Sajuneun Yeppeun Nuna'),
    ('37993', 'Traffic Light', 'Ramzor'),
    ('36072', 'The Chalet', 'Le chalet'),
)

@pytest.mark.asyncio
@pytest.mark.parametrize('id, english, original', title_test_cases)
async def test_title_original_english(id, english, original, store_request_cache):
    assert await tvmaze.title_english(id) == english
    assert await tvmaze.title_original(id) == original

@pytest.mark.asyncio
async def test_cast(store_request_cache):
    assert 'Bryan Cranston' in await _info.cast('169')
