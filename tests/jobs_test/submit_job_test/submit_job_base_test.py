import os
from unittest.mock import Mock, call, patch

import pytest

from upsies import errors
from upsies.jobs.submit import SubmitJobBase


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@pytest.mark.parametrize('method', SubmitJobBase.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in SubmitJobBase.__abstractmethods__}
    del attrs[method]
    cls = type('TestSubmitJob', (SubmitJobBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class TestSubmitJob with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def make_TestSubmitJob_class(**kwargs):
    attrs = {
        'tracker_name': 'TEST',
        'login': AsyncMock(),
        'logout': AsyncMock(),
        'upload': AsyncMock(),
    }
    attrs.update(kwargs)
    clsname = 'TestSubmitJob'
    bases = (SubmitJobBase,)
    return type(clsname, bases, attrs)

def make_TestSubmitJob_instance(tmp_path, **kwargs):
    cls = make_TestSubmitJob_class(
        tracker_name=kwargs.pop('tracker_name', 'TEST'),
        login=kwargs.pop('login', AsyncMock()),
        logout=kwargs.pop('logout', AsyncMock()),
        upload=kwargs.pop('upload', AsyncMock()),
    )
    kw = {
        'homedir': tmp_path / 'foo.mkv.project',
        'ignore_cache': False,
        'tracker_config': {},
        'jobs_before_upload': (),
        'jobs_after_upload': (),
    }
    kw.update(kwargs)
    return cls(**kw)


@patch('bs4.BeautifulSoup')
def test_parse_html_succeeds(bs_mock):
    bs_mock.return_value = {'html': 'foo'}
    html = SubmitJobBase.parse_html('<html>foo</html>')
    assert html == {'html': 'foo'}
    assert bs_mock.call_args_list == [call(
        '<html>foo</html>',
        features='html.parser',
    )]

@patch('bs4.BeautifulSoup')
def test_parse_html_fails(bs_mock):
    bs_mock.side_effect = ValueError('Invalid HTML')
    with pytest.raises(RuntimeError, match=r'^Failed to parse HTML: Invalid HTML$'):
        SubmitJobBase.parse_html('<html>foo</html')


def test_dump_html(tmp_path):
    filepath = tmp_path / 'foo'
    job = make_TestSubmitJob_instance(tmp_path)
    assert job.dump_html(filepath, '<html>foo</html>') is None
    assert os.path.exists(filepath)
    assert open(filepath, 'r').read() == '<html>\n foo\n</html>'

def test_dump_html_gets_non_string(tmp_path):
    filepath = tmp_path / 'foo'
    job = make_TestSubmitJob_instance(tmp_path)
    assert job.dump_html(filepath, 123) is None
    assert os.path.exists(filepath)
    assert open(filepath, 'r').read() == '123\n'


def test_tracker_config(tmp_path):
    config = {'username': 'foo', 'password': 'bar'}
    job = make_TestSubmitJob_instance(tmp_path, tracker_config=config)
    assert job.tracker_config == config


@pytest.mark.parametrize('arg', ('jobs_before_upload', 'jobs_after_upload'))
def test_jobs_before_after_upload(arg, tmp_path):
    jobs = (None, 'mock job 1', None, 'mock job 2', None)
    kwargs = {arg: jobs}
    job = make_TestSubmitJob_instance(tmp_path, **kwargs)
    assert getattr(job, arg) == ('mock job 1', 'mock job 2')


def test_tracker_name_property(tmp_path):
    job = make_TestSubmitJob_instance(tmp_path, tracker_name='ASDF')
    assert job.tracker_name == 'ASDF'


def test_metadata_property(tmp_path):
    job = make_TestSubmitJob_instance(tmp_path)
    assert job.metadata is job._metadata
    assert job.metadata == {}


@pytest.mark.asyncio
async def test_wait_waits_for_jobs_in_correct_order(tmp_path):
    mocks = Mock()
    mocks.job1 = AsyncMock()
    mocks.job2 = AsyncMock()
    mocks.job3 = AsyncMock()
    mocks.job4 = AsyncMock()
    mocks._submit = AsyncMock()
    job = make_TestSubmitJob_instance(
        tmp_path,
        jobs_before_upload=(mocks.job1, mocks.job2),
        jobs_after_upload=(mocks.job3, mocks.job4),
    )
    assert not job.is_finished
    with patch.object(job, '_submit', mocks._submit):
        await job.wait()
    # The order of wait() calls within each job list is not predictable and not
    # important. We can't use sets because call() objects are not hashable.
    assert call.job1.wait() in mocks.method_calls[:2]
    assert call.job2.wait() in mocks.method_calls[:2]
    assert mocks.method_calls[2] == call._submit()
    assert call.job3.wait() in mocks.method_calls[3:5]
    assert call.job4.wait() in mocks.method_calls[3:5]
    assert len(mocks.method_calls) == 5
    assert job.metadata == {
        mocks.job1.name: mocks.job1.output,
        mocks.job2.name: mocks.job2.output,
    }
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_can_be_called_multiple_times(tmp_path):
    mocks = AsyncMock()
    job = make_TestSubmitJob_instance(
        tmp_path,
        jobs_before_upload=(mocks.job1, mocks.job2, mocks.job3),
        jobs_after_upload=(mocks.job4, mocks.job5),
    )
    assert not job.is_finished
    with patch.object(job, '_submit', mocks._submit):
        for _ in range(3):
            await job.wait()
            assert job.is_finished
        # The order of wait() calls within each job list is not predictable and
        # not important. We can't use sets because call() objects are not
        # hashable.
        assert call.job1.wait() in mocks.method_calls[:3]
        assert call.job2.wait() in mocks.method_calls[:3]
        assert call.job3.wait() in mocks.method_calls[:3]
        assert mocks.method_calls[3] == call._submit()
        assert call.job4.wait() in mocks.method_calls[4:6]
        assert call.job5.wait() in mocks.method_calls[4:6]
        assert len(mocks.method_calls) == 6


@pytest.mark.asyncio
async def test_submit_sends_upload_return_value_as_output(tmp_path):
    upload_mock = AsyncMock(return_value='http://torrent.url/')
    job = make_TestSubmitJob_instance(
        tmp_path,
        upload=upload_mock,
    )
    job._metadata = {'create-torrent': 'file.torrent'}
    assert await job._submit() is None
    assert job.output == ('http://torrent.url/',)

@pytest.mark.parametrize('method', ('login', 'logout', 'upload'))
@pytest.mark.asyncio
async def test_submit_handles_RequestError_from_abstract_method(method, tmp_path):
    mock = AsyncMock(side_effect=errors.RequestError('No connection'))
    kwargs = {method: mock}
    job = make_TestSubmitJob_instance(tmp_path, **kwargs)
    job._metadata = {'create-torrent': 'file.torrent'}
    assert await job._submit() is None
    if method == 'logout':
        assert job.output == (str(job.upload.return_value),)
    else:
        assert job.output == ()
    assert job.errors == (errors.RequestError('No connection'),)

@pytest.mark.asyncio
async def test_submit_calls_methods_and_callbacks_in_correct_order(tmp_path):
    mocks = Mock()
    mocks.login = AsyncMock()
    mocks.logout = AsyncMock()
    mocks.upload = AsyncMock()

    job = make_TestSubmitJob_instance(
        tmp_path,
        login=mocks.login,
        logout=mocks.logout,
        upload=mocks.upload,
    )
    job._metadata = {'create-torrent': 'file.torrent'}

    with patch.object(job, '_call_callbacks', mocks._call_callbacks):
        await job._submit()
    assert mocks.method_calls == [
        call._call_callbacks(job.signal.logging_in),
        call.login(),
        call._call_callbacks(job.signal.logged_in),

        call._call_callbacks(job.signal.uploading),
        call.upload(),
        call._call_callbacks(job.signal.uploaded),

        call._call_callbacks(job.signal.logging_out),
        call.logout(),
        call._call_callbacks(job.signal.logged_out),
    ]


@pytest.mark.parametrize('signal', SubmitJobBase.signal, ids=lambda v: v.name)
def test_callback_with_valid_signal(signal, tmp_path):
    job = make_TestSubmitJob_instance(tmp_path)
    cb = Mock()
    job.on(signal, cb)
    job._call_callbacks(signal)
    assert cb.call_args_list == [call()]
    job._call_callbacks(signal)
    assert cb.call_args_list == [call(), call()]

@pytest.mark.parametrize('signal', SubmitJobBase.signal, ids=lambda v: v.name)
def test_callback_with_invalid_signal(signal, tmp_path):
    job = make_TestSubmitJob_instance(tmp_path)
    cb = Mock()
    with pytest.raises(RuntimeError, match=r"^Unknown signal: 'foo'$"):
        job.on('foo', cb)
    job._call_callbacks(signal)
    assert cb.call_args_list == []
