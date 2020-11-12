# Don't make HTTP requests unless they are explicitly allowed.
# See tests/tools_test/dbs_test/conftest.py
def pytest_addoption(parser):
    parser.addoption('--allow-http-requests', action='store_true',
                     help='Use this option to update the request cache')
