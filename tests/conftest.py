import asyncio

import pytest

from upsies.utils import http


# Don't make HTTP requests unless they are explicitly allowed.
# See tests/tools_test/dbs_test/conftest.py
def pytest_addoption(parser):
    parser.addoption('--allow-http-requests', action='store_true',
                     help='Use this option to update the request cache')


# httpx.AsyncClient() must be closed before the process terminates. We need a
# loop for that. By default, pytest-asyncio uses a new loop for every test. By
# overloading the event_loop fixture, we use one AsyncClient instance for every
# test module and close it after all tests ran.
@pytest.fixture(scope='module', autouse=True)
def event_loop():
    loop = asyncio.new_event_loop()
    http._client = type(http._client)()
    yield loop
    loop.run_until_complete(http._client.aclose())
    loop.close()
