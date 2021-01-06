from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
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


@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video')
def test_duration_gets_first_video_from_path(first_video_mock, run_mediainfo_mock):
    first_video_mock.return_value = 'some/path/to/foo.mkv'
    run_mediainfo_mock.return_value = '{"media": {"track": []}}'
    video.duration('some/path')
    assert first_video_mock.call_args_list == [call('some/path')]
    assert run_mediainfo_mock.call_args_list == [call('some/path/to/foo.mkv', '--Output=JSON')]

@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video')
def test_duration_finds_duration(first_video_mock, run_mediainfo_mock):
    first_video_mock.return_value = 'some/path/to/foo.mkv'
    run_mediainfo_mock.return_value = '{"media": {"track": [{"@type": "General", "Duration": "123.4"}]}}'
    assert video.duration('some/path') == 123.4

@patch('upsies.utils.video._run_mediainfo')
@patch('upsies.utils.video.first_video')
@pytest.mark.parametrize(
    argnames='track',
    argvalues=(
        '{"@type": "General", "Duration": "foo"}',
        '{"@type": "General"}',
    ),
)
def test_duration_does_not_find_duration(first_video_mock, run_mediainfo_mock, track):
    first_video_mock.return_value = 'some/path/to/foo.mkv'
    run_mediainfo_mock.return_value = '{"media": {"track": [' + track + ']}}'
    assert video.duration('some/path') == 0.0


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
    argnames='width, height, exp_res',
    argvalues=(
        ('7680', '4320', '4320p'),
        ('3840', '2160', '2160p'),
        ('1920', '1080', '1080p'),
        ('1920', '1044', '1080p'),
        ('1920', '800', '1080p'),
        ('1390', '1080', '1080p'),
        ('1280', '533', '720p'),
        ('768', '720', '720p'),
        ('768', '576', '576p'),
        ('640', '480', '480p')
    ),
    ids=lambda value: str(value),
)
@patch('upsies.utils.video.default_track')
def test_resolution(default_track_mock, width, height, exp_res):
    default_track_mock.return_value = {'@type': 'Video',
                                       'Width': width,
                                       'Height': height}
    video.resolution.cache_clear()
    assert video.resolution('foo.mkv') == exp_res

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


@pytest.mark.parametrize(
    argnames='exp_audio_format, audio_dict',
    argvalues=(
        (None, {}),
        ('DTS:X', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD Master Audio', 'Format_AdditionalFeatures': 'XLL X'}),
        ('DTS-HD MA', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-HD Master Audio', 'Format_AdditionalFeatures': 'XLL'}),
        ('DTS-ES', {'Format': 'DTS', 'Format_Commercial_IfAny': 'DTS-ES Matrix'}),
        ('TrueHD', {'Format': 'MLP FBA', 'Format_Commercial_IfAny': 'Dolby TrueHD'}),
        ('TrueHD Atmos', {'Format': 'MLP FBA', 'Format_Commercial_IfAny': 'Dolby TrueHD with Dolby Atmos'}),
        ('AAC', {'Format': 'AAC', 'Format_AdditionalFeatures': 'LC'}),
        ('DD', {'Format': 'AC-3', 'Format_Commercial_IfAny': 'Dolby Digital'}),
        ('DD+', {'Format': 'E-AC-3', 'Format_Commercial_IfAny': 'Dolby Digital Plus'}),
        ('DD+ Atmos', {'Format': 'E-AC-3', 'Format_Commercial_IfAny': 'Dolby Digital Plus with Dolby Atmos'}),
        ('FLAC', {'Format': 'FLAC'}),
        ('MP3', {'Format': 'MPEG Audio'}),
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
        ('2.1', {'Channels': '3'}),
        ('3.1', {'Channels': '4'}),
        ('4.1', {'Channels': '5'}),
        ('5.1', {'Channels': '6'}),
        ('6.1', {'Channels': '7'}),
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
        call(tmp_path, extensions=video._video_file_extensions),
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
        call(tmp_path, extensions=video._video_file_extensions),
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
        call(tmp_path, extensions=video._video_file_extensions),
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
