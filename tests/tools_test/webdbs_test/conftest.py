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

        # IMDb uses imdbpie which doesn't use our utils.http module.
        module_mocker.patch('upsies.tools.webdbs.imdb._ImdbPie._sync_request', Mock(side_effect=exc))


# When HTTP requests are allowed, store responses in ./cached_responses.
@pytest.fixture
def store_response():
    tmpdir = os.path.join(os.path.dirname(__file__), 'cached_responses')
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    with patch('upsies.utils.fs.tmpdir', Mock(return_value=tmpdir)):
        yield
