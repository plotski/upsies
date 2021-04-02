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


def test_name_property():
    job = TextFieldJob(name='foo', label='Foo')
    assert job.name == 'foo'


def test_label_property():
    job = TextFieldJob(name='foo', label='Foo')
    assert job.label == 'Foo'


@pytest.mark.parametrize('read_only', (True, False))
def test_text_property(read_only):
    job = TextFieldJob(name='foo', label='Foo', text='0',
                       validator=Mock(side_effect=ValueError('No likey')),
                       read_only=read_only)
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.text == '0'
    assert cb.call_args_list == []
    job.text = 123
    assert job.text == '123'
    assert cb.call_args_list == [call(job)]
    job.text = 'foo'
    assert job.text == 'foo'
    assert cb.call_args_list == [call(job), call(job)]


def test_obscured_property():
    job = TextFieldJob(name='foo', label='Foo', obscured=True)
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.obscured is True
    assert cb.call_args_list == []
    job.obscured = 0
    assert job.obscured is False
    assert cb.call_args_list == [call(job)]


def test_read_only_property():
    job = TextFieldJob(name='foo', label='Foo', read_only=True)
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.read_only is True
    assert cb.call_args_list == []
    job.read_only = ''
    assert job.read_only is False
    assert cb.call_args_list == [call(job)]


def test_send_valid_text():
    validator = Mock()
    job = TextFieldJob(name='foo', label='Foo', text='bar', validator=validator)
    assert validator.call_args_list == []
    job.send('baz')
    assert validator.call_args_list == [call('baz')]
    assert job.warnings == ()
    assert job.is_finished
    assert job.output == ('baz',)

def test_finish_with_invalid_text():
    validator = Mock(side_effect=ValueError('Nope'))
    job = TextFieldJob(name='foo', label='Foo', text='bar', validator=validator)
    assert validator.call_args_list == []
    job.send('baz')
    assert validator.call_args_list == [call('baz')]
    assert len(job.warnings) == 1
    assert isinstance(job.warnings[0], ValueError)
    assert str(job.warnings[0]) == 'Nope'
    assert not job.is_finished
    assert job.output == ()


@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.asyncio
async def test_fetch_text_sets_read_only_while_fetching(finish_on_success):
    async def fetcher(job):
        assert job.read_only
        assert job.text == 'Loading...'

    job = TextFieldJob(name='foo', label='Foo', text='bar')
    assert not job.read_only
    await job.fetch_text(fetcher(job), finish_on_success=finish_on_success)
    assert not job.read_only
    assert job.is_finished is finish_on_success

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.asyncio
async def test_fetch_text_catches_fatal_error(finish_on_success):
    fetcher = AsyncMock(side_effect=errors.RequestError('connection failed'))
    job = TextFieldJob(name='foo', label='Foo')
    assert not job.is_finished
    await job.fetch_text(fetcher, default_text='default text', finish_on_success=finish_on_success, error_is_fatal=True)
    assert job.text == 'default text'
    assert job.errors == (errors.RequestError('connection failed'),)
    assert job.warnings == ()
    assert job.is_finished is True

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.asyncio
async def test_fetch_text_catches_nonfatal_error(finish_on_success):
    fetcher = AsyncMock(side_effect=errors.RequestError('connection failed'))
    job = TextFieldJob(name='foo', label='Foo')
    assert not job.is_finished
    await job.fetch_text(fetcher, default_text='default text', finish_on_success=finish_on_success, error_is_fatal=False)
    assert job.text == 'default text'
    assert job.errors == ()
    assert job.warnings == (errors.RequestError('connection failed'),)
    assert job.is_finished is False

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.asyncio
async def test_fetch_text_finishes_job(finish_on_success):
    fetcher = AsyncMock(return_value='fetched text')
    job = TextFieldJob(name='foo', label='Foo')
    assert not job.is_finished
    await job.fetch_text(fetcher, finish_on_success=finish_on_success)
    assert job.is_finished is finish_on_success
