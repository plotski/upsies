import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(scope='module', autouse=True)
def disable_http_requests(pytestconfig, module_mocker):
    if not pytestconfig.getoption('--allow-requests', None):
        exc = RuntimeError('HTTP requests are disabled; use --allow-requests')

        class AsyncMock(Mock):
            def __call__(self, *args, **kwargs):
                async def coro(_sup=super()):
                    return _sup.__call__(*args, **kwargs)
                return coro()

        # We can't patch utils.http._request() because we want it to return
        # cached requests. utils.http._request() only uses
        # httpx.AsyncClient.send() so we can patch that.
        module_mocker.patch('httpx.AsyncClient.send', AsyncMock(side_effect=exc))


# When HTTP requests are allowed, store responses tests/data/webdbs.
# See tests/conftest.py for the data_dir fixture.
@pytest.fixture(scope='session')
def store_response(data_dir):
    cache_dir = os.path.join(data_dir, 'scene')
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)
    with patch('upsies.constants.CACHE_DIRPATH', cache_dir):
        yield
