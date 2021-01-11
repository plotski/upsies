import asyncio
from unittest.mock import call, patch

from upsies import errors
from upsies.jobs.mediainfo import MediainfoJob


@patch('upsies.utils.video.mediainfo')
def test_execute_gets_mediainfo(mediainfo_mock, tmp_path):
    mediainfo_mock.return_value = 'mock mediainfo output'
    mi = MediainfoJob(
        home_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert mediainfo_mock.call_args_list == []
    assert mi.output == ()
    assert mi.errors == ()
    assert mi.exit_code is None
    assert not mi.is_finished
    mi.execute()
    asyncio.get_event_loop().run_until_complete(mi.wait())
    assert mediainfo_mock.call_args_list == [call('mock/path')]
    assert mi.output == ('mock mediainfo output',)
    assert mi.errors == ()
    assert mi.exit_code == 0
    assert mi.is_finished

@patch('upsies.utils.video.mediainfo')
def test_execute_catches_ContentError(mediainfo_mock, tmp_path):
    mediainfo_mock.side_effect = errors.ContentError('Ouch')
    mi = MediainfoJob(
        home_directory=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert mediainfo_mock.call_args_list == []
    assert mi.output == ()
    assert mi.errors == ()
    assert mi.exit_code is None
    assert not mi.is_finished
    mi.execute()
    asyncio.get_event_loop().run_until_complete(mi.wait())
    assert mediainfo_mock.call_args_list == [call('mock/path')]
    assert mi.output == ()
    assert [str(e) for e in mi.errors] == ['Ouch']
    assert mi.exit_code == 1
    assert mi.is_finished
