import re
from unittest.mock import Mock, call

import pytest

from upsies.utils.scene import srrdb


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def api():
    return srrdb.SrrDbApi()


def test_name():
    assert srrdb.SrrDbApi.name == 'srrdb'


def test_label():
    assert srrdb.SrrDbApi.label == 'srrDB'


def test_default_config():
    assert srrdb.SrrDbApi.default_config == {}


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
