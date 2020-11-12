import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(scope='module', autouse=True)
def disable_aiohttp_ClientSession(pytestconfig):
    if pytestconfig.getoption('--allow-http-requests', None):
        yield
    else:
        exc = RuntimeError('aiohttp.ClientSession is disabled; use --allow-http-requests')
        with patch('aiohttp.ClientSession', Mock(side_effect=exc)):
            yield


@pytest.fixture
def store_response():
    tmpdir = os.path.join(os.path.dirname(__file__), 'cached_responses')
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    with patch('upsies.utils.fs.tmpdir', Mock(return_value=tmpdir)):
        yield
