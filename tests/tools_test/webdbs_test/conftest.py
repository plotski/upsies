import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(scope='module', autouse=True)
def disable_http_requests(pytestconfig):
    from upsies.utils import http
    if pytestconfig.getoption('--allow-requests', None):
        yield
    else:
        # We can't patch utils.http._request() because we want it to return
        # cached requests. utils.http._request() only uses
        # httpx.AsyncClient.send() so we can patch that.
        exc = RuntimeError('HTTP requests are disabled; use --allow-requests')
        with patch.object(http._client, 'send', Mock(side_effect=exc)):
            yield


# When HTTP requests are allowed, store responses in ./cached_responses.
@pytest.fixture
def store_response():
    tmpdir = os.path.join(os.path.dirname(__file__), 'cached_responses')
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    with patch('upsies.utils.fs.tmpdir', Mock(return_value=tmpdir)):
        yield
