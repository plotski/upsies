from unittest.mock import call

import pytest

from upsies import errors
from upsies.jobs.mediainfo import MediainfoJob


def test_cache_id(tmp_path):
    mi = MediainfoJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        content_path='mock/path',
    )
    assert mi.cache_id == 'path'


@pytest.mark.asyncio
async def test_execute_gets_mediainfo(tmp_path, mocker):
    mediainfo_mock = mocker.patch('upsies.utils.video.mediainfo', return_value='mock mediainfo output')
    mi = MediainfoJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert mediainfo_mock.call_args_list == []
    assert mi.output == ()
    assert mi.errors == ()
    assert mi.exit_code is None
    assert not mi.is_finished
    mi.execute()
    await mi.wait()
    assert mediainfo_mock.call_args_list == [call('mock/path')]
    assert mi.output == ('mock mediainfo output',)
    assert mi.errors == ()
    assert mi.exit_code == 0
    assert mi.is_finished

@pytest.mark.asyncio
async def test_execute_catches_ContentError(tmp_path, mocker):
    mediainfo_mock = mocker.patch('upsies.utils.video.mediainfo', side_effect=errors.ContentError('Ouch'))
    mi = MediainfoJob(
        home_directory=tmp_path,
        cache_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert mediainfo_mock.call_args_list == []
    assert mi.output == ()
    assert mi.errors == ()
    assert mi.exit_code is None
    assert not mi.is_finished
    mi.execute()
    await mi.wait()
    assert mediainfo_mock.call_args_list == [call('mock/path')]
    assert mi.output == ()
    assert [str(e) for e in mi.errors] == ['Ouch']
    assert mi.exit_code == 1
    assert mi.is_finished
