import random
import shlex
from unittest.mock import Mock, call, patch

import pytest

from upsies import binaries, errors
from upsies.utils import video


@patch('os.path.isdir', Mock(return_value=False))
def test_first_video_gets_video_file():
    for ext in video._video_file_extensions:
        assert video.first_video(f'Foo.{ext}') == f'Foo.{ext}'

@patch('os.path.isdir', Mock(return_value=False))
def test_first_video_gets_nonvideo_file():
    with pytest.raises(errors.NoContentError, match=r'^Foo.txt: Not a video file$'):
        video.first_video('Foo.txt')

@patch('os.path.isdir', Mock(side_effect=(True, True)))
def test_first_video_bluray_copy():
    assert video.first_video('path/to/Foo') == 'path/to/Foo'

@patch('os.path.isdir', Mock(side_effect=(True, False)))
@patch('os.walk')
def test_first_video_selects_correct_video_from_directory(walk_mock):
    walk_mock.return_value = (
        ('path/to/Foo', (), ('Foo 2.mp4', 'Foo 10.mp4')),
    )
    assert video.first_video('path/to/Foo') == 'path/to/Foo/Foo 2.mp4'

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

@patch('os.path.isdir', Mock(side_effect=(True, False)))
@patch('os.walk')
def test_first_video_gets_directory_without_videos(walk_mock):
    walk_mock.return_value = (
        ('path/to/Foo', (), ('Foo.jpg', 'Foo.txt')),
    )
    with pytest.raises(errors.NoContentError, match=r'^path/to/Foo: No video file found$'):
        video.first_video('path/to/Foo')

@patch('os.path.isdir', Mock(side_effect=(True, False)))
@patch('os.walk')
def test_first_video_gets_empty_directory(walk_mock):
    walk_mock.return_value = (
        ('path/to/Foo', (), ()),
    )
    with pytest.raises(errors.NoContentError, match=r'^path/to/Foo: No video file found$'):
        video.first_video('path/to/Foo')

@patch('os.walk')
@pytest.mark.parametrize(
    argnames=('extension',),
    argvalues=((ext,)
               for extension in video._video_file_extensions
               for ext in (extension.lower(), extension.upper())),
)
def test_first_video_finds_all_video_file_extensions(walk_mock, extension):
    def shuffle(*items):
        return sorted(items, key=lambda _: random.random())

    walk_mock.return_value = (
        ('path/to/Foo', (), shuffle(f'Foo.{extension}', 'Foo.jpg', 'Foo.txt')),
    )
    with patch('os.path.isdir', Mock(side_effect=(True, False))):
        assert video.first_video('path/to/Foo') == f'path/to/Foo/Foo.{extension}'


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
