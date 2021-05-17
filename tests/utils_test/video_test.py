import os
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
def test_mediainfo_contains_relative_path_when_passed_file(first_video_mock, run_mediainfo_mock):
    run_mediainfo_mock.return_value = (
        'Complete name : some/path/to/foo.mkv\n'
        'Something     : asdf\n'
    )
    assert video.mediainfo('some/path/to/foo.mkv') == (
        'Complete name : foo.mkv\n'
        'Something     : asdf\n'
    )

@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video')
def test_mediainfo_contains_relative_path_when_passed_directory(first_video_mock, run_mediainfo_mock):
    run_mediainfo_mock.return_value = (
        'Complete name : some/path/to/foo.mkv\n'
        'Something     : asdf\n'
    )
    assert video.mediainfo('some/path') == (
        'Complete name : path/to/foo.mkv\n'
        'Something     : asdf\n'
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
        video.tracks('foo/bar.mkv')

    run_mediainfo_mock.return_value = '{"this": ["is", "unexpected", "json"]}'
    with pytest.raises(RuntimeError, match=(r'^foo/bar.mkv: Unexpected mediainfo output: '
                                            r'\{"this": \["is", "unexpected", "json"\]\}: '
                                            r"Missing field: 'media'$")):
        video.tracks('foo/bar.mkv')


@patch('upsies.utils.video.tracks')
def test_default_track_returns_track_with_default_tag(default_track_mock):
    default_track_mock.return_value = {
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
    assert video.default_track('video', 'foo.mkv') == default_track_mock.return_value['Video'][-2]
    assert video.default_track('audio', 'foo.mkv') == default_track_mock.return_value['Audio'][-2]

@patch('upsies.utils.video.tracks')
def test_default_track_returns_first_track_if_no_default_tag_exists(default_track_mock):
    default_track_mock.return_value = {
        'Video': [
            {'@type': 'Video', 'Some': 'video info'},
            {'@type': 'Video', 'Default': 'No'},
        ],
        'Audio': [
            {'@type': 'Audio', 'Some': 'audio info'},
            {'@type': 'Audio', 'Default': 'No'},
        ],
    }
    assert video.default_track('video', 'foo.mkv') == default_track_mock.return_value['Video'][0]
    assert video.default_track('audio', 'foo.mkv') == default_track_mock.return_value['Audio'][0]

@patch('upsies.utils.video.tracks')
def test_default_track_fails_to_find_any_track(default_track_mock):
    default_track_mock.return_value = {}
    with pytest.raises(errors.ContentError, match=r'^foo.mkv: No audio track found$'):
        video.default_track('audio', 'foo.mkv')
    with pytest.raises(errors.ContentError, match=r'^foo.mkv: No video track found$'):
        video.default_track('video', 'foo.mkv')


@pytest.mark.parametrize(
    argnames='width, par, exp_width',
    argvalues=(
        ('1920', '1.0', 1920),
        ('704', '1.455', 1024),
        ('704', '0.888', 704),
    ),
)
@patch('upsies.utils.video.default_track')
def test_width(default_track_mock, width, par, exp_width):
    default_track_mock.return_value = {
        '@type': 'Video',
        'Width': width,
        'PixelAspectRatio': par,
    }
    video.width.cache_clear()
    assert video.width('foo.mkv') == exp_width
    default_track_mock.side_effect = errors.ContentError('No')
    video.width.cache_clear()
    assert video.width('foo.mkv') == 0


@pytest.mark.parametrize(
    argnames='height, par, exp_height',
    argvalues=(
        ('1080', '1.0', 1080),
        ('560', '1.455', 560),
        ('480', '0.888', 540),
    ),
)
@patch('upsies.utils.video.default_track')
def test_height(default_track_mock, height, par, exp_height):
    default_track_mock.return_value = {
        '@type': 'Video',
        'Height': height,
        'PixelAspectRatio': par,
    }
    video.height.cache_clear()
    assert video.height('foo.mkv') == exp_height
    default_track_mock.side_effect = errors.ContentError('No')
    video.height.cache_clear()
    assert video.height('foo.mkv') == 0


@pytest.mark.parametrize('scan_type, exp_scan_type', (('Progressive', 'p'), ('Interlaced', 'i')))
@pytest.mark.parametrize(
    argnames='width, height, par, exp_res',
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
        ('640', '480', None, '480'),
        ('704', '400', None, '480'),
        ('704', '572', '1.422', '576'),  # mpv output: 704x572 => 1001x572
        ('704', '560', '1.455', '576'),  # mpv output: 704x560 => 1024x560
        ('704', '480', '0.888', '576'),  # mpv output: 704x480 => 704x540
        ('702', '478', '0.889', '576'),  # mpv output: 702x478 => 702x537
        ('720', '428', '1.422', '576'),  # mpv output: 720x428 => 1024x428
        ('716', '480', '1.185', '480'),  # mpv output: 716x480 => 848x480
    ),
    ids=lambda value: str(value),
)
@patch('upsies.utils.video.default_track')
def test_resolution(default_track_mock, width, height, par, exp_res, scan_type, exp_scan_type):
    default_track_mock.return_value = {
        '@type': 'Video',
        'Width': width,
        'Height': height,
        'PixelAspectRatio': par,
        'ScanType': scan_type,
    }
    video.resolution.cache_clear()
    assert video.resolution('foo.mkv') == f'{exp_res}{exp_scan_type}'

@patch('upsies.utils.video.default_track')
def test_resolution_is_unknown(default_track_mock):
    default_track_mock.return_value = {}
    video.resolution.cache_clear()
    assert video.resolution('foo.mkv') is None

@patch('upsies.utils.video.default_track')
def test_resolution_catches_ContentError_from_default_track(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.resolution.cache_clear()
    assert video.resolution('foo.mkv') is None

def test_resolution_uses_display_aspect_ratio(data_dir):
    video.resolution.cache_clear()
    video_file = os.path.join(data_dir, 'video', 'aspect_ratio.mkv')
    assert video.resolution(video_file) == '720p'


@pytest.mark.parametrize(
    argnames='exp_frame_rate, video_dict',
    argvalues=(
        (0.0, {}),
        (25.0, {'FrameRate': '25.000'}),
        (23.976, {'FrameRate': '23.976'}),
    ),
    ids=lambda v: str(v),
)
@patch('upsies.utils.video.default_track')
def test_frame_rate(default_track_mock, exp_frame_rate, video_dict):
    default_track_mock.return_value = video_dict
    video.frame_rate.cache_clear()
    assert video.frame_rate('foo.mkv') == exp_frame_rate

@patch('upsies.utils.video.default_track')
def test_frame_rate_catches_ContentError(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.frame_rate.cache_clear()
    assert video.frame_rate('foo.mkv') == 0.0


@pytest.mark.parametrize(
    argnames='exp_bit_depth, video_dict',
    argvalues=(
        (None, {}),
        ('8', {'BitDepth': '8'}),
        ('10', {'BitDepth': '10'}),
    ),
    ids=lambda v: str(v),
)
@patch('upsies.utils.video.default_track')
def test_bit_depth(default_track_mock, exp_bit_depth, video_dict):
    default_track_mock.return_value = video_dict
    video.bit_depth.cache_clear()
    assert video.bit_depth('foo.mkv') == exp_bit_depth

@patch('upsies.utils.video.default_track')
def test_bit_depth_catches_ContentError(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.bit_depth.cache_clear()
    assert video.bit_depth('foo.mkv') is None


@pytest.mark.parametrize(
    argnames='exp_return_value, video_dict',
    argvalues=(
        (False, {}),
        (False, {'colour_primaries': 'BT.601 NTSC'}),
        (True, {'colour_primaries': 'BT.2020 foo'}),
        (True, {'colour_primaries': 'bar BT.2020'}),
    ),
    ids=lambda v: str(v),
)
@patch('upsies.utils.video.default_track')
def test_is_hdr10(default_track_mock, exp_return_value, video_dict):
    default_track_mock.return_value = video_dict
    video.is_hdr10.cache_clear()
    assert video.is_hdr10('foo.mkv') == exp_return_value

@patch('upsies.utils.video.default_track')
def test_is_hdr10_catches_ContentError(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.is_hdr10.cache_clear()
    assert video.is_hdr10('foo.mkv') is None


@pytest.mark.parametrize(
    argnames='exp_return_value, audio_dicts',
    argvalues=(
        (False, []),
        (False, [{}, {}]),
        (False, [{'Language': 'en'}]),
        (False, [{'Language': 'fr'}]),
        (True, [{'Language': 'fr'}, {'Language': 'en'}]),
        (True, [{'Language': 'en'}, {'Language': 'fr'}]),
        (True, [{'Language': 'en'}, {'Language': 'fr'}, {'Language': 'fr', 'Title': 'Commentary with Foo'}]),
        (False, [{'Language': 'fr'}, {'Language': 'en', 'Title': 'Commentary with Foo'}]),
    ),
    ids=lambda v: str(v),
)
@patch('upsies.utils.video.tracks')
def test_has_dual_audio(tracks_mock, exp_return_value, audio_dicts):
    tracks_mock.return_value = {'Audio': audio_dicts}
    video.has_dual_audio.cache_clear()
    assert video.has_dual_audio('foo.mkv') == exp_return_value

@patch('upsies.utils.video.default_track')
def test_has_dual_audio_catches_ContentError(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.has_dual_audio.cache_clear()
    assert video.has_dual_audio('foo.mkv') is None


@pytest.mark.parametrize(
    argnames='exp_audio_format, audio_dict',
    argvalues=(
        (None, {}),
        ('AAC', {'Format': 'AAC', 'Format_AdditionalFeatures': 'LC'}),
        ('AC-3', {'Format': 'AC-3'}),
        ('E-AC-3', {'Format': 'E-AC-3'}),
        ('E-AC-3 Atmos', {'Format': 'E-AC-3', 'Format_Commercial_IfAny': 'Dolby Digital Plus with Dolby Atmos'}),
        ('TrueHD', {'Format': 'MLP FBA', 'Format_Commercial_IfAny': 'Dolby TrueHD'}),
        ('TrueHD Atmos', {'Format': 'MLP FBA', 'Format_Commercial_IfAny': 'Dolby TrueHD with Dolby Atmos'}),
        ('DTS', {'Format': 'DTS'}),
        ('DTS-ES', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-ES Matrix'}),
        ('DTS-ES', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-ES Discrete'}),
        ('DTS-HD', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD High Resolution Audio', 'Format_AdditionalFeatures': 'XBR'}),
        ('DTS-HD MA', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD Master Audio', 'Format_AdditionalFeatures': 'XLL'}),
        ('DTS:X', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD Master Audio', 'Format_AdditionalFeatures': 'XLL X'}),
        ('FLAC', {'Format': 'FLAC'}),
        ('MP3', {'Format': 'MPEG Audio'}),
        ('Vorbis', {'Format': 'Vorbis'}),
        ('Vorbis', {'Format': 'Ogg'}),
    ),
    ids=lambda v: str(v),
)
@patch('upsies.utils.video.default_track')
def test_audio_format(default_track_mock, exp_audio_format, audio_dict):
    default_track_mock.return_value = audio_dict
    video.audio_format.cache_clear()
    assert video.audio_format('foo.mkv') == exp_audio_format

@patch('upsies.utils.video.default_track')
def test_audio_format_catches_ContentError_from_default_track(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.audio_format.cache_clear()
    assert video.audio_format('foo.mkv') is None


@pytest.mark.parametrize(
    argnames='exp_audio_channels, audio_dict',
    argvalues=(
        (None, {}),
        ('1.0', {'Channels': '1'}),
        ('2.0', {'Channels': '2'}),
        ('2.0', {'Channels': '3'}),
        ('2.0', {'Channels': '4'}),
        ('2.0', {'Channels': '5'}),
        ('5.1', {'Channels': '6'}),
        ('5.1', {'Channels': '7'}),
        ('7.1', {'Channels': '8'}),
    ),
    ids=lambda value: str(value),
)
@patch('upsies.utils.video.default_track')
def test_audio_channels(default_track_mock, exp_audio_channels, audio_dict):
    default_track_mock.return_value = audio_dict
    video.audio_channels.cache_clear()
    assert video.audio_channels('foo.mkv') == exp_audio_channels

@patch('upsies.utils.video.default_track')
def test_audio_channels_catches_ContentError_from_default_track(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.audio_channels.cache_clear()
    assert video.audio_channels('foo.mkv') is None


@pytest.mark.parametrize(
    argnames='exp_video_format, video_dict',
    argvalues=(
        (None, {}),
        ('XviD', {'Encoded_Library_Name': 'XviD'}),
        ('x264', {'Encoded_Library_Name': 'x264'}),
        ('x265', {'Encoded_Library_Name': 'x265'}),
        ('H.264', {'Format': 'AVC'}),
        ('H.265', {'Format': 'HEVC'}),
        ('VP9', {'Format': 'VP9'}),
        ('MPEG-2', {'Format': 'MPEG Video', 'Format Version': '2'}),
    ),
    ids=lambda value: str(value),
)
@patch('upsies.utils.video.default_track')
def test_video_format(default_track_mock, exp_video_format, video_dict):
    default_track_mock.return_value = video_dict
    video.video_format.cache_clear()
    assert video.video_format('foo.mkv') == exp_video_format

@patch('upsies.utils.video.default_track')
def test_video_format_of_unsupported_or_nonexisting_file(default_track_mock):
    default_track_mock.side_effect = errors.ContentError('Something went wrong')
    video.video_format.cache_clear()
    assert video.video_format('foo.mkv') is None


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

def test_first_video_gets_directory(tmp_path, mocker):
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
