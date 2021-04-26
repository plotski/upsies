import re
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import __homepage__, __project_name__, __version__, utils
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
    mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                        PropertyMock(return_value=Mock(choice=utils.types.ReleaseType.movie)))
    assert bb_tracker_jobs.is_movie_release is True
    for value in (None, utils.types.ReleaseType.series, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                            PropertyMock(return_value=Mock(choice=value)))
        assert bb_tracker_jobs.is_movie_release is False

def test_is_season_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                        PropertyMock(return_value=Mock(choice=utils.types.ReleaseType.season)))
    assert bb_tracker_jobs.is_season_release is True
    for value in (None, utils.types.ReleaseType.movie, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                            PropertyMock(return_value=Mock(choice=value)))
        assert bb_tracker_jobs.is_season_release is False

def test_is_episode_release(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                        PropertyMock(return_value=Mock(choice=utils.types.ReleaseType.episode)))
    assert bb_tracker_jobs.is_episode_release is True
    for value in (None, utils.types.ReleaseType.movie, utils.types.ReleaseType.season):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                            PropertyMock(return_value=Mock(choice=value)))
        assert bb_tracker_jobs.is_episode_release is False

def test_is_series_release(bb_tracker_jobs, mocker):
    for value in (utils.types.ReleaseType.season, utils.types.ReleaseType.episode):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                            PropertyMock(return_value=Mock(choice=value)))
        assert bb_tracker_jobs.is_series_release is True
    for value in (None, utils.types.ReleaseType.movie):
        mocker.patch.object(type(bb_tracker_jobs), 'release_type_job',
                            PropertyMock(return_value=Mock(choice=value)))
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
        call('scene_check_job', ReleaseType.movie, ReleaseType.season, ReleaseType.episode),
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
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob')
    assert bb_tracker_jobs.imdb_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [call(
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
        'output', bb_tracker_jobs.movie_title_imdb_id_handler,
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

def test_movie_title_imdb_id_handler(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_name',
                        PropertyMock(title_with_aka='The Title AKA Teh Tilte'))
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_movie_title', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_title_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_title_job, 'add_task', Mock())

    bb_tracker_jobs.movie_title_imdb_id_handler('tt0123')

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
        'output', bb_tracker_jobs.movie_year_imdb_id_handler,
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

def test_movie_year_imdb_id_handler(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_name', PropertyMock(year='2014'))
    mocker.patch.object(bb_tracker_jobs.imdb, 'year', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_year_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_year_job, 'add_task', Mock())

    bb_tracker_jobs.movie_year_imdb_id_handler('tt0123')

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
    mocker.patch.object(bb_tracker_jobs, 'make_choices_job')
    assert bb_tracker_jobs.movie_resolution_job is bb_tracker_jobs.make_choices_job.return_value
    assert bb_tracker_jobs.make_choices_job.call_args_list == [call(
        name='movie-resolution',
        label='Resolution',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetect_value=bb_tracker_jobs.release_info_resolution,
        autofinish=True,
        options=(
            ('4320p', '2160p', re.compile(r'4320p')),
            ('2160p', '2160p', re.compile(r'2160p')),
            ('1080p', '1080p', re.compile(r'1080p')),
            ('1080i', '1080i', re.compile(r'1080i')),
            ('720p', '720p', re.compile(r'720p')),
            ('720i', '720i', re.compile(r'720i')),
            ('576p', '480p', re.compile(r'576p')),
            ('576i', '480i', re.compile(r'576i')),
            ('480p', '480p', re.compile(r'480p')),
            ('480i', '480i', re.compile(r'480i')),
            ('SD', 'SD', re.compile(r'SD')),
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_resolution_job', ReleaseType.movie)]


def test_movie_source_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choices_job')
    assert bb_tracker_jobs.movie_source_job is bb_tracker_jobs.make_choices_job.return_value
    assert bb_tracker_jobs.make_choices_job.call_args_list == [call(
        name='movie-source',
        label='Source',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetect_value=bb_tracker_jobs.release_name.source,
        autofinish=True,
        options=(
            ('BluRay', 'BluRay', re.compile('^BluRay')),  # BluRay or BluRay Remux
            # ('BluRay 3D', ' ', re.compile('^ $')),
            # ('BluRay RC', ' ', re.compile('^ $')),
            # ('CAM', ' ', re.compile('^ $')),
            ('DVD5', 'DVD5', re.compile('^DVD5$')),
            ('DVD9', 'DVD9', re.compile('^DVD9$')),
            ('DVDRip', 'DVDRip', re.compile('^DVDRip$')),
            # ('DVDSCR', ' ', re.compile('^ $')),
            ('HD-DVD', 'HD-DVD', re.compile('^HD-DVD$')),
            # ('HDRip', ' ', re.compile('^ $')),
            ('HDTV', 'HDTV', re.compile('^HDTV$')),
            # ('PDTV', ' ', re.compile('^ $')),
            # ('R5', ' ', re.compile('^ $')),
            # ('SDTV', ' ', re.compile('^ $')),
            # ('TC', ' ', re.compile('^ $')),
            # ('TeleSync', ' ', re.compile('^ $')),
            # ('VHSRip', ' ', re.compile('^ $')),
            # ('VODRip', ' ', re.compile('^ $')),
            ('WEB-DL', 'WEB-DL', re.compile('^WEB-DL$')),
            ('WEBRip', 'WebRip', re.compile('^WEBRip$')),
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_source_job', ReleaseType.movie)]


def test_movie_audio_codec_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choices_job')
    assert bb_tracker_jobs.movie_audio_codec_job is bb_tracker_jobs.make_choices_job.return_value
    assert bb_tracker_jobs.make_choices_job.call_args_list == [call(
        name='movie-audio-codec',
        label='Audio Codec',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetect_value=bb_tracker_jobs.release_info_audio_format,
        autofinish=True,
        options=(
            ('AAC', 'AAC', re.compile(r'^AAC$')),
            ('AC-3', 'AC-3', re.compile(r'^(?:E-|)AC-3$')),   # AC-3, E-AC-3
            ('DTS', 'DTS', re.compile(r'^DTS(?!-HD)')),       # DTS, DTS-ES
            ('DTS-HD', 'DTS-HD', re.compile(r'^DTS-HD\b')),   # DTS-HD, DTS-HD MA
            ('DTS:X', 'DTS:X', re.compile(r'^DTS:X$')),
            ('Dolby Atmos', 'Atmos', re.compile(r'Atmos')),
            ('FLAC', 'FLAC', re.compile(r'^FLAC$')),
            ('MP3', 'MP3', re.compile(r'^MP3$')),
            # ('PCM', 'PCM', re.compile(r'^$')),
            ('TrueHD', 'True-HD', re.compile(r'TrueHD')),
            ('Vorbis', 'Vorbis', re.compile(r'^Vorbis$')),
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_audio_codec_job', ReleaseType.movie)]


def test_movie_video_codec_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choices_job')
    assert bb_tracker_jobs.movie_video_codec_job is bb_tracker_jobs.make_choices_job.return_value
    assert bb_tracker_jobs.make_choices_job.call_args_list == [call(
        name='movie-video-codec',
        label='Video Codec',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetect_value=bb_tracker_jobs.release_name.video_format,
        autofinish=True,
        options=(
            ('x264', 'x264', re.compile(r'x264')),
            ('x265', 'x265', re.compile(r'x265')),
            ('XviD', 'XVid', re.compile(r'(?i:XviD)')),
            # ('MPEG-2', 'MPEG-2', re.compile(r'')),
            # ('WMV-HD', 'WMV-HD', re.compile(r'')),
            # ('DivX', 'DivX', re.compile(r'')),
            ('H.264', 'H.264', re.compile(r'H.264')),
            ('H.265', 'H.265', re.compile(r'H.265')),
            # ('VC-1', 'VC-1', re.compile(r'')),
        ),
    )]
    assert bb_tracker_jobs.make_job_condition.call_args_list == [call('movie_video_codec_job', ReleaseType.movie)]


def test_movie_container_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'make_choices_job')
    assert bb_tracker_jobs.movie_container_job is bb_tracker_jobs.make_choices_job.return_value
    assert bb_tracker_jobs.make_choices_job.call_args_list == [call(
        name='movie-container',
        label='Container',
        condition=bb_tracker_jobs.make_job_condition.return_value,
        autodetect_value=utils.fs.file_extension(utils.video.first_video(bb_tracker_jobs.content_path)),
        autofinish=True,
        options=(
            ('AVI', 'AVI', re.compile(r'(?i:AVI)')),
            ('MKV', 'MKV', re.compile('(?i:MKV)')),
            ('MP4', 'MP4', re.compile(r'(?i:MP4)')),
            ('TS', 'TS', re.compile(r'(?i:TS)')),
            ('VOB', 'VOB', re.compile(r'(?i:VOB)')),
            ('WMV', 'WMV', re.compile(r'(?i:WMV)')),
            ('m2ts', 'm2ts', re.compile(r'(?i:m2ts)')),
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
    mocker.patch.object(bb_tracker_jobs, 'get_poster_url', AsyncMock(return_value='http://foo'))
    poster_job = Mock()
    poster_url = await bb_tracker_jobs.movie_get_poster_url(poster_job)
    assert poster_url == 'http://foo'
    assert bb_tracker_jobs.get_poster_url.call_args_list == [
        call(poster_job, bb_tracker_jobs.get_movie_poster_url),
    ]


def test_movie_tags_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'imdb_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.movie_tags_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.imdb_job.signal.register.call_args_list == [call(
        'output', bb_tracker_jobs.movie_tags_imdb_id_handler,
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

def test_movie_tags_imdb_id_handler(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_tags', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_tags_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_tags_job, 'add_task', Mock())

    bb_tracker_jobs.movie_tags_imdb_id_handler('tt0123')

    assert bb_tracker_jobs.get_tags.call_args_list == [call(bb_tracker_jobs.imdb, 'tt0123')]
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
        'output', bb_tracker_jobs.movie_description_imdb_id_handler,
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

def test_movie_description_imdb_id_handler(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_description', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_description_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.movie_description_job, 'add_task', Mock())

    bb_tracker_jobs.movie_description_imdb_id_handler('tt0123')

    assert bb_tracker_jobs.get_description.call_args_list == [call(bb_tracker_jobs.imdb, 'tt0123')]
    assert bb_tracker_jobs.movie_description_job.fetch_text.call_args_list == [call(
        coro=bb_tracker_jobs.get_description.return_value,
        finish_on_success=True,
    )]
    assert bb_tracker_jobs.movie_description_job.add_task.call_args_list == [call(
        bb_tracker_jobs.movie_description_job.fetch_text.return_value
    )]


def test_tvmaze_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    SearchWebDbJob_mock = mocker.patch('upsies.jobs.webdb.SearchWebDbJob')
    assert bb_tracker_jobs.tvmaze_job is SearchWebDbJob_mock.return_value
    assert SearchWebDbJob_mock.call_args_list == [call(
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
        'output', bb_tracker_jobs.series_title_tvmaze_id_handler,
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

def test_series_title_tvmaze_id_handler(bb_tracker_jobs, mocker):
    mocker.patch.object(type(bb_tracker_jobs), 'release_name',
                        PropertyMock(title_with_aka_and_year='The Title S01 [foo / bar / baz]'))
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_series_title_and_release_info', Mock())
    mocker.patch.object(bb_tracker_jobs.series_title_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.series_title_job, 'add_task', Mock())

    bb_tracker_jobs.series_title_tvmaze_id_handler('tt0123')

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
    mocker.patch.object(bb_tracker_jobs, 'get_poster_url', AsyncMock(return_value='http://foo'))
    poster_job = Mock()
    poster_url = await bb_tracker_jobs.series_get_poster_url(poster_job)
    assert poster_url == 'http://foo'
    assert bb_tracker_jobs.get_poster_url.call_args_list == [
        call(poster_job, bb_tracker_jobs.get_series_poster_url),
    ]


def test_series_tags_job(bb_tracker_jobs, mocker):
    mocker.patch.object(bb_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bb_tracker_jobs, 'tvmaze_job')
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')
    assert bb_tracker_jobs.series_tags_job is TextFieldJob_mock.return_value
    assert bb_tracker_jobs.tvmaze_job.signal.register.call_args_list == [call(
        'output', bb_tracker_jobs.series_tags_tvmaze_id_handler,
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

def test_series_tags_tvmaze_id_handler(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_tags', Mock())
    mocker.patch.object(bb_tracker_jobs.series_tags_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.series_tags_job, 'add_task', Mock())

    bb_tracker_jobs.series_tags_tvmaze_id_handler('tt0123')

    assert bb_tracker_jobs.get_tags.call_args_list == [call(bb_tracker_jobs.tvmaze, 'tt0123')]
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
        'output', bb_tracker_jobs.series_description_tvmaze_id_handler,
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

def test_series_description_tvmaze_id_handler(bb_tracker_jobs, mocker):
    mocker.patch('upsies.trackers.bb.BbTrackerJobs.get_description', Mock())
    mocker.patch.object(bb_tracker_jobs.series_description_job, 'fetch_text', Mock())
    mocker.patch.object(bb_tracker_jobs.series_description_job, 'add_task', Mock())

    bb_tracker_jobs.series_description_tvmaze_id_handler('tt0123')

    assert bb_tracker_jobs.get_description.call_args_list == [call(bb_tracker_jobs.tvmaze, 'tt0123')]
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
        ('BluRay', 'BluRay'),
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
