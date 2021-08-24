import os
import random
import re
from unittest.mock import Mock, call, patch

import pytest

from upsies import constants, errors
from upsies.utils import video


def test_run_mediainfo_gets_unreadable_file(mocker):
    run_mock = mocker.patch('upsies.utils.subproc.run')
    assert_file_readable_mock = mocker.patch(
        'upsies.utils.fs.assert_file_readable',
        side_effect=errors.ContentError("Can't read this, yo"),
    )
    with pytest.raises(errors.ContentError, match=r"^Can't read this, yo$"):
        video._run_mediainfo('some/path')
    assert assert_file_readable_mock.call_args_list == [
        call('some/path'),
    ]
    assert run_mock.call_args_list == []

def test_run_mediainfo_passes_positional_args_to_mediainfo_command(mocker):
    run_mock = mocker.patch('upsies.utils.subproc.run')
    assert_file_readable_mock = mocker.patch('upsies.utils.fs.assert_file_readable')
    args = ('--foo', '--bar=baz')
    assert video._run_mediainfo('some/path', *args) == run_mock.return_value
    assert assert_file_readable_mock.call_args_list == [
        call('some/path'),
    ]
    assert run_mock.call_args_list == [
        call((video._mediainfo_executable, 'some/path') + args, cache=True),
    ]

def test_run_mediainfo_catches_DependencyError(mocker):
    run_mock = mocker.patch(
        'upsies.utils.subproc.run',
        side_effect=errors.DependencyError('Missing dependency: your mom'),
    )
    assert_file_readable_mock = mocker.patch('upsies.utils.fs.assert_file_readable')
    with pytest.raises(errors.ContentError, match=r'^Missing dependency: your mom$'):
        video._run_mediainfo('some/path')
    assert assert_file_readable_mock.call_args_list == [
        call('some/path'),
    ]
    assert run_mock.call_args_list == [
        call((video._mediainfo_executable, 'some/path'), cache=True),
    ]

def test_run_mediainfo_does_not_catch_ProcessError(mocker):
    run_mock = mocker.patch(
        'upsies.utils.subproc.run',
        side_effect=errors.ProcessError('Bogus command'),
    )
    assert_file_readable_mock = mocker.patch('upsies.utils.fs.assert_file_readable')
    with pytest.raises(errors.ProcessError, match=r'^Bogus command$'):
        video._run_mediainfo('some/path')
    assert assert_file_readable_mock.call_args_list == [
        call('some/path'),
    ]
    assert run_mock.call_args_list == [
        call((video._mediainfo_executable, 'some/path'),
             cache=True),
    ]


@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video')
def test_mediainfo_gets_first_video_from_path(first_video_mock, run_mediainfo_mock):
    first_video_mock.return_value = 'some/path/to/foo.mkv'
    video.mediainfo('some/path')
    assert first_video_mock.call_args_list == [call('some/path')]
    assert run_mediainfo_mock.call_args_list == [call('some/path/to/foo.mkv')]

@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video')
@pytest.mark.parametrize(
    argnames='argument, orig_complete_name, exp_complete_name',
    argvalues=(
        ('/absolute/path/to/foo.mkv', '/absolute/path/to/foo.mkv', 'foo.mkv'),
        ('relative/path/to/foo.mkv', 'relative/path/to/foo.mkv', 'foo.mkv'),
        ('/absolute/path', '/absolute/path/to/foo.mkv', 'path/to/foo.mkv'),
        ('relative/path', 'relative/path/to/foo.mkv', 'path/to/foo.mkv'),
        ('directory', 'directory/foo.mkv', 'directory/foo.mkv'),
        ('foo.mkv', 'foo.mkv', 'foo.mkv'),
    ),
)
def test_mediainfo_path_is_stripped_to_relevant_parts(first_video_mock, run_mediainfo_mock,
                                                      argument, orig_complete_name, exp_complete_name):
    run_mediainfo_mock.return_value = (
        f'Complete name : {orig_complete_name}\n'
        'Something     : asdf\n'
        'Format/Info   : hjkl\n'
    )
    assert video.mediainfo(argument) == (
        f'Complete name : {exp_complete_name}\n'
        'Something     : asdf\n'
        'Format/Info   : hjkl\n'
    )


@patch('upsies.utils.video._duration_from_mediainfo')
@patch('upsies.utils.video._duration_from_ffprobe')
@patch('upsies.utils.video.first_video')
def test_duration_gets_duration_from_ffprobe(first_video_mock, duration_from_ffprobe, duration_from_mediainfo):
    first_video_mock.return_value = 'some/path/to/foo.mkv'
    duration_from_ffprobe.return_value = 123.4
    duration_from_mediainfo.return_value = 567.8
    video.duration.cache_clear()
    assert video.duration('some/path') == 123.4

@pytest.mark.parametrize(
    argnames='exception',
    argvalues=(
        RuntimeError('foo'),
        errors.DependencyError('bar'),
        errors.ProcessError('baz'),
    ),
)
@patch('upsies.utils.video._duration_from_mediainfo')
@patch('upsies.utils.video._duration_from_ffprobe')
@patch('upsies.utils.video.first_video')
def test_duration_gets_duration_from_mediainfo(first_video_mock, duration_from_ffprobe, duration_from_mediainfo, exception):
    first_video_mock.return_value = 'some/path/to/foo.mkv'
    duration_from_ffprobe.side_effect = exception
    duration_from_mediainfo.return_value = 567.8
    video.duration.cache_clear()
    assert video.duration('some/path') == 567.8


@patch('upsies.utils.video.make_ffmpeg_input')
@patch('upsies.utils.subproc.run')
def test_duration_from_ffprobe_succeeds(run_mock, make_ffmpeg_input_mock):
    make_ffmpeg_input_mock.return_value = 'path/to/foo.mkv'
    run_mock.return_value = ' 123.4 '
    assert video._duration_from_ffprobe('foo') == 123.4
    assert make_ffmpeg_input_mock.call_args_list == [call('foo')]
    assert run_mock.call_args_list == [call(
        (video._ffprobe_executable,
         '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1',
         make_ffmpeg_input_mock.return_value),
        ignore_errors=True,
    )]

@patch('upsies.utils.video.make_ffmpeg_input')
@patch('upsies.utils.subproc.run')
def test_duration_from_ffprobe_fails(run_mock, make_ffmpeg_input_mock):
    make_ffmpeg_input_mock.return_value = 'path/to/foo.mkv'
    run_mock.return_value = 'arf!'
    exp_error = (
        'Unexpected output from '
        f"({video._ffprobe_executable!r}, "
        "'-v', 'error', '-show_entries', 'format=duration', "
        "'-of', 'default=noprint_wrappers=1:nokey=1', "
        f"{make_ffmpeg_input_mock.return_value!r}): 'arf!'"
    )
    with pytest.raises(RuntimeError, match=rf'^{re.escape(exp_error)}$'):
        video._duration_from_ffprobe('foo')
    assert make_ffmpeg_input_mock.call_args_list == [call('foo')]
    assert run_mock.call_args_list == [call(
        (video._ffprobe_executable,
         '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1',
         make_ffmpeg_input_mock.return_value),
        ignore_errors=True,
    )]


@patch('upsies.utils.video._tracks')
def test_duration_from_mediainfo_finds_duration(tracks_mock):
    tracks_mock.return_value = {'General': [{'@type': 'General', 'Duration': '123.4'}]}
    assert video._duration_from_mediainfo('some/path') == 123.4

@pytest.mark.parametrize(
    argnames='track',
    argvalues=(
        {'@type': 'General', 'Duration': 'foo'},
        {'@type': 'General'},
    ),
)
@patch('upsies.utils.video._tracks')
def test_duration_from_mediainfo_does_not_find_duration(tracks_mock, track):
    tracks_mock.return_value = {'General': [track]}
    assert video._duration_from_mediainfo('some/path') == 0.0


@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video')
def test_tracks_gets_first_video_from_path(first_video_mock, run_mediainfo_mock):
    first_video_mock.return_value = 'some/path/to/foo.mkv'
    run_mediainfo_mock.return_value = '{"media": {"track": []}}'
    video._tracks.cache_clear()
    video.tracks('some/path')
    assert first_video_mock.call_args_list == [call('some/path')]
    assert run_mediainfo_mock.call_args_list == [call('some/path/to/foo.mkv', '--Output=JSON')]

@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video', Mock(return_value='foo/bar.mkv'))
def test_tracks_returns_expected_structure(run_mediainfo_mock):
    run_mediainfo_mock.return_value = ('{"media": {"track": ['
                                       '{"@type": "Video", "foo": "bar"}, '
                                       '{"@type": "Audio", "bar": "baz"}, '
                                       '{"@type": "Audio", "also": "this"}]}}')
    video._tracks.cache_clear()
    tracks = video.tracks('foo/bar.mkv')
    assert run_mediainfo_mock.call_args_list == [call('foo/bar.mkv', '--Output=JSON')]
    assert tracks == {'Video': [{'@type': 'Video', 'foo': 'bar'}],
                      'Audio': [{'@type': 'Audio', 'bar': 'baz'},
                                {'@type': 'Audio', 'also': 'this'}]}

@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video', Mock(return_value='foo/bar.mkv'))
def test_tracks_gets_unexpected_output_from_mediainfo(run_mediainfo_mock):
    run_mediainfo_mock.return_value = 'this is not JSON'
    with pytest.raises(RuntimeError, match=(r'^foo/bar.mkv: Unexpected mediainfo output: '
                                            r'this is not JSON: Expecting value: line 1 column 1 \(char 0\)$')):
        video._tracks.cache_clear()
        video.tracks('foo/bar.mkv')

    run_mediainfo_mock.return_value = '{"this": ["is", "unexpected", "json"]}'
    with pytest.raises(RuntimeError, match=(r'^foo/bar.mkv: Unexpected mediainfo output: '
                                            r'\{"this": \["is", "unexpected", "json"\]\}: '
                                            r"Missing field: 'media'$")):
        video._tracks.cache_clear()
        video.tracks('foo/bar.mkv')


@patch('upsies.utils.video.tracks')
def test_default_track_returns_track_with_default_tag(tracks_mock):
    tracks_mock.return_value = {
        'Video': [
            {'@type': 'Video', 'Some': 'video info'},
            {'@type': 'Video', 'Default': 'No'},
            {'@type': 'Video', 'Default': 'Yes'},
            {'@type': 'Video', 'Default': 'Yes', 'But too late': ':('},
        ],
        'Audio': [
            {'@type': 'Audio', 'Some': 'audio info'},
            {'@type': 'Audio', 'Default': 'No'},
            {'@type': 'Audio', 'Default': 'Yes'},
            {'@type': 'Audio', 'Default': 'Yes', 'But too late': ':('},
        ],
    }
    assert video.default_track('video', 'foo.mkv') == tracks_mock.return_value['Video'][-2]
    assert video.default_track('audio', 'foo.mkv') == tracks_mock.return_value['Audio'][-2]

@patch('upsies.utils.video.tracks')
def test_default_track_returns_first_track_if_no_default_tag_exists(tracks_mock):
    tracks_mock.return_value = {
        'Video': [
            {'@type': 'Video', 'Some': 'video info'},
            {'@type': 'Video', 'Default': 'No'},
        ],
        'Audio': [
            {'@type': 'Audio', 'Some': 'audio info'},
            {'@type': 'Audio', 'Default': 'No'},
        ],
    }
    assert video.default_track('video', 'foo.mkv') == tracks_mock.return_value['Video'][0]
    assert video.default_track('audio', 'foo.mkv') == tracks_mock.return_value['Audio'][0]

@patch('upsies.utils.video.tracks')
def test_default_track_fails_to_find_any_track(track_mock):
    track_mock.return_value = {}
    with pytest.raises(errors.ContentError, match=r'^foo.mkv: No audio track found$'):
        video.default_track('audio', 'foo.mkv')
    with pytest.raises(errors.ContentError, match=r'^foo.mkv: No video track found$'):
        video.default_track('video', 'foo.mkv')


@pytest.mark.parametrize(
    argnames='video_track, exp_width, exp_exception',
    argvalues=(
        ({'@type': 'Video', 'Width': '1920'}, 1920, None),
        ({'@type': 'Video', 'Width': '1920', 'PixelAspectRatio': '1.0'}, 1920, None),
        ({'@type': 'Video', 'Width': '704', 'PixelAspectRatio': '1.455'}, 1024, None),
        ({'@type': 'Video', 'Width': '704', 'PixelAspectRatio': '0.888'}, 704, None),
        ({'@type': 'Video', 'Width': 'nan'}, None, errors.ContentError('Unable to determine video width')),
        ({'@type': 'Video', 'Width': ()}, None, errors.ContentError('Unable to determine video width')),
        ({'@type': 'Video'}, None, errors.ContentError('Unable to determine video width')),
        ({}, None, errors.ContentError('Unable to determine video width')),
        (errors.ContentError('Permission denied'), None, errors.ContentError('Permission denied')),
    ),
    ids=lambda v: str(v),
)
def test_width(video_track, exp_width, exp_exception, mocker):
    if isinstance(video_track, Exception):
        mocker.patch('upsies.utils.video.default_track', side_effect=video_track)
    else:
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            video.width('foo.mkv')
    else:
        assert video.width('foo.mkv') == exp_width

@pytest.mark.parametrize(
    argnames='video_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'@type': 'Video', 'Width': '1080'}, video.NO_DEFAULT_VALUE, 1080, None),
        ({'@type': 'Video', 'Width': '1080'}, 'default value', 1080, None),
        ({'@type': 'Video', 'Width': '1080'}, None, 1080, None),
        ({}, video.NO_DEFAULT_VALUE, True, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_width_with_default_value(video_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if video_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.width(path, default=default)
        else:
            assert video.width(path, default=default) is default
    else:
        assert video.width(path, default=default) == exp_return_value


@pytest.mark.parametrize(
    argnames='video_track, exp_height, exp_exception',
    argvalues=(
        ({'@type': 'Video', 'Height': '1080'}, 1080, None),
        ({'@type': 'Video', 'Height': '1080', 'PixelAspectRatio': '1.0'}, 1080, None),
        ({'@type': 'Video', 'Height': '560', 'PixelAspectRatio': '1.455'}, 560, None),
        ({'@type': 'Video', 'Height': '480', 'PixelAspectRatio': '0.888'}, 540, None),
        ({'@type': 'Video', 'Height': 'nan'}, None, errors.ContentError('Unable to determine video height')),
        ({'@type': 'Video', 'Height': ()}, None, errors.ContentError('Unable to determine video height')),
        ({'@type': 'Video'}, None, errors.ContentError('Unable to determine video height')),
        ({}, None, errors.ContentError('Unable to determine video height')),
        (errors.ContentError('Permission denied'), None, errors.ContentError('Permission denied')),
    ),
    ids=lambda v: str(v),
)
def test_height(video_track, exp_height, exp_exception, mocker):
    if isinstance(video_track, Exception):
        mocker.patch('upsies.utils.video.default_track', side_effect=video_track)
    else:
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            video.height('foo.mkv')
    else:
        assert video.height('foo.mkv') == exp_height

@pytest.mark.parametrize(
    argnames='video_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'@type': 'Video', 'Height': '1080'}, video.NO_DEFAULT_VALUE, 1080, None),
        ({'@type': 'Video', 'Height': '1080'}, 'default value', 1080, None),
        ({'@type': 'Video', 'Height': '1080'}, None, 1080, None),
        ({}, video.NO_DEFAULT_VALUE, True, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_height_with_default_value(video_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if video_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.height(path, default=default)
        else:
            assert video.height(path, default=default) is default
    else:
        assert video.height(path, default=default) == exp_return_value


@pytest.mark.parametrize('scan_type, exp_scan_type', (('Progressive', 'p'), ('Interlaced', 'i'), (None, 'p')))
@pytest.mark.parametrize(
    argnames='width, height, par, exp_resolution',
    argvalues=(
        ('7680', '4320', None, '4320'),
        ('3840', '2160', None, '2160'),
        ('1920', '1080', None, '1080'),
        ('1920', '1044', None, '1080'),
        ('1918', '1040', None, '1080'),
        ('1920', '804', None, '1080'),
        ('1392', '1080', None, '1080'),
        ('1280', '534', None, '720'),
        ('768', '720', None, '720'),
        ('768', '576', None, '576'),
        ('768', '576', None, '576'),
        ('720', '540', None, '540'),
        ('704', '400', None, '480'),
        ('704', '572', '1.422', '576'),  # mpv output: 704x572 => 1001x572
        ('704', '560', '1.455', '576'),  # mpv output: 704x560 => 1024x560
        ('704', '480', '0.888', '540'),  # mpv output: 704x480 => 704x540
        ('702', '478', '0.889', '540'),  # mpv output: 702x478 => 702x537
        ('720', '428', '1.422', '576'),  # mpv output: 720x428 => 1024x428
        ('716', '480', '1.185', '480'),  # mpv output: 716x480 => 848x480
    ),
    ids=lambda value: str(value),
)
def test_resolution(width, height, par, exp_resolution, scan_type, exp_scan_type, mocker):
    default_track_mock = mocker.patch('upsies.utils.video.default_track', return_value={
        '@type': 'Video',
        'Width': width,
        'Height': height,
        'PixelAspectRatio': par,
        'ScanType': scan_type,
    })
    for key in tuple(default_track_mock.return_value):
        if default_track_mock.return_value[key] is None:
            del default_track_mock.return_value[key]

    if exp_resolution and exp_scan_type:
        assert video.resolution('foo.mkv') == f'{exp_resolution}{exp_scan_type}'
    else:
        with pytest.raises(errors.ContentError, match=r'^Unable to determine video resolution$'):
            video.resolution('foo.mkv')

@pytest.mark.parametrize(
    argnames='video_track, exp_exception',
    argvalues=(
        ({'@type': 'Video', 'Height': 'nan', 'Width': '123'},
         errors.ContentError('Unable to determine video resolution')),
        ({'@type': 'Video', 'Height': '123', 'Width': 'nan'},
         errors.ContentError('Unable to determine video resolution')),
        ({'@type': 'Video', 'Width': '123'},
         errors.ContentError('Unable to determine video resolution')),
        ({'@type': 'Video', 'Height': '123'},
         errors.ContentError('Unable to determine video resolution')),
        ({},
         errors.ContentError('Unable to determine video resolution')),
    ),
    ids=lambda value: str(value),
)
def test_resolution_detection_fails(video_track, exp_exception, mocker):
    mocker.patch('upsies.utils.video.default_track', return_value=video_track)
    with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
        video.resolution('foo.mkv')

@pytest.mark.parametrize(
    argnames='video_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'@type': 'Video', 'Height': '1080', 'Width': '1920'}, video.NO_DEFAULT_VALUE, '1080p', None),
        ({'@type': 'Video', 'Height': '1080', 'Width': '1920'}, 'default value', '1080p', None),
        ({'@type': 'Video', 'Height': '1080', 'Width': '1920'}, None, '1080p', None),
        ({}, video.NO_DEFAULT_VALUE, True, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_resolution_with_default_value(video_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if video_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.resolution(path, default=default)
        else:
            assert video.resolution(path, default=default) is default
    else:
        assert video.resolution(path, default=default) == exp_return_value

def test_resolution_forwards_ContentError_from_default_track(mocker):
    mocker.patch('upsies.utils.video.default_track', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.resolution('foo.mkv')

def test_resolution_uses_display_aspect_ratio(data_dir):
    video_file = os.path.join(data_dir, 'video', 'aspect_ratio.mkv')
    assert video.resolution(video_file) == '720p'


@pytest.mark.parametrize(
    argnames='video_track, exp_frame_rate',
    argvalues=(
        ({'FrameRate': '25.000'}, 25.0),
        ({'FrameRate': '23.976'}, 23.976),
        ({'FrameRate': 'foo'}, 0.0),
        ({}, 0.0),
    ),
    ids=lambda v: str(v),
)
def test_frame_rate(video_track, exp_frame_rate, mocker):
    mocker.patch('upsies.utils.video.default_track', return_value=video_track)
    assert video.frame_rate('foo.mkv') == exp_frame_rate

@pytest.mark.parametrize(
    argnames='video_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'FrameRate': '25.000'}, video.NO_DEFAULT_VALUE, 25.0, None),
        ({'FrameRate': '25.000'}, 'default value', 25.0, None),
        ({'FrameRate': '25.000'}, None, 25.0, None),
        ({}, video.NO_DEFAULT_VALUE, True, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_frame_rate_with_default_value(video_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if video_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.frame_rate(path, default=default)
        else:
            assert video.frame_rate(path, default=default) is default
    else:
        assert video.frame_rate(path, default=default) == exp_return_value

def test_frame_rate_forwards_ContentError_from_default_track(mocker):
    mocker.patch('upsies.utils.video.default_track', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.frame_rate('foo.mkv')


@pytest.mark.parametrize(
    argnames='video_track, exp_bit_depth',
    argvalues=(
        ({'BitDepth': '8'}, 8),
        ({'BitDepth': '10'}, 10),
        ({'BitDepth': 'foo'}, 0),
        ({}, 0),
    ),
    ids=lambda v: str(v),
)
def test_bit_depth(video_track, exp_bit_depth, mocker):
    mocker.patch('upsies.utils.video.default_track', return_value=video_track)
    assert video.bit_depth('foo.mkv') == exp_bit_depth

@pytest.mark.parametrize(
    argnames='video_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'BitDepth': '10'}, video.NO_DEFAULT_VALUE, 10, None),
        ({'BitDepth': '10'}, 'default value', 10, None),
        ({'BitDepth': '10'}, None, 10, None),
        ({}, video.NO_DEFAULT_VALUE, True, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_bit_depth_with_default_value(video_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if video_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.bit_depth(path, default=default)
        else:
            assert video.bit_depth(path, default=default) is default
    else:
        assert video.bit_depth(path, default=default) == exp_return_value

def test_bit_depth_forwards_ContentError_from_default_track(mocker):
    mocker.patch('upsies.utils.video.default_track', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.bit_depth('foo.mkv')


@pytest.mark.parametrize(
    argnames='video_track, exp_return_value',
    argvalues=(
        ({}, ''),
        ({'HDR_Format': 'foo'}, ''),
        ({'HDR_Format': 'Dolby Vision'}, 'Dolby Vision'),
        ({'HDR_Format_Compatibility': 'HDR10+ Profile A'}, 'HDR10+'),
        ({'HDR_Format_Compatibility': 'HDR10+ Profile B'}, 'HDR10+'),
        ({'HDR_Format_Compatibility': 'HDR10'}, 'HDR10'),
        ({'HDR_Format_Compatibility': 'foo HDR bar'}, 'HDR'),
        ({'HDR_Format': 'foo HDR bar'}, 'HDR'),
    ),
    ids=lambda v: str(v),
)
def test_hdr_format(video_track, exp_return_value, mocker):
    mocker.patch('upsies.utils.video.default_track', return_value=video_track)
    assert video.hdr_format('foo.mkv') == exp_return_value

@pytest.mark.parametrize(
    argnames='video_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'HDR_Format_Compatibility': 'HDR10'}, video.NO_DEFAULT_VALUE, 'HDR10', None),
        ({'HDR_Format_Compatibility': 'HDR10'}, 'default value', 'HDR10', None),
        ({'HDR_Format_Compatibility': 'HDR10'}, None, 'HDR10', None),
        ({}, video.NO_DEFAULT_VALUE, True, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_hdr_format_with_default_value(video_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if video_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=video_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.hdr_format(path, default=default)
        else:
            assert video.hdr_format(path, default=default) is default
    else:
        assert video.hdr_format(path, default=default) == exp_return_value

def test_hdr_format_forwards_ContentError_from_default_track(mocker):
    mocker.patch('upsies.utils.video.default_track', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.hdr_format('foo.mkv')


@pytest.mark.parametrize(
    argnames='audio_tracks, exp_dual_audio',
    argvalues=(
        ([], False),
        ([{}, {}], False),
        ([{'Language': 'en'}], False),
        ([{'Language': 'fr'}], False),
        ([{'Language': 'fr'}, {'Language': 'en'}], True),
        ([{'Language': 'en'}, {'Language': 'fr'}], True),
        ([{'Language': 'en'}, {'Language': 'fr'}, {'Language': 'fr', 'Title': 'Commentary with Foo'}], True),
        ([{'Language': 'fr'}, {'Language': 'en', 'Title': 'Commentary with Foo'}], False),
    ),
    ids=lambda v: str(v),
)
def test_has_dual_audio(audio_tracks, exp_dual_audio, mocker):
    mocker.patch('upsies.utils.video.tracks', return_value={'Audio': audio_tracks})
    assert video.has_dual_audio('foo.mkv') == exp_dual_audio

@pytest.mark.parametrize(
    argnames='audio_tracks, default, exp_return_value, exp_exception',
    argvalues=(
        ([{'Language': 'fr'}, {'Language': 'en'}], video.NO_DEFAULT_VALUE, True, None),
        ([{'Language': 'fr'}, {'Language': 'en'}], 'default value', True, None),
        ([{'Language': 'fr'}, {'Language': 'en'}], None, True, None),
        ([], video.NO_DEFAULT_VALUE, True, errors.ContentError('{path}: No such file or directory')),
        ([], 'default value', 'default value', None),
        ([], None, None, None),
    ),
)
def test_has_dual_audio_with_default_value(audio_tracks, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if audio_tracks:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.tracks', return_value={'Audio': audio_tracks})

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.has_dual_audio(path, default=default)
        else:
            assert video.has_dual_audio(path, default=default) is default
    else:
        assert video.has_dual_audio(path, default=default) == exp_return_value

def test_has_dual_audio_forwards_ContentError_from_tracks(mocker):
    mocker.patch('upsies.utils.video.tracks', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.has_dual_audio('foo.mkv')


@pytest.mark.parametrize(
    argnames='audio_tracks, exp_return_value',
    argvalues=(
        ([], False),
        ([{}, {}], False),
        ([{'Title': 'Shlommentary'}], False),
        ([{'Title': 'Commentary with Foo'}], True),
        ([{'Title': "Foo's commentary"}], True),
        ([{'Title': "THE FRICKIN' COMMENTARY, OMG"}], True),
    ),
    ids=lambda v: str(v),
)
def test_has_commentary(exp_return_value, audio_tracks, mocker):
    mocker.patch('upsies.utils.video.tracks', return_value={'Audio': audio_tracks})
    assert video.has_commentary('foo.mkv') == exp_return_value

@pytest.mark.parametrize(
    argnames='audio_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'Title': 'Commentary with Foo'}, video.NO_DEFAULT_VALUE, True, None),
        ({'Title': 'Commentary with Foo'}, 'default value', True, None),
        ({'Title': 'Commentary with Foo'}, '', True, None),
        ({'Title': 'Commentary with Foo'}, None, True, None),
        ({}, video.NO_DEFAULT_VALUE, False, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, '', '', None),
        ({}, None, None, None),
    ),
)
def test_has_commentary_with_default_value(audio_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if audio_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.tracks', return_value={'Audio': [audio_track]})

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.has_commentary(path, default=default)
        else:
            assert video.has_commentary(path, default=default) is default
    else:
        assert video.has_commentary(path, default=default) == exp_return_value

def test_has_commentary_forwards_ContentError_from_tracks(mocker):
    mocker.patch('upsies.utils.video.tracks', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.has_commentary('foo.mkv')


@pytest.mark.parametrize(
    argnames='audio_track, exp_audio_format',
    argvalues=(
        ({}, ''),
        ({'Format': 'AAC', 'Format_AdditionalFeatures': 'LC'}, 'AAC'),
        ({'Format': 'AC-3'}, 'AC-3'),
        ({'Format': 'E-AC-3'}, 'E-AC-3'),
        ({'Format': 'E-AC-3', 'Format_Commercial_IfAny': 'Dolby Digital Plus with Dolby Atmos'}, 'E-AC-3 Atmos'),
        ({'Format': 'MLP FBA', 'Format_Commercial_IfAny': 'Dolby TrueHD'}, 'TrueHD'),
        ({'Format': 'MLP FBA', 'Format_Commercial_IfAny': 'Dolby TrueHD with Dolby Atmos'}, 'TrueHD Atmos'),
        ({'Format': 'DTS'}, 'DTS'),
        ({'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-ES Matrix'}, 'DTS-ES'),
        ({'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-ES Discrete'}, 'DTS-ES'),
        ({'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD High Resolution Audio', 'Format_AdditionalFeatures': 'XBR'}, 'DTS-HD'),
        ({'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD Master Audio', 'Format_AdditionalFeatures': 'XLL'}, 'DTS-HD MA'),
        ({'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD Master Audio', 'Format_AdditionalFeatures': 'XLL X'}, 'DTS:X'),
        ({'Format': 'FLAC'}, 'FLAC'),
        ({'Format': 'MPEG Audio'}, 'MP3'),
        ({'Format': 'Vorbis'}, 'Vorbis'),
        ({'Format': 'Ogg'}, 'Vorbis'),
    ),
    ids=lambda v: str(v),
)
def test_audio_format(audio_track, exp_audio_format, mocker):
    mocker.patch('upsies.utils.video.default_track', return_value=audio_track)
    assert video.audio_format('foo.mkv') == exp_audio_format

@pytest.mark.parametrize(
    argnames='audio_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'Format': 'FLAC'}, video.NO_DEFAULT_VALUE, 'FLAC', None),
        ({'Format': 'FLAC'}, 'default value', 'FLAC', None),
        ({'Format': 'FLAC'}, None, 'FLAC', None),
        ({}, video.NO_DEFAULT_VALUE, None, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_audio_format_with_default_value(audio_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if audio_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=audio_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.audio_format(path, default=default)
        else:
            assert video.audio_format(path, default=default) is default
    else:
        assert video.audio_format(path, default=default) == exp_return_value

def test_audio_format_catches_ContentError_from_default_track(mocker):
    mocker.patch('upsies.utils.video.default_track', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.audio_format('foo.mkv')


@pytest.mark.parametrize(
    argnames='audio_track, exp_audio_channels',
    argvalues=(
        ({}, ''),
        ({'Channels': '1'}, '1.0'),
        ({'Channels': '2'}, '2.0'),
        ({'Channels': '3'}, '2.0'),
        ({'Channels': '4'}, '2.0'),
        ({'Channels': '5'}, '2.0'),
        ({'Channels': '6'}, '5.1'),
        ({'Channels': '7'}, '5.1'),
        ({'Channels': '8'}, '7.1'),
    ),
    ids=lambda value: str(value),
)
def test_audio_channels(audio_track, exp_audio_channels, mocker):
    mocker.patch('upsies.utils.video.default_track', return_value=audio_track)
    assert video.audio_channels('foo.mkv') == exp_audio_channels

@pytest.mark.parametrize(
    argnames='audio_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'Channels': '2'}, video.NO_DEFAULT_VALUE, '2.0', None),
        ({'Channels': '2'}, 'default value', '2.0', None),
        ({'Channels': '2'}, None, '2.0', None),
        ({}, video.NO_DEFAULT_VALUE, None, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_audio_channels_with_default_value(audio_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if audio_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=audio_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.audio_channels(path, default=default)
        else:
            assert video.audio_channels(path, default=default) is default
    else:
        assert video.audio_channels(path, default=default) == exp_return_value

def test_audio_channels_catches_ContentError_from_default_track(mocker):
    mocker.patch('upsies.utils.video.default_track', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.audio_channels('foo.mkv')


@pytest.mark.parametrize(
    argnames='video_track, exp_video_format',
    argvalues=(
        ({}, ''),
        ({'Encoded_Library_Name': 'XviD'}, 'XviD'),
        ({'Encoded_Library_Name': 'x264'}, 'x264'),
        ({'Encoded_Library_Name': 'x265'}, 'x265'),
        ({'Format': 'AVC'}, 'H.264'),
        ({'Format': 'HEVC'}, 'H.265'),
        ({'Format': 'VP9'}, 'VP9'),
        ({'Format': 'MPEG Video'}, 'MPEG-2'),
    ),
    ids=lambda value: str(value),
)
def test_video_format(video_track, exp_video_format, mocker):
    mocker.patch('upsies.utils.video.default_track', return_value=video_track)
    assert video.video_format('foo.mkv') == exp_video_format

@pytest.mark.parametrize(
    argnames='audio_track, default, exp_return_value, exp_exception',
    argvalues=(
        ({'Encoded_Library_Name': 'x264'}, video.NO_DEFAULT_VALUE, 'x264', None),
        ({'Encoded_Library_Name': 'x264'}, 'default value', 'x264', None),
        ({'Encoded_Library_Name': 'x264'}, None, 'x264', None),
        ({}, video.NO_DEFAULT_VALUE, None, errors.ContentError('{path}: No such file or directory')),
        ({}, 'default value', 'default value', None),
        ({}, None, None, None),
    ),
)
def test_video_format_with_default_value(audio_track, default, exp_return_value, exp_exception, mocker, tmp_path):
    path = tmp_path / 'foo.mkv'
    if audio_track:
        path.write_bytes(b'mock data')
        mocker.patch('upsies.utils.video.default_track', return_value=audio_track)

    if exp_exception:
        if default is video.NO_DEFAULT_VALUE:
            exp_error = str(exp_exception).format(path=path)
            with pytest.raises(type(exp_exception), match=rf'^{re.escape(exp_error)}$'):
                video.video_format(path, default=default)
        else:
            assert video.video_format(path, default=default) is default
    else:
        assert video.video_format(path, default=default) == exp_return_value

def test_video_format_catches_ContentError_from_default_track(mocker):
    mocker.patch('upsies.utils.video.default_track', side_effect=errors.ContentError('Something went wrong'))
    with pytest.raises(errors.ContentError, match=r'^Something went wrong$'):
        video.video_format('foo.mkv')


def test_first_video_finds_no_videos(tmp_path, mocker):
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=())
    filter_similar_duration_mock = mocker.patch('upsies.utils.video.filter_similar_duration')
    with pytest.raises(errors.ContentError, match=rf'^{tmp_path}: No video file found$'):
        video.first_video(tmp_path)
    assert file_list_mock.call_args_list == [
        call(tmp_path, extensions=constants.VIDEO_FILE_EXTENSIONS),
    ]
    assert filter_similar_duration_mock.call_args_list == []

def test_first_video_gets_file(tmp_path, mocker):
    file_list_mock = mocker.patch(
        'upsies.utils.fs.file_list',
        return_value=('some/path/foo.mkv',),
    )
    filter_similar_duration_mock = mocker.patch(
        'upsies.utils.video.filter_similar_duration',
        return_value=file_list_mock.return_value,
    )
    assert video.first_video(tmp_path) == 'some/path/foo.mkv'
    assert file_list_mock.call_args_list == [
        call(tmp_path, extensions=constants.VIDEO_FILE_EXTENSIONS),
    ]
    assert filter_similar_duration_mock.call_args_list == [
        call(file_list_mock.return_value),
    ]

def test_first_video_gets_directory_with_unexpected_filenames(tmp_path, mocker):
    file_list_mock = mocker.patch(
        'upsies.utils.fs.file_list',
        return_value=('some/path/foo.mkv', 'some/path/bar.mkv', 'some/path/baz.mkv'),
    )
    filter_similar_duration_mock = mocker.patch(
        'upsies.utils.video.filter_similar_duration',
        return_value=file_list_mock.return_value,
    )
    assert video.first_video(tmp_path) == 'some/path/foo.mkv'
    assert file_list_mock.call_args_list == [
        call(tmp_path, extensions=constants.VIDEO_FILE_EXTENSIONS),
    ]
    assert filter_similar_duration_mock.call_args_list == [
        call(file_list_mock.return_value),
    ]

@pytest.mark.parametrize('separator', ('.', ' '))
@pytest.mark.parametrize(
    argnames='filelist',
    argvalues=(
        ('some/path/S01E01.mkv', 'some/path/S01E02.mkv', 'some/path/S01E03.mkv'),
        ('some/path/Foo S02E01.mkv', 'some/path/Foo S02E02.mkv', 'some/path/Foo S02E03.mkv'),
        ('some/path/Foo S03E01 x264.mkv', 'some/path/Foo S03E02 x264.mkv', 'some/path/Foo S03E03 x264.mkv'),
        ('some/path/Foo S4E1 x264.mkv', 'some/path/Foo S4E2 x264.mkv', 'some/path/Foo S4E03 x264.mkv'),
    ),
    ids=lambda v: str(v),
)
def test_first_video_gets_directory_with_expected_filenames(filelist, separator, tmp_path, mocker):
    filelist_shuffled = [file.replace(' ', separator)
                         for file in random.sample(filelist, k=len(filelist))]
    file_list_mock = mocker.patch('upsies.utils.fs.file_list', return_value=filelist_shuffled)
    filter_similar_duration_mock = mocker.patch('upsies.utils.video.filter_similar_duration')
    assert video.first_video(tmp_path) == filelist[0].replace(' ', separator)
    assert file_list_mock.call_args_list == [
        call(tmp_path, extensions=constants.VIDEO_FILE_EXTENSIONS),
    ]
    assert filter_similar_duration_mock.call_args_list == []

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
    filter_similar_duration_mock = mocker.patch(
        'upsies.utils.video.filter_similar_duration',
        return_value=(
            'path/to/VIDEO_TS/VTS_02_0.VOB',
            'path/to/VIDEO_TS/VTS_02_1.VOB',
            'path/to/VIDEO_TS/VTS_02_2.VOB',
            'path/to/VIDEO_TS/VTS_02_3.VOB',
        )
    )
    path = tmp_path / 'foo'
    (path / 'VIDEO_TS').mkdir(parents=True)
    assert video.first_video(path) == 'path/to/VIDEO_TS/VTS_02_0.VOB'
    assert file_list_mock.call_args_list == [
        call(path, extensions=('VOB',)),
    ]
    assert filter_similar_duration_mock.call_args_list == [
        call(file_list_mock.return_value),
    ]


def test_filter_similar_duration_gets_multiple_files(mocker):
    durations = {
        'a.mkv': 50,
        'b.mkv': 500,
        'c.mkv': 20,
        'd.mkv': 10000,
        'e.mkv': 11000,
        'f.mkv': 0,
        'g.mkv': 10500,
        'h.mkv': 9000,
    }
    duration_mock = mocker.patch(
        'upsies.utils.video._duration',
        side_effect=tuple(durations.values()),
    )
    assert video.filter_similar_duration(tuple(durations.keys())) == (
        'd.mkv',
        'e.mkv',
        'g.mkv',
        'h.mkv',
    )
    assert duration_mock.call_args_list == [
        call('a.mkv'),
        call('b.mkv'),
        call('c.mkv'),
        call('d.mkv'),
        call('e.mkv'),
        call('f.mkv'),
        call('g.mkv'),
        call('h.mkv'),
    ]

def test_filter_similar_duration_gets_single_file(mocker):
    duration_mock = mocker.patch('upsies.utils.video._duration', return_value=12345)
    assert video.filter_similar_duration(('foo.mkv',)) == ('foo.mkv',)
    assert duration_mock.call_args_list == []

def test_filter_similar_duration_gets_no_files(mocker):
    duration_mock = mocker.patch('upsies.utils.video._duration', return_value=12345)
    assert video.filter_similar_duration(()) == ()
    assert duration_mock.call_args_list == []


def test_make_ffmpeg_input_gets_bluray_directory(tmp_path):
    path = tmp_path / 'foo'
    (path / 'BDMV').mkdir(parents=True)
    exp_ffmpeg_input = f'bluray:{path}'
    assert video.make_ffmpeg_input(path) == exp_ffmpeg_input

@patch('upsies.utils.video._duration')
def test_make_ffmpeg_input_gets_dvd_directory(duration_mock, tmp_path):
    path = tmp_path / 'foo'
    (path / 'VIDEO_TS').mkdir(parents=True)
    (path / 'VIDEO_TS' / '1.VOB').write_text('video data')
    (path / 'VIDEO_TS' / '2.VOB').write_text('video data')
    (path / 'VIDEO_TS' / '3.VOB').write_text('video data')
    duration_mock.side_effect = (100, 1000, 900)
    assert video.make_ffmpeg_input(path) == str(path / 'VIDEO_TS' / '2.VOB')
    assert duration_mock.call_args_list == [
        call(str(path / 'VIDEO_TS' / '1.VOB')),
        call(str(path / 'VIDEO_TS' / '2.VOB')),
        call(str(path / 'VIDEO_TS' / '3.VOB')),
    ]

def test_make_ffmpeg_input_something_else(tmp_path):
    path = tmp_path / 'foo'
    assert video.make_ffmpeg_input(path) == str(path)
