import pytest

from upsies.utils import image


@pytest.mark.parametrize(
    argnames='os, exp_executable',
    argvalues=(
        ('linux', 'ffmpeg'),
        ('windows', 'ffmpeg.exe'),
        ('plan9', 'ffmpeg'),
    ),
    ids=lambda v: str(v),
)
def test_ffmpeg_executable(os, exp_executable, mocker):
    mocker.patch('upsies.utils.os_family', return_value=os)
    assert image._ffmpeg_executable() == exp_executable
