import re
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies.trackers import nbl


@pytest.fixture
def tracker():
    tracker = Mock()
    tracker.name = 'nbl'
    return tracker


@pytest.fixture
def nbl_tracker_jobs(tracker, tmp_path, mocker):
    content_path = tmp_path / 'Foo S01 1080p BluRay x264-ASDF'

    nbl_tracker_jobs = nbl.NblTrackerJobs(
        content_path=str(content_path),
        tracker=tracker,
        torrent_destination=str(tmp_path / 'destination'),
        common_job_args={
            'home_directory': str(tmp_path / 'home_directory'),
            'ignore_cache': True,
        },
        options=None,
    )

    return nbl_tracker_jobs


def test_jobs_before_upload(nbl_tracker_jobs, tmp_path, mocker):
    create_torrent_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.create_torrent_job', Mock())
    mediainfo_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.mediainfo_job', Mock())
    tvmaze_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.tvmaze_job', Mock())
    category_job_mock = mocker.patch('upsies.trackers.nbl.NblTrackerJobs.category_job', Mock())
    assert nbl_tracker_jobs.jobs_before_upload == (
        create_torrent_job_mock,
        mediainfo_job_mock,
        tvmaze_job_mock,
        category_job_mock,
    )


def test_category_job(nbl_tracker_jobs, mocker):
    mocker.patch.object(nbl_tracker_jobs, 'make_choice_job')
    mocker.patch.object(type(nbl_tracker_jobs), 'release_name', PropertyMock())

    assert nbl_tracker_jobs.category_job is nbl_tracker_jobs.make_choice_job.return_value
    assert nbl_tracker_jobs.make_choice_job.call_args_list == [call(
        name='nbl-category',
        label='Category',
        autodetected=str(nbl_tracker_jobs.release_name.type),
        options=(
            {'label': 'Season', 'value': '3', 'regex': re.compile(r'^(?i:season)$')},
            {'label': 'Episode', 'value': '1', 'regex': re.compile(r'^(?i:episode)$')},
        ),
    )]


def test_post_data(nbl_tracker_jobs, mocker):
    mocker.patch.object(type(nbl_tracker_jobs), 'options', PropertyMock(return_value={
        'apikey': 'mock api key',
    }))
    mocker.patch.object(nbl_tracker_jobs, 'get_job_attribute', side_effect=(
        'mock category',
    ))
    mocker.patch.object(nbl_tracker_jobs, 'get_job_output', side_effect=(
        'mock tvmaze id',
        'mock mediainfo',
    ))
    mocker.patch.object(type(nbl_tracker_jobs), 'category_job', PropertyMock())
    mocker.patch.object(type(nbl_tracker_jobs), 'tvmaze_job', PropertyMock())
    mocker.patch.object(type(nbl_tracker_jobs), 'mediainfo_job', PropertyMock())

    assert nbl_tracker_jobs.post_data == {
        'api_key': 'mock api key',
        'category': 'mock category',
        'tvmazeid': 'mock tvmaze id',
        'mediainfo': 'mock mediainfo',
    }
    assert nbl_tracker_jobs.get_job_attribute.call_args_list == [
        call(nbl_tracker_jobs.category_job, 'choice'),
    ]
    assert nbl_tracker_jobs.get_job_output.call_args_list == [
        call(nbl_tracker_jobs.tvmaze_job, slice=0),
        call(nbl_tracker_jobs.mediainfo_job, slice=0),
    ]


def test_torrent_filepath(nbl_tracker_jobs, mocker):
    mocker.patch.object(type(nbl_tracker_jobs), 'create_torrent_job', PropertyMock(
        return_value='mock create_torrent_job',
    ))
    mocker.patch.object(nbl_tracker_jobs, 'get_job_output', side_effect=(
        'mock torrent filepath',
    ))

    assert nbl_tracker_jobs.torrent_filepath == 'mock torrent filepath'
    assert nbl_tracker_jobs.get_job_output.call_args_list == [
        call(nbl_tracker_jobs.create_torrent_job, slice=0),
    ]
