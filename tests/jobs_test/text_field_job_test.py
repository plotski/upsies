from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.dialog import TextFieldJob


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@pytest.fixture
def make_TextFieldJob(tmp_path):
    def make_TextFieldJob(**kwargs):
        return TextFieldJob(home_directory=tmp_path, cache_directory=tmp_path, **kwargs)
    return make_TextFieldJob

def test_name_property(make_TextFieldJob):
    job = make_TextFieldJob(name='foo', label='Foo')
    assert job.name == 'foo'


def test_label_property(make_TextFieldJob):
    job = make_TextFieldJob(name='foo', label='Foo')
    assert job.label == 'Foo'


@pytest.mark.parametrize('read_only', (True, False))
def test_text_property(read_only, make_TextFieldJob):
    job = make_TextFieldJob(name='foo', label='Foo', text='0',
                            validator=Mock(side_effect=ValueError('No likey')),
                            normalizer=Mock(side_effect=str.capitalize),
                            read_only=read_only)
    cb = Mock()
    job.signal.register('dialog_updating', cb.dialog_updating)
    job.signal.register('dialog_updated', cb.dialog_updated)
    assert job.text == '0'
    assert cb.dialog_updating.call_args_list == []
    assert cb.dialog_updated.call_args_list == []
    job.text = 123
    assert job.text == '123'
    assert cb.dialog_updating.call_args_list == []
    assert cb.dialog_updated.call_args_list == [call(job)]
    job.text = 'foo'
    assert job.text == 'Foo'
    assert cb.dialog_updating.call_args_list == []
    assert cb.dialog_updated.call_args_list == [call(job), call(job)]


def test_obscured_property(make_TextFieldJob):
    job = make_TextFieldJob(name='foo', label='Foo', obscured=True)
    cb = Mock()
    job.signal.register('dialog_updating', cb.dialog_updating)
    job.signal.register('dialog_updated', cb.dialog_updated)
    assert job.obscured is True
    assert cb.dialog_updating.call_args_list == []
    assert cb.dialog_updated.call_args_list == []
    job.obscured = 0
    assert job.obscured is False
    assert cb.dialog_updating.call_args_list == []
    assert cb.dialog_updated.call_args_list == [call(job)]


def test_read_only_property(make_TextFieldJob):
    job = make_TextFieldJob(name='foo', label='Foo', read_only=True)
    cb = Mock()
    job.signal.register('dialog_updating', cb.dialog_updating)
    job.signal.register('dialog_updated', cb.dialog_updated)
    assert job.read_only is True
    assert cb.dialog_updating.call_args_list == []
    assert cb.dialog_updated.call_args_list == []
    job.read_only = ''
    assert job.read_only is False
    assert cb.dialog_updating.call_args_list == []
    assert cb.dialog_updated.call_args_list == [call(job)]


def test_send_valid_text(make_TextFieldJob):
    callables = Mock()
    callables.normalizer = Mock(side_effect=str.upper)
    job = make_TextFieldJob(
        name='foo',
        label='Foo',
        text='bar',
        validator=callables.validator,
        normalizer=callables.normalizer,
    )
    assert callables.mock_calls == [
        call.normalizer('bar'),
    ]
    assert job.text == 'BAR'
    assert job.output == ()

    callables.reset_mock()
    job.send('baz')

    assert callables.mock_calls == [
        call.normalizer('baz'),
        call.validator('BAZ'),
    ]
    assert job.warnings == ()
    assert job.is_finished
    assert job.exit_code == 0
    assert job.output == ('BAZ',)

def test_send_invalid_text(make_TextFieldJob):
    callables = Mock()
    callables.validator = Mock(side_effect=ValueError('Nope'))
    callables.normalizer = Mock(side_effect=str.upper)
    job = make_TextFieldJob(
        name='foo',
        label='Foo',
        text='bar',
        validator=callables.validator,
        normalizer=callables.normalizer,
    )
    assert callables.mock_calls == [
        call.normalizer('bar'),
    ]

    callables.reset_mock()
    job.send('baz')

    assert callables.mock_calls == [
        call.normalizer('baz'),
        call.validator('BAZ'),
    ]
    assert job.warnings == ('Nope',)
    assert not job.is_finished
    assert job.exit_code is None
    assert job.output == ()


@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.asyncio
async def test_fetch_text_sets_read_only_while_fetching(finish_on_success, make_TextFieldJob):
    async def fetcher(job):
        assert job.read_only
        assert cb.dialog_updating.call_args_list == [call(job)]
        return 'Fetched text'

    cb = Mock()
    job = make_TextFieldJob(name='foo', label='Foo', text='bar')
    job.signal.register('dialog_updating', cb.dialog_updating)
    assert not job.read_only
    assert cb.dialog_updating.call_args_list == []
    await job.fetch_text(fetcher(job), finish_on_success=finish_on_success)
    assert not job.read_only
    assert cb.dialog_updating.call_args_list == [call(job)]
    assert job.is_finished is finish_on_success
    if finish_on_success:
        assert job.exit_code == 0
    else:
        assert job.exit_code is None

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.parametrize('default_text', (None, '', 'Default text'))
@pytest.mark.asyncio
async def test_fetch_text_catches_fatal_error(default_text, finish_on_success, make_TextFieldJob):
    fetcher = AsyncMock(side_effect=errors.RequestError('connection failed'))
    job = make_TextFieldJob(name='foo', label='Foo', text='Original text')
    assert not job.is_finished
    await job.fetch_text(fetcher, default_text=default_text, finish_on_success=finish_on_success, error_is_fatal=True)
    assert job.text == ('Original text' if default_text is None else default_text)
    assert job.output == ()
    assert job.errors == (errors.RequestError('connection failed'),)
    assert job.warnings == ()
    assert job.is_finished is True
    assert job.exit_code == 0

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.parametrize('default_text', (None, '', 'Default text'))
@pytest.mark.asyncio
async def test_fetch_text_catches_nonfatal_error(default_text, finish_on_success, make_TextFieldJob):
    fetcher = AsyncMock(side_effect=errors.RequestError('connection failed'))
    job = make_TextFieldJob(name='foo', label='Foo', text='Original text')
    assert not job.is_finished
    await job.fetch_text(fetcher, default_text=default_text, finish_on_success=finish_on_success, error_is_fatal=False)
    assert job.text == ('Original text' if default_text is None else default_text)
    assert job.output == ()
    assert job.errors == ()
    assert job.warnings == ('connection failed',)
    assert job.is_finished is False
    assert job.exit_code is None

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.parametrize('default_text', (None, '', 'Default text'))
@pytest.mark.asyncio
async def test_fetch_text_sets_default_text_if_coro_returns_None(default_text, finish_on_success, make_TextFieldJob):
    fetcher = AsyncMock(return_value=None)
    job = make_TextFieldJob(name='foo', label='Foo', text='Original text')
    assert not job.is_finished
    await job.fetch_text(fetcher, default_text=default_text)
    assert job.text == ('Original text' if default_text is None else default_text)
    assert job.output == ()
    assert job.errors == ()
    assert job.warnings == ()
    assert job.is_finished is False
    assert job.exit_code is None

@pytest.mark.parametrize('fetched_text', (None, '', 'Fetched text'))
@pytest.mark.asyncio
async def test_fetch_text_finishes_only_if_coro_returns_text(fetched_text, make_TextFieldJob):
    fetcher = AsyncMock(return_value=fetched_text)
    job = make_TextFieldJob(name='foo', label='Foo', text='Original text')
    assert not job.is_finished
    await job.fetch_text(fetcher, default_text='Default text', finish_on_success=True)
    assert job.text == ('Default text' if fetched_text is None else fetched_text)
    assert job.output == ((fetched_text,) if fetched_text is not None else ())
    assert job.errors == ()
    assert job.warnings == ()
    assert job.is_finished is (True if fetched_text is not None else False)
    assert job.exit_code is (0 if fetched_text is not None else None)

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.parametrize('default_text', (None, '', 'Default text'))
@pytest.mark.asyncio
async def test_fetch_text_succeeds(default_text, finish_on_success, make_TextFieldJob):
    fetcher = AsyncMock(return_value='Fetched text')
    job = make_TextFieldJob(name='foo', label='Foo', text='Original text')
    assert not job.is_finished
    await job.fetch_text(fetcher, default_text=default_text, finish_on_success=finish_on_success)
    assert job.text == 'Fetched text'
    assert job.output == (('Fetched text',) if finish_on_success else ())
    assert job.errors == ()
    assert job.warnings == ()
    assert job.is_finished is finish_on_success
    if finish_on_success:
        assert job.exit_code == 0
    else:
        assert job.exit_code is None
