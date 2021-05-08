import asyncio
from unittest.mock import Mock, call

import pytest

from upsies.jobs.release_name import ReleaseNameJob
from upsies.utils.release import ReleaseName


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


def test_cache_id(mocker, tmp_path):
    job = ReleaseNameJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert job.cache_id == 'path'


def test_release_name_property(mocker, tmp_path):
    ReleaseName_mock = mocker.patch('upsies.utils.release.ReleaseName')
    job = ReleaseNameJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert ReleaseName_mock.call_args_list == [call('mock/path')]
    assert job.release_name is ReleaseName_mock.return_value


def test_release_name_selected(tmp_path):
    release_name = Mock(spec=ReleaseName)
    job = ReleaseNameJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    cb = Mock()
    job.signal.register('release_name_updating', cb.release_name_updating)
    job.signal.register('release_name_updated', cb.release_name_updated)
    job.signal.register('release_name', cb.release_name)
    job.release_name_selected(release_name)
    assert job.output == (str(release_name),)
    assert job.is_finished
    assert cb.release_name_updating.call_args_list == []
    assert cb.release_name_updated.call_args_list == []
    assert cb.release_name.call_args_list == [call(job.release_name)]


def test_fetch_info(tmp_path, mocker):
    job = ReleaseNameJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    mocker.patch.object(job, '_release_name', Mock(
        spec=ReleaseName,
        fetch_info=AsyncMock(),
    ))
    cb = Mock()
    job.signal.register('release_name_updating', cb.release_name_updating)
    job.signal.register('release_name_updated', cb.release_name_updated)
    job.signal.register('release_name', cb.release_name)
    job.fetch_info('arg1', 'arg2', kw='arg3')
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert job.release_name.fetch_info.call_args_list == [call(
        'arg1', 'arg2', kw='arg3',
    )]
    assert cb.release_name_updating.call_args_list == [call()]
    assert cb.release_name_updated.call_args_list == [call(job.release_name)]
    assert cb.release_name.call_args_list == []

def test_fetch_info_raises_exception(tmp_path, mocker):
    job = ReleaseNameJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    mocker.patch.object(job, '_release_name', Mock(
        spec=ReleaseName,
        fetch_info=AsyncMock(side_effect=Exception('No')),
    ))
    cb = Mock()
    job.signal.register('release_name_updating', cb.release_name_updating)
    job.signal.register('release_name_updated', cb.release_name_updated)
    job.signal.register('release_name', cb.release_name)
    job.fetch_info('arg1', 'arg2', kw='arg3')
    with pytest.raises(Exception, match='^No$'):
        asyncio.get_event_loop().run_until_complete(job.wait())
    assert cb.release_name_updating.call_args_list == [call()]
    assert cb.release_name_updated.call_args_list == []
    assert cb.release_name.call_args_list == []
