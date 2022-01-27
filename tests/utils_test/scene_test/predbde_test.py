import re
from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.utils.scene import predbde


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def api():
    return predbde.PredbdeApi()


def test_name():
    assert predbde.PredbdeApi.name == 'predbde'


def test_label():
    assert predbde.PredbdeApi.label == 'PreDB.de'


def test_default_config():
    assert predbde.PredbdeApi.default_config == {}


@pytest.mark.parametrize(
    argnames='q, results, exp_results',
    argvalues=(
        (None, None, ()),
        ('', None, ()),
        ((), None, ()),
        ('kw1 kw2', ('Foo', 'Bar', 'Baz'), ('Foo', 'Bar', 'Baz')),
    ),
)
@pytest.mark.asyncio
async def test_search(q, results, exp_results, api, mocker):
    mocker.patch.object(api, '_get_q', return_value=q)
    mocker.patch.object(api, '_request_all_pages', AsyncMock(return_value=results))
    results = await api._search(('kw1', 'kw2'), group='ASDF')
    assert results == exp_results
    assert api._get_q.call_args_list == [call(('kw1', 'kw2'), 'ASDF')]
    if q:
        assert api._request_all_pages.call_args_list == [call(q)]
    else:
        assert api._request_all_pages.call_args_list == []


@pytest.mark.parametrize(
    argnames='keywords, group, exp_q',
    argvalues=(
        ((), None, ''),
        (('',), None, ''),
        ((' ', '', '  '), None, ''),
        (('foo', 'bar'), None, 'foo bar'),
        (('', '  '' foo ', '', '  ' 'b a r', '  ', '', ' ', 'baz', '', '  '), None, 'foo b a r baz'),
        (('foo', 'bar'), 'ASDF', 'foo bar asdf'),
    ),
    ids=lambda v: str(v),
)
def test_get_q(keywords, group, exp_q, api):
    q = api._get_q(keywords, group)
    assert q == exp_q


@pytest.mark.parametrize('last_result_index', (5, 6, 7, 8, 9, 10))
@pytest.mark.asyncio
async def test_request_all_pages_stops_when_there_is_no_next_page(last_result_index, api, mocker):
    results_count = 100
    results_per_page = 3
    results = [f'Result {i}' for i in range(1, (results_count) + 1)]

    pages = []
    for i in range(0, len(results), results_per_page):
        page = results[i:i + results_per_page]
        if i >= last_result_index - 2:
            page_len = last_result_index % results_per_page
            page = page[:page_len]
            next_page = -1
            pages.append((page, next_page))
            break
        else:
            page = results[i:i + results_per_page]
            next_page = int((i / results_per_page) + 2)
            pages.append((page, next_page))

    mocker.patch.object(api, '_request_page', AsyncMock(side_effect=pages))

    exp_results = results[:last_result_index]

    mock_q = 'foo bar baz'
    return_value = await api._request_all_pages(mock_q)
    assert return_value == exp_results

    max_page_index_requested = (last_result_index // results_per_page) + 1
    exp_request_page_calls = [
        call(mock_q, i) for i in range(1, max_page_index_requested + 1)
    ]
    assert api._request_page.call_args_list == exp_request_page_calls

@pytest.mark.asyncio
async def test_request_all_pages_does_not_request_pages_indefinitely(api, mocker):
    results_count = 100
    results_per_page = 3
    results = [f'Result {i}' for i in range(1, (results_count) + 1)]

    pages = [
        (results[i:i + results_per_page], int((i / results_per_page) + 2))
        for i in range(0, len(results), results_per_page)
    ]
    mocker.patch.object(api, '_request_page', AsyncMock(side_effect=pages))
    mocker.patch.object(api, '_max_pages', 10)

    exp_results = results[:results_per_page * (api._max_pages - 1)]

    mock_q = 'foo bar baz'
    return_value = await api._request_all_pages(mock_q)
    assert return_value == exp_results

    assert api._request_page.call_args_list == [
        call(mock_q, i) for i in range(1, api._max_pages)
    ]


@pytest.mark.parametrize(
    argnames='q, page, response, exp_return_value, exp_exception',
    argvalues=(
        (
            'foo bar baz',
            1,
            {'status': 'success', 'data': [{'release': f'Foo {i}'} for i in range(30)]},
            (tuple(f'Foo {i}' for i in range(30)), 2),
            None,
        ),
        (
            'foo bar baz',
            2,
            {'status': 'success', 'data': [{'release': f'Foo {i}'} for i in range(30)]},
            (tuple(f'Foo {i}' for i in range(30)), 3),
            None,
        ),
        (
            'foo bar baz',
            3,
            {'status': 'success', 'data': [{'release': f'Foo {i}'} for i in range(7)]},
            (tuple(f'Foo {i}' for i in range(7)), -1),
            None,
        ),
        (
            'foo bar baz',
            3,
            {'status': 'success', 'data': None},
            ((), -1),
            None,
        ),
        (
            'foo bar baz',
            3,
            {'status': 'not success', 'message': 'Something went wrong'},
            None,
            errors.RequestError(f'{predbde.PredbdeApi.label}: Something went wrong'),
        ),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_request_page(q, page, response, exp_return_value, exp_exception, api, mocker):
    mock_search_url = 'http://foo/api'
    mocker.patch.object(api, '_search_url', mock_search_url)

    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=Mock(
        json=Mock(return_value=response),
    )))

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            await api._request_page(q, page)
    else:
        return_value = await api._request_page(q, page)
        assert return_value == exp_return_value

    exp_params = {'q': q, 'page': page}
    assert get_mock.call_args_list == [call(mock_search_url, params=exp_params, cache=True)]


@pytest.mark.asyncio
async def test_release_files(api):
    return_value = await api.release_files('foo')
    assert return_value == {}
