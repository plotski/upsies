import re
from unittest.mock import AsyncMock, Mock, call

import pytest

from upsies.utils.scene import srrdb


@pytest.fixture
def api():
    return srrdb.SrrdbApi()


def test_name():
    assert srrdb.SrrdbApi.name == 'srrdb'


def test_label():
    assert srrdb.SrrdbApi.label == 'srrDB'


def test_default_config():
    assert srrdb.SrrdbApi.default_config == {}


@pytest.mark.parametrize('group', (None, '', 'ASDF'), ids=lambda v: str(v))
@pytest.mark.parametrize(
    argnames='keywords, keyword_separators_regex, exp_path',
    argvalues=(
        (['10,000', 'BC'], None, "10/000/bc"),
        (["Lot's", 'of', 'Riff-Raff'], re.compile(r'[-]'), "lot's/of/riff/raff"),
        (["Lot's", 'of', 'Riff-Raff'], re.compile(r"[']"), "lot/s/of/riff-raff"),
        (["Lot's", 'of', 'Riff-Raff'], re.compile(r"['\-]"), "lot/s/of/riff/raff"),
    ),
)
@pytest.mark.asyncio
async def test_search_calls_http_get(keywords, keyword_separators_regex, exp_path, group, api, mocker):
    response = Mock(json=Mock(return_value={
        'results': [{'release': 'Foo'}],
    }))
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=response))
    if keyword_separators_regex:
        mocker.patch.object(api, '_keyword_separators_regex', keyword_separators_regex)

    if group:
        exp_path += f'/group:{group.lower()}'

    response = await api._search(keywords=keywords, group=group)
    assert get_mock.call_args_list == [
        call(f'{api._search_url}/{exp_path}', cache=True),
    ]
    assert list(response) == ['Foo']
