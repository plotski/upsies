import os
import sys
from unittest.mock import Mock, PropertyMock, call, patch

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


abstract_methods = (
    'trackername', 'login', 'logout', 'upload', 'jobs',
)

@pytest.mark.parametrize('method', abstract_methods)
def test_abstract_method(method):
    attrs = {name:lambda self: None for name in abstract_methods}
    del attrs[method]
    cls = type('TestSubmissionJob', (_base.SubmissionJobBase,), attrs)
    # Python 3.9 changed "methods" to "method"
    exp_msg = rf"^Can't instantiate abstract class TestSubmissionJob with abstract methods? {method}$"
    with pytest.raises(TypeError, match=exp_msg):
        cls()


def make_TestSubmissionJob_class(**kwargs):
    attrs = {
        'trackername': 'TEST',
        'login': AsyncMock(),
        'logout': AsyncMock(),
        'upload': AsyncMock(),
        'jobs': PropertyMock(return_value=()),
    }
    attrs.update(kwargs)
    clsname = 'TestSubmission'
    bases = (_base.SubmissionJobBase,)
    return type(clsname, bases, attrs)

def make_TestSubmissionJob_instance(tmp_path, **kwargs):
    cls = make_TestSubmissionJob_class(
        trackername=kwargs.pop('trackername', 'TEST'),
        login=kwargs.pop('login', AsyncMock()),
        logout=kwargs.pop('logout', AsyncMock()),
        upload=kwargs.pop('upload', AsyncMock()),
        jobs=kwargs.pop('jobs', PropertyMock(return_value=())),
    )
    kw = {
        'homedir': tmp_path / 'foo.mkv.project',
        'ignore_cache': False,
        'args': Mock(),
        'config': Mock(),
        'content_path': tmp_path / 'foo.mkv',
    }
    kw.update(kwargs)
    return cls(**kw)


@pytest.mark.asyncio
async def test_http_session_is_ClientSession(tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    assert isinstance(job._http_session, aiohttp.ClientSession)


needs_pytyon38_because_unpatchable_ClientSession = pytest.mark.skipif(
    sys.version_info < (3, 8),
    reason='Python <3.8 refuses to patch aiohttp.ClientSession',
)

needs_pytyon38_because_missing_async_mocking_support = pytest.mark.skipif(
    sys.version_info < (3, 8),
    reason='Python <3.8 does not support AsyncMock',
)

@needs_pytyon38_because_unpatchable_ClientSession
@patch('aiohttp.ClientSession')
@pytest.mark.asyncio
async def test_http_session_is_created_correctly(ClientSession_mock, tmp_path):
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


@needs_pytyon38_because_unpatchable_ClientSession
@patch('aiohttp.ClientSession')
@pytest.mark.parametrize('method', ('get', 'post'), ids=lambda v: f'method={v.upper()}')
@pytest.mark.asyncio
async def test_http_method_uses_http_session(ClientSession_mock, method, tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    session_mock = ClientSession_mock.return_value
    setattr(session_mock, method, AsyncMock())
    method_coro = getattr(job, f'http_{method}')
    response = await method_coro('http://localhost:123', bar='baz')
    assert getattr(session_mock, method).call_args_list == [call(
        'http://localhost:123',
        bar='baz',
    )]
    assert response is getattr(session_mock, method).return_value

@needs_pytyon38_because_unpatchable_ClientSession
@patch('aiohttp.ClientSession')
@pytest.mark.parametrize('method', ('get', 'post'), ids=lambda v: f'method={v.upper()}')
@pytest.mark.asyncio
async def test_http_method_raises_ResponseError(ClientSession_mock, method, tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    session_mock = ClientSession_mock.return_value
    setattr(
        session_mock,
        method,  # get or post
        AsyncMock(side_effect=aiohttp.ClientError('Nope')),
    )
    method_coro = getattr(job, f'http_{method}')
    with pytest.raises(errors.RequestError, match=r'^http://localhost:123: Nope$'):
        await method_coro('http://localhost:123')


@patch('bs4.BeautifulSoup')
def test_parse_html(bs_mock):
    bs_mock.return_value = {'html': 'foo'}
    html = _base.SubmissionJobBase.parse_html('<html>foo</html>')
    assert html == {'html': 'foo'}
    assert bs_mock.call_args_list == [call(
        '<html>foo</html>',
        features='html.parser',
    )]


def test_dump_html(tmp_path):
    filepath = tmp_path / 'foo'
    html = '<html>foo</html>'
    assert _base.SubmissionJobBase.dump_html(filepath, html) is None
    assert os.path.exists(filepath)
    assert open(filepath, 'r').read() == html


@pytest.mark.parametrize('attribute', ('args', 'config', 'content_path'))
def test_argument_as_attribute(attribute, tmp_path):
    mock_obj = object()
    kwargs = {attribute: mock_obj}
    job = make_TestSubmissionJob_instance(tmp_path, **kwargs)
    assert getattr(job, attribute) is mock_obj


@needs_pytyon38_because_missing_async_mocking_support
@pytest.mark.asyncio
async def test_wait(tmp_path):
    job_mocks = (AsyncMock(), AsyncMock(), AsyncMock())
    job = make_TestSubmissionJob_instance(
        tmp_path,
        jobs=PropertyMock(return_value=job_mocks),
    )
    with patch.object(job, '_submit'):
        await job.wait()
        for job_mock in job_mocks:
            assert job_mock.wait.call_args_list == [call()]
        assert job._submit.call_args_list == [call()]
        assert job.is_finished


@pytest.mark.asyncio
async def test_submit_calls_abstract_methods_in_correct_order(tmp_path):
    calls = []
    login_mock = AsyncMock(side_effect=lambda: calls.append('login'))
    logout_mock = AsyncMock(side_effect=lambda: calls.append('logout'))
    upload_mock = AsyncMock(side_effect=lambda: calls.append('upload'))
    job = make_TestSubmissionJob_instance(
        tmp_path,
        login=login_mock,
        logout=logout_mock,
        upload=upload_mock,
    )
    assert await job._submit() is None
    assert calls == ['login', 'upload', 'logout']
    assert job._http_session.closed

@pytest.mark.asyncio
async def test_submit_sends_upload_return_value_as_output(tmp_path):
    upload_mock = AsyncMock(return_value='http://torrent.url/')
    job = make_TestSubmissionJob_instance(
        tmp_path,
        upload=upload_mock,
    )
    assert await job._submit() is None
    assert job.output == ('http://torrent.url/',)
    assert job._http_session.closed

@pytest.mark.parametrize('method', ('login', 'logout', 'upload'))
@pytest.mark.asyncio
async def test_submit_handles_RequestError_from_abstract_method(method, tmp_path):
    mock = AsyncMock(side_effect=errors.RequestError('No connection'))
    kwargs = {method: mock}
    job = make_TestSubmissionJob_instance(tmp_path, **kwargs)
    assert await job._submit() is None
    if method == 'logout':
        assert job.output == (str(job.upload.return_value),)
    else:
        assert job.output == ()
    assert len(job.errors) == 1
    assert str(job.errors[0]) == 'No connection'
    assert isinstance(job.errors[0], errors.RequestError)
    assert job._http_session.closed

@pytest.mark.asyncio
async def test_submit_calls_callbacks(tmp_path):
    job = make_TestSubmissionJob_instance(tmp_path)
    with patch.object(job, '_call_callbacks'):
        await job._submit()
        assert job._call_callbacks.call_args_list == [
            call(job.signal.logging_in),
            call(job.signal.logged_in),
            call(job.signal.submitting),
            call(job.signal.submitted),
            call(job.signal.logging_out),
            call(job.signal.logged_out),
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
