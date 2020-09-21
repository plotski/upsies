import asyncio
from unittest.mock import Mock, call, patch

from upsies.jobs.release_name import ReleaseNameJob


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@patch('upsies.tools.release_name.ReleaseName')
def test_release_name_property(ReleaseName_mock, tmp_path):
    ReleaseName_mock.return_value = 'Mock Name'
    rnj = ReleaseNameJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert ReleaseName_mock.call_args_list == [call('mock/path')]
    assert rnj.release_name == 'Mock Name'


@patch('upsies.tools.release_name.ReleaseName')
def test_release_name_selected(ReleaseName_mock, tmp_path):
    ReleaseName_mock.return_value = 'Mock Name'
    rnj = ReleaseNameJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    rnj.release_name_selected('Real Mock Name')
    assert rnj.output == ('Real Mock Name',)
    assert rnj.is_finished


@patch('upsies.tools.release_name.ReleaseName')
def test_fetch_info(ReleaseName_mock, tmp_path):
    rnj = ReleaseNameJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    rn_mock = ReleaseName_mock.return_value
    rn_mock.fetch_info = AsyncMock()
    rnj.fetch_info('arg1', 'arg2', kw='arg3')
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert rn_mock.fetch_info.call_args_list == [call(
        'arg1', 'arg2', kw='arg3',
        callback=rnj.handle_release_name_update,
    )]

@patch('upsies.tools.release_name.ReleaseName')
def test_release_name_update_callback(ReleaseName_mock, tmp_path):
    rnj = ReleaseNameJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    cb = Mock()
    rnj.on_release_name_update(cb)
    rnj.handle_release_name_update('mock release name')
    assert cb.call_args_list == [call('mock release name')]
