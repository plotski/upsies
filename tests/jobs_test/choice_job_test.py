import re
from unittest.mock import Mock, call

import pytest

from upsies.jobs import prompt


def test_choices_is_shorter_than_two(tmp_path):
    choices = ('foo',)
    with pytest.raises(ValueError, match=(r'^Choices must have at least 2 items: '
                                          rf'{re.escape(str(choices))}$')):
        prompt.ChoiceJob(name='foo', label='Foo', choices=choices)


def test_focused_argument_is_not_given(tmp_path):
    choices = ('foo', 'bar', 'baz')
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=choices)
    assert job.focused == 'foo'

@pytest.mark.parametrize('focused', ('foo', 'bar', 'baz'))
def test_focused_argument_is_valid(focused, tmp_path):
    choices = ('foo', 'bar', 'baz')
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=choices, focused=focused)
    assert job.focused == focused

def test_focused_argument_is_invalid(tmp_path):
    choices = ('foo', 'bar', 'baz')
    with pytest.raises(ValueError, match=(r'^Invalid choice: asdf$')):
        prompt.ChoiceJob(name='foo', label='Foo', choices=choices, focused='asdf')


def test_name_property(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=(1, 2, 3))
    assert job.name == 'foo'


def test_label_property(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=(1, 2, 3))
    assert job.label == 'Foo'


def test_choices_property(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=(1, 2, 3))
    cb = Mock()
    job.signal.register('prompt_updated', cb)
    assert job.choices == ('1', '2', '3')
    job.focused = '3'
    assert cb.call_args_list == [call()]
    job.choices = ('a', 'b', 'c')
    assert cb.call_args_list == [call(), call()]
    assert job.choices == ('a', 'b', 'c')
    assert job.focused == 'a'
    job.choices = ('foo', 'a', 'bar')
    assert cb.call_args_list == [call(), call(), call()]
    assert job.focused == 'a'
    with pytest.raises(ValueError, match=r"^Choices must have at least 2 items: \('x',\)$"):
        job.choices = ('x',)
    assert job.choices == ('foo', 'a', 'bar')
    assert cb.call_args_list == [call(), call(), call()]


def test_focused_property(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=(1, 2, 3))
    cb = Mock()
    job.signal.register('prompt_updated', cb)
    assert job.focused == '1'
    job.focused = '2'
    assert cb.call_args_list == [call()]
    assert job.focused == '2'
    job.focused = None
    assert cb.call_args_list == [call(), call()]
    assert job.focused == '1'
    with pytest.raises(ValueError, match=r"^Invalid choice: 4$"):
        job.focused = '4'
    assert job.focused == '1'
    assert cb.call_args_list == [call(), call()]


def test_choice_selected_value_is_valid(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=(1, 2, 3), focused=2)
    assert not job.is_finished
    job.choice_selected('3')
    assert job.is_finished
    assert job.output == ('3',)
    assert job.errors == ()
    assert job.exit_code == 0

@pytest.mark.asyncio
async def test_choice_selected_value_is_invalid(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=(1, 2, 3), focused=2)
    assert not job.is_finished
    job.choice_selected('4')
    assert job.is_finished
    assert job.output == ()
    assert job.errors == ()
    assert job.exit_code > 0
    with pytest.raises(ValueError, match=r'^Invalid value: 4$'):
        await job.wait()

def test_choice_selected_index_is_valid(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=('a', 'b', 'c'), focused='a')
    assert not job.is_finished
    job.choice_selected(1)
    assert job.is_finished
    assert job.output == ('b',)
    assert job.errors == ()
    assert job.exit_code == 0

@pytest.mark.asyncio
async def test_choice_selected_index_is_invalid(tmp_path):
    job = prompt.ChoiceJob(name='foo', label='Foo', choices=('a', 'b', 'c'), focused='b')
    assert not job.is_finished
    job.choice_selected(3)
    assert job.is_finished
    assert job.output == ()
    assert job.errors == ()
    assert job.exit_code > 0
    with pytest.raises(ValueError, match=r'^Invalid index: 3$'):
        await job.wait()
