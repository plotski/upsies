import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(scope='module', autouse=True)
def disable_http_requests(pytestconfig, module_mocker):
    from upsies.utils import http
    if not pytestconfig.getoption('--allow-requests', None):
        exc = RuntimeError('HTTP requests are disabled; use --allow-requests')

        # We can't patch utils.http._request() because we want it to return
        # cached requests. utils.http._request() only uses
        # httpx.AsyncClient.send() so we can patch that.
        module_mocker.patch.object(http._client, 'send', Mock(side_effect=exc))


# When HTTP requests are allowed, store responses tests/data/webdbs.
# See tests/conftest.py for the data_dir fixture.
@pytest.fixture(scope='session')
def store_response(data_dir):
    tmpdir = os.path.join(data_dir, 'webdbs')
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    with patch('upsies.utils.fs.tmpdir', Mock(return_value=tmpdir)):
        yield
