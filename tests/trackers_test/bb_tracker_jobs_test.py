from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import (__homepage__, __project_name__, __version__, errors, jobs,
                    utils)
from upsies.trackers import bb


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

@pytest.fixture
def imghost():
    class MockImageHost(utils.imghosts.base.ImageHostBase):
        async def _upload(self, path):
            pass


@pytest.fixture
def bb_tracker_jobs(imghost, tmp_path):
    content_path = tmp_path / 'content.mkv'
    content_path.write_bytes(b'mock matroska data')
    return bb.BbTrackerJobs(
        content_path=str(content_path),
        tracker=Mock(),
        image_host=imghost,
        bittorrent_client=Mock(),
        torrent_destination=str(tmp_path / 'destination'),
        common_job_args={
            'home_directory': tmp_path / 'home_directory',
            'ignore_cache': True,
        },
        cli_args=None,
    )


def test_release_name_property(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'content_path',
                        PropertyMock(return_value='path/to/content'))
    ReleaseName_mock = mocker.patch('upsies.utils.release.ReleaseName')
    # Property should be cached
    for i in range(3):
        assert bb_tracker_jobs.release_name is ReleaseName_mock.return_value
    assert ReleaseName_mock.call_args_list == [call('path/to/content')]


def test_is_movie_release_property(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice',
                        PropertyMock(return_value=utils.types.ReleaseType.movie))
    assert bb_tracker_jobs.is_movie_release is True
    for value in (None, utils.types.ReleaseType.series, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_movie_release is False

def test_is_season_release_property(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice',
                        PropertyMock(return_value=utils.types.ReleaseType.season))
    assert bb_tracker_jobs.is_season_release is True
    for value in (None, utils.types.ReleaseType.movie, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_season_release is False

def test_is_episode_release_property(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice',
                        PropertyMock(return_value=utils.types.ReleaseType.episode))
    assert bb_tracker_jobs.is_episode_release is True
    for value in (None, utils.types.ReleaseType.movie, utils.types.ReleaseType.season):
        mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_episode_release is False

def test_is_series_release_property(bb_tracker_jobs, mocker):
    for value in (utils.types.ReleaseType.season, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_series_release is True
    for value in (None, utils.types.ReleaseType.movie):
        mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_series_release is False


@pytest.mark.parametrize(
    argnames='episodes, exp_season',
    argvalues=(
        ('S03', 3),
        ('S04E05', 4),
        ('S06S07', 6),
        ('S10', 10),
        ('foo', None),
    ),
)
def test_season_property(episodes, exp_season, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'episodes', PropertyMock(return_value=episodes))
    assert bb_tracker_jobs.season == exp_season

@pytest.mark.parametrize(
    argnames='episodes, exp_episode',
    argvalues=(
        ('S03E04', 4),
        ('S04E23', 23),
        ('S05E10E11', 10),
        ('foo', None),
    ),
)
def test_episode_property(episodes, exp_episode, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'episodes', PropertyMock(return_value=episodes))
    assert bb_tracker_jobs.episode == exp_episode


def test_promotion_property(bb_tracker_jobs, mocker):
    assert bb_tracker_jobs.promotion == ''.join((
        '[align=right][size=1]Shared with ',
        f'[url={__homepage__}]{__project_name__} {__version__}[/url]',
        '[/size][/align]',
    ))


def test_imdb_property(bb_tracker_jobs, mocker):
    assert isinstance(bb_tracker_jobs.imdb, utils.webdbs.imdb.ImdbApi)

def test_tvmaze_property(bb_tracker_jobs, mocker):
    assert isinstance(bb_tracker_jobs.tvmaze, utils.webdbs.tvmaze.TvmazeApi)


@pytest.mark.parametrize('output, exp_id', ((('123',), '123'), ((), None)))
@pytest.mark.asyncio
async def test_get_imdb_id_from_imdb_job(output, exp_id, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'imdb_job', Mock(
        is_enabled=True, wait=AsyncMock(), output=output,
    ))
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value='wrong id'))
    id = await bb_tracker_jobs.get_imdb_id()
    assert id == exp_id
    assert bb_tracker_jobs.imdb_job.wait.call_args_list == [call()]
    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == []

@pytest.mark.parametrize('output, exp_id', ((('123',), '123'), ((), None)))
@pytest.mark.asyncio
async def test_get_imdb_id_from_tvmaze_job(output, exp_id, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'imdb_job', Mock(
        is_enabled=False, wait=AsyncMock(), output=(),
    ))
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value='tvmaze id'))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'imdb_id', AsyncMock(return_value=exp_id))
    id = await bb_tracker_jobs.get_imdb_id()
    assert id == exp_id
    assert bb_tracker_jobs.imdb_job.wait.call_args_list == []
    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == [call()]
    assert bb_tracker_jobs.tvmaze.imdb_id.call_args_list == [call('tvmaze id')]

@pytest.mark.asyncio
async def test_get_imdb_id_from_nowhere(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'imdb_job', Mock(
        is_enabled=False, wait=AsyncMock(), output=(),
    ))
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value=None))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'imdb_id', AsyncMock(return_value='123'))
    id = await bb_tracker_jobs.get_imdb_id()
    assert id == None
    assert bb_tracker_jobs.imdb_job.wait.call_args_list == []
    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == [call()]
    assert bb_tracker_jobs.tvmaze.imdb_id.call_args_list == []


@pytest.mark.parametrize('output, exp_id', ((('123',), '123'), ((), None)))
@pytest.mark.asyncio
async def test_get_tvmaze_id_from_tvmaze_job(output, exp_id, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'tvmaze_job', Mock(
        is_enabled=True, wait=AsyncMock(), output=output,
    ))
    id = await bb_tracker_jobs.get_tvmaze_id()
    assert id == exp_id
    assert bb_tracker_jobs.tvmaze_job.wait.call_args_list == [call()]

@pytest.mark.asyncio
async def test_get_tvmaze_id_from_nowhere(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'tvmaze_job', Mock(
        is_enabled=False, wait=AsyncMock(), output=(),
    ))
    id = await bb_tracker_jobs.get_tvmaze_id()
    assert id == None
    assert bb_tracker_jobs.tvmaze_job.wait.call_args_list == []


@pytest.mark.asyncio
async def test_try_webdbs(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_db1_id', AsyncMock(return_value=None), create=True)
    mocker.patch.object(bb_tracker_jobs, 'get_db2_id', AsyncMock(return_value='123'), create=True)
    mocker.patch.object(bb_tracker_jobs, 'get_db3_id', AsyncMock(return_value='456'), create=True)
    mocker.patch.object(bb_tracker_jobs, 'get_db4_id', AsyncMock(return_value='789'), create=True)
    db1 = Mock()
    db2 = Mock()
    db3 = Mock()
    db4 = Mock()
    db1.configure_mock(name='db1', get_result=AsyncMock(return_value='db1 result'))
    db2.configure_mock(name='db2', get_result=AsyncMock(return_value=None))
    db3.configure_mock(name='db3', get_result=AsyncMock(return_value='db3 result'))
    db4.configure_mock(name='db4', get_result=AsyncMock(return_value='db4 result'))
    return_value = await bb_tracker_jobs.try_webdbs((db1, db2, db3, db4), 'get_result')
    assert return_value == 'db3 result'
    assert bb_tracker_jobs.get_db1_id.call_args_list == [call()]
    assert bb_tracker_jobs.get_db2_id.call_args_list == [call()]
    assert bb_tracker_jobs.get_db3_id.call_args_list == [call()]
    assert bb_tracker_jobs.get_db4_id.call_args_list == []
    assert db1.get_result.call_args_list == []
    assert db2.get_result.call_args_list == [call('123')]
    assert db3.get_result.call_args_list == [call('456')]
    assert db4.get_result.call_args_list == []


@pytest.mark.asyncio
async def test_jobs_before_upload(bb_tracker_jobs, mocker):
    assert bb_tracker_jobs.jobs_before_upload == (
        # Generic jobs
        bb_tracker_jobs.release_type_job,
        bb_tracker_jobs.mediainfo_job,
        bb_tracker_jobs.create_torrent_job,
        bb_tracker_jobs.screenshots_job,
        bb_tracker_jobs.upload_screenshots_job,
        bb_tracker_jobs.scene_check_job,

        # Movie jobs
        bb_tracker_jobs.imdb_job,
        bb_tracker_jobs.movie_title_job,
        bb_tracker_jobs.movie_year_job,
        bb_tracker_jobs.movie_resolution_job,
        bb_tracker_jobs.movie_source_job,
        bb_tracker_jobs.movie_audio_codec_job,
        bb_tracker_jobs.movie_video_codec_job,
        bb_tracker_jobs.movie_container_job,
        bb_tracker_jobs.movie_release_info_job,
        bb_tracker_jobs.movie_poster_job,
        bb_tracker_jobs.movie_tags_job,
        bb_tracker_jobs.movie_description_job,

        # Series jobs
        bb_tracker_jobs.tvmaze_job,
        bb_tracker_jobs.series_title_job,
        bb_tracker_jobs.series_poster_job,
        bb_tracker_jobs.series_tags_job,
        bb_tracker_jobs.series_description_job,
    )


def test_condition_is_movie_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value='foo'))
    assert bb_tracker_jobs.condition_is_movie_release() == 'foo'

def test_condition_is_season_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_season_release', PropertyMock(return_value='foo'))
    assert bb_tracker_jobs.condition_is_season_release() == 'foo'

def test_condition_is_episode_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value='foo'))
    assert bb_tracker_jobs.condition_is_episode_release() == 'foo'

def test_condition_is_series_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value='foo'))
    assert bb_tracker_jobs.condition_is_series_release() == 'foo'
