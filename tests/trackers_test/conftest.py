import os

import pytest


# Get canned HTML pages from tests/data/trackers.
# See tests/conftest.py for the data_dir fixture.
@pytest.fixture(scope='session')
def get_html_page(data_dir):
    cache_dir = os.path.join(data_dir, 'trackers')

    def get_html_page(tracker, page):
        filepath = os.path.join(cache_dir, f'{tracker}.{page}.html')
        with open(filepath, 'r') as f:
            return f.read()

    return get_html_page
