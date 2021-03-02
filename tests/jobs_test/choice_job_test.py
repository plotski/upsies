import asyncio
from unittest.mock import Mock, call

import pytest

from upsies.jobs import dialog


def test_name_property():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    assert job.name == 'foo'


def test_label_property():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    assert job.label == 'Foo'


def test_choices_are_strings():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    cb = Mock()
    assert job.choices == (('1', '1'), ('2', '2'), ('3', '3'))
    assert job.focused == ('1', '1')
    job.signal.register('dialog_updated', cb)

    job.focused = '3'
    assert job.choices == (('1', '1'), ('2', '2'), ('3', '3'))
    assert job.focused == ('3', '3')
    assert cb.call_args_list == [call((('1', '1'), ('2', '2'), ('3', '3')), 2)]
    cb.reset_mock()

    job.choices = ('a', 'b', 'c')
    assert job.choices == (('a', 'a'), ('b', 'b'), ('c', 'c'))
    assert job.focused == ('a', 'a')
    assert cb.call_args_list == [call((('a', 'a'), ('b', 'b'), ('c', 'c')), 0)]
    cb.reset_mock()

    job.choices = ['foo', 'a', 'bar']
    assert job.choices == (('foo', 'foo'), ('a', 'a'), ('bar', 'bar'))
    assert job.focused == ('a', 'a')
    assert cb.call_args_list == [call((('foo', 'foo'), ('a', 'a'), ('bar', 'bar')), 1)]
    cb.reset_mock()

    job.choices = ['bar', 'baz']
    assert job.choices == (('bar', 'bar'), ('baz', 'baz'))
    assert job.focused == ('bar', 'bar')
    assert cb.call_args_list == [call((('bar', 'bar'), ('baz', 'baz')), 0)]
    cb.reset_mock()

    with pytest.raises(ValueError, match=r"^Choices must have at least 2 items: \('x',\)$"):
        job.choices = ('x',)
    assert job.choices == (('bar', 'bar'), ('baz', 'baz'))
    assert job.focused == ('bar', 'bar')

def test_choices_are_sequences():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    cb = Mock()
    assert job.choices == (('a', 1), ('b', 2), ('c', 3))
    assert job.focused == ('a', 1)
    job.signal.register('dialog_updated', cb)

    job.focused = ('c', 3)
    assert job.choices == (('a', 1), ('b', 2), ('c', 3))
    assert job.focused == ('c', 3)
    assert cb.call_args_list == [call((('a', 1), ('b', 2), ('c', 3)), 2)]
    cb.reset_mock()

    job.choices = (('d', 4), ('e', 5), ('f', 6))
    assert job.choices == (('d', 4), ('e', 5), ('f', 6))
    assert job.focused == ('d', 4)
    assert cb.call_args_list == [call((('d', 4), ('e', 5), ('f', 6)), 0)]
    cb.reset_mock()

    job.choices = [('x', 100), ('y', 200), ('d', 4)]
    assert job.choices == (('x', 100), ('y', 200), ('d', 4))
    assert job.focused == ('d', 4)
    assert cb.call_args_list == [call((('x', 100), ('y', 200), ('d', 4)), 2)]
    cb.reset_mock()

    job.choices = [('hello', 99), ('world', 33)]
    assert job.choices == (('hello', 99), ('world', 33))
    assert job.focused == ('hello', 99)
    assert cb.call_args_list == [call((('hello', 99), ('world', 33)), 0)]
    cb.reset_mock()

    with pytest.raises(ValueError, match=r"^Choices must have at least 2 items: \(\('x', -1\),\)$"):
        job.choices = (('x', -1),)
    assert job.choices == (('hello', 99), ('world', 33))
    assert job.focused == ('hello', 99)
    assert cb.call_args_list == []

    with pytest.raises(ValueError, match=r"^Choice must be a 2-tuple, not \('x',\)$"):
        job.choices = (('x',),)
    with pytest.raises(ValueError, match=r"^Choice must be a 2-tuple, not \('x', 'y', 'z'\)$"):
        job.choices = (('x', 'y', 'z'),)
    assert job.choices == (('hello', 99), ('world', 33))
    assert job.focused == ('hello', 99)
    assert cb.call_args_list == []

def test_choices_are_invalid():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=('a', 'b',))
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    with pytest.raises(ValueError, match=r"^Choice must be a 2-tuple, not 123$"):
        job.choices = ('x', ('y', 'why'), 123, ('z', 'see'))
    assert job.choices == (('a', 'a'), ('b', 'b'))
    assert job.focused == ('a', 'a')
    assert cb.call_args_list == []


@pytest.mark.parametrize('current', ('a', 'b', 'c'))
def test_focused_set_to_None(current):
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=('a', 'b', 'c'), focused=current)
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.focused == (current, current)
    job.focused = None
    assert job.focused == ('a', 'a')
    assert cb.call_args_list == [call((('a', 'a'), ('b', 'b'), ('c', 'c')), 0)]

@pytest.mark.parametrize('focus', (0, 1, 2))
def test_focused_set_to_int(focus):
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=('a', 'b', 'c'))
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.focused == ('a', 'a')
    job.focused = focus
    assert job.focused == job.choices[focus]
    assert cb.call_args_list == [call((('a', 'a'), ('b', 'b'), ('c', 'c')), focus)]

@pytest.mark.parametrize('focus, exp_focused', (
    ('a', ('a', 'foo')),
    ('b', ('b', 'bar')),
    ('c', ('c', 'baz')),
    ('foo', ('a', 'foo')),
    ('bar', ('b', 'bar')),
    ('baz', ('c', 'baz')),
))
def test_focused_set_to_valid_value(focus, exp_focused):
    choices = (('a', 'foo'), ('b', 'bar'), ('c', 'baz'))
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=choices)
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.focused == ('a', 'foo')
    job.focused = focus
    assert job.focused == exp_focused
    assert cb.call_args_list == [call((('a', 'foo'), ('b', 'bar'), ('c', 'baz')), choices.index(exp_focused))]

def test_focused_set_to_invalid_value():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.focused == ('a', 1)
    with pytest.raises(ValueError, match=r"^Invalid choice: 'x'$"):
        job.focused = 'x'
    assert job.focused == ('a', 1)
    assert cb.call_args_list == []

@pytest.mark.parametrize('choice', (('a', 1), ('b', 2), ('c', 3)))
def test_focused_set_to_valid_choice(choice):
    choices = (('a', 1), ('b', 2), ('c', 3))
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=choices)
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.focused == ('a', 1)
    job.focused = choice
    assert job.focused == choice
    assert cb.call_args_list == [call((('a', 1), ('b', 2), ('c', 3)), choices.index(choice))]

def test_focused_set_to_invalid_choice():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.focused == ('a', 1)
    with pytest.raises(ValueError, match=r"^Invalid choice: \('d', 4\)$"):
        job.focused = ('d', 4)
    assert job.focused == ('a', 1)
    assert cb.call_args_list == []


@pytest.mark.parametrize('choice', (('a', 'foo'), ('b', 'bar'), ('c', 'baz')))
def test_choice_selected_with_valid_choice(choice):
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 'foo'), ('b', 'bar'), ('c', 'baz')))
    cb = Mock()
    job.signal.register('chosen', cb.chosen)
    job.signal.register('output', cb.output)
    assert job.choice is None
    job.choice_selected(choice)
    assert cb.mock_calls == [call.chosen(choice[1]), call.output(choice[0])]
    assert job.choice == choice[1]
    assert job.output == (choice[0],)
    assert job.errors == ()
    asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished

def test_choice_selected_with_invalid_choice():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    cb = Mock()
    job.signal.register('chosen', cb)
    assert job.focused == ('a', 1)
    assert job.choice is None
    job.choice_selected(('d', 4))
    assert job.focused == ('a', 1)
    assert job.choice is None
    assert cb.call_args_list == []
    assert job.output == ()
    assert job.errors == ()
    with pytest.raises(ValueError, match=r"^Invalid choice: \('d', 4\)$"):
        asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished

@pytest.mark.parametrize('index, exp_choice', ((0, ('a', 'foo')), (1, ('b', 'bar')), (2, ('c', 'baz'))))
def test_choice_selected_with_valid_index(index, exp_choice):
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 'foo'), ('b', 'bar'), ('c', 'baz')))
    cb = Mock()
    job.signal.register('chosen', cb.chosen)
    job.signal.register('output', cb.output)
    assert job.choice is None
    job.choice_selected(index)
    assert job.choice is exp_choice[1]
    assert cb.mock_calls == [call.chosen(exp_choice[1]), call.output(exp_choice[0])]
    assert job.output == (exp_choice[0],)
    assert job.errors == ()
    asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished

def test_choice_selected_with_invalid_index():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 'foo'), ('b', 'bar'), ('c', 'baz')))
    cb = Mock()
    job.signal.register('chosen', cb.chosen)
    job.signal.register('output', cb.output)
    assert job.choice is None
    job.choice_selected(3)
    assert job.choice is None
    assert cb.mock_calls == []
    assert job.output == ()
    assert job.errors == ()
    with pytest.raises(ValueError, match=r"^Invalid choice: 3$"):
        asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished

@pytest.mark.parametrize('value, exp_choice', (
    ('a', ('a', 'foo')),
    ('b', ('b', 'bar')),
    ('c', ('c', 'baz')),
    ('foo', ('a', 'foo')),
    ('bar', ('b', 'bar')),
    ('baz', ('c', 'baz')),
))
def test_choice_selected_with_valid_value(value, exp_choice):
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 'foo'), ('b', 'bar'), ('c', 'baz')))
    cb = Mock()
    job.signal.register('chosen', cb.chosen)
    job.signal.register('output', cb.output)
    assert job.choice is None
    job.choice_selected(value)
    assert job.choice is exp_choice[1]
    assert cb.mock_calls == [call.chosen(exp_choice[1]), call.output(exp_choice[0])]
    assert job.output == (exp_choice[0],)
    assert job.errors == ()
    asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished

def test_choice_selected_with_invalid_value():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 'foo'), ('b', 'bar'), ('c', 'baz')))
    cb = Mock()
    job.signal.register('chosen', cb.chosen)
    job.signal.register('output', cb.output)
    assert job.choice is None
    job.choice_selected('arf')
    assert job.choice is None
    assert cb.mock_calls == []
    assert job.output == ()
    assert job.errors == ()
    with pytest.raises(ValueError, match=r"^Invalid choice: 'arf'$"):
        asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished

def test_choice_selected_with_None():
    job = dialog.ChoiceJob(name='foo', label='Foo', choices=(('a', 'foo'), ('b', 'bar'), ('c', 'baz')))
    cb = Mock()
    job.signal.register('chosen', cb.chosen)
    job.signal.register('output', cb.output)
    assert job.choice is None
    job.choice_selected(None)
    assert job.choice is None
    assert cb.mock_calls == []
    assert job.output == ()
    assert job.errors == ()
    asyncio.get_event_loop().run_until_complete(job.wait())
    assert job.is_finished
