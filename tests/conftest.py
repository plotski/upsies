import os

import pytest


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
