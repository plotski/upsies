import shlex
from unittest.mock import call, patch

import pytest

from upsies import binaries, errors
from upsies.utils import video


def test_first_video_finds_no_videos(tmp_path, mocker):
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=())
    filter_similar_length_mock = mocker.patch('upsies.utils.video.filter_similar_length')
    assert_file_readable_mock = mocker.patch('upsies.utils.fs.assert_file_readable')
    with pytest.raises(errors.ContentError, match=rf'^{tmp_path}: No video file found$'):
        video.first_video(tmp_path)
    assert file_list_mock.call_args_list == [
        call(tmp_path, extensions=video._video_file_extensions),
    ]
    assert filter_similar_length_mock.call_args_list == []
    assert assert_file_readable_mock.call_args_list == []

def test_first_video_gets_file(tmp_path, mocker):
    file_list_mock = mocker.patch(
        'upsies.utils.fs.file_list',
        return_value=('some/path/foo.mkv',),
    )
    filter_similar_length_mock = mocker.patch(
        'upsies.utils.video.filter_similar_length',
        return_value=file_list_mock.return_value,
    )
    assert_file_readable_mock = mocker.patch('upsies.utils.fs.assert_file_readable')
    assert video.first_video(tmp_path) == 'some/path/foo.mkv'
    assert file_list_mock.call_args_list == [
        call(tmp_path, extensions=video._video_file_extensions),
    ]
    assert filter_similar_length_mock.call_args_list == [
        call(file_list_mock.return_value),
    ]
    assert assert_file_readable_mock.call_args_list == [
        call('some/path/foo.mkv'),
    ]

def test_first_video_gets_directory(tmp_path, mocker):
    file_list_mock = mocker.patch(
        'upsies.utils.fs.file_list',
        return_value=('some/path/foo.mkv', 'some/path/bar.mkv', 'some/path/baz.mkv'),
    )
    filter_similar_length_mock = mocker.patch(
        'upsies.utils.video.filter_similar_length',
        return_value=file_list_mock.return_value,
    )
    assert_file_readable_mock = mocker.patch('upsies.utils.fs.assert_file_readable')
    assert video.first_video(tmp_path) == 'some/path/foo.mkv'
    assert file_list_mock.call_args_list == [
        call(tmp_path, extensions=video._video_file_extensions),
    ]
    assert filter_similar_length_mock.call_args_list == [
        call(file_list_mock.return_value),
    ]
    assert assert_file_readable_mock.call_args_list == [
        call('some/path/foo.mkv'),
    ]

def test_first_video_gets_bluray_image(tmp_path, mocker):
    path = tmp_path / 'foo'
    (path / 'BDMV').mkdir(parents=True)
    assert video.first_video(path) == str(path)

def test_first_video_gets_dvd_image(tmp_path, mocker):
    file_list_mock = mocker.patch(
        'upsies.utils.fs.file_list',
        return_value=(
            'path/to/VIDEO_TS/VTS_01_0.VOB',
            'path/to/VIDEO_TS/VTS_01_1.VOB',
            'path/to/VIDEO_TS/VTS_02_0.VOB',
            'path/to/VIDEO_TS/VTS_02_1.VOB',
            'path/to/VIDEO_TS/VTS_02_2.VOB',
            'path/to/VIDEO_TS/VTS_02_3.VOB',
        )
    )
    filter_similar_length_mock = mocker.patch(
        'upsies.utils.video.filter_similar_length',
        return_value=(
            'path/to/VIDEO_TS/VTS_02_0.VOB',
            'path/to/VIDEO_TS/VTS_02_1.VOB',
            'path/to/VIDEO_TS/VTS_02_2.VOB',
            'path/to/VIDEO_TS/VTS_02_3.VOB',
        )
    )
    assert_file_readable_mock = mocker.patch('upsies.utils.fs.assert_file_readable')
    path = tmp_path / 'foo'
    (path / 'VIDEO_TS').mkdir(parents=True)
    assert video.first_video(path) == 'path/to/VIDEO_TS/VTS_02_0.VOB'
    assert file_list_mock.call_args_list == [
        call(path, extensions=('VOB',)),
    ]
    assert filter_similar_length_mock.call_args_list == [
        call(file_list_mock.return_value),
    ]
    assert assert_file_readable_mock.call_args_list == [
        call('path/to/VIDEO_TS/VTS_02_0.VOB'),
    ]


def test_filter_similar_length(mocker):
    lengths = {
        'a.mkv': 50,
        'b.mkv': 500,
        'c.mkv': 20,
        'd.mkv': 10000,
        'e.mkv': 11000,
        'f.mkv': 0,
        'g.mkv': 10500,
        'h.mkv': 9000,
    }
    mocker.patch(
        'upsies.utils.video.length',
        side_effect=tuple(lengths.values()),
    )
    assert video.filter_similar_length(tuple(lengths.keys())) == (
        'd.mkv',
        'e.mkv',
        'g.mkv',
        'h.mkv',
    )


@patch('upsies.utils.subproc.run')
def test_length_calls_ffprobe(run_mock, tmp_path):
    filepath = tmp_path / 'foo.mkv'
    filepath.write_bytes(b'foo data')
    exp_cmd = (
        binaries.ffprobe,
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(filepath),
    )
    run_mock.return_value = '12345.098'
    assert video.length(filepath) == 12345.098
    assert run_mock.call_args_list == [call(exp_cmd, ignore_errors=True)]

@patch('upsies.utils.subproc.run')
def test_length_catches_DependencyError(run_mock, tmp_path):
    filepath = tmp_path / 'foo.mkv'
    filepath.write_bytes(b'foo data')
    run_mock.side_effect = errors.DependencyError('you need ffprobe')
    with pytest.raises(errors.ContentError, match=r'^you need ffprobe$'):
        video.length(filepath)

@patch('upsies.utils.subproc.run')
def test_length_does_not_catch_ProcessError(run_mock, tmp_path):
    filepath = tmp_path / 'foo.mkv'
    filepath.write_bytes(b'foo data')
    run_mock.side_effect = errors.ProcessError('do you even ffprobe?')
    with pytest.raises(errors.ProcessError, match=r'^do you even ffprobe\?$'):
        video.length(filepath)

@patch('upsies.utils.fs.assert_file_readable')
@patch('upsies.utils.subproc.run')
def test_length_gets_unreadable_file(run_mock, assert_file_readable_mock, tmp_path):
    filepath = tmp_path / 'the foo.mkv'
    assert_file_readable_mock.side_effect = errors.ContentError('Nope')
    with pytest.raises(errors.ContentError, match=r'^Nope$'):
        video.length(filepath)
    assert assert_file_readable_mock.call_args_list == [call(filepath)]
    assert run_mock.call_args_list == []

@patch('upsies.utils.fs.assert_file_readable')
@patch('upsies.utils.subproc.run')
def test_length_expects_na_from_ffprobe(run_mock, assert_file_readable_mock, tmp_path):
    run_mock.return_value = 'N/A'
    assert video.length('some/path.mp4') == 0

@patch('upsies.utils.subproc.run')
def test_length_crashes_if_ffprobe_returns_unexpected_value(run_mock, tmp_path):
    filepath = tmp_path / 'the foo.mkv'
    filepath.write_bytes(b'the data')
    exp_cmd = (
        binaries.ffprobe,
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        filepath,
    )
    exp_cmd_string = ' '.join(shlex.quote(str(arg)) for arg in exp_cmd)
    run_mock.return_value = 'forever'
    with pytest.raises(RuntimeError, match=(r'^Unexpected output from command: '
                                            rf'{exp_cmd_string}:\n'
                                            r'forever$')):
        video.length(filepath)
        assert run_mock.call_args_list == [call(exp_cmd, ignore_errors=True)]


def test_make_ffmpeg_input_gets_bluray_directory(tmp_path):
    path = tmp_path / 'foo'
    (path / 'BDMV').mkdir(parents=True)
    exp_ffmpeg_input = f'bluray:{path}'
    assert video.make_ffmpeg_input(path) == exp_ffmpeg_input

@patch('upsies.utils.video.length')
def test_make_ffmpeg_input_gets_dvd_directory(length_mock, tmp_path):
    path = tmp_path / 'foo'
    (path / 'VIDEO_TS').mkdir(parents=True)
    (path / 'VIDEO_TS' / '1.VOB').write_text('video data')
    (path / 'VIDEO_TS' / '2.VOB').write_text('video data')
    (path / 'VIDEO_TS' / '3.VOB').write_text('video data')
    length_mock.side_effect = (100, 1000, 900)
    assert video.make_ffmpeg_input(path) == str(path / 'VIDEO_TS' / '2.VOB')
    assert length_mock.call_args_list == [
        call(str(path / 'VIDEO_TS' / '1.VOB')),
        call(str(path / 'VIDEO_TS' / '2.VOB')),
        call(str(path / 'VIDEO_TS' / '3.VOB')),
    ]

def test_make_ffmpeg_input_something_else(tmp_path):
    path = tmp_path / 'foo'
    assert video.make_ffmpeg_input(path) == str(path)
