import asyncio
from unittest.mock import call, patch

from upsies import errors
from upsies.jobs.mediainfo import MediainfoJob


@patch('upsies.jobs.mediainfo.mediainfo')
def test_execute_gets_mediainfo_as_string(mediainfo_mock, tmp_path):
    mediainfo_mock.as_string.return_value = 'mock mediainfo output'
    mi = MediainfoJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert mediainfo_mock.as_string.call_args_list == []
    assert mi.output == ()
    assert mi.errors == ()
    assert mi.exit_code is None
    assert not mi.is_finished
    mi.execute()
    asyncio.get_event_loop().run_until_complete(mi.wait())
    assert mediainfo_mock.as_string.call_args_list == [call('mock/path')]
    assert mi.output == ('mock mediainfo output',)
    assert mi.errors == ()
    assert mi.exit_code == 0
    assert mi.is_finished

@patch('upsies.jobs.mediainfo.mediainfo')
def test_execute_catches_MediainfoError(mediainfo_mock, tmp_path):
    mediainfo_mock.as_string.side_effect = errors.MediainfoError('Ouch')
    mi = MediainfoJob(
        homedir=tmp_path,
        ignore_cache=True,
        content_path='mock/path',
    )
    assert mediainfo_mock.as_string.call_args_list == []
    assert mi.output == ()
    assert mi.errors == ()
    assert mi.exit_code is None
    assert not mi.is_finished
    mi.execute()
    asyncio.get_event_loop().run_until_complete(mi.wait())
    assert mediainfo_mock.as_string.call_args_list == [call('mock/path')]
    assert mi.output == ()
    assert [str(e) for e in mi.errors] == ['Ouch']
    assert mi.exit_code == 1
    assert mi.is_finished
