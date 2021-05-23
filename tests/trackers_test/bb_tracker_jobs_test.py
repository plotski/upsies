import re
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import __homepage__, __project_name__, __version__, errors, utils
from upsies.trackers import bb
from upsies.utils.types import ReleaseType


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def imghost():
    class MockImageHost(utils.imghosts.base.ImageHostBase):
        name = 'mock image host'

        async def _upload(self, path):
            pass

    return MockImageHost()


@pytest.fixture
def btclient():
    class MockClientApi(utils.btclients.base.ClientApiBase):
        name = 'mock bittorrent client'

        async def add_torrent(self, torrent_path, download_path=None):
            pass

    return MockClientApi()


@pytest.fixture
def bb_tracker_jobs(imghost, btclient, tmp_path, mocker):
    content_path = tmp_path / 'content.mkv'
    content_path.write_bytes(b'mock matroska data')

    # Prevent black magic from coroutines to seep into our realm
    mocker.patch('upsies.utils.release.ReleaseName._tracks')

    bb_tracker_jobs = bb.BbTrackerJobs(
        content_path=str(content_path),
        tracker=Mock(),
        image_host=imghost,
        bittorrent_client=btclient,
        torrent_destination=str(tmp_path / 'destination'),
        common_job_args={
            'home_directory': str(tmp_path / 'home_directory'),
            'ignore_cache': True,
        },
        cli_args=None,
    )

    return bb_tracker_jobs


def test_release_name(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'content_path',
                        PropertyMock(return_value='path/to/content'))
    ReleaseName_mock = mocker.patch('upsies.utils.release.ReleaseName')
    # Property should be cached
    for i in range(3):
        assert bb_tracker_jobs.release_name is ReleaseName_mock.return_value
    assert ReleaseName_mock.call_args_list == [call('path/to/content')]


def test_release_type(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_type_job), 'choice',
                        PropertyMock(return_value='foo'))
    assert bb_tracker_jobs.release_type == 'foo'


def test_is_movie_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=utils.types.ReleaseType.movie))
    assert bb_tracker_jobs.is_movie_release is True
    for value in (None, utils.types.ReleaseType.series, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_movie_release is False

def test_is_season_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=utils.types.ReleaseType.season))
    assert bb_tracker_jobs.is_season_release is True
    for value in (None, utils.types.ReleaseType.movie, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_season_release is False

def test_is_episode_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=utils.types.ReleaseType.episode))
    assert bb_tracker_jobs.is_episode_release is True
    for value in (None, utils.types.ReleaseType.movie, utils.types.ReleaseType.season):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_episode_release is False

def test_is_series_release(bb_tracker_jobs, mocker):
    for value in (utils.types.ReleaseType.season, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=value))
        assert bb_tracker_jobs.is_series_release is True
    for value in (None, utils.types.ReleaseType.movie):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=value))
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
def test_season(episodes, exp_season, bb_tracker_jobs, mocker):
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
def test_episode(episodes, exp_episode, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'episodes', PropertyMock(return_value=episodes))
    assert bb_tracker_jobs.episode == exp_episode


def test_promotion(bb_tracker_jobs, mocker):
    assert bb_tracker_jobs.promotion == ''.join((
        '[align=right][size=1]Shared with ',
        f'[url={__homepage__}]{__project_name__} {__version__}[/url]',
        '[/size][/align]',
    ))


def test_imdb(bb_tracker_jobs, mocker):
    assert isinstance(bb_tracker_jobs.imdb, utils.webdbs.imdb.ImdbApi)

def test_tvmaze(bb_tracker_jobs, mocker):
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
    assert id is None
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
    assert id is None
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
async def test_try_webdbs_defaults_to_result_from_last_webdb(bb_tracker_jobs, mocker):
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
    db3.configure_mock(name='db3', get_result=AsyncMock(return_value=()))
    db4.configure_mock(name='db4', get_result=AsyncMock(return_value={}))
    return_value = await bb_tracker_jobs.try_webdbs((db1, db2, db3, db4), 'get_result')
    assert return_value == {}
    assert bb_tracker_jobs.get_db1_id.call_args_list == [call()]
    assert bb_tracker_jobs.get_db2_id.call_args_list == [call()]
    assert bb_tracker_jobs.get_db3_id.call_args_list == [call()]
    assert bb_tracker_jobs.get_db4_id.call_args_list == [call()]
    assert db1.get_result.call_args_list == []
    assert db2.get_result.call_args_list == [call('123')]
    assert db3.get_result.call_args_list == [call('456')]
    assert db4.get_result.call_args_list == [call('789')]


@pytest.mark.asyncio
async def test_jobs_before_upload(bb_tracker_jobs, mocker):
    make_job_condition_mock = mocker.patch('upsies.trackers.bb.jobs.BbTrackerJobs.make_job_condition')
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

    assert make_job_condition_mock.call_args_list == [
        call('mediainfo_job', ReleaseType.movie, ReleaseType.season, ReleaseType.episode),
        call('create_torrent_job', ReleaseType.movie, ReleaseType.season, ReleaseType.episode),
        call('screenshots_job', ReleaseType.movie, ReleaseType.season, ReleaseType.episode),
        call('upload_screenshots_job', ReleaseType.movie, ReleaseType.season, ReleaseType.episode),
        call('add_torrent_job', ReleaseType.movie, ReleaseType.season, ReleaseType.episode),
        call('copy_torrent_job', ReleaseType.movie, ReleaseType.season, ReleaseType.episode),
        call('imdb_job', ReleaseType.movie),
        call('movie_title_job', ReleaseType.movie),
        call('movie_year_job', ReleaseType.movie),
        call('movie_resolution_job', ReleaseType.movie),
        call('movie_source_job', ReleaseType.movie),
        call('movie_audio_codec_job', ReleaseType.movie),
        call('movie_video_codec_job', ReleaseType.movie),
        call('movie_container_job', ReleaseType.movie),
        call('movie_release_info_job', ReleaseType.movie),
        call('movie_poster_job', ReleaseType.movie),
        call('movie_tags_job', ReleaseType.movie),
        call('movie_description_job', ReleaseType.movie),
        call('tvmaze_job', ReleaseType.season, ReleaseType.episode),
        call('series_title_job', ReleaseType.season, ReleaseType.episode),
        call('series_poster_job', ReleaseType.season, ReleaseType.episode),
        call('series_tags_job', ReleaseType.season, ReleaseType.episode),
        call('series_description_job', ReleaseType.season, ReleaseType.episode),
    ]


@pytest.mark.parametrize(
    argnames='release_type, release_types, monojob_attributes, job_attr, exp_return_value',
    argvalues=(
        (None, (ReleaseType.movie,), (), 'foo', False),
        (None, (ReleaseType.movie,), ('foo', 'bar'), 'foo', False),
        (ReleaseType, (ReleaseType.series,), ('foo', 'bar'), 'foo', False),
        (ReleaseType.movie, (ReleaseType.movie,), ('foo', 'bar'), 'foo', True),
        (ReleaseType.movie, (ReleaseType.movie,), ('foo', 'bar'), 'baz', False),
        (ReleaseType.movie, (ReleaseType.movie,), (), 'foo', True),
        (ReleaseType.movie, (ReleaseType.movie,), (), 'baz', True),
        (ReleaseType.movie, (ReleaseType.series,), (), 'foo', False),
        (ReleaseType.movie, (ReleaseType.series,), ('foo', 'bar'), 'foo', False),
    ),
)
def test_make_job_condition(release_type, release_types, monojob_attributes, exp_return_value, job_attr, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value=release_type))
    mocker.patch.object(type(bb_tracker_jobs), 'monojob_attributes', PropertyMock(return_value=monojob_attributes))
    return_value = bb_tracker_jobs.make_job_condition(job_attr, *release_types)()
    assert return_value == exp_return_value


@pytest.mark.parametrize(
    argnames='is_movie_release, is_series_release, cli_args, exp_monojobs',
    argvalues=(
        (False, False, SimpleNamespace(title=True, description=False, poster=False, release_info=False, tags=False),
         ()),
        (True, False, SimpleNamespace(title=True, description=False, poster=False, release_info=False, tags=False),
         ('imdb_job', 'movie_title_job')),
        (True, False, SimpleNamespace(title=False, description=True, poster=False, release_info=False, tags=False),
         ('imdb_job', 'movie_description_job')),
        (True, False, SimpleNamespace(title=False, description=False, poster=True, release_info=False, tags=False),
         ('imdb_job', 'movie_poster_job')),
        (True, False, SimpleNamespace(title=False, description=False, poster=False, release_info=True, tags=False),
         ('movie_release_info_job',)),
        (True, False, SimpleNamespace(title=False, description=False, poster=False, release_info=False, tags=True),
         ('imdb_job', 'movie_tags_job')),
        (True, False, SimpleNamespace(), ()),
        (False, True, SimpleNamespace(title=True, description=False, poster=False, release_info=False, tags=False),
         ('tvmaze_job', 'series_title_job')),
        (False, True, SimpleNamespace(title=False, description=True, poster=False, release_info=False, tags=False),
         ('tvmaze_job', 'mediainfo_job', 'screenshots_job', 'upload_screenshots_job', 'series_description_job')),
        (False, True, SimpleNamespace(title=False, description=False, poster=True, release_info=False, tags=False),
         ('tvmaze_job', 'series_poster_job')),
        (False, True, SimpleNamespace(title=False, description=False, poster=False, release_info=True, tags=False),
         ('tvmaze_job', 'series_title_job')),
        (False, True, SimpleNamespace(title=False, description=False, poster=False, release_info=False, tags=True),
         ('tvmaze_job', 'series_tags_job')),
        (False, True, SimpleNamespace(), ()),
    ),
)
def test_monojob_attributes(is_movie_release, is_series_release, cli_args, exp_monojobs, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=is_movie_release))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=is_series_release))
    mocker.patch.object(type(bb_tracker_jobs), 'cli_args', PropertyMock(return_value=cli_args))
    assert bb_tracker_jobs.monojob_attributes == exp_monojobs


def test_release_type_job(bb_tracker_jobs, mocker):
    ChoiceJob_mock = mocker.patch('upsies.jobs.dialog.ChoiceJob')
    assert bb_tracker_jobs.release_type_job is ChoiceJob_mock.return_value
    assert ChoiceJob_mock.call_args_list == [call(
        name='release-type',
        label='Release Type',
        choices=(
            ('Movie', utils.types.ReleaseType.movie),
            ('Season', utils.types.ReleaseType.season),
            ('Episode', utils.types.ReleaseType.episode),
        ),
        focused=bb_tracker_jobs.release_name.type,
        **bb_tracker_jobs.common_job_args,
    )]


def test_imdb_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    WebDbSearchJob_mock = mocker.patch('upsies.jobs.webdb.WebDbSearchJob')
    assert bb_tracker_jobs.imdb_job is WebDbSearchJob_mock.return_value
    assert WebDbSearchJob_mock.call_args_list == [call(
        condition=bb_tracker_jobs.make_job_condition.return_value,
        content_path=bb_tracker_jobs.content_path,
        db=bb_tracker_jobs.imdb,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('imdb_job', ReleaseType.movie)]


def test_movie_title_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'imdb_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.movie_title_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.imdb_job.signal.register.call_args_list == [call(
        'output', bb_tracker_jobs.fill_in_movie_title,
    )]
    assert TextFieldJob_mock.call_args_list == [call(
        name='movie-title',
        label='Title',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        validator=bb_tracker_jobs.movie_title_validator,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('imdb_job', ReleaseType.movie),
        call('movie_title_job', ReleaseType.movie),
    ]

@pytest.mark.parametrize(
    argnames='title, exp_error',
    argvalues=(
        ('the title', None),
        ('', 'Invalid title: '),
        (' ', 'Invalid title: '),
        ('\t', 'Invalid title: '),
    ),
)
def test_movie_title_validator(title, exp_error, bb_tracker_jobs, mocker):
    if exp_error is None:
        bb_tracker_jobs.movie_title_validator(title)
    else:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            bb_tracker_jobs.movie_title_validator(title)

def test_fill_in_movie_title(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_name',
                        PropertyMock(title_with_aka='The Title AKA Teh Tilte'))
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_movie_title', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_title_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_title_job, 'add_task', Mock())

    bb_tracker_jobs.fill_in_movie_title('tt0123')

    assert bb_tracker_jobs.get_movie_title.call_args_list == [call('tt0123')]
    assert bb_tracker_jobs.movie_title_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.get_movie_title.return_value,
        default_text=bb_tracker_jobs.release_name.title_with_aka,
        finish_on_success=False,
    )]
    assert bb_tracker_jobs.movie_title_job.add_task.call_args_list == [call(
        bb_tracker_jobs.movie_title_job.fetch_text.return_value
    )]


def test_movie_year_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'imdb_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.movie_year_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.imdb_job.signal.register.call_args_list == [call(
        'output', bb_tracker_jobs.fill_in_movie_year,
    )]
    assert TextFieldJob_mock.call_args_list == [call(
        name='movie-year',
        label='Year',
        text=bb_tracker_jobs.release_name.year,
        condition=bb_tracker_jobs.make_job_condition.return_value,
        validator=bb_tracker_jobs.movie_year_validator,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('imdb_job', ReleaseType.movie),
        call('movie_year_job', ReleaseType.movie),
    ]

def test_movie_year_validator(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'release_name')
    bb_tracker_jobs.movie_year_validator('2015')
    assert bb_tracker_jobs.release_name.year == '2015'

def test_fill_in_movie_year(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_name', PropertyMock(year='2014'))
    mocker.patch.object(bb_tracker_jobs.imdb, 'year', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_year_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_year_job, 'add_task', Mock())

    bb_tracker_jobs.fill_in_movie_year('tt0123')

    assert bb_tracker_jobs.imdb.year.call_args_list == [call('tt0123')]
    assert bb_tracker_jobs.movie_year_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.imdb.year.return_value,
        default_text=bb_tracker_jobs.release_name.year,
        finish_on_success=True,
    )]
    assert bb_tracker_jobs.movie_year_job.add_task.call_args_list == [call(
        bb_tracker_jobs.movie_year_job.fetch_text.return_value
    )]


def test_movie_resolution_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choice_job')
    assert bb_tracker_jobs.movie_resolution_job is bb_tracker_jobs.make_choice_job.return_value
    assert bb_tracker_jobs.make_choice_job.call_args_list == [call(
        name='movie-resolution',
        label='Resolution',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetected=bb_tracker_jobs.release_info_resolution,
        autofinish=True,
        options=(
            {'label': '4320p', 'value': '2160p', 'regex': re.compile(r'4320p')},
            {'label': '2160p', 'value': '2160p', 'regex': re.compile(r'2160p')},
            {'label': '1080p', 'value': '1080p', 'regex': re.compile(r'1080p')},
            {'label': '1080i', 'value': '1080i', 'regex': re.compile(r'1080i')},
            {'label': '720p', 'value': '720p', 'regex': re.compile(r'720p')},
            {'label': '720i', 'value': '720i', 'regex': re.compile(r'720i')},
            {'label': '576p', 'value': '480p', 'regex': re.compile(r'576p')},
            {'label': '576i', 'value': '480i', 'regex': re.compile(r'576i')},
            {'label': '540p', 'value': '480p', 'regex': re.compile(r'540p')},
            {'label': '540i', 'value': '480i', 'regex': re.compile(r'540i')},
            {'label': '480p', 'value': '480p', 'regex': re.compile(r'480p')},
            {'label': '480i', 'value': '480i', 'regex': re.compile(r'480i')},
            {'label': 'SD', 'value': 'SD', 'regex': re.compile(r'SD')},
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_resolution_job', ReleaseType.movie)]


def test_movie_source_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choice_job')
    assert bb_tracker_jobs.movie_source_job is bb_tracker_jobs.make_choice_job.return_value
    assert bb_tracker_jobs.make_choice_job.call_args_list == [call(
        name='movie-source',
        label='Source',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetected=bb_tracker_jobs.release_name.source,
        autofinish=True,
        options=(
            {'label': 'BluRay', 'value': 'BluRay', 'regex': re.compile('^BluRay')},  # BluRay or BluRay Remux
            # {'label': 'BluRay 3D', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'BluRay RC', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'CAM', 'value': ' ', 'regex': re.compile('^ $')},
            {'label': 'DVD5', 'value': 'DVD5', 'regex': re.compile('^DVD5$')},
            {'label': 'DVD9', 'value': 'DVD9', 'regex': re.compile('^DVD9$')},
            {'label': 'DVDRip', 'value': 'DVDRip', 'regex': re.compile('^DVDRip$')},
            # {'label': 'DVDSCR', 'value': ' ', 'regex': re.compile('^ $')},
            {'label': 'HD-DVD', 'value': 'HD-DVD', 'regex': re.compile('^HD-DVD$')},
            # {'label': 'HDRip', 'value': ' ', 'regex': re.compile('^ $')},
            {'label': 'HDTV', 'value': 'HDTV', 'regex': re.compile('^HDTV$')},
            # {'label': 'PDTV', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'R5', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'SDTV', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'TC', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'TeleSync', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'VHSRip', 'value': ' ', 'regex': re.compile('^ $')},
            # {'label': 'VODRip', 'value': ' ', 'regex': re.compile('^ $')},
            {'label': 'WEB-DL', 'value': 'WEB-DL', 'regex': re.compile('^WEB-DL$')},
            {'label': 'WEBRip', 'value': 'WebRip', 'regex': re.compile('^WEBRip$')},
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_source_job', ReleaseType.movie)]


def test_movie_audio_codec_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choice_job')
    assert bb_tracker_jobs.movie_audio_codec_job is bb_tracker_jobs.make_choice_job.return_value
    assert bb_tracker_jobs.make_choice_job.call_args_list == [call(
        name='movie-audio-codec',
        label='Audio Codec',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetected=bb_tracker_jobs.release_info_audio_format,
        autofinish=True,
        options=(
            {'label': 'AAC', 'value': 'AAC', 'regex': re.compile(r'^AAC$')},
            {'label': 'AC-3', 'value': 'AC-3', 'regex': re.compile(r'^(?:E-|)AC-3$')},   # AC-3, E-AC-3
            {'label': 'DTS', 'value': 'DTS', 'regex': re.compile(r'^DTS(?!-HD)')},       # DTS, DTS-ES
            {'label': 'DTS-HD', 'value': 'DTS-HD', 'regex': re.compile(r'^DTS-HD\b')},   # DTS-HD, DTS-HD MA
            {'label': 'DTS:X', 'value': 'DTS:X', 'regex': re.compile(r'^DTS:X$')},
            {'label': 'Dolby Atmos', 'value': 'Atmos', 'regex': re.compile(r'Atmos')},
            {'label': 'FLAC', 'value': 'FLAC', 'regex': re.compile(r'^FLAC$')},
            {'label': 'MP3', 'value': 'MP3', 'regex': re.compile(r'^MP3$')},
            # {'label': 'PCM', 'value': 'PCM', 'regex': re.compile(r'^$')},
            {'label': 'TrueHD', 'value': 'True-HD', 'regex': re.compile(r'TrueHD')},
            {'label': 'Vorbis', 'value': 'Vorbis', 'regex': re.compile(r'^Vorbis$')},
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_audio_codec_job', ReleaseType.movie)]


def test_movie_video_codec_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choice_job')
    assert bb_tracker_jobs.movie_video_codec_job is bb_tracker_jobs.make_choice_job.return_value
    assert bb_tracker_jobs.make_choice_job.call_args_list == [call(
        name='movie-video-codec',
        label='Video Codec',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetected=bb_tracker_jobs.release_name.video_format,
        autofinish=True,
        options=(
            {'label': 'x264', 'value': 'x264', 'regex': re.compile(r'x264')},
            {'label': 'x265', 'value': 'x265', 'regex': re.compile(r'x265')},
            {'label': 'XviD', 'value': 'XVid', 'regex': re.compile(r'(?i:XviD)')},
            # {'label': 'MPEG-2', 'value': 'MPEG-2', 'regex': re.compile(r'')},
            # {'label': 'WMV-HD', 'value': 'WMV-HD', 'regex': re.compile(r'')},
            # {'label': 'DivX', 'value': 'DivX', 'regex': re.compile(r'')},
            {'label': 'H.264', 'value': 'H.264', 'regex': re.compile(r'H.264')},
            {'label': 'H.265', 'value': 'H.265', 'regex': re.compile(r'H.265')},
            # {'label': 'VC-1', 'value': 'VC-1', 'regex': re.compile(r'')},
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_video_codec_job', ReleaseType.movie)]


def test_movie_container_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choice_job')
    assert bb_tracker_jobs.movie_container_job is bb_tracker_jobs.make_choice_job.return_value
    assert bb_tracker_jobs.make_choice_job.call_args_list == [call(
        name='movie-container',
        label='Container',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetected=utils.fs.file_extension(utils.video.first_video(bb_tracker_jobs.content_path)),
        autofinish=True,
        options=(
            {'label': 'AVI', 'value': 'AVI', 'regex': re.compile(r'(?i:AVI)')},
            {'label': 'MKV', 'value': 'MKV', 'regex': re.compile('(?i:MKV)')},
            {'label': 'MP4', 'value': 'MP4', 'regex': re.compile(r'(?i:MP4)')},
            {'label': 'TS', 'value': 'TS', 'regex': re.compile(r'(?i:TS)')},
            {'label': 'VOB', 'value': 'VOB', 'regex': re.compile(r'(?i:VOB)')},
            {'label': 'WMV', 'value': 'WMV', 'regex': re.compile(r'(?i:WMV)')},
            {'label': 'm2ts', 'value': 'm2ts', 'regex': re.compile(r'(?i:m2ts)')},
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_container_job', ReleaseType.movie)]


def test_movie_release_info_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.movie_release_info_job is TextFieldJob_mock.return_value
    assert TextFieldJob_mock.call_args_list == [call(
        name='movie-release-info',
        label='Release Info',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        text=bb_tracker_jobs.get_movie_release_info(),
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_release_info_job', ReleaseType.movie)]


def test_movie_poster_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    CustomJob_mock = mocker.patch('upsies.jobs.custom.CustomJob')
    assert bb_tracker_jobs.movie_poster_job is CustomJob_mock.return_value
    assert CustomJob_mock.call_args_list == [call(
        name='movie-poster',
        label='Poster',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        worker=bb_tracker_jobs.movie_get_poster_url,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_poster_job', ReleaseType.movie)]

@pytest.mark.asyncio
async def test_movie_get_poster_url(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_resized_poster_url', AsyncMock(return_value='http://foo'))
    poster_job = Mock()
    poster_url = await bb_tracker_jobs.movie_get_poster_url(poster_job)
    assert poster_url == 'http://foo'
    assert bb_tracker_jobs.get_resized_poster_url.call_args_list == [
        call(poster_job, bb_tracker_jobs.get_movie_poster_url),
    ]


def test_movie_tags_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'imdb_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.movie_tags_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.imdb_job.signal.register.call_args_list == [call(
        'output', bb_tracker_jobs.fill_in_movie_tags,
    )]
    assert TextFieldJob_mock.call_args_list == [call(
        name='movie-tags',
        label='Tags',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        validator=bb_tracker_jobs.movie_tags_validator,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('imdb_job', ReleaseType.movie),
        call('movie_tags_job', ReleaseType.movie),
    ]

@pytest.mark.parametrize(
    argnames='tags, exp_error',
    argvalues=(
        ('foo,bar,baz', None),
        ('', 'Invalid tags: '),
        (' ', 'Invalid tags: '),
        ('\t', 'Invalid tags: '),
    ),
)
def test_movie_tags_validator(tags, exp_error, bb_tracker_jobs, mocker):
    if exp_error is None:
        bb_tracker_jobs.movie_tags_validator(tags)
    else:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            bb_tracker_jobs.movie_tags_validator(tags)

def test_fill_in_movie_tags(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_tags', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_tags_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_tags_job, 'add_task', Mock())

    bb_tracker_jobs.fill_in_movie_tags('tt0123')

    assert bb_tracker_jobs.get_tags.call_args_list == [call()]
    assert bb_tracker_jobs.movie_tags_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.get_tags.return_value,
        finish_on_success=True,
    )]
    assert bb_tracker_jobs.movie_tags_job.add_task.call_args_list == [call(
        bb_tracker_jobs.movie_tags_job.fetch_text.return_value
    )]


def test_movie_description_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'imdb_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.movie_description_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.imdb_job.signal.register.call_args_list == [call(
        'finished', bb_tracker_jobs.fill_in_movie_description,
    )]
    assert TextFieldJob_mock.call_args_list == [call(
        name='movie-description',
        label='Description',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        validator=bb_tracker_jobs.movie_description_validator,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('imdb_job', ReleaseType.movie),
        call('movie_description_job', ReleaseType.movie),
    ]

@pytest.mark.parametrize(
    argnames='description, exp_error',
    argvalues=(
        ('Something happens.', None),
        ('', 'Invalid description: '),
        (' ', 'Invalid description: '),
        ('\t', 'Invalid description: '),
    ),
)
def test_movie_description_validator(description, exp_error, bb_tracker_jobs, mocker):
    if exp_error is None:
        bb_tracker_jobs.movie_description_validator(description)
    else:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            bb_tracker_jobs.movie_description_validator(description)

def test_fill_in_movie_description(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_description', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_description_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_description_job, 'add_task', Mock())

    bb_tracker_jobs.fill_in_movie_description('ignored mock job')

    assert bb_tracker_jobs.get_description.call_args_list == [call()]
    assert bb_tracker_jobs.movie_description_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.get_description.return_value,
        finish_on_success=True,
    )]
    assert bb_tracker_jobs.movie_description_job.add_task.call_args_list == [call(
        bb_tracker_jobs.movie_description_job.fetch_text.return_value
    )]


def test_tvmaze_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    WebDbSearchJob_mock = mocker.patch('upsies.jobs.webdb.WebDbSearchJob')
    assert bb_tracker_jobs.tvmaze_job is WebDbSearchJob_mock.return_value
    assert WebDbSearchJob_mock.call_args_list == [call(
        condition=bb_tracker_jobs.make_job_condition.return_value,
        content_path=bb_tracker_jobs.content_path,
        db=bb_tracker_jobs.tvmaze,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('tvmaze_job', ReleaseType.series, ReleaseType.episode),
    ]


def test_series_title_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'tvmaze_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.series_title_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.tvmaze_job.signal.register.call_args_list == [call(
        'output', bb_tracker_jobs.fill_in_series_title,
    )]
    assert TextFieldJob_mock.call_args_list == [call(
        name='series-title',
        label='Title',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        validator=bb_tracker_jobs.series_title_validator,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('tvmaze_job', ReleaseType.series, ReleaseType.episode),
        call('series_title_job', ReleaseType.series, ReleaseType.episode),
    ]

@pytest.mark.parametrize(
    argnames='title, exp_error',
    argvalues=(
        ('The Title S01 [foo / bar / baz]', None),
        ('The Title S01 [foo / UNKNOWN_BAR / baz]', 'Failed to autodetect: bar'),
        ('UNKNOWN_TITLE S01 [foo / bar / baz]', 'Failed to autodetect: title'),
        ('', 'Invalid title: '),
        (' ', 'Invalid title: '),
        ('\t', 'Invalid title: '),
    ),
)
def test_series_title_validator(title, exp_error, bb_tracker_jobs, mocker):
    if exp_error is None:
        bb_tracker_jobs.series_title_validator(title)
    else:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            bb_tracker_jobs.series_title_validator(title)

def test_fill_in_series_title(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_name',
                        PropertyMock(title_with_aka_and_year='The Title S01 [foo / bar / baz]'))
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_series_title_and_release_info', Mock())
    mocker.patch.object(bb_tracker_jobs.series_title_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.series_title_job, 'add_task', Mock())

    bb_tracker_jobs.fill_in_series_title('tt0123')

    assert bb_tracker_jobs.get_series_title_and_release_info.call_args_list == [call('tt0123')]
    assert bb_tracker_jobs.series_title_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.get_series_title_and_release_info.return_value,
        default_text=bb_tracker_jobs.release_name.title_with_aka_and_year,
        finish_on_success=False,
    )]
    assert bb_tracker_jobs.series_title_job.add_task.call_args_list == [call(
        bb_tracker_jobs.series_title_job.fetch_text.return_value
    )]


def test_series_poster_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    CustomJob_mock = mocker.patch('upsies.jobs.custom.CustomJob')
    assert bb_tracker_jobs.series_poster_job is CustomJob_mock.return_value
    assert CustomJob_mock.call_args_list == [call(
        name='series-poster',
        label='Poster',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        worker=bb_tracker_jobs.series_get_poster_url,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('series_poster_job', ReleaseType.series, ReleaseType.episode),
    ]

@pytest.mark.asyncio
async def test_series_get_poster_url(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_resized_poster_url', AsyncMock(return_value='http://foo'))
    poster_job = Mock()
    poster_url = await bb_tracker_jobs.series_get_poster_url(poster_job)
    assert poster_url == 'http://foo'
    assert bb_tracker_jobs.get_resized_poster_url.call_args_list == [
        call(poster_job, bb_tracker_jobs.get_series_poster_url),
    ]


def test_series_tags_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'tvmaze_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.series_tags_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.tvmaze_job.signal.register.call_args_list == [call(
        'output', bb_tracker_jobs.fill_in_series_tags,
    )]
    assert TextFieldJob_mock.call_args_list == [call(
        name='series-tags',
        label='Tags',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        validator=bb_tracker_jobs.series_tags_validator,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('tvmaze_job', ReleaseType.series, ReleaseType.episode),
        call('series_tags_job', ReleaseType.series, ReleaseType.episode),
    ]

@pytest.mark.parametrize(
    argnames='tags, exp_error',
    argvalues=(
        ('foo,bar,baz', None),
        ('', 'Invalid tags: '),
        (' ', 'Invalid tags: '),
        ('\t', 'Invalid tags: '),
    ),
)
def test_series_tags_validator(tags, exp_error, bb_tracker_jobs, mocker):
    if exp_error is None:
        bb_tracker_jobs.series_tags_validator(tags)
    else:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            bb_tracker_jobs.series_tags_validator(tags)

def test_fill_in_series_tags(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_tags', Mock())
    mocker.patch.object(bb_tracker_jobs.series_tags_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.series_tags_job, 'add_task', Mock())

    bb_tracker_jobs.fill_in_series_tags('tt0123')

    assert bb_tracker_jobs.get_tags.call_args_list == [call()]
    assert bb_tracker_jobs.series_tags_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.get_tags.return_value,
        finish_on_success=True,
    )]
    assert bb_tracker_jobs.series_tags_job.add_task.call_args_list == [call(
        bb_tracker_jobs.series_tags_job.fetch_text.return_value
    )]


def test_series_description_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'tvmaze_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.series_description_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.tvmaze_job.signal.register.call_args_list == [call(
        'finished', bb_tracker_jobs.fill_in_series_description,
    )]
    assert TextFieldJob_mock.call_args_list == [call(
        name='series-description',
        label='Description',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        validator=bb_tracker_jobs.series_description_validator,
        **bb_tracker_jobs.common_job_args,
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [
        call('tvmaze_job', ReleaseType.series, ReleaseType.episode),
        call('series_description_job', ReleaseType.series, ReleaseType.episode),
    ]

@pytest.mark.parametrize(
    argnames='description, exp_error',
    argvalues=(
        ('foo,bar,baz', None),
        ('', 'Invalid description: '),
        (' ', 'Invalid description: '),
        ('\t', 'Invalid description: '),
    ),
)
def test_series_description_validator(description, exp_error, bb_tracker_jobs, mocker):
    if exp_error is None:
        bb_tracker_jobs.series_description_validator(description)
    else:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            bb_tracker_jobs.series_description_validator(description)

def test_fill_in_series_description(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_description', Mock())
    mocker.patch.object(bb_tracker_jobs.series_description_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.series_description_job, 'add_task', Mock())

    bb_tracker_jobs.fill_in_series_description('ignored mock job')

    assert bb_tracker_jobs.get_description.call_args_list == [call()]
    assert bb_tracker_jobs.series_description_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.get_description.return_value,
        finish_on_success=True,
    )]
    assert bb_tracker_jobs.series_description_job.add_task.call_args_list == [call(
        bb_tracker_jobs.series_description_job.fetch_text.return_value
    )]


@pytest.mark.parametrize(
    argnames='tracks, exp_text',
    argvalues=(
        ({}, None),
        ({'foo': 'bar'}, None),
        ({'Text': ({},)}, None),
        ({'Text': ({'Language': 'foo'},)}, None),
        ({'Text': ({'Language': 'en'},)}, 'w. Subtitles'),
        ({'Text': ({'Language': 'foo'}, {'Language': 'en'}, {'Language': 'bar'})}, 'w. Subtitles'),
    ),
)
def test_release_info_subtitles(tracks, exp_text, bb_tracker_jobs, mocker):
    mocker.patch('upsies.utils.video.tracks', return_value=tracks)
    assert bb_tracker_jobs.release_info_subtitles == exp_text


@pytest.mark.parametrize(
    argnames='has_commentary, exp_text',
    argvalues=(
        (False, None),
        (True, 'w. Commentary'),
    ),
)
def test_release_info_commentary(has_commentary, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'has_commentary',
                        PropertyMock(return_value=has_commentary))
    assert bb_tracker_jobs.release_info_commentary == exp_text


@pytest.mark.parametrize(
    argnames='source, exp_source',
    argvalues=(
        ('WEB-DL', 'WEB-DL'),
        ('WEB-DL Remux', 'WEB-DL'),
        ('BluRay', 'BluRay'),
        ('BluRay Remux', 'BluRay'),
        ('WEBRip', 'WebRip'),
    ),
)
def test_release_info_source(source, exp_source, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'source',
                        PropertyMock(return_value=source))
    assert bb_tracker_jobs.release_info_source == exp_source


@pytest.mark.parametrize(
    argnames='source, exp_text',
    argvalues=(
        ('WEB-DL', None),
        ('BluRay', None),
        ('BluRay Remux', 'REMUX'),
    ),
)
def test_release_info_remux(source, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'source',
                        PropertyMock(return_value=source))
    assert bb_tracker_jobs.release_info_remux == exp_text


@pytest.mark.parametrize(
    argnames='width, height, frame_rate, resolution, exp_text',
    argvalues=(
        (700, 460, 0, '123p', '123p'),
        (699, 460, 0, '123p', '123p'),
        (700, 459, 0, '123p', '123p'),
        (699, 459, 0, '123p', 'SD'),
        (1000, 1000, 25, '576p', '576p PAL'),
        (1000, 1000, 25, '480p', '480p'),
        (1000, 1000, 24, '576p', '576p'),
    ),
)
def test_release_info_resolution(width, height, frame_rate, resolution, exp_text, bb_tracker_jobs, mocker):
    mocker.patch('upsies.utils.video.width', return_value=width)
    mocker.patch('upsies.utils.video.height', return_value=height)
    mocker.patch('upsies.utils.video.frame_rate', return_value=frame_rate)
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'resolution',
                        PropertyMock(return_value=resolution))
    assert bb_tracker_jobs.release_info_resolution == exp_text


@pytest.mark.parametrize(
    argnames='release_info_resolution, exp_text',
    argvalues=(
        ('480p', None),
        ('576p', None),
        ('576p PAL', '576p PAL'),
    ),
)
def test_release_info_576p_PAL(release_info_resolution, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_resolution',
                        PropertyMock(return_value=release_info_resolution))
    assert bb_tracker_jobs.release_info_576p_PAL == exp_text


@pytest.mark.parametrize(
    argnames='edition, exp_text',
    argvalues=(
        ((), None),
        (('Proper',), 'PROPER'),
        (('foo', 'Proper', 'bar'), 'PROPER'),
    ),
)
def test_release_info_proper(edition, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition',
                        PropertyMock(return_value=edition))
    assert bb_tracker_jobs.release_info_proper == exp_text


@pytest.mark.parametrize(
    argnames='edition, exp_text',
    argvalues=(
        ((), None),
        (('Repack',), 'REPACK'),
        (('foo', 'Repack', 'bar'), 'REPACK'),
    ),
)
def test_release_info_repack(edition, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition',
                        PropertyMock(return_value=edition))
    assert bb_tracker_jobs.release_info_repack == exp_text


@pytest.mark.parametrize(
    argnames='is_hdr10, exp_text',
    argvalues=(
        (False, None),
        (True, 'HDR10'),
    ),
)
def test_release_info_hdr10(is_hdr10, exp_text, bb_tracker_jobs, mocker):
    mocker.patch('upsies.utils.video.is_hdr10', return_value=is_hdr10)
    assert bb_tracker_jobs.release_info_hdr10 == exp_text


@pytest.mark.parametrize(
    argnames='bit_depth, exp_text',
    argvalues=(
        ('5', None),
        ('9', None),
        ('10', '10-bit'),
        ('11', None),
    ),
)
def test_release_info_10bit(bit_depth, exp_text, bb_tracker_jobs, mocker):
    mocker.patch('upsies.utils.video.bit_depth', return_value=bit_depth)
    assert bb_tracker_jobs.release_info_10bit == exp_text


@pytest.mark.parametrize(
    argnames='has_dual_audio, exp_text',
    argvalues=(
        (False, None),
        (True, 'Dual Audio'),
    ),
)
def test_release_info_dual_audio(has_dual_audio, exp_text, bb_tracker_jobs, mocker):
    mocker.patch('upsies.utils.video.has_dual_audio', return_value=has_dual_audio)
    assert bb_tracker_jobs.release_info_dual_audio == exp_text


@pytest.mark.parametrize(
    argnames='audio_format, exp_text',
    argvalues=(
        ('DTS', 'DTS'),
        ('E-AC-3', 'E-AC-3'),
        ('E-AC-3 Atmos', 'Atmos'),
        ('TrueHD Atmos', 'Atmos'),
    ),
)
def test_release_info_audio_format(audio_format, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'audio_format',
                        PropertyMock(return_value=audio_format))
    assert bb_tracker_jobs.release_info_audio_format == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('Uncensored',), 'Uncensored'),
    ),
)
def test_release_info_uncensored(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_uncensored == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('Uncut',), 'Uncut'),
    ),
)
def test_release_info_uncut(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_uncut == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('Unrated',), 'Unrated'),
    ),
)
def test_release_info_unrated(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_unrated == exp_text


@pytest.mark.parametrize(
    argnames='release_name, exp_text',
    argvalues=(
        ('Foo.2000.BluRay.720p.DTS.5.1.x264-ASDF', None),
        ('Foo.2000.Remaster.BluRay.720p.DTS.5.1.x264-ASDF', 'Remastered'),
        ('Foo.2000.Remastered.BluRay.720p.DTS.5.1.x264-ASDF', 'Remastered'),
        ('Foo.2000.4k.Remaster.BluRay.720p.DTS.5.1.x264-ASDF', '4k Remaster'),
        ('Foo.2000.4k.Remastered.BluRay.720p.DTS.5.1.x264-ASDF', '4k Remaster'),
    ),
)
def test_release_info_remastered(release_name, exp_text, bb_tracker_jobs, mocker, tmp_path):
    content_path = tmp_path / f'{release_name}.mkv'
    content_path.write_text('teh data')
    mocker.patch.object(type(bb_tracker_jobs), 'content_path', PropertyMock(return_value=str(content_path)))
    assert bb_tracker_jobs.release_info_remastered == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('DC',), "Director's Cut"),
    ),
)
def test_release_info_directors_cut(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_directors_cut == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('Extended',), 'Extended Edition'),
    ),
)
def test_release_info_extended_edition(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_extended_edition == exp_text


@pytest.mark.parametrize(
    argnames='release_name, exp_text',
    argvalues=(
        ('Foo.2000.BluRay.720p.DTS.5.1.x264-ASDF', None),
        ('Foo.2000.10th.Anniversary.Edition.BluRay.720p.DTS.5.1.x264-ASDF', '10th Anniversary Edition'),
        ('Foo.2000.15TH.anniversary.edition.BluRay.720p.DTS.5.1.x264-ASDF', '15th Anniversary Edition'),
        ('Foo.2000.ANNIVERSARY.EDITION.BluRay.720p.DTS.5.1.x264-ASDF', 'Anniversary Edition'),
    ),
)
def test_release_info_anniversary_edition(release_name, exp_text, bb_tracker_jobs, mocker, tmp_path):
    content_path = tmp_path / f'{release_name}.mkv'
    content_path.write_text('teh data')
    mocker.patch.object(type(bb_tracker_jobs), 'content_path', PropertyMock(return_value=str(content_path)))
    assert bb_tracker_jobs.release_info_anniversary_edition == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('Criterion',), 'Criterion Edition'),
    ),
)
def test_release_info_criterion_edition(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_criterion_edition == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('Special',), 'Special Edition'),
    ),
)
def test_release_info_special_edition(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_special_edition == exp_text


@pytest.mark.parametrize(
    argnames='editions, exp_text',
    argvalues=(
        (('Foo',), None),
        (('Limited',), 'Limited'),
    ),
)
def test_release_info_limited_edition(editions, exp_text, bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'edition', PropertyMock(return_value=editions))
    assert bb_tracker_jobs.release_info_limited_edition == exp_text


@pytest.mark.asyncio
async def test_get_movie_title(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.release_name, 'fetch_info', AsyncMock())
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'title_with_aka',
                        PropertyMock(return_value='Title AKA Tilte'))
    movie_title = await bb_tracker_jobs.get_movie_title('imdb id')
    assert movie_title == 'Title AKA Tilte'
    assert bb_tracker_jobs.release_name.fetch_info.call_args_list == [call('imdb id')]


@pytest.mark.parametrize(
    argnames='tvmaze_id, imdb_id, exp_fetch_info_calls',
    argvalues=(
        ('tvmaze id', 'imdb id', [call('imdb id')]),
        ('tvmaze id', '', []),
        ('tvmaze id', None, []),
    ),
)
@pytest.mark.asyncio
async def test_get_series_title_and_release_info_calls_fetch_info(tvmaze_id, imdb_id, exp_fetch_info_calls, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.release_name, 'fetch_info', AsyncMock())
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'imdb_id', AsyncMock(return_value=imdb_id))
    await bb_tracker_jobs.get_series_title_and_release_info(tvmaze_id)
    assert bb_tracker_jobs.tvmaze.imdb_id.call_args_list == [call(tvmaze_id)]
    assert bb_tracker_jobs.release_name.fetch_info.call_args_list == exp_fetch_info_calls

@pytest.mark.parametrize('year_required', (True, False))
@pytest.mark.asyncio
async def test_get_series_title_and_release_info_title_with_aka_and_year(year_required, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.release_name, 'fetch_info', AsyncMock())
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'imdb_id', AsyncMock())
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'title_with_aka',
                        PropertyMock(return_value='Title AKA Tilte'))
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'year_required',
                        PropertyMock(return_value=year_required))
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'year',
                        PropertyMock(return_value='2015'))
    title = await bb_tracker_jobs.get_series_title_and_release_info('tvmaze id')
    if year_required:
        assert title.startswith('Title AKA Tilte (2015) [UNKNOWN')
    else:
        assert title.startswith('Title AKA Tilte [UNKNOWN')

@pytest.mark.parametrize(
    argnames='is_season_release, season, exp_season_in_string',
    argvalues=(
        (True, 5, True),
        (True, '', False),
        (True, None, False),
        (False, 5, False),
        (False, '', False),
        (False, None, False),
    ),
)
@pytest.mark.asyncio
async def test_get_series_title_and_release_info_season(is_season_release, season, exp_season_in_string, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.release_name, 'fetch_info', AsyncMock())
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'imdb_id', AsyncMock())
    mocker.patch.object(type(bb_tracker_jobs), 'is_season_release', PropertyMock(return_value=is_season_release))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value=season))
    title = await bb_tracker_jobs.get_series_title_and_release_info('tvmaze id')
    if exp_season_in_string:
        assert ' - Season 5 [UNKNOWN' in title
    else:
        assert ' - Season 5 [UNKNOWN' not in title

@pytest.mark.parametrize(
    argnames='is_episode_release, episodes, exp_episode_in_string',
    argvalues=(
        (True, utils.release.Episodes.from_string('S05E10'), True),
        (True, '', False),
        (True, None, False),
        (False, utils.release.Episodes.from_string('S05E10'), False),
        (False, '', False),
        (False, None, False),
    ),
)
@pytest.mark.asyncio
async def test_get_series_title_and_release_info_episode(is_episode_release, episodes, exp_episode_in_string, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.release_name, 'fetch_info', AsyncMock())
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'imdb_id', AsyncMock())
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=is_episode_release))
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'episodes', PropertyMock(return_value=episodes))
    title = await bb_tracker_jobs.get_series_title_and_release_info('tvmaze id')
    if exp_episode_in_string:
        assert ' S05E10 [UNKNOWN' in title
    else:
        assert ' S05E10 [UNKNOWN' not in title

@pytest.mark.asyncio
async def test_get_series_title_and_release_info_has_release_info(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.release_name, 'fetch_info', AsyncMock())
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'imdb_id', AsyncMock())
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'episodes', PropertyMock(return_value=False))

    mocker.patch.object(type(bb_tracker_jobs), 'release_info_source', PropertyMock(return_value='BluRay'))
    mocker.patch.object(type(bb_tracker_jobs.release_name), 'video_format', PropertyMock(return_value='x264'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_audio_format', PropertyMock(return_value='E-AC-3'))
    mocker.patch('upsies.utils.fs.file_extension', return_value='mkv')
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_resolution', PropertyMock(return_value='1080p'))

    mocker.patch.object(type(bb_tracker_jobs), 'release_info_proper', PropertyMock(return_value='PROPER'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_repack', PropertyMock(return_value='REPACK'))

    mocker.patch.object(type(bb_tracker_jobs), 'release_info_remux', PropertyMock(return_value='REMUX'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_576p_PAL', PropertyMock(return_value='576p PAL'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_hdr10', PropertyMock(return_value='HDR10'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_10bit', PropertyMock(return_value='10-bit'))

    mocker.patch.object(type(bb_tracker_jobs), 'release_info_uncensored', PropertyMock(return_value='Uncensored'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_uncut', PropertyMock(return_value='Uncut'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_unrated', PropertyMock(return_value='Unrated'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_remastered', PropertyMock(return_value='Remastered'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_directors_cut', PropertyMock(return_value="Director's Cut"))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_extended_edition', PropertyMock(return_value='Extended Edition'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_anniversary_edition', PropertyMock(return_value='Anniversary Edition'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_criterion_edition', PropertyMock(return_value='Criterion Edition'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_special_edition', PropertyMock(return_value='Special Edition'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_limited_edition', PropertyMock(return_value='Limited'))

    mocker.patch.object(type(bb_tracker_jobs), 'release_info_dual_audio', PropertyMock(return_value='Dual Audio'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_commentary', PropertyMock(return_value='w. Commentary'))
    mocker.patch.object(type(bb_tracker_jobs), 'release_info_subtitles', PropertyMock(return_value='w. Subtitles'))

    title = await bb_tracker_jobs.get_series_title_and_release_info('tvmaze id')
    exp_info = ('[BluRay / x264 / E-AC-3 / MKV / 1080p / '
                'PROPER / REPACK / '
                'REMUX / HDR10 / 10-bit / '
                "Uncensored / Uncut / Unrated / Remastered / Director's Cut / "
                'Extended Edition / Anniversary Edition / Criterion Edition / Special Edition / Limited / '
                'Dual Audio / w. Commentary / w. Subtitles]')
    assert title.endswith(exp_info)


@pytest.mark.asyncio
async def test_get_resized_poster_url_fails_to_get_poster_file(bb_tracker_jobs, mocker):
    get_poster_file_mock = mocker.patch.object(bb_tracker_jobs, 'get_poster_file', AsyncMock(return_value=None))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    resize_mock = mocker.patch('upsies.utils.image.resize', return_value='path/to/resized.jpg')
    upload_mock = mocker.patch.object(bb_tracker_jobs.image_host, 'upload', AsyncMock(return_value='http://real.poster.jpg'))
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock()
    poster_url = await bb_tracker_jobs.get_resized_poster_url(poster_job, poster_url_getter)
    assert poster_url is None
    assert get_poster_file_mock.call_args_list == [call(poster_job, poster_url_getter)]
    assert resize_mock.call_args_list == []
    assert upload_mock.call_args_list == []
    assert error_mock.call_args_list == [call('Provide a poster file or URL with the --poster-file option.')]

@pytest.mark.asyncio
async def test_get_resized_poster_url_fails_to_resize_poster(bb_tracker_jobs, mocker):
    get_poster_file_mock = mocker.patch.object(bb_tracker_jobs, 'get_poster_file', AsyncMock(return_value='poster/path.jpg'))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    resize_mock = mocker.patch('upsies.utils.image.resize', side_effect=errors.ImageResizeError('No resize!'))
    upload_mock = mocker.patch.object(bb_tracker_jobs.image_host, 'upload', AsyncMock(return_value='http://real.poster.jpg'))
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock()
    poster_url = await bb_tracker_jobs.get_resized_poster_url(poster_job, poster_url_getter)
    assert poster_url is None
    assert get_poster_file_mock.call_args_list == [call(poster_job, poster_url_getter)]
    assert resize_mock.call_args_list == [call('poster/path.jpg', width=300)]
    assert upload_mock.call_args_list == []
    assert error_mock.call_args_list == [call('Poster resizing failed: No resize!')]

@pytest.mark.asyncio
async def test_get_resized_poster_url_fails_to_reupload_poster(bb_tracker_jobs, mocker):
    get_poster_file_mock = mocker.patch.object(bb_tracker_jobs, 'get_poster_file', AsyncMock(return_value='poster/path.jpg'))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    resize_mock = mocker.patch('upsies.utils.image.resize', return_value='path/to/resized.jpg')
    upload_mock = mocker.patch.object(bb_tracker_jobs.image_host, 'upload', AsyncMock(side_effect=errors.RequestError('nope')))
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock()
    poster_url = await bb_tracker_jobs.get_resized_poster_url(poster_job, poster_url_getter)
    assert poster_url is None
    assert get_poster_file_mock.call_args_list == [call(poster_job, poster_url_getter)]
    assert resize_mock.call_args_list == [call('poster/path.jpg', width=300)]
    assert upload_mock.call_args_list == [call('path/to/resized.jpg')]
    assert error_mock.call_args_list == [call('Poster upload failed: nope')]

@pytest.mark.asyncio
async def test_get_resized_poster_url_succeeds(bb_tracker_jobs, mocker):
    get_poster_file_mock = mocker.patch.object(bb_tracker_jobs, 'get_poster_file', AsyncMock(return_value='poster/path.jpg'))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    resize_mock = mocker.patch('upsies.utils.image.resize', return_value='path/to/resized.jpg')
    upload_mock = mocker.patch.object(bb_tracker_jobs.image_host, 'upload', AsyncMock(return_value='http://real.poster.jpg'))
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock()
    poster_url = await bb_tracker_jobs.get_resized_poster_url(poster_job, poster_url_getter)
    assert poster_url == 'http://real.poster.jpg'
    assert get_poster_file_mock.call_args_list == [call(poster_job, poster_url_getter)]
    assert resize_mock.call_args_list == [call('poster/path.jpg', width=300)]
    assert upload_mock.call_args_list == [call('path/to/resized.jpg')]
    assert error_mock.call_args_list == []


@pytest.mark.asyncio
async def test_get_poster_file_gets_poster_url_from_cli_argument(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'cli_args', Mock(poster_file='http://cli/poster.jpg'))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    download_mock = mocker.patch('upsies.utils.http.download', AsyncMock())
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock(return_value='http://original/poster/url.jpg')
    poster_file = await bb_tracker_jobs.get_poster_file(poster_job, poster_url_getter)
    assert poster_file == 'path/to/job/poster.bb.jpg'
    assert download_mock.call_args_list == [call('http://cli/poster.jpg', 'path/to/job/poster.bb.jpg')]
    assert poster_url_getter.call_args_list == []
    assert error_mock.call_args_list == []

@pytest.mark.asyncio
async def test_get_poster_file_gets_poster_file_from_cli_argument(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'cli_args', Mock(poster_file='path/to/cli/poster.jpg'))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    download_mock = mocker.patch('upsies.utils.http.download', AsyncMock())
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock(return_value='http://original/poster/url.jpg')
    poster_file = await bb_tracker_jobs.get_poster_file(poster_job, poster_url_getter)
    assert poster_file == 'path/to/cli/poster.jpg'
    assert download_mock.call_args_list == []
    assert poster_url_getter.call_args_list == []
    assert error_mock.call_args_list == []

@pytest.mark.asyncio
async def test_get_poster_file_fails_to_get_poster_file_from_poster_url_getter(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'cli_args', Mock(poster_file=None))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    download_mock = mocker.patch('upsies.utils.http.download', AsyncMock())
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock(return_value=None)
    poster_file = await bb_tracker_jobs.get_poster_file(poster_job, poster_url_getter)
    assert poster_file is None
    assert download_mock.call_args_list == []
    assert poster_url_getter.call_args_list == [call()]
    assert error_mock.call_args_list == [call('Failed to find poster URL.')]

@pytest.mark.asyncio
async def test_get_poster_file_fails_to_download_poster_from_cli_url(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'cli_args', Mock(poster_file='http://cli/poster.jpg'))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    download_mock = mocker.patch('upsies.utils.http.download', AsyncMock(
        side_effect=errors.RequestError('Failed to download'),
    ))
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock(return_value=None)
    poster_file = await bb_tracker_jobs.get_poster_file(poster_job, poster_url_getter)
    assert poster_file is None
    assert download_mock.call_args_list == [call('http://cli/poster.jpg', 'path/to/job/poster.bb.jpg')]
    assert poster_url_getter.call_args_list == []
    assert error_mock.call_args_list == [call('Poster download failed: Failed to download')]

@pytest.mark.asyncio
async def test_get_poster_file_fails_to_download_poster_from_poster_url_getter(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'cli_args', Mock(poster_file=None))
    error_mock = mocker.patch.object(bb_tracker_jobs, 'error')
    download_mock = mocker.patch('upsies.utils.http.download', AsyncMock(
        side_effect=errors.RequestError('Failed to download'),
    ))
    poster_job = Mock(home_directory='path/to/job')
    poster_url_getter = AsyncMock(return_value='http://url/getter/poster.jpg')
    poster_file = await bb_tracker_jobs.get_poster_file(poster_job, poster_url_getter)
    assert poster_file is None
    assert download_mock.call_args_list == [call('http://url/getter/poster.jpg', 'path/to/job/poster.bb.jpg')]
    assert poster_url_getter.call_args_list == [call()]
    assert error_mock.call_args_list == [call('Poster download failed: Failed to download')]


@pytest.mark.parametrize(
    argnames='imdb_id, poster_url, exp_return_value',
    argvalues=(
        (None, None, None),
        ('tt12345', None, None),
        ('tt12345', 'http://poster.url', 'http://poster.url'),
    ),
)
@pytest.mark.asyncio
async def test_get_movie_poster_url(imdb_id, poster_url, exp_return_value, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_imdb_id', AsyncMock(return_value=imdb_id))
    mocker.patch.object(bb_tracker_jobs.imdb, 'poster_url', AsyncMock(return_value=poster_url))
    poster_url = await bb_tracker_jobs.get_movie_poster_url()
    assert poster_url == exp_return_value


@pytest.mark.parametrize(
    argnames='tvmaze_id, poster_url, exp_return_value',
    argvalues=(
        (None, None, None),
        ('tt12345', None, None),
        ('tt12345', 'http://poster.url', 'http://poster.url'),
    ),
)
@pytest.mark.asyncio
async def test_get_series_poster_url(tvmaze_id, poster_url, exp_return_value, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value=tvmaze_id))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'poster_url', AsyncMock(return_value=poster_url))
    poster_url = await bb_tracker_jobs.get_series_poster_url()
    assert poster_url == exp_return_value


def test_get_movie_release_info(bb_tracker_jobs, mocker):
    infos = {
        # Scene tags
        'release_info_proper': 'PROPER',
        'release_info_repack': 'REPACK',

        # Special formats
        'release_info_remux': 'REMUX',
        'release_info_576p_PAL': '576p PAL',
        'release_info_hdr10': 'HDR10',
        'release_info_10bit': '10-bit',

        # Editions
        'release_info_uncensored': 'Uncensored',
        'release_info_uncut': 'Uncut',
        'release_info_unrated': 'Unrated',
        'release_info_remastered': 'Remastered',
        'release_info_directors_cut': "Director's Cut",
        'release_info_extended_edition': 'Extended Edition',
        'release_info_anniversary_edition': 'Anniversary Edition',
        'release_info_criterion_edition': 'Criterion Edition',
        'release_info_special_edition': 'Special Edition',
        'release_info_limited_edition': 'Limited',

        # Features
        'release_info_dual_audio': 'Dual Audio',
        'release_info_commentary': 'w. Commentary',
        'release_info_subtitles': 'w. Subtitles',
    }
    for k, v in infos.items():
        mocker.patch.object(type(bb_tracker_jobs), k, PropertyMock(return_value=v))
    release_info = bb_tracker_jobs.get_movie_release_info()
    assert release_info == ' / '.join(infos.values())


@pytest.mark.asyncio
async def test_get_tags_for_movie(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(side_effect=(
        # Genres
        ('comedy', 'hörrór'),
        # Directors
        ('Jim J. Jackson', "Émile 'E' Jaques"),
        # Cast
        ('Foo', 'Bar', 'BaZ'),
    )))
    tags = await bb_tracker_jobs.get_tags()
    assert tags == 'comedy,horror,jim.j.jackson,emile.e.jaques,foo,bar,baz'
    assert bb_tracker_jobs.try_webdbs.call_args_list == [
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'genres'),
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'directors'),
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'cast'),
    ]

@pytest.mark.asyncio
async def test_get_tags_for_series(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=True))
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(side_effect=(
        # Genres
        ('comedy', 'hörrór'),
        # Creators
        ('Jim J. Jackson', "Émile 'E' Jaques"),
        # Cast
        ('Foo', 'Bar', 'BaZ'),
    )))
    tags = await bb_tracker_jobs.get_tags()
    assert tags == 'comedy,horror,jim.j.jackson,emile.e.jaques,foo,bar,baz'
    assert bb_tracker_jobs.try_webdbs.call_args_list == [
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'genres'),
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'creators'),
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'cast'),
    ]

@pytest.mark.asyncio
async def test_get_tags_is_not_longer_than_200_characters(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(side_effect=(
        # Genres
        ('comedy', 'hörrór', 'drama', 'science-fiction', 'romance', 'action', 'thriller', 'documentary'),
        # Cast
        ('Mark Hamill', 'Harrison Ford', 'Carrie Fisher', 'Peter Cushing',
         'Alec Guinness', 'Anthony Daniels', 'Kenny Baker', 'Peter Mayhew',
         'David Prowse', 'Phil Brown', 'Shelagh Fraser', 'Jack Purvis',
         'Alex McCrindle', 'Eddie Byrne', 'Drewe Henley', 'Denis Lawson',
         'Garrick Hagon', 'Jack Klaff', 'William Hootkins', 'Angus MacInnes'),
    )))
    tags = await bb_tracker_jobs.get_tags()
    assert tags == (
        'comedy,horror,drama,science.fiction,romance,action,thriller,documentary,'
        'mark.hamill,harrison.ford,carrie.fisher,peter.cushing,alec.guinness,'
        'anthony.daniels,kenny.baker,peter.mayhew,david.prowse'
    )


@pytest.mark.asyncio
async def test_get_description_for_movie(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    mocker.patch.object(bb_tracker_jobs, 'format_description_summary', AsyncMock(return_value='summary'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_webdbs', AsyncMock(return_value='info from webdbs'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_year', AsyncMock(return_value='year'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_status', AsyncMock(return_value='status'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_countries', AsyncMock(return_value='countries'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_runtime', AsyncMock(return_value='runtime'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_directors', AsyncMock(return_value='directors'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_creators', AsyncMock(return_value=None))
    mocker.patch.object(bb_tracker_jobs, 'format_description_cast', AsyncMock(return_value='cast'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_series_screenshots', AsyncMock(return_value='series screenshots'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_series_mediainfo', AsyncMock(return_value='series mediainfo'))
    description = await bb_tracker_jobs.get_description()
    assert description == (
        'summary'
        '[quote]'
        'info from webdbs\n'
        'year\n'
        'status\n'
        'countries\n'
        'runtime\n'
        'directors\n'
        'cast'
        '[/quote]'
    ) + bb_tracker_jobs.promotion

@pytest.mark.asyncio
async def test_get_description_for_series(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=True))
    mocker.patch.object(bb_tracker_jobs, 'format_description_summary', AsyncMock(return_value='summary'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_webdbs', AsyncMock(return_value='info from webdbs'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_year', AsyncMock(return_value='year'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_status', AsyncMock(return_value='status'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_countries', AsyncMock(return_value='countries'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_runtime', AsyncMock(return_value='runtime'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_directors', AsyncMock(return_value=None))
    mocker.patch.object(bb_tracker_jobs, 'format_description_creators', AsyncMock(return_value='creators'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_cast', AsyncMock(return_value='cast'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_series_screenshots', AsyncMock(return_value='series screenshots'))
    mocker.patch.object(bb_tracker_jobs, 'format_description_series_mediainfo', AsyncMock(return_value='series mediainfo'))
    description = await bb_tracker_jobs.get_description()
    assert description == (
        'summary'
        '[quote]'
        'info from webdbs\n'
        'year\n'
        'status\n'
        'countries\n'
        'runtime\n'
        'creators\n'
        'cast'
        '[/quote]'
        'series screenshots'
        'series mediainfo'
    ) + bb_tracker_jobs.promotion


@pytest.mark.parametrize(
    argnames='summary, episode_summary, is_episode_release, season, episode, exp_summary',
    argvalues=(
        ('', '', False, None, None, None),
        ('', 'Episode summary', True, '1', '2', None),
        ('A true story.', '', False, None, None, '[quote]A true story.[/quote]'),
        ('A true story.', 'Episode summary', True, '1', '2', '[quote]A true story.\n\nEpisode summary[/quote]'),
        ('A true story.', '', True, '1', '2', '[quote]A true story.[/quote]'),
        ('A true story.', 'Episode summary', True, '1', None, '[quote]A true story.[/quote]'),
        ('A true story.', 'Episode summary', True, None, '2', '[quote]A true story.[/quote]'),
        ('A true story.', 'Episode summary', False, '1', '2', '[quote]A true story.[/quote]'),
    ),
)
@pytest.mark.asyncio
async def test_format_description_summary(summary, episode_summary, exp_summary,
                                          is_episode_release, season, episode, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(return_value=summary))
    mocker.patch.object(bb_tracker_jobs, 'format_description_episode_summary', AsyncMock(return_value=episode_summary))
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=is_episode_release))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value=season))
    mocker.patch.object(type(bb_tracker_jobs), 'episode', PropertyMock(return_value=episode))
    summary = await bb_tracker_jobs.format_description_summary()
    assert summary == exp_summary
    assert bb_tracker_jobs.try_webdbs.call_args_list == [
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'summary'),
    ]
    if summary and is_episode_release and season and episode:
        assert bb_tracker_jobs.format_description_episode_summary.call_args_list == [call()]
    else:
        assert bb_tracker_jobs.format_description_episode_summary.call_args_list == []


@pytest.mark.parametrize(
    argnames='tvmaze_id, episode',
    argvalues=(
        (None, {}),
        ('mock tvmaze id',
         {'url': 'http://mock.episode.url', 'title': 'Episode Title', 'season': 10, 'episode': 4,
          'date': '2000-01-02',
          'summary': 'Episode Summary'}),
        ('mock tvmaze id',
         {'url': 'http://mock.episode.url', 'title': 'Episode Title', 'season': 10, 'episode': 4,
          'date': '2000-01-02'}),
        ('mock tvmaze id',
         {'url': 'http://mock.episode.url', 'title': 'Episode Title', 'season': 10, 'episode': 4}),
    ),
)
@pytest.mark.asyncio
async def test_format_description_episode_summary(tvmaze_id, episode, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value=tvmaze_id))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'episode', AsyncMock(return_value=episode))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value=episode.get('season')))
    mocker.patch.object(type(bb_tracker_jobs), 'episode', PropertyMock(return_value=episode.get('episode')))
    summary = await bb_tracker_jobs.format_description_episode_summary()
    if episode:
        exp_summary = (
            f'[url={episode["url"]}]{episode["title"]}[/url]'
            ' - '
            f'Season {episode["season"]}, Episode {episode["episode"]}'
        )
        if episode.get('date'):
            exp_summary += f' - [size=2]{episode["date"]}[/size]'
        if episode.get('summary'):
            exp_summary += f'\n\n[spoiler]\n{episode["summary"]}[/spoiler]'
    else:
        exp_summary = None
    assert summary == exp_summary
    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == [call()]
    if tvmaze_id:
        assert bb_tracker_jobs.tvmaze.episode.call_args_list == [
            call(id=tvmaze_id, season=episode['season'], episode=episode['episode']),
        ]
    else:
        assert bb_tracker_jobs.tvmaze.episode.call_args_list == []

@pytest.mark.asyncio
async def test_format_description_episode_summary_ignores_RequestError(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value='mock tvmaze id'))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'episode', AsyncMock(side_effect=errors.RequestError('nope')))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value='12'))
    mocker.patch.object(type(bb_tracker_jobs), 'episode', PropertyMock(return_value='34'))
    summary = await bb_tracker_jobs.format_description_episode_summary()
    assert summary is None
    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == [call()]
    assert bb_tracker_jobs.tvmaze.episode.call_args_list == [
        call(id='mock tvmaze id', season='12', episode='34'),
    ]


@pytest.mark.parametrize(
    argnames='imdb_id, tvmaze_id, imdb_rating, tvmaze_rating',
    argvalues=(
        (None, None, None, None),
        ('mock imdb id', None, 5, 7),
        (None, 'mock tvmaze id', 5, 7),
        ('mock imdb id', 'mock tvmaze id', 5, 7),
        ('mock imdb id', 'mock tvmaze id', 5, None),
        ('mock imdb id', 'mock tvmaze id', None, 7),
    ),
)
@pytest.mark.asyncio
async def test_format_description_webdbs(tvmaze_id, imdb_id, tvmaze_rating, imdb_rating, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value=tvmaze_id))
    mocker.patch.object(bb_tracker_jobs, 'get_imdb_id', AsyncMock(return_value=imdb_id))
    mocker.patch.object(type(bb_tracker_jobs), 'imdb', PropertyMock(return_value=Mock(
        label='IMDb',
        rating_max=10.0,
        url=AsyncMock(return_value='http://link.to.imdb'),
        rating=AsyncMock(return_value=imdb_rating),
    )))
    mocker.patch.object(type(bb_tracker_jobs), 'tvmaze', PropertyMock(return_value=Mock(
        label='TVmaze',
        rating_max=1000.0,
        url=AsyncMock(return_value='http://link.to.tvmaze'),
        rating=AsyncMock(return_value=tvmaze_rating),
    )))
    star_rating_mock = mocker.patch('upsies.utils.string.star_rating', return_value='***')
    text = await bb_tracker_jobs.format_description_webdbs()

    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == [call()]
    assert bb_tracker_jobs.get_imdb_id.call_args_list == [call()]

    if imdb_id:
        assert bb_tracker_jobs.imdb.url.call_args_list == [call(imdb_id)]
        assert bb_tracker_jobs.imdb.rating.call_args_list == [call(imdb_id)]
        exp_line = '[b]IMDb[/b]: [url=http://link.to.imdb]mock imdb id[/url]'
        if imdb_rating:
            assert call(imdb_rating, max_rating=10.0) in star_rating_mock.call_args_list
            exp_line += f' | {imdb_rating}/10 [color=#ffff00]***[/color]'
        else:
            assert call(imdb_rating, max_rating=10.0) not in star_rating_mock.call_args_list
        assert exp_line in text.split('\n')

    if tvmaze_id:
        assert bb_tracker_jobs.tvmaze.url.call_args_list == [call(tvmaze_id)]
        assert bb_tracker_jobs.tvmaze.rating.call_args_list == [call(tvmaze_id)]
        exp_line = '[b]TVmaze[/b]: [url=http://link.to.tvmaze]mock tvmaze id[/url]'
        if tvmaze_rating:
            assert call(tvmaze_rating, max_rating=1000.0) in star_rating_mock.call_args_list
            exp_line += f' | {tvmaze_rating}/1000 [color=#ffff00]***[/color]'
        else:
            assert call(tvmaze_rating, max_rating=1000.0) not in star_rating_mock.call_args_list
        assert exp_line in text.split('\n')

    if not tvmaze_id and not imdb_id:
        assert text == ''


@pytest.mark.parametrize(
    argnames='imdb_id, year, exp_text',
    argvalues=(
        (None, None, None),
        ('mock imdb id', None, None),
        ('mock imdb id', '2000', '[b]Year[/b]: 2000'),
    ),
)
@pytest.mark.asyncio
async def test_format_description_year_for_movie(imdb_id, year, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    mocker.patch.object(bb_tracker_jobs, 'get_imdb_id', AsyncMock(return_value=imdb_id))
    mocker.patch.object(bb_tracker_jobs.imdb, 'year', AsyncMock(return_value=year))
    text = await bb_tracker_jobs.format_description_year()
    assert text == exp_text
    assert bb_tracker_jobs.get_imdb_id.call_args_list == [call()]
    if imdb_id:
        assert bb_tracker_jobs.imdb.year.call_args_list == [call(imdb_id)]
    else:
        assert bb_tracker_jobs.imdb.year.call_args_list == []

@pytest.mark.asyncio
async def test_format_description_year_for_movie_ignores_RequestError_from_get_imdb_id(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    mocker.patch.object(bb_tracker_jobs, 'get_imdb_id', AsyncMock(side_effect=errors.RequestError('nope')))
    mocker.patch.object(bb_tracker_jobs.imdb, 'year', AsyncMock(return_value='2030'))
    text = await bb_tracker_jobs.format_description_year()
    assert text is None
    assert bb_tracker_jobs.get_imdb_id.call_args_list == [call()]
    assert bb_tracker_jobs.imdb.year.call_args_list == []

@pytest.mark.asyncio
async def test_format_description_year_for_movie_ignores_RequestError_from_year_getter(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    mocker.patch.object(bb_tracker_jobs, 'get_imdb_id', AsyncMock(return_value='mock imdb id'))
    mocker.patch.object(bb_tracker_jobs.imdb, 'year', AsyncMock(side_effect=errors.RequestError('nope')))
    text = await bb_tracker_jobs.format_description_year()
    assert text is None
    assert bb_tracker_jobs.get_imdb_id.call_args_list == [call()]
    assert bb_tracker_jobs.imdb.year.call_args_list == [call('mock imdb id')]

@pytest.mark.parametrize(
    argnames='tvmaze_id, season, episode, year, exp_text',
    argvalues=(
        (None, None, {}, None, None),
        ('mock tvmaze id', None, {}, None, None),
        ('mock tvmaze id', '5', {}, None, None),
        ('mock tvmaze id', None, {}, '2035', '[b]Year[/b]: 2035'),
        ('mock tvmaze id', '5', {}, '2035', '[b]Year[/b]: 2035'),
        ('mock tvmaze id', '5', {'date': '2034-10-29'}, '2034', '[b]Year[/b]: 2034'),
    ),
)
@pytest.mark.asyncio
async def test_format_description_year_for_series(tvmaze_id, season, episode, year, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value=season))
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value=tvmaze_id))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'year', AsyncMock(return_value=year))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'episode', AsyncMock(return_value=episode))
    text = await bb_tracker_jobs.format_description_year()
    assert text == exp_text
    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == [call()]
    if tvmaze_id:
        if season:
            assert bb_tracker_jobs.tvmaze.episode.call_args_list == [call(id=tvmaze_id, season=season, episode=1)]
        else:
            assert bb_tracker_jobs.tvmaze.year.call_args_list == [call(tvmaze_id)]
    else:
        assert bb_tracker_jobs.tvmaze.year.call_args_list == []
        assert bb_tracker_jobs.tvmaze.episode.call_args_list == []

@pytest.mark.asyncio
async def test_format_description_year_for_series_ignores_RequestError_from_get_tvmaze_id(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value='3'))
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(side_effect=errors.RequestError('nope')))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'year', AsyncMock(return_value='2023'))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'episode', AsyncMock(return_value={'date': '2009-05-01'}))
    text = await bb_tracker_jobs.format_description_year()
    assert text is None

@pytest.mark.asyncio
async def test_format_description_year_for_series_ignores_RequestError_from_year_getter(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value=None))
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value='mock tvmaze id'))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'year', AsyncMock(side_effect=errors.RequestError('nope')))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'episode', AsyncMock(return_value=None))
    text = await bb_tracker_jobs.format_description_year()
    assert text is None

@pytest.mark.asyncio
async def test_format_description_year_for_series_ignores_RequestError_from_episode_getter(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'season', PropertyMock(return_value='3'))
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value='mock tvmaze id'))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'year', AsyncMock(return_value='2023'))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'episode', AsyncMock(side_effect=errors.RequestError('nope')))
    text = await bb_tracker_jobs.format_description_year()
    assert text is None

@pytest.mark.asyncio
async def test_format_description_year_for_exotic_type(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    text = await bb_tracker_jobs.format_description_year()
    assert text is None


@pytest.mark.parametrize(
    argnames='tvmaze_id, status, exp_text',
    argvalues=(
        (None, None, None),
        ('mock tvmaze id', None, None),
        ('mock tvmaze id', 'Running', None),
        ('mock tvmaze id', 'Ended', '[b]Status[/b]: Ended'),
    ),
)
@pytest.mark.asyncio
async def test_format_description_status(tvmaze_id, status, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_tvmaze_id', AsyncMock(return_value=tvmaze_id))
    mocker.patch.object(bb_tracker_jobs.tvmaze, 'status', AsyncMock(return_value=status))
    text = await bb_tracker_jobs.format_description_status()
    assert text == exp_text
    assert bb_tracker_jobs.get_tvmaze_id.call_args_list == [call()]
    if tvmaze_id:
        assert bb_tracker_jobs.tvmaze.status.call_args_list == [call(tvmaze_id)]
    else:
        assert bb_tracker_jobs.tvmaze.status.call_args_list == []


@pytest.mark.parametrize(
    argnames='countries, exp_text',
    argvalues=(
        ((), None),
        (('Foo',), '[b]Country[/b]: Foo'),
        (('Foo', 'Bar'), '[b]Countries[/b]: Foo, Bar'),
    ),
)
@pytest.mark.asyncio
async def test_format_description_countries(countries, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(return_value=countries))
    text = await bb_tracker_jobs.format_description_countries()
    assert text == exp_text
    assert bb_tracker_jobs.try_webdbs.call_args_list == [
        call((bb_tracker_jobs.tvmaze, bb_tracker_jobs.imdb), 'countries'),
    ]


@pytest.mark.asyncio
async def test_format_description_runtime_for_movie(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_season_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'content_path', PropertyMock(return_value='path/to/content'))
    duration_mock = mocker.patch('upsies.utils.video.duration', return_value=123)
    text = await bb_tracker_jobs.format_description_runtime()
    assert text == '[b]Runtime[/b]: 0:02:03'
    assert duration_mock.call_args_list == [call('path/to/content')]

@pytest.mark.asyncio
async def test_format_description_runtime_for_episode(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'is_season_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'content_path', PropertyMock(return_value='path/to/content'))
    duration_mock = mocker.patch('upsies.utils.video.duration', return_value=123)
    text = await bb_tracker_jobs.format_description_runtime()
    assert text == '[b]Runtime[/b]: 0:02:03'
    assert duration_mock.call_args_list == [call('path/to/content')]

@pytest.mark.asyncio
async def test_format_description_runtime_for_season_with_few_episodes(bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_season_release', PropertyMock(return_value=True))
    content_path = tmp_path / 'content'
    content_path.mkdir()
    (content_path / 'episode 1.mkv').write_bytes(b'episode 1 data')
    (content_path / 'episode 2.mkv').write_bytes(b'episode 2 data')
    (content_path / 'episode 3.mkv').write_bytes(b'episode 3 data')
    (content_path / 'content.nfo').write_bytes(b'text')
    mocker.patch.object(type(bb_tracker_jobs), 'content_path', PropertyMock(return_value=str(content_path)))
    duration_mock = mocker.patch('upsies.utils.video.duration', side_effect=(100, 127, 109))
    text = await bb_tracker_jobs.format_description_runtime()
    assert text == '[b]Runtime[/b]: 0:01:52'
    assert duration_mock.call_args_list == [
        call(str(content_path / 'episode 1.mkv')),
        call(str(content_path / 'episode 2.mkv')),
        call(str(content_path / 'episode 3.mkv')),
    ]

@pytest.mark.asyncio
async def test_format_description_runtime_for_season_with_many_episodes(bb_tracker_jobs, mocker, tmp_path):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_season_release', PropertyMock(return_value=True))
    content_path = tmp_path / 'content'
    content_path.mkdir()
    (content_path / 'episode 1.mkv').write_bytes(b'episode 1 data')
    (content_path / 'episode 2.mkv').write_bytes(b'episode 2 data')
    (content_path / 'episode 3.mkv').write_bytes(b'episode 3 data')
    (content_path / 'episode 4.mkv').write_bytes(b'episode 4 data')
    (content_path / 'episode 5.mkv').write_bytes(b'episode 5 data')
    (content_path / 'episode 6.mkv').write_bytes(b'episode 6 data')
    (content_path / 'content.nfo').write_bytes(b'text')
    mocker.patch.object(type(bb_tracker_jobs), 'content_path', PropertyMock(return_value=str(content_path)))
    duration_mock = mocker.patch('upsies.utils.video.duration', side_effect=(100, 127, 109, 90, 99, 102))
    text = await bb_tracker_jobs.format_description_runtime()
    assert text == '[b]Runtime[/b]: 0:01:46'
    assert duration_mock.call_args_list == [
        call(str(content_path / 'episode 2.mkv')),
        call(str(content_path / 'episode 3.mkv')),
        call(str(content_path / 'episode 4.mkv')),
        call(str(content_path / 'episode 5.mkv')),
    ]

@pytest.mark.asyncio
async def test_format_description_runtime_for_unknown_type(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_episode_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_season_release', PropertyMock(return_value=False))
    text = await bb_tracker_jobs.format_description_runtime()
    assert text is None


@pytest.mark.parametrize(
    argnames='directors, exp_text',
    argvalues=(
        ((), None),
        (('Ridley Lynch',), '[b]Director[/b]: Ridley Lynch'),
        (('Ridley Lynch', 'Jackson Tarkovsky'), '[b]Directors[/b]: Ridley Lynch, Jackson Tarkovsky'),
        ((Mock(__str__=Mock(return_value='Ridley Lynch'), url='http://url/to/Ridley_Lynch'),
          Mock(__str__=Mock(return_value='Jackson Tarkovsky'), url='http://url/to/Jackson_Tarkovsky')),
         ('[b]Directors[/b]: [url=http://url/to/Ridley_Lynch]Ridley Lynch[/url], '
          '[url=http://url/to/Jackson_Tarkovsky]Jackson Tarkovsky[/url]')),
    ),
)
@pytest.mark.asyncio
async def test_format_description_directors(directors, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(return_value=directors))
    text = await bb_tracker_jobs.format_description_directors()
    assert text == exp_text


@pytest.mark.parametrize(
    argnames='creators, exp_text',
    argvalues=(
        ((), None),
        (('Joss Harmon',), '[b]Creator[/b]: Joss Harmon'),
        (('Joss Harmon', 'Mitch Nolan'), '[b]Creators[/b]: Joss Harmon, Mitch Nolan'),
        ((Mock(__str__=Mock(return_value='Joss Harmon'), url='http://url/to/Joss_Harmon'),
          Mock(__str__=Mock(return_value='Mitch Nolan'), url='http://url/to/Mitch_Nolan')),
         ('[b]Creators[/b]: [url=http://url/to/Joss_Harmon]Joss Harmon[/url], '
          '[url=http://url/to/Mitch_Nolan]Mitch Nolan[/url]')),
    ),
)
@pytest.mark.asyncio
async def test_format_description_creators(creators, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(return_value=creators))
    text = await bb_tracker_jobs.format_description_creators()
    assert text == exp_text


@pytest.mark.parametrize(
    argnames='actors, exp_text',
    argvalues=(
        ((), None),
        (('Wayne Spencer',), '[b]Cast[/b]: Wayne Spencer'),
        (('Wayne Spencer', 'Rufus Weaver'), '[b]Cast[/b]: Wayne Spencer, Rufus Weaver'),
        ((Mock(__str__=Mock(return_value='Wayne Spencer'), url='http://url/to/Wayne_Spencer'),
          Mock(__str__=Mock(return_value='Rufus Weaver'), url='http://url/to/Rufus_Weaver')),
         ('[b]Cast[/b]: [url=http://url/to/Wayne_Spencer]Wayne Spencer[/url], '
          '[url=http://url/to/Rufus_Weaver]Rufus Weaver[/url]')),
    ),
)
@pytest.mark.asyncio
async def test_format_description_cast(actors, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'try_webdbs', AsyncMock(return_value=actors))
    text = await bb_tracker_jobs.format_description_cast()
    assert text == exp_text


@pytest.mark.parametrize(
    argnames='screenshot_urls, exp_text',
    argvalues=(
        ((), None),
        (('http://screenshot1.url',),
         ('[quote]\n[align=center]'
          '[img=http://screenshot1.url]'
          '[/align]\n[/quote]')),
        (('http://screenshot1.url', 'http://screenshot2.url'),
         ('[quote]\n[align=center]'
          '[img=http://screenshot1.url]\n\n'
          '[img=http://screenshot2.url]'
          '[/align]\n[/quote]')),
    ),
)
@pytest.mark.asyncio
async def test_format_description_series_screenshots(screenshot_urls, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.upload_screenshots_job, 'wait', AsyncMock())
    mocker.patch.object(bb_tracker_jobs, 'get_job_output', return_value=screenshot_urls)
    text = await bb_tracker_jobs.format_description_series_screenshots()
    assert text == exp_text
    assert bb_tracker_jobs.upload_screenshots_job.wait.call_args_list == [call()]
    assert bb_tracker_jobs.get_job_output.call_args_list == [call(bb_tracker_jobs.upload_screenshots_job)]


@pytest.mark.parametrize(
    argnames='mediainfo, exp_text',
    argvalues=(
        (None, None),
        ('', None),
        ('mock mediainfo', '[mediainfo]mock mediainfo[/mediainfo]\n'),
    ),
)
@pytest.mark.asyncio
async def test_format_description_series_mediainfo(mediainfo, exp_text, bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs.mediainfo_job, 'wait', AsyncMock())
    mocker.patch.object(bb_tracker_jobs, 'get_job_output', return_value=mediainfo)
    text = await bb_tracker_jobs.format_description_series_mediainfo()
    assert text == exp_text
    assert bb_tracker_jobs.mediainfo_job.wait.call_args_list == [call()]
    assert bb_tracker_jobs.get_job_output.call_args_list == [call(bb_tracker_jobs.mediainfo_job, slice=0)]


@pytest.mark.parametrize(
    argnames='monojob_attributes, parent_ok, exp_ok',
    argvalues=(
        ((), 'parent value', 'parent value'),
        (('foo',), 'parent value', False),
    ),
)
@pytest.mark.asyncio
async def test_submission_ok(monojob_attributes, parent_ok, exp_ok, bb_tracker_jobs, mocker):
    parent_submission_ok = mocker.patch('upsies.trackers.base.TrackerJobsBase.submission_ok', new_callable=PropertyMock)
    parent_submission_ok.return_value = parent_ok
    mocker.patch.object(type(bb_tracker_jobs), 'monojob_attributes', PropertyMock(return_value=monojob_attributes))
    ok = bb_tracker_jobs.submission_ok
    assert ok == exp_ok


@pytest.mark.asyncio
async def test_torrent_filepath(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_job_output', return_value='path/to/torrent')
    assert bb_tracker_jobs.torrent_filepath == 'path/to/torrent'
    assert bb_tracker_jobs.get_job_output.call_args_list == [
        call(bb_tracker_jobs.create_torrent_job, slice=0),
    ]


@pytest.mark.parametrize('is_scene_release', (True, False))
@pytest.mark.asyncio
async def test_post_data_for_movie(is_scene_release, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'post_data_screenshot_urls', PropertyMock(
        return_value={'screenshot1': 'http://foo', 'screenshot2': 'http://bar'}))

    def mock_get_job_output(job, slice):
        if job is bb_tracker_jobs.movie_title_job:
            assert slice == 0 ; return 'title value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_year_job:
            assert slice == 0 ; return 'year value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_release_info_job:
            assert slice == 0 ; return 'release_info value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_tags_job:
            assert slice == 0 ; return 'tags value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_description_job:
            assert slice == 0 ; return 'description value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.mediainfo_job:
            assert slice == 0 ; return 'mediainfo value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_poster_job:
            assert slice == 0 ; return 'poster value'  # noqa: E702 multiple statements on one line
        raise AssertionError(f'Job was not supposed to get involved: {job!r}')

    def mock_get_job_attribute(job, attr):
        if job is bb_tracker_jobs.movie_source_job:
            assert attr == 'choice' ; return 'source value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_video_codec_job:
            assert attr == 'choice' ; return 'video_codec value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_audio_codec_job:
            assert attr == 'choice' ; return 'audio_codec value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_container_job:
            assert attr == 'choice' ; return 'container value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.movie_resolution_job:
            assert attr == 'choice' ; return 'resolution value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.scene_check_job:
            assert attr == 'is_scene_release'
            return '1' if is_scene_release else None
        raise AssertionError(f'Job was not supposed to get involved: {job!r}')

    mocker.patch.object(bb_tracker_jobs, 'get_job_output', mock_get_job_output)
    mocker.patch.object(bb_tracker_jobs, 'get_job_attribute', mock_get_job_attribute)

    exp_post_data = {
        'submit': 'true',
        'type': 'Movies',
        'title': 'title value',
        'year': 'year value',
        'source': 'source value',
        'videoformat': 'video_codec value',
        'audioformat': 'audio_codec value',
        'container': 'container value',
        'resolution': 'resolution value',
        'remaster_title': 'release_info value',
        'tags': 'tags value',
        'desc': 'description value',
        'release_desc': 'mediainfo value',
        'image': 'poster value',
        'screenshot1': 'http://foo',
        'screenshot2': 'http://bar',
    }
    if is_scene_release:
        exp_post_data['scene'] = '1'
    post_data = bb_tracker_jobs.post_data
    assert post_data == exp_post_data

@pytest.mark.parametrize('is_scene_release', (True, False))
@pytest.mark.asyncio
async def test_post_data_for_series(is_scene_release, bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=True))
    mocker.patch.object(type(bb_tracker_jobs), 'post_data_screenshot_urls', PropertyMock(
        return_value={'screenshot1': 'http://foo', 'screenshot2': 'http://bar'}))

    def mock_get_job_output(job, slice):
        if job is bb_tracker_jobs.series_title_job:
            assert slice == 0 ; return 'title value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.series_tags_job:
            assert slice == 0 ; return 'tags value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.series_description_job:
            assert slice == 0 ; return 'description value'  # noqa: E702 multiple statements on one line
        if job is bb_tracker_jobs.series_poster_job:
            assert slice == 0 ; return 'poster value'  # noqa: E702 multiple statements on one line
        raise AssertionError(f'Job was not supposed to get involved: {job!r}')

    def mock_get_job_attribute(job, attr):
        if job is bb_tracker_jobs.scene_check_job:
            assert attr == 'is_scene_release'
            return '1' if is_scene_release else None
        raise AssertionError(f'Job was not supposed to get involved: {job!r}')

    mocker.patch.object(bb_tracker_jobs, 'get_job_output', mock_get_job_output)
    mocker.patch.object(bb_tracker_jobs, 'get_job_attribute', mock_get_job_attribute)

    exp_post_data = {
        'submit': 'true',
        'type': 'TV',
        'title': 'title value',
        'tags': 'tags value',
        'desc': 'description value',
        'image': 'poster value',
    }
    if is_scene_release:
        exp_post_data['scene'] = '1'
    post_data = bb_tracker_jobs.post_data
    assert post_data == exp_post_data

@pytest.mark.asyncio
async def test_post_data_for_unknown_release_type(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'is_movie_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'is_series_release', PropertyMock(return_value=False))
    mocker.patch.object(type(bb_tracker_jobs), 'release_type', PropertyMock(return_value='foo'))
    with pytest.raises(RuntimeError, match="Weird release type: 'foo'"):
        bb_tracker_jobs.post_data


@pytest.mark.asyncio
async def test_post_data_screenshot_urls(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'get_job_output', return_value=('http://foo', 'http://bar'))
    assert bb_tracker_jobs.post_data_screenshot_urls == {
        'screenshot1': 'http://foo',
        'screenshot2': 'http://bar',
    }
    assert bb_tracker_jobs.get_job_output.call_args_list == [
        call(bb_tracker_jobs.upload_screenshots_job),
    ]
