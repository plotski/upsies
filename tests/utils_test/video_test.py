import random
import shlex
from unittest.mock import Mock, call, patch

import pytest

from upsies import binaries, errors
from upsies.utils import video


def test_first_video_gets_nonexisting_directory():
    with pytest.raises(errors.NoContentError, match=r'^/no/such/dir: No such file or directory$'):
        video.first_video('/no/such/dir')

def test_first_video_gets_video_file(tmp_path):
    for ext in video._video_file_extensions:
        path = tmp_path / f'Foo.{ext}'
        assert video.first_video(path) == str(path)

def test_first_video_gets_nonvideo_file(tmp_path):
    path = tmp_path / 'foo.txt'
    path.write_text('foo')
    with pytest.raises(errors.NoContentError, match=rf'^{path}: Not a video file$'):
        video.first_video(path)

def test_first_video_bluray_copy(tmp_path):
    path = tmp_path / 'foo'
    (path / 'BDMV').mkdir(parents=True)
    assert video.first_video(path) == str(path)

def test_first_video_selects_correct_video_from_directory(tmp_path):
    path = tmp_path / 'foo'
    path.mkdir()
    (path / 'foo2.mp4').write_bytes(b'bleep bloop')
    (path / 'foo10.mp4').write_bytes(b'bloop bleep')
    assert video.first_video(tmp_path) == str(path / 'foo2.mp4')

def test_first_video_selects_first_video_from_subdirectory(tmp_path):
    foo = tmp_path / 'foo'
    foo.mkdir()
    bar = foo / 'bar'
    bar.mkdir()
    nothing_txt = bar / 'nothing.txt'
    nothing_txt.write_text('nothing')
    video_mp4 = bar / 'video.mp4'
    video_mp4.write_text('video data')
    assert video.first_video(foo) == str(video_mp4)

def test_first_video_gets_directory_without_videos(tmp_path):
    path = tmp_path / 'foo'
    path.mkdir()
    (path / 'foo.txt').write_text('bleep bloop')
    (path / 'bar.jpg').write_bytes(b'bloop bleep')

    with pytest.raises(errors.NoContentError, match=rf'^{path}: No video file found$'):
        video.first_video(path)

def test_first_video_gets_empty_directory(tmp_path):
    path = tmp_path / 'foo'
    path.mkdir()
    with pytest.raises(errors.NoContentError, match=rf'^{path}: No video file found$'):
        video.first_video(path)

@pytest.mark.parametrize(
    argnames=('extension',),
    argvalues=((ext,)
               for extension in video._video_file_extensions
               for ext in (extension.lower(), extension.upper())),
)
def test_first_video_finds_all_video_file_extensions(extension, tmp_path):
    def shuffle(*items):
        return sorted(items, key=lambda _: random.random())

    path = tmp_path / 'foo'
    path.mkdir()
    (path / f'foo.{extension}').write_text('bleep bloop')
    (path / 'bar.jpg').write_bytes(b'bloop bleep')
    (path / 'baz.jpg').write_bytes(b'nerrhg')
    assert video.first_video(path) == str(path / f'foo.{extension}')


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
    length = video.length(filepath)
    assert length == 12345.098
    assert run_mock.call_args_list == [call(exp_cmd, ignore_stderr=True)]

@patch('upsies.utils.subproc.run')
def test_length_gets_nonexisting_file(run_mock, tmp_path):
    filepath = tmp_path / 'the foo.mkv'
    with pytest.raises(FileNotFoundError, match=rf'^{filepath}: No such file or directory$'):
        video.length(filepath)
    assert run_mock.call_args_list == []

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
        assert run_mock.call_args_list == [call(exp_cmd, ignore_stderr=True)]


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
    length_mock.side_effect = (100, 300, 200)
    assert video.make_ffmpeg_input(path) == str(path / 'VIDEO_TS' / '2.VOB')
    assert length_mock.call_args_list == [
        call(str(path / 'VIDEO_TS' / '1.VOB')),
        call(str(path / 'VIDEO_TS' / '2.VOB')),
        call(str(path / 'VIDEO_TS' / '3.VOB')),
    ]

def test_make_ffmpeg_input_something_else(tmp_path):
    path = tmp_path / 'foo'
    assert video.make_ffmpeg_input(path) == str(path)
