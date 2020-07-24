import os
from unittest.mock import Mock, call, patch

import pytest

from upsies import binaries, errors
from upsies.tools import mediainfo


@patch('upsies.utils.run.run')
def test_run_mediainfo_fails_to_chdir(run_mock, tmp_path):
    video_path = tmp_path / 'foo.mkv'
    video_path.write_bytes(b'video data')
    video_path.parent.chmod(0o660)
    try:
        with pytest.raises(errors.MediainfoError, match=rf'^{video_path.parent}: Permission denied$'):
            mediainfo._run_mediainfo(video_path)
        assert run_mock.call_args_list == []
    finally:
        video_path.parent.chmod(770)

@patch('upsies.utils.run.run')
def test_run_mediainfo_returns_cwd_to_original_path(run_mock, tmp_path):
    orig_cwd = os.getcwd()
    video_path = tmp_path / 'foo.mkv'
    video_path.write_bytes(b'video data')
    run_mock.return_value = '<all the media info>'
    mediainfo._run_mediainfo(video_path)
    assert os.getcwd() == orig_cwd

@patch('upsies.utils.run.run')
def test_run_mediainfo_fails_to_find_video_file(run_mock, tmp_path):
    file1 = tmp_path / 'foo.txt'
    file1.write_text('some text')
    file2 = tmp_path / 'foo.jpg'
    file2.write_bytes(b'image data')
    with pytest.raises(errors.MediainfoError, match=rf'^{tmp_path}: No video file found$'):
        mediainfo._run_mediainfo(tmp_path)
    assert run_mock.call_args_list == []

@patch('upsies.utils.run.run')
def test_run_mediainfo_fails_to_run_mediainfo(run_mock, tmp_path):
    video_path = tmp_path / 'foo.mkv'
    video_path.write_bytes(b'video data')
    run_mock.side_effect = errors.ProcessError('Invalid argument: --abc')
    with pytest.raises(errors.MediainfoError, match=rf'^{video_path}: Invalid argument: --abc$'):
        mediainfo._run_mediainfo(video_path)
    assert run_mock.call_args_list == [call((binaries.mediainfo, video_path.name), cache=True)]

@patch('upsies.utils.run.run')
def test_run_mediainfo_forwards_arguments(run_mock, tmp_path):
    video_path = tmp_path / 'foo.mkv'
    video_path.write_bytes(b'video data')
    mediainfo._run_mediainfo(video_path, '--foo', '--bar')
    assert run_mock.call_args_list == [call((binaries.mediainfo, video_path.name,
                                             '--foo', '--bar'), cache=True)]

@patch('upsies.utils.run.run')
def test_run_mediainfo_returns_mediainfo_output(run_mock, tmp_path):
    video_path = tmp_path / 'foo.mkv'
    video_path.write_bytes(b'video data')
    run_mock.return_value = '<all the media info>'
    stdout = mediainfo._run_mediainfo(video_path)
    assert stdout == '<all the media info>'

@patch('upsies.utils.run.run')
def test_run_mediainfo_contains_correct_relative_path_when_passed_directory(run_mock, tmp_path):
    video_path = tmp_path / 'foo' / 'bar.mkv'
    video_path.parent.mkdir()
    video_path.write_bytes(b'video data')
    mediainfo._run_mediainfo(video_path.parent)
    assert run_mock.call_args_list == [call((binaries.mediainfo, 'foo/bar.mkv'), cache=True)]


@patch('upsies.tools.mediainfo._run_mediainfo')
def test_tracks_requests_json_output_from_mediainfo(run_mediainfo_mock):
    video_path = 'foo/bar.mkv'
    run_mediainfo_mock.return_value = '{"media": {"track": ["track1", "track2"]}}'
    tracks = mediainfo.tracks(video_path)
    assert run_mediainfo_mock.call_args_list == [call('foo/bar.mkv', '--Output=JSON')]
    assert tracks == ['track1', 'track2']

@patch('upsies.tools.mediainfo._run_mediainfo')
def test_tracks_gets_unexpected_output_from_mediainfo(run_mediainfo_mock):
    video_path = 'foo/bar.mkv'
    run_mediainfo_mock.return_value = 'this is not JSON'
    with pytest.raises(RuntimeError, match=(r'^foo/bar.mkv: Unexpected mediainfo output: '
                                            r'this is not JSON: Expecting value: line 1 column 1 \(char 0\)$')):
        mediainfo.tracks(video_path)

    video_path = 'foo/bar.mkv'
    run_mediainfo_mock.return_value = '{"this": ["is", "unexpected", "json"]}'
    with pytest.raises(RuntimeError, match=(r'^foo/bar.mkv: Unexpected mediainfo output: '
                                            r'\{"this": \["is", "unexpected", "json"\]\}: '
                                            r"Missing field: 'media'$")):
        mediainfo.tracks(video_path)


@patch('upsies.tools.mediainfo.tracks')
def test_default_track_returns_track_with_default_tag(tracks_mock):
    tracks_mock.return_value = [{'@type': 'Video'},
                                {'@type': 'Audio', 'Some': 'information'},
                                {'@type': 'Video', 'Default': 'No'},
                                {'@type': 'Audio', 'More': 'information'},
                                {'@type': 'Video', 'Default': 'Yes'}]
    assert mediainfo.default_track('video', 'foo.mkv') == tracks_mock.return_value[-1]

@patch('upsies.tools.mediainfo.tracks')
def test_default_track_returns_first_track(tracks_mock):
    tracks_mock.return_value = [{'@type': 'Video', 'Some': 'information'},
                                {'@type': 'Audio', 'Other': 'information'}]
    assert mediainfo.default_track('video', 'foo.mkv') == tracks_mock.return_value[0]
    tracks_mock.return_value = [{'@type': 'Audio', 'Other': 'information'},
                                {'@type': 'Video', 'Some': 'information'}]
    assert mediainfo.default_track('video', 'bar.mkv') == tracks_mock.return_value[1]

@patch('upsies.tools.mediainfo.tracks')
def test_default_track_ignores_MediainfoError(tracks_mock):
    tracks_mock.side_effect = errors.MediainfoError('No')
    assert mediainfo.default_track('video', 'foo.mkv') == {}

@patch('upsies.tools.mediainfo.tracks')
def test_default_track_raises_nonMediainfoError(tracks_mock):
    tracks_mock.side_effect = errors.DependencyError('I need something')
    with pytest.raises(errors.DependencyError, match=r'^I need something$'):
        mediainfo.default_track('video', 'foo.mkv')


video_resolution_samples = (
    (7680, 4320, '4320p'),
    (3840, 2160, '2160p'),
    (1920, 1080, '1080p'),
    (1920, 1044, '1080p'),
    (1920, 800, '1080p'),
    (1390, 1080, '1080p'),
    (1280, 533, '720p'),
    (768, 720, '720p'),
    (768, 576, '576p'),
    (640, 480, '480p')
)

@pytest.mark.parametrize('width, height, exp_res', video_resolution_samples)
@patch('os.path.exists', Mock(return_value=True))
@patch('upsies.tools.mediainfo.tracks')
def test_resolution(tracks_mock, width, height, exp_res):
    tracks_mock.return_value = [{'@type': 'Video',
                                 'Width': str(width),
                                 'Height': str(height)}]
    mediainfo.resolution.cache_clear()
    assert mediainfo.resolution('foo.mkv') == exp_res

@patch('os.path.exists', Mock(return_value=True))
@patch('upsies.tools.mediainfo.tracks')
def test_resolution_is_unknown(tracks_mock):
    tracks_mock.return_value = [{'@type': 'Video'}]
    mediainfo.resolution.cache_clear()
    assert mediainfo.resolution('foo.mkv') is None


audio_format_samples = (
    (None, {}),
    ('DTS:X', {"Format": "DTS", "Format_Commercial_IfAny": "DTS-HD Master Audio", "Format_AdditionalFeatures": "XLL X"}),
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
)

@pytest.mark.parametrize('exp_audio_format, audio_dict', audio_format_samples)
@patch('upsies.tools.mediainfo.tracks')
def test_audio_format(tracks_mock, exp_audio_format, audio_dict):
    tracks_mock.return_value = [{**{'@type': 'Audio'}, **audio_dict}]
    mediainfo.audio_format.cache_clear()
    assert mediainfo.audio_format('foo.mkv') == exp_audio_format

@patch('upsies.tools.mediainfo.tracks')
def test_audio_format_of_unsupported_or_nonexisting_file(tracks_mock):
    tracks_mock.side_effect = errors.MediainfoError('Something went wrong')
    mediainfo.audio_format.cache_clear()
    assert mediainfo.audio_format('foo.mkv') is None


audio_channels_samples = (
    (None, {}),
    ('1.0', {'Channels': '1'}),
    ('2.0', {'Channels': '2'}),
    ('2.1', {'Channels': '3'}),
    ('3.1', {'Channels': '4'}),
    ('4.1', {'Channels': '5'}),
    ('5.1', {'Channels': '6'}),
    ('6.1', {'Channels': '7'}),
    ('7.1', {'Channels': '8'}),
)

@pytest.mark.parametrize('exp_audio_channels, audio_dict', audio_channels_samples)
@patch('upsies.tools.mediainfo.tracks')
def test_audio_channels(tracks_mock, exp_audio_channels, audio_dict):
    tracks_mock.return_value = [{**{'@type': 'Audio'}, **audio_dict}]
    mediainfo.audio_channels.cache_clear()
    assert mediainfo.audio_channels('foo.mkv') == exp_audio_channels

@patch('upsies.tools.mediainfo.tracks')
def test_audio_channels_of_unsupported_or_nonexisting_file(tracks_mock):
    tracks_mock.side_effect = errors.MediainfoError('Something went wrong')
    mediainfo.audio_channels.cache_clear()
    assert mediainfo.audio_channels('foo.mkv') is None


video_format_samples = (
    (None, {}),
    ('XviD', {"Encoded_Library_Name": "XviD"}),
    ('x264', {"Encoded_Library_Name": "x264"}),
    ('x265', {"Encoded_Library_Name": "x265"}),
    ('H.264', {"Format": "AVC"}),
    ('H.265', {"Format": "HEVC"}),
    ('VP9', {"Format": "VP9"}),
)

@pytest.mark.parametrize('exp_video_format, video_dict', video_format_samples)
@patch('upsies.tools.mediainfo.tracks')
def test_video_format(tracks_mock, exp_video_format, video_dict):
    tracks_mock.return_value = [{**{'@type': 'Video'}, **video_dict}]
    mediainfo.video_format.cache_clear()
    assert mediainfo.video_format('foo.mkv') == exp_video_format

@patch('upsies.tools.mediainfo.tracks')
def test_video_format_of_unsupported_or_nonexisting_file(tracks_mock):
    tracks_mock.side_effect = errors.MediainfoError('Something went wrong')
    mediainfo.video_format.cache_clear()
    assert mediainfo.video_format('foo.mkv') is None
