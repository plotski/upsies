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
    def validator(text):
        if not text.isdigit():
            raise ValueError('Not a number')

    job = TextFieldJob(name='foo', label='Foo', text='0',
                       validator=validator, read_only=read_only)
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.text == '0'
    assert cb.call_args_list == []
    job.text = 123
    assert job.text == '123'
    assert cb.call_args_list == [call(job)]
    with pytest.raises(ValueError, match=r'^Not a number$'):
        job.text = 'foo'
    assert cb.call_args_list == [call(job)]


def test_clear():
    validator = Mock()
    job = TextFieldJob(name='foo', label='Foo', text='foo', validator=validator)
    assert validator.call_args_list == [call('foo')]
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    job.clear()
    assert job.text == ''
    assert validator.call_args_list == [call('foo')]
    assert cb.call_args_list == [call(job)]


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
def test_finish(read_only):
    validator = Mock()
    job = TextFieldJob(name='foo', label='Foo', text='bar',
                       validator=validator, read_only=read_only)
    assert validator.call_args_list == [call('bar')]
    job.finish()
    assert job.is_finished
    assert job.output == ('bar',)
