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
    assert job.text == 'foo'
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
    validator = Mock()
    job = make_TextFieldJob(name='foo', label='Foo', text='bar', validator=validator)
    assert validator.call_args_list == []
    job.send('baz')
    assert validator.call_args_list == [call('baz')]
    assert job.warnings == ()
    assert job.is_finished
    assert job.exit_code == 0
    assert job.output == ('baz',)

def test_send_invalid_text(make_TextFieldJob):
    validator = Mock(side_effect=ValueError('Nope'))
    job = make_TextFieldJob(name='foo', label='Foo', text='bar', validator=validator)
    assert validator.call_args_list == []
    job.send('baz')
    assert validator.call_args_list == [call('baz')]
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
    assert job.errors == ()
    assert job.warnings == ('connection failed',)
    assert job.is_finished is False
    assert job.exit_code is None

@pytest.mark.parametrize('finish_on_success', (True, False))
@pytest.mark.asyncio
async def test_fetch_text_finishes_job(finish_on_success, make_TextFieldJob):
    fetcher = AsyncMock(return_value='fetched text')
    job = make_TextFieldJob(name='foo', label='Foo')
    assert not job.is_finished
    await job.fetch_text(fetcher, finish_on_success=finish_on_success)
    assert job.is_finished is finish_on_success
    if finish_on_success:
        assert job.exit_code == 0
    else:
        assert job.exit_code is None
