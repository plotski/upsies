from unittest.mock import Mock, call

from upsies.jobs.dialog import TextFieldJob


def test_name_property():
    job = TextFieldJob(name='foo', label='Foo')
    assert job.name == 'foo'


def test_label_property():
    job = TextFieldJob(name='foo', label='Foo')
    assert job.label == 'Foo'


def test_text_property():
    job = TextFieldJob(name='foo', label='Foo', text='bar')
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.text == 'bar'
    assert cb.call_args_list == []
    job.text = 123
    assert job.text == '123'
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


def test_text_accepted_with_successful_validation():
    validator = Mock()
    job = TextFieldJob(name='foo', label='Foo', text='bar', validator=validator)
    job.text_accepted('asdf')
    assert validator.call_args_list == [call('asdf')]
    assert job.is_finished
    assert job.output == ('asdf',)

def test_text_accepted_with_failed_validation():
    validator = Mock(side_effect=ValueError('no good'))
    job = TextFieldJob(name='foo', label='Foo', text='bar', validator=validator)
    job.text_accepted('asdf')
    assert validator.call_args_list == [call('asdf')]
    assert not job.is_finished
    assert job.output == ()
    assert len(job.warnings) == 1
    assert isinstance(job.warnings[0], ValueError)
    assert str(job.warnings[0]) == 'no good'

def test_text_accepted_while_read_only():
    validator = Mock()
    job = TextFieldJob(name='foo', label='Foo', text='bar', validator=validator)
    job.read_only = True
    job.text_accepted('asdf')
    assert validator.call_args_list == []
    assert not job.is_finished
    assert job.output == ()
