import os
import re
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import __homepage__, __project_name__, utils
from upsies.trackers import bhd


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()


@pytest.fixture
def tracker():
    tracker = Mock()
    tracker.name = 'bhd'
    return tracker


@pytest.fixture
def imghost():
    class MockImageHost(utils.imghosts.base.ImageHostBase):
        name = 'mock image host'
        default_config = {}

        async def _upload_image(self, path):
            pass

    return MockImageHost()


@pytest.fixture
def btclient():
    class MockClientApi(utils.btclients.base.ClientApiBase):
        name = 'mock bittorrent client'
        default_config = {}

        async def add_torrent(self, torrent_path, download_path=None):
            pass

    return MockClientApi()


@pytest.fixture
def bhd_tracker_jobs(imghost, btclient, tracker, tmp_path, mocker):
    content_path = tmp_path / 'Foo 2000 1080p BluRay x264-ASDF'

    bhd_tracker_jobs = bhd.BhdTrackerJobs(
        content_path=str(content_path),
        tracker=tracker,
        image_host=imghost,
        bittorrent_client=btclient,
        torrent_destination=str(tmp_path / 'destination'),
        common_job_args={
            'home_directory': str(tmp_path / 'home_directory'),
            'ignore_cache': True,
        },
        options=None,
    )

    return bhd_tracker_jobs


@pytest.fixture
def mock_job_attributes(mocker):
    def mock_job_attributes(bhd_tracker_jobs):
        job_attrs = (
            # Background jobs
            'create_torrent_job',
            'mediainfo_job',
            'screenshots_job',
            'upload_screenshots_job',

            # Interactive jobs
            'imdb_job',
            'tmdb_job',
            'release_name_job',
            'category_job',
            'type_job',
            'source_job',
            'description_job',
            'scene_check_job',
            'tags_job',
        )
        for job_attr in job_attrs:
            mocker.patch.object(type(bhd_tracker_jobs), job_attr, PropertyMock(return_value=Mock(attr=job_attr)))

    return mock_job_attributes


def test_release_name_translation():
    assert bhd.BhdTrackerJobs.release_name_translation == {
        'audio_format': {
            re.compile(r'^AC-3'): r'DD',
            re.compile(r'^E-AC-3'): r'DDP',
        },
    }


def test_jobs_before_upload_items(bhd_tracker_jobs, mock_job_attributes, mocker):
    mock_job_attributes(bhd_tracker_jobs)

    print(bhd_tracker_jobs.jobs_before_upload)
    assert tuple(job.attr for job in bhd_tracker_jobs.jobs_before_upload) == (
        # Background jobs
        'create_torrent_job',
        'mediainfo_job',
        'screenshots_job',
        'upload_screenshots_job',

        # Interactive jobs
        'imdb_job',
        'tmdb_job',
        'release_name_job',
        'category_job',
        'type_job',
        'source_job',
        'description_job',
        'scene_check_job',
        'tags_job',
    )

def test_jobs_before_upload_sets_conditions_on_base_class_jobs(bhd_tracker_jobs, mock_job_attributes, mocker):
    mock_job_attributes(bhd_tracker_jobs)

    base_class_job_attributes = (
        'imdb_job',
        'tmdb_job',
        'release_name_job',
        'scene_check_job',
        'create_torrent_job',
        'mediainfo_job',
        'screenshots_job',
        'upload_screenshots_job',
        'add_torrent_job',
        'copy_torrent_job',
    )

    make_job_condition_return_values = {
        job_attr: Mock(name=f'{job_attr} mock condition')
        for job_attr in base_class_job_attributes
    }
    mocker.patch.object(type(bhd_tracker_jobs), 'add_torrent_job', PropertyMock(return_value=None))
    mocker.patch.object(bhd_tracker_jobs, 'make_job_condition', Mock(
        side_effect=lambda job_attr: make_job_condition_return_values[job_attr],
    ))

    bhd_tracker_jobs.jobs_before_upload

    for job_attr in base_class_job_attributes:
        job = getattr(bhd_tracker_jobs, job_attr)
        if job is not None:
            assert job.condition is make_job_condition_return_values[job_attr]

    assert bhd_tracker_jobs.make_job_condition.call_args_list == [
        call(job_attr) for job_attr in base_class_job_attributes
        if getattr(bhd_tracker_jobs, job_attr) is not None
    ]


@pytest.mark.parametrize(
    argnames='job_attr, isolated_jobs, exp_return_value',
    argvalues=(
        ('foo', (), True),
        ('foo', ('foo', 'bar'), True),
        ('bar', ('foo', 'bar'), True),
        ('baz', ('foo', 'bar'), False),
    ),
    ids=lambda v: str(v),
)
def test_make_job_condition(job_attr, isolated_jobs, exp_return_value, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'isolated_jobs', PropertyMock(return_value=isolated_jobs))
    condition = bhd_tracker_jobs.make_job_condition(job_attr)
    return_value = condition()
    assert return_value == exp_return_value


@pytest.mark.parametrize(
    argnames='options, exp_isolated_jobs',
    argvalues=(
        ({'only_description': True}, ('description_job', 'screenshots_job', 'upload_screenshots_job')),
        ({'only_title': True}, ('release_name_job', 'imdb_job')),
        ({}, ()),
    ),
)
def test_isolated_jobs(options, exp_isolated_jobs, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'options', PropertyMock(return_value=options))
    assert bhd_tracker_jobs.isolated_jobs == exp_isolated_jobs


def test_imdb_job(bhd_tracker_jobs):
    output_callbacks = bhd_tracker_jobs.imdb_job.signal.signals.get('output', [])
    assert bhd_tracker_jobs.handle_imdb_job_output in output_callbacks


def test_handle_imdb_job_output(bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs.imdb_job.query), 'type', 'mock type')
    assert bhd_tracker_jobs.tmdb_job.query.type != 'mock type'
    bhd_tracker_jobs.handle_imdb_job_output('ignored argument')
    assert bhd_tracker_jobs.tmdb_job.query.type == 'mock type'


def test_category_job(bhd_tracker_jobs, mocker):
    mocker.patch.object(bhd_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bhd_tracker_jobs, 'make_choice_job')

    assert bhd_tracker_jobs.category_job is bhd_tracker_jobs.make_choice_job.return_value
    assert bhd_tracker_jobs.make_choice_job.call_args_list == [call(
        name='bhd-category',
        label='Category',
        condition=bhd_tracker_jobs.make_job_condition.return_value,
        options=(
            {'label': 'Movie', 'value': '1'},
            {'label': 'TV', 'value': '2'},
        ),
    )]
    bhd_tracker_jobs.make_job_condition.call_args_list == [call('category_job')]
    assert bhd_tracker_jobs.autodetect_category in bhd_tracker_jobs.release_name_job.signal.signals['output']


@pytest.mark.parametrize(
    argnames='release_type, exp_focused',
    argvalues=(
        (utils.release.ReleaseType.movie, ('Movie (autodetected)', '1')),
        (utils.release.ReleaseType.series, ('TV (autodetected)', '2')),
        (utils.release.ReleaseType.episode, ('TV (autodetected)', '2')),
        (None, ('Movie', '1')),
    ),
    ids=lambda v: str(v),
)
def test_autodetect_category(release_type, exp_focused, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        type=release_type,
    )))
    bhd_tracker_jobs.autodetect_category('_')
    assert bhd_tracker_jobs.category_job.focused == exp_focused


def test_type_job(bhd_tracker_jobs, mocker):
    mocker.patch.object(bhd_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bhd_tracker_jobs, 'make_choice_job')

    assert bhd_tracker_jobs.type_job is bhd_tracker_jobs.make_choice_job.return_value
    assert bhd_tracker_jobs.make_choice_job.call_args_list == [call(
        name='bhd-type',
        label='Type',
        condition=bhd_tracker_jobs.make_job_condition.return_value,
        options=(
            {'label': 'UHD 100', 'value': 'UHD 100'},
            {'label': 'UHD 66', 'value': 'UHD 66'},
            {'label': 'UHD 50', 'value': 'UHD 50'},
            {'label': 'UHD Remux', 'value': 'UHD Remux'},
            {'label': 'BD 50', 'value': 'BD 50'},
            {'label': 'BD 25', 'value': 'BD 25'},
            {'label': 'BD Remux', 'value': 'BD Remux'},
            {'label': '2160p', 'value': '2160p'},
            {'label': '1080p', 'value': '1080p'},
            {'label': '1080i', 'value': '1080i'},
            {'label': '720p', 'value': '720p'},
            {'label': '576p', 'value': '576p'},
            {'label': '540p', 'value': '540p'},
            {'label': 'DVD 9', 'value': 'DVD 9'},
            {'label': 'DVD 5', 'value': 'DVD 5'},
            {'label': 'DVD Remux', 'value': 'DVD Remux'},
            {'label': '480p', 'value': '480p'},
            {'label': 'Other', 'value': 'Other'},
        ),
    )]
    bhd_tracker_jobs.make_job_condition.call_args_list == [call('type_job')]
    assert bhd_tracker_jobs.autodetect_type in bhd_tracker_jobs.release_name_job.signal.signals['output']


@pytest.mark.parametrize(
    argnames='resolution, source, exp_focused, exp_choice, exp_output',
    argvalues=(
        ('', 'DVD9', ('DVD 9 (autodetected)', 'DVD 9'), 'DVD 9', ('DVD 9 (autodetected)',)),
        ('', 'DVD5', ('DVD 5 (autodetected)', 'DVD 5'), 'DVD 5', ('DVD 5 (autodetected)',)),
        ('', 'DVD Remux', ('DVD Remux (autodetected)', 'DVD Remux'), 'DVD Remux', ('DVD Remux (autodetected)',)),
        ('2160p', '', ('2160p (autodetected)', '2160p'), '2160p', ('2160p (autodetected)',)),
        ('1080p', '', ('1080p (autodetected)', '1080p'), '1080p', ('1080p (autodetected)',)),
        ('1080i', '', ('1080i (autodetected)', '1080i'), '1080i', ('1080i (autodetected)',)),
        ('720p', '', ('720p (autodetected)', '720p'), '720p', ('720p (autodetected)',)),
        ('576p', '', ('576p (autodetected)', '576p'), '576p', ('576p (autodetected)',)),
        ('540p', '', ('540p (autodetected)', '540p'), '540p', ('540p (autodetected)',)),
        ('480p', '', ('480p (autodetected)', '480p'), '480p', ('480p (autodetected)',)),
        ('123p', '', ('Other', 'Other'), None, ()),
    ),
    ids=lambda v: str(v),
)
def test_autodetect_type(resolution, source, exp_focused, exp_choice, exp_output, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        resolution=resolution,
        source=source,
    )))
    bhd_tracker_jobs.autodetect_type('_')
    assert bhd_tracker_jobs.type_job.focused == exp_focused
    assert bhd_tracker_jobs.type_job.choice == exp_choice
    assert bhd_tracker_jobs.type_job.output == exp_output


def test_source_job(bhd_tracker_jobs, mocker):
    mocker.patch.object(bhd_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bhd_tracker_jobs, 'make_choice_job')

    assert bhd_tracker_jobs.source_job is bhd_tracker_jobs.make_choice_job.return_value
    assert bhd_tracker_jobs.make_choice_job.call_args_list == [call(
        name='bhd-source',
        label='Source',
        condition=bhd_tracker_jobs.make_job_condition.return_value,
        options=(
            {'label': 'Blu-ray', 'value': 'Blu-ray'},
            {'label': 'HD-DVD', 'value': 'HD-DVD'},
            {'label': 'WEB', 'value': 'WEB'},
            {'label': 'HDTV', 'value': 'HDTV'},
            {'label': 'DVD', 'value': 'DVD'},
        ),
    )]
    bhd_tracker_jobs.make_job_condition.call_args_list == [call('source_job')]
    assert bhd_tracker_jobs.autodetect_source in bhd_tracker_jobs.release_name_job.signal.signals['output']


@pytest.mark.parametrize(
    argnames='source, exp_focused, exp_choice, exp_output',
    argvalues=(
        ('BluRay', ('Blu-ray (autodetected)', 'Blu-ray'), 'Blu-ray', ('Blu-ray (autodetected)',)),
        ('BluRay Remux', ('Blu-ray (autodetected)', 'Blu-ray'), 'Blu-ray', ('Blu-ray (autodetected)',)),
        ('WEB-DL', ('WEB (autodetected)', 'WEB'), 'WEB', ('WEB (autodetected)',)),
        ('WEBRip', ('WEB (autodetected)', 'WEB'), 'WEB', ('WEB (autodetected)',)),
        ('WEB', ('WEB (autodetected)', 'WEB'), 'WEB', ('WEB (autodetected)',)),
        ('DVD9', ('DVD (autodetected)', 'DVD'), 'DVD', ('DVD (autodetected)',)),
        ('DVD5', ('DVD (autodetected)', 'DVD'), 'DVD', ('DVD (autodetected)',)),
        ('DVD Remux', ('DVD (autodetected)', 'DVD'), 'DVD', ('DVD (autodetected)',)),
        ('Foo', ('Blu-ray', 'Blu-ray'), None, ()),
    ),
    ids=lambda v: str(v),
)
def test_autodetect_source(source, exp_focused, exp_output, exp_choice, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        source=source,
    )))
    bhd_tracker_jobs.autodetect_source('_')
    assert bhd_tracker_jobs.source_job.focused == exp_focused
    assert bhd_tracker_jobs.source_job.choice == exp_choice
    assert bhd_tracker_jobs.source_job.output == exp_output


def test_description_job(bhd_tracker_jobs, mocker):
    mocker.patch.object(bhd_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bhd_tracker_jobs, 'generate_description', Mock())
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')

    assert bhd_tracker_jobs.description_job is TextFieldJob_mock.return_value
    assert TextFieldJob_mock.call_args_list == [call(
        name='bhd-description',
        label='Description',
        condition=bhd_tracker_jobs.make_job_condition.return_value,
        read_only=True,
        **bhd_tracker_jobs.common_job_args,
    )]
    bhd_tracker_jobs.make_job_condition.call_args_list == [call('description_job')]

    assert bhd_tracker_jobs.generate_description.call_args_list == [call()]
    assert TextFieldJob_mock.return_value.fetch_text.call_args_list == [call(
        coro=bhd_tracker_jobs.generate_description.return_value,
        finish_on_success=True,
    )]
    assert TextFieldJob_mock.return_value.add_task.call_args_list == [call(
        TextFieldJob_mock.return_value.fetch_text.return_value
    )]


def test_image_host_config(bhd_tracker_jobs, mocker):
    assert bhd_tracker_jobs.image_host_config == {
        'common': {'thumb_width': 350},
    }


class ImageUrl(str):
    def __new__(cls, *args, thumbnail=True, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        self._thumbnail = thumbnail
        return self

    @property
    def thumbnail_url(self):
        if self._thumbnail:
            return f'thumb_{self}'

@pytest.mark.parametrize(
    argnames='uploaded_images, exp_bbcode',
    argvalues=(
        (
            (ImageUrl('a.png'), ImageUrl('b.png'), ImageUrl('c.png')),
            (
                '[center]\n'
                '[url=a.png][img]thumb_a.png[/img][/url] [url=b.png][img]thumb_b.png[/img][/url]\n'
                '\n'
                '[url=c.png][img]thumb_c.png[/img][/url]\n'
                '[/center]\n'
                '\n'
                f'[right][size=1]Shared with [url={__homepage__}]{__project_name__}[/url][/size][/right]'
            ),
        ),
        (
            (ImageUrl('a.png'), ImageUrl('b.png'), ImageUrl('c.png'), ImageUrl('d.png')),
            (
                '[center]\n'
                '[url=a.png][img]thumb_a.png[/img][/url] [url=b.png][img]thumb_b.png[/img][/url]\n'
                '\n'
                '[url=c.png][img]thumb_c.png[/img][/url] [url=d.png][img]thumb_d.png[/img][/url]\n'
                '[/center]\n'
                '\n'
                f'[right][size=1]Shared with [url={__homepage__}]{__project_name__}[/url][/size][/right]'
            ),
        ),
        (
            (ImageUrl('a.png'), ImageUrl('b.png'), ImageUrl('c.png'), ImageUrl('d.png'), ImageUrl('e.png')),
            (
                '[center]\n'
                '[url=a.png][img]thumb_a.png[/img][/url] [url=b.png][img]thumb_b.png[/img][/url]\n'
                '\n'
                '[url=c.png][img]thumb_c.png[/img][/url] [url=d.png][img]thumb_d.png[/img][/url]\n'
                '\n'
                '[url=e.png][img]thumb_e.png[/img][/url]\n'
                '[/center]\n'
                '\n'
                f'[right][size=1]Shared with [url={__homepage__}]{__project_name__}[/url][/size][/right]'
            ),
        ),
        (
            (ImageUrl('a.png'), ImageUrl('b.png'), ImageUrl('c.png'), ImageUrl('d.png'), ImageUrl('e.png'), ImageUrl('f.png')),
            (
                '[center]\n'
                '[url=a.png][img]thumb_a.png[/img][/url] [url=b.png][img]thumb_b.png[/img][/url]\n'
                '\n'
                '[url=c.png][img]thumb_c.png[/img][/url] [url=d.png][img]thumb_d.png[/img][/url]\n'
                '\n'
                '[url=e.png][img]thumb_e.png[/img][/url] [url=f.png][img]thumb_f.png[/img][/url]\n'
                '[/center]\n'
                '\n'
                f'[right][size=1]Shared with [url={__homepage__}]{__project_name__}[/url][/size][/right]'
            ),
        ),
    ),
)
@pytest.mark.asyncio
async def test_generate_description(uploaded_images, exp_bbcode, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'upload_screenshots_job', PropertyMock(return_value=Mock(
        wait=AsyncMock(),
        uploaded_images=uploaded_images,
    )))

    bbcode = await bhd_tracker_jobs.generate_description()
    assert bhd_tracker_jobs.upload_screenshots_job.wait.call_args_list == [call()]
    assert bbcode == exp_bbcode

@pytest.mark.asyncio
async def test_generate_description_without_thumbnail_url(bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'upload_screenshots_job', PropertyMock(return_value=Mock(
        wait=AsyncMock(),
        uploaded_images=(ImageUrl('a.png'), ImageUrl('b.png', thumbnail=False), ImageUrl('c.png')),
    )))

    with pytest.raises(RuntimeError, match=r'^No thumbnail for b\.png$'):
        await bhd_tracker_jobs.generate_description()


def test_tags_job(bhd_tracker_jobs, mocker):
    mocker.patch.object(bhd_tracker_jobs, 'make_job_condition')
    mocker.patch.object(bhd_tracker_jobs, 'autodetect_tags', Mock())
    TextFieldJob_mock = mocker.patch('upsies.jobs.dialog.TextFieldJob')

    assert bhd_tracker_jobs.tags_job is TextFieldJob_mock.return_value
    assert TextFieldJob_mock.call_args_list == [call(
        name='bhd-tags',
        label='Tags',
        condition=bhd_tracker_jobs.make_job_condition.return_value,
        read_only=True,
        **bhd_tracker_jobs.common_job_args,
    )]
    bhd_tracker_jobs.make_job_condition.call_args_list == [call('tags_job')]

    assert bhd_tracker_jobs.autodetect_tags.call_args_list == [call()]
    assert TextFieldJob_mock.return_value.fetch_text.call_args_list == [call(
        coro=bhd_tracker_jobs.autodetect_tags.return_value,
        finish_on_success=True,
    )]
    assert TextFieldJob_mock.return_value.add_task.call_args_list == [call(
        TextFieldJob_mock.return_value.fetch_text.return_value
    )]


@pytest.mark.parametrize('source, exp_source_tag', (('WEBRip', 'WEBRip'), ('WEB-DL', 'WEBDL'), ('', None)))
@pytest.mark.parametrize('hybrid, exp_hybrid_tag', (('Hybrid', 'Hybrid'), ('', None)))
@pytest.mark.parametrize('has_commentary, exp_commentary_tag', ((True, 'Commentary'), (False, None)))
@pytest.mark.parametrize('has_dual_audio, exp_dual_audio_tag', ((True, 'DualAudio'), (False, None)))
@pytest.mark.parametrize('edition, exp_open_matte_tag', ((['Open Matte'], 'OpenMatte'), ([], None)))
@pytest.mark.parametrize('is_scene_release, exp_scene_tag', ((True, 'Scene'), (False, None)))
@pytest.mark.parametrize('options, exp_personal_tag', (({'personal_rip': True}, 'Personal'), ({'personal_rip': False}, None)))
@pytest.mark.asyncio
async def test_autodetect_tags(options, exp_personal_tag,
                               is_scene_release, exp_scene_tag,
                               edition, exp_open_matte_tag,
                               has_dual_audio, exp_dual_audio_tag,
                               has_commentary, exp_commentary_tag,
                               hybrid, exp_hybrid_tag,
                               source, exp_source_tag,
                               bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        source=' '.join((source, hybrid)),
        edition=edition,
        has_commentary=has_commentary,
        has_dual_audio=has_dual_audio,
    )))
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name_job', AsyncMock())
    mocker.patch.object(type(bhd_tracker_jobs), 'scene_check_job', AsyncMock(
        is_finished=True,
        is_scene_release=is_scene_release,
    ))
    mocker.patch.object(type(bhd_tracker_jobs), 'options', options)

    assert bhd_tracker_jobs.release_name_job.wait.call_args_list == []
    assert bhd_tracker_jobs.scene_check_job.wait.call_args_list == []
    tags = await bhd_tracker_jobs.autodetect_tags()
    assert bhd_tracker_jobs.release_name_job.wait.call_args_list == [call()]
    assert bhd_tracker_jobs.scene_check_job.wait.call_args_list == [call()]

    exp_tags = [
        exp_source_tag,
        exp_hybrid_tag,
        exp_commentary_tag,
        exp_dual_audio_tag,
        exp_open_matte_tag,
        exp_scene_tag,
        exp_personal_tag,
    ]
    assert tags == '\n'.join(
        exp_tag for exp_tag in exp_tags
        if exp_tag is not None
    )


@pytest.mark.parametrize(
    argnames='isolated_jobs, parent_ok, exp_ok',
    argvalues=(
        ((), 'parent value', 'parent value'),
        (('foo',), 'parent value', False),
    ),
)
def test_submission_ok(isolated_jobs, parent_ok, exp_ok, bhd_tracker_jobs, mocker):
    parent_submission_ok = mocker.patch('upsies.trackers.base.TrackerJobsBase.submission_ok', new_callable=PropertyMock)
    parent_submission_ok.return_value = parent_ok
    mocker.patch.object(type(bhd_tracker_jobs), 'isolated_jobs', PropertyMock(return_value=isolated_jobs))
    ok = bhd_tracker_jobs.submission_ok
    assert ok == exp_ok

@pytest.mark.parametrize('draft, exp_live', ((True, '0'), (False, '1'),))
@pytest.mark.parametrize('anonymous, exp_anon', ((True, '1'), (False, '0'),))
def test_post_data(anonymous, exp_anon, draft, exp_live, bhd_tracker_jobs, mock_job_attributes, mocker):
    mock_job_attributes(bhd_tracker_jobs)
    mocker.patch.object(bhd_tracker_jobs, 'get_job_output', side_effect=(
        'mock release name',
        'tt00123456',
        'movie/1234',
        'mock description',
        'Some\nMock\nTags',
    ))
    mocker.patch.object(bhd_tracker_jobs, 'get_job_attribute', side_effect=(
        'mock category',
        'mock type',
        'mock source',
    ))
    mocker.patch.object(type(bhd_tracker_jobs), 'options', PropertyMock(return_value={
        'custom_edition': 'mock custom edition',
        'anonymous': anonymous,
        'draft': draft,
    }))
    mocker.patch.object(type(bhd_tracker_jobs), 'post_data_edition', PropertyMock(return_value='mock edition'))
    mocker.patch.object(type(bhd_tracker_jobs), 'post_data_nfo', PropertyMock(return_value='mock nfo'))
    mocker.patch.object(type(bhd_tracker_jobs), 'post_data_pack', PropertyMock(return_value='mock pack'))
    mocker.patch.object(type(bhd_tracker_jobs), 'post_data_sd', PropertyMock(return_value='mock sd'))
    mocker.patch.object(type(bhd_tracker_jobs), 'post_data_special', PropertyMock(return_value='mock special'))

    assert bhd_tracker_jobs.post_data == {
        'name': 'mock release name',
        'category_id': 'mock category',
        'type': 'mock type',
        'source': 'mock source',
        'imdb_id': 'tt00123456',
        'tmdb_id': '1234',
        'description': 'mock description',
        'edition': 'mock edition',
        'custom_edition': 'mock custom edition',
        'tags': 'Some,Mock,Tags',
        'nfo': 'mock nfo',
        'pack': 'mock pack',
        'sd': 'mock sd',
        'special': 'mock special',
        'anon': exp_anon,
        'live': exp_live,
    }
    assert bhd_tracker_jobs.get_job_output.call_args_list == [
        call(bhd_tracker_jobs.release_name_job, slice=0),
        call(bhd_tracker_jobs.imdb_job, slice=0),
        call(bhd_tracker_jobs.tmdb_job, slice=0),
        call(bhd_tracker_jobs.description_job, slice=0),
        call(bhd_tracker_jobs.tags_job, slice=0),
    ]
    assert bhd_tracker_jobs.get_job_attribute.call_args_list == [
        call(bhd_tracker_jobs.category_job, 'choice'),
        call(bhd_tracker_jobs.type_job, 'choice'),
        call(bhd_tracker_jobs.source_job, 'choice'),
    ]


@pytest.mark.parametrize(
    argnames='edition, exp_edition',
    argvalues=(
        ("Collector's Edition", 'Collector'),
        ("Director's Cut", 'Director'),
        ('Extended Cut', 'Extended'),
        ('Limited', 'Limited'),
        ('Special Edition', 'Special'),
        ('Theatrical Cut', 'Theatrical'),
        ('Uncut', 'Uncut'),
        ('Uncensored', 'Uncut'),
        ('Unrated', 'Unrated'),
        ('Super Duper Custom Cut', None),
        ('', None),
    ),
)
def test_post_data_edition(edition, exp_edition, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        edition=edition,
    )))
    assert bhd_tracker_jobs.post_data_edition == exp_edition


@pytest.mark.parametrize(
    argnames='approved_type, exp_pack',
    argvalues=(
        (utils.types.ReleaseType.movie, '0'),
        (utils.types.ReleaseType.season, '1'),
        (utils.types.ReleaseType.episode, '0'),
    ),
)
def test_post_data_pack(approved_type, exp_pack, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        type=approved_type,
    )))
    assert bhd_tracker_jobs.post_data_pack == exp_pack


@pytest.mark.parametrize(
    argnames='resolution, exp_sd',
    argvalues=(
        ('2160p', '0'),
        ('1080p', '0'),
        ('1080i', '0'),
        ('720p', '0'),
        ('576p', '1'),
        ('540p', '1'),
        ('480p', '1'),
        ('asdf', '0'),
        ('', '0'),
    ),
)
def test_post_data_sd(resolution, exp_sd, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        resolution=resolution,
    )))
    assert bhd_tracker_jobs.post_data_sd == exp_sd


@pytest.mark.parametrize(
    argnames='isdir, nfo_file, nfo_data, nfo_readable, exp_value, exp_errors',
    argvalues=(
        (False, None, None, True, None, []),
        (True, None, None, True, None, []),
        (True, 'foo.nfo', b'x' * (bhd.BhdTrackerJobs.max_nfo_size + 1), True, None, []),
        (True, 'foo.nfo', b'x' * bhd.BhdTrackerJobs.max_nfo_size, True, 'x' * bhd.BhdTrackerJobs.max_nfo_size, []),
        (True, 'foo.nfo', b'x' * bhd.BhdTrackerJobs.max_nfo_size, False, None, [call('Permission denied')]),
        (True, 'foo.txt', b'x' * bhd.BhdTrackerJobs.max_nfo_size, True, None, []),
        (True, 'foo.nfo', b'\xb2\xdb', True, '²Û', []),
    ),
    ids=lambda v: str(v)[:20] if len(str(v)) > 20 else str(v),
)
def test_post_data_nfo(isdir, nfo_file, nfo_data, nfo_readable, exp_value, exp_errors, bhd_tracker_jobs, mocker):
    mocker.patch.object(bhd_tracker_jobs, 'error')
    if not isdir:
        with open(f'{bhd_tracker_jobs.content_path}.mkv', 'wb') as f:
            f.write(b'mock matroska data')
    elif nfo_file:
        nfo_filepath = os.path.join(bhd_tracker_jobs.content_path, nfo_file)
        os.makedirs(os.path.dirname(nfo_filepath), exist_ok=True)
        with open(nfo_filepath, 'wb') as f:
            f.write(nfo_data)
        if not nfo_readable:
            os.chmod(nfo_filepath, 0o222)
    assert bhd_tracker_jobs.post_data_nfo == exp_value
    assert bhd_tracker_jobs.error.call_args_list == exp_errors


@pytest.mark.parametrize(
    argnames='approved_type, options, exp_special',
    argvalues=(
        (utils.types.ReleaseType.movie, {'special': False}, '0'),
        (utils.types.ReleaseType.season, {'special': False}, '0'),
        (utils.types.ReleaseType.episode, {'special': False}, '0'),
        (utils.types.ReleaseType.movie, {'special': True}, '0'),
        (utils.types.ReleaseType.season, {'special': True}, '0'),
        (utils.types.ReleaseType.episode, {'special': True}, '1'),
    ),
)
def test_post_data_special(approved_type, options, exp_special, bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'release_name', PropertyMock(return_value=Mock(
        type=approved_type,
    )))
    mocker.patch.object(type(bhd_tracker_jobs), 'options', PropertyMock(return_value=options))
    assert bhd_tracker_jobs.post_data_special == exp_special


def test_torrent_filepath(bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'create_torrent_job', PropertyMock(return_value=Mock(
        output=('path/to/file.torrent',),
    )))
    assert bhd_tracker_jobs.torrent_filepath == 'path/to/file.torrent'


def test_mediainfo_filehandle(bhd_tracker_jobs, mocker):
    mocker.patch.object(type(bhd_tracker_jobs), 'mediainfo_job', PropertyMock(return_value=Mock(
        output=('mock mediainfo',),
    )))
    assert bhd_tracker_jobs.mediainfo_filehandle.read() == b'mock mediainfo'
