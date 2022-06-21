import asyncio
import os

import pytest

from upsies.utils import http


@pytest.fixture(scope='module')
def strict_filename_sanitization(module_mocker):
    # Allow this project to be cloned on Windows.
    def sanitize_filename(filename):
        for c in r'<>:"/\|?*':
            filename = filename.replace(c, '_')
        return filename

    module_mocker.patch('upsies.utils.fs.sanitize_filename', sanitize_filename)


@pytest.fixture(scope='session')
def data_dir():
    segments = __file__.split(os.sep)
    tests_index = segments[::-1].index('tests')
    tests_dir = os.sep.join(segments[:-tests_index])
    data_dir = os.path.join(tests_dir, 'data')
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
    return data_dir


# Don't make HTTP requests unless they are explicitly allowed.
# See tests/tools_test/dbs_test/conftest.py
def pytest_addoption(parser):
    parser.addoption('--allow-requests', action='store_true',
                     help='Use this option to update the request cache')


# By default, pytest-asyncio uses a new loop for every test, but utils.http uses
# module-level request asyncio.Lock() objects to avoid making the same request
# multiple times simultaneously. This fixture uses the same event_loop for all
# test modules in this package and closes it after all tests ran.
@pytest.fixture(scope='module', autouse=True)
def event_loop():
    import httpx
    http._client = httpx.AsyncClient(
        timeout=http._default_timeout,
        headers=http._default_headers,
    )
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
