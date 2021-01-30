from unittest.mock import Mock, call

import pytest

from upsies.trackers.nbl import NblTrackerJobs
from upsies.utils.types import ReleaseType


def test_jobs_before_upload(tmp_path, mocker):
    create_torrent_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.create_torrent_job', Mock())
    mediainfo_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.mediainfo_job', Mock())
    tvmaze_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.tvmaze_job', Mock())
    category_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.category_job', Mock())
    tracker_jobs = NblTrackerJobs(
        content_path=Mock(),
        tracker=Mock(),
        image_host=Mock(),
        bittorrent_client=Mock(),
        torrent_destination=Mock(),
        common_job_args=Mock(),
    )
    assert tuple(tracker_jobs.jobs_before_upload) == (
        create_torrent_job_mock,
        mediainfo_job_mock,
        tvmaze_job_mock,
        category_job_mock,
    )


@pytest.mark.parametrize(
    argnames=('release_info', 'focused_choice'),
    argvalues=(
        (ReleaseType.episode, 'Episode'),
        (ReleaseType.season, 'Season'),
        (ReleaseType.movie, 'Season'),
        (ReleaseType.unknown, 'Season'),
    ),
)
def test_category_job(release_info, focused_choice, tmp_path, mocker):
    mocker.patch('upsies.utils.release.ReleaseInfo', return_value={'type': release_info})
    ChoiceJob_mock = mocker.patch('upsies.jobs.prompt.ChoiceJob', Mock())
    tracker_jobs = NblTrackerJobs(
        content_path=Mock(),
        tracker=Mock(),
        image_host=Mock(),
        bittorrent_client=Mock(),
        torrent_destination=Mock(),
        common_job_args={'home_directory': 'path/to/home', 'ignore_cache': 'mock bool'},
    )
    assert tracker_jobs.category_job == ChoiceJob_mock.return_value
    assert ChoiceJob_mock.call_args_list == [
        call(
            name='category',
            label='Category',
            choices=('Season', 'Episode'),
            focused=focused_choice,
            home_directory='path/to/home',
            ignore_cache='mock bool',
        ),
    ]
