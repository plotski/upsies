import os
from unittest.mock import Mock, patch

import pytest


# Platform independent fs.filename_sanitization() mocking fixture from
# tests/conftest.py
@pytest.fixture(scope='module', autouse=True)
def strict_filename_sanitization(strict_filename_sanitization):
    pass


@pytest.fixture(scope='module', autouse=True)
def disable_http_requests(pytestconfig, module_mocker):
    from upsies.utils import http
    if not pytestconfig.getoption('--allow-requests', None):
        exc = RuntimeError('HTTP requests are disabled; use --allow-requests')

        # We can't patch utils.http._request() because we want it to return
        # cached requests. utils.http._request() only uses
        # httpx.AsyncClient.send() so we can patch that.
        module_mocker.patch('httpx.AsyncClient.send', Mock(side_effect=exc))


# When HTTP requests are allowed, store responses tests/data/webdbs.
# See tests/conftest.py for the data_dir fixture.
@pytest.fixture(scope='session')
def store_response(data_dir):
    cache_dir = os.path.join(data_dir, 'webdbs')
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)
    with patch('upsies.constants.CACHE_DIRPATH', cache_dir):
        yield
