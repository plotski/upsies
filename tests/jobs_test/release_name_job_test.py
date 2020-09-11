import asyncio
from unittest.mock import Mock, call, patch

from upsies.jobs.release_name import ReleaseNameJob

try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)


@patch('upsies.tools.release_name.ReleaseName')
def test_release_name_property(ReleaseName_mock, tmp_path):
    ReleaseName_mock.return_value = 'Mock Name'
    rn = ReleaseNameJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert ReleaseName_mock.call_args_list == [call('mock/path')]
    assert rn.release_name == 'Mock Name'


@patch('upsies.tools.release_name.ReleaseName')
def test_release_name_selected(ReleaseName_mock, tmp_path):
    ReleaseName_mock.return_value = 'Mock Name'
    rn = ReleaseNameJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    rn.release_name_selected('Real Mock Name')
    assert rn.output == ('Real Mock Name',)
    assert rn.is_finished


@patch('upsies.tools.release_name.ReleaseName')
def test_fetch_info(ReleaseName_mock, tmp_path):
    rn = ReleaseNameJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    info = {
        'title_original': 'Original Title',
        'title_english': 'English Title',
        'year': '1234',
    }
    db = Mock(info=AsyncMock(return_value=info))
    cb = Mock()
    rn.on_release_name_updated(cb)
    rn.fetch_info('mock id', db)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert db.info.call_args_list == [call(
        'mock id',
        db.title_english,
        db.title_original,
        db.year,
    )]
    assert rn.release_name.title == 'Original Title'
    assert rn.release_name.title_aka == 'English Title'
    assert rn.release_name.title_english == 'English Title'
    assert rn.release_name.year == '1234'
    assert cb.call_args_list == [call(rn.release_name)]
