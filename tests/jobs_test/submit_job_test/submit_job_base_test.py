import os
from unittest.mock import Mock, call, patch

import aiohttp
import aiohttp.test_utils
import pytest

from upsies import __project_name__, __version__, errors
from upsies.jobs.submit import _base


# FIXME: The AsyncMock class from Python 3.8 is missing __await__(), making it
# not a subclass of typing.Awaitable.
class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@pytest.mark.parametrize('method', _base.SubmissionJobBase.__abstractmethods__)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in _base.SubmissionJobBase.__abstractmethods__}
    del attrs[method]
    cls = type('TestSubmissionJob', (_base.SubmissionJobBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class TestSubmissionJob with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def make_TestSubmissionJob_class(**kwargs):
    attrs = {
        'tracker_name': 'TEST',
        'login': AsyncMock(),
        'logout': AsyncMock(),
        'upload': AsyncMock(),
    }
    attrs.update(kwargs)
    clsname = 'TestSubmission'
    bases = (_base.SubmissionJobBase,)
    return type(clsname, bases, attrs)

def make_TestSubmissionJob_instance(tmp_path, **kwargs):
    cls = make_TestSubmissionJob_class(
        tracker_name=kwargs.pop('tracker_name', 'TEST'),
        login=kwargs.pop('login', AsyncMock()),
        logout=kwargs.pop('logout', AsyncMock()),
        upload=kwargs.pop('upload', AsyncMock()),
    )
    kw = {
        'homedir': tmp_path / 'foo.mkv.project',
        'ignore_cache': False,
        'tracker_config': {},
        'required_jobs': (),
    }
    kw.update(kwargs)
    return cls(**kw)


@patch('bs4.BeautifulSoup')
def test_parse_html_succeeds(bs_mock):
    bs_mock.return_value = {'html': 'foo'}
    html = _base.SubmissionJobBase.parse_html('<html>foo</html>')
    assert html == {'html': 'foo'}
    assert bs_mock.call_args_list == [call(
        '<html>foo</html>',
        features='html.parser',
    )]

@patch('bs4.BeautifulSoup')
def test_parse_html_fails(bs_mock):
    bs_mock.side_effect = ValueError('Invalid HTML')
    with pytest.raises(RuntimeError, match=r'^Failed to parse HTML: Invalid HTML$'):
        _base.SubmissionJobBase.parse_html('<html>foo</html')


def test_dump_html(tmp_path):
    filepath = tmp_path / 'foo'
    html = '<html>foo</html>'
    assert _base.SubmissionJobBase.dump_html(filepath, html) is None
    assert os.path.exists(filepath)
    assert open(filepath, 'r').read() == html


@pytest.mark.parametrize('attribute', ('tracker_config', 'required_jobs'))
def test_initialize_argument_as_properties(attribute, tmp_path):
    mock_obj = object()
    kwargs = {attribute: mock_obj}
    job = make_TestSubmissionJob_instance(tmp_path, **kwargs)
    assert getattr(job, attribute) is mock_obj

def test_properties(tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path, tracker_name='ASDF')
    assert job.tracker_name == 'ASDF'
    assert job.metadata is job._metadata
    assert job.metadata == {}


@pytest.mark.asyncio
async def test_wait(tmp_path):
    mocks = Mock()
    mocks.job1 = AsyncMock()
    mocks.job2 = AsyncMock()
    mocks._submit = AsyncMock()
    job = make_TestSubmissionJob_instance(
        tmp_path,
        required_jobs=(mocks.job1, mocks.job2),
    )
    assert not job.is_finished
    with patch.object(job, '_submit', mocks._submit):
        await job.wait()
    # The order of jobX.wait() calls is not predictable.
    # We can't use sets because call() objects are not hashable.
    assert call.job1.wait() in mocks.method_calls[:2]
    assert call.job2.wait() in mocks.method_calls[:2]
    assert mocks.method_calls[-1] == call._submit()
    assert len(mocks.method_calls) == 3
    assert job.metadata == {
        mocks.job1.name: mocks.job1.output,
        mocks.job2.name: mocks.job2.output,
    }
    assert job.is_finished


@pytest.mark.asyncio
async def test_http_session_is_ClientSession(tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    assert isinstance(job._http_session, aiohttp.ClientSession)

@patch('aiohttp.ClientSession')
def test_http_session_is_created_correctly(ClientSession_mock, tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    job._http_session
    assert ClientSession_mock.call_args_list == [call(
        headers={'User-Agent': f'{__project_name__}/{__version__}'},
        raise_for_status=True,
        timeout=aiohttp.ClientTimeout(total=job.timeout),
    )]

@pytest.mark.asyncio
async def test_http_session_is_singleton(tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    assert job._http_session is job._http_session


@pytest.mark.asyncio
async def test_submit_passes_http_session_to_abstract_methods(tmp_path):
    sessions = []
    login_mock = AsyncMock(side_effect=lambda session: sessions.append(session))
    logout_mock = AsyncMock(side_effect=lambda session: sessions.append(session))
    upload_mock = AsyncMock(side_effect=lambda session: sessions.append(session))
    job = make_TestSubmissionJob_instance(
        tmp_path,
        login=login_mock,
        logout=logout_mock,
        upload=upload_mock,
    )
    job._metadata = {'create-torrent': 'file.torrent'}
    assert await job._submit() is None
    assert all(s is job._http_session for s in sessions)

@pytest.mark.asyncio
async def test_submit_sends_upload_return_value_as_output(tmp_path):
    upload_mock = AsyncMock(return_value='http://torrent.url/')
    job = make_TestSubmissionJob_instance(
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
    job = make_TestSubmissionJob_instance(tmp_path, **kwargs)
    job._metadata = {'create-torrent': 'file.torrent'}
    assert await job._submit() is None
    if method == 'logout':
        assert job.output == (str(job.upload.return_value),)
    else:
        assert job.output == ()
    assert len(job.errors) == 1
    assert str(job.errors[0]) == 'No connection'
    assert isinstance(job.errors[0], errors.RequestError)

@pytest.mark.asyncio
async def test_submit_calls_methods_and_callbacks_in_correct_order(tmp_path):
    mocks = Mock()
    mocks.login = AsyncMock()
    mocks.logout = AsyncMock()
    mocks.upload = AsyncMock()

    job = make_TestSubmissionJob_instance(
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
        call.login(job._http_session),
        call._call_callbacks(job.signal.logged_in),

        call._call_callbacks(job.signal.uploading),
        call.upload(job._http_session),
        call._call_callbacks(job.signal.uploaded),

        call._call_callbacks(job.signal.logging_out),
        call.logout(job._http_session),
        call._call_callbacks(job.signal.logged_out),
    ]


@pytest.mark.parametrize('signal', _base.SubmissionJobBase.signal, ids=lambda v: v.name)
def test_callback_with_valid_signal(signal, tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    cb = Mock()
    job.on(signal, cb)
    job._call_callbacks(signal)
    assert cb.call_args_list == [call()]
    job._call_callbacks(signal)
    assert cb.call_args_list == [call(), call()]

@pytest.mark.parametrize('signal', _base.SubmissionJobBase.signal, ids=lambda v: v.name)
def test_callback_with_invalid_signal(signal, tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    cb = Mock()
    with pytest.raises(RuntimeError, match=r"^Unknown signal: 'foo'$"):
        job.on('foo', cb)
    job._call_callbacks(signal)
    assert cb.call_args_list == []
