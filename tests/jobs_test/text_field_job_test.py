from unittest.mock import Mock, call

import pytest

from upsies.jobs.dialog import TextFieldJob


def test_name_property():
    job = TextFieldJob(name='foo', label='Foo')
    assert job.name == 'foo'


def test_label_property():
    job = TextFieldJob(name='foo', label='Foo')
    assert job.label == 'Foo'


def test_cache_id_property():
    job = TextFieldJob(name='foo', label='Foo', text='asdf')
    assert job.cache_id == ('foo', 'asdf')


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


@pytest.mark.parametrize('read_only', (True, False))
def test_finish_with_valid_text(read_only):
    validator = Mock()
    job = TextFieldJob(name='foo', label='Foo', text='bar',
                       validator=validator, read_only=read_only)
    assert validator.call_args_list == []
    job.text = 'baz'
    job.finish()
    assert validator.call_args_list == [call('baz')]
    assert job.warnings == ()
    assert job.is_finished
    assert job.output == ('baz',)

@pytest.mark.parametrize('read_only', (True, False))
def test_finish_with_invalid_text(read_only):
    validator = Mock(side_effect=ValueError('Nope'))
    job = TextFieldJob(name='foo', label='Foo', text='bar',
                       validator=validator, read_only=read_only)
    assert validator.call_args_list == []
    job.text = 'baz'
    job.finish()
    assert validator.call_args_list == [call('baz')]
    assert len(job.warnings) == 1
    assert isinstance(job.warnings[0], ValueError)
    assert str(job.warnings[0]) == 'Nope'
    assert not job.is_finished
    assert job.output == ()
