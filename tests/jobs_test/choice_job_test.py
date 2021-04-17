import re
from unittest.mock import Mock, call

import pytest

from upsies.jobs import dialog


@pytest.fixture
def make_ChoiceJob(tmp_path):
    def make_ChoiceJob(**kwargs):
        return dialog.ChoiceJob(home_directory=tmp_path, cache_directory=tmp_path, **kwargs)
    return make_ChoiceJob


def test_name_property(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    assert job.name == 'foo'


def test_label_property(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    assert job.label == 'Foo'


def test_choices_getter(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    assert job.choices is job._choices
    assert job._choices == (('1', '1'), ('2', '2'), ('3', '3'))

def test_choices_setter_with_strings(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    job.choices = ('a', 'b', 'c')
    assert job._choices == (('a', 'a'), ('b', 'b'), ('c', 'c'))

@pytest.mark.parametrize('invalid_sequence', (['b'], ['b', 2, 'foo']))
def test_choices_setter_with_invalid_sequence(invalid_sequence, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    with pytest.raises(ValueError, match=(r'^Choice must be 2-tuple, '
                                          rf'not {re.escape(str(invalid_sequence))}$')):
        job.choices = (['a', 1], invalid_sequence, ['c', 3])
    assert job._choices == (('1', '1'), ('2', '2'), ('3', '3'))

def test_choices_setter_with_valid_sequence(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    job.choices = (['a', 1], ['b', 2], ['c', 3])
    assert job._choices == (('a', 1), ('b', 2), ('c', 3))

def test_choices_setter_with_invalid_choice(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    with pytest.raises(ValueError, match=r'^Choice must be 2-tuple, not None$'):
        job.choices = (['a', 1], None, ['c', 3])
    assert job._choices == (('1', '1'), ('2', '2'), ('3', '3'))

def test_choices_setter_with_too_few_choices(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    with pytest.raises(ValueError, match=r"^There must be at least 2 choices: \['a'\]$"):
        job.choices = ['a']
    assert job._choices == (('1', '1'), ('2', '2'), ('3', '3'))

@pytest.mark.parametrize('focused_choice', (('2', 2), '2', 2))
def test_choices_setter_preserves_focus_if_possible(focused_choice, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('1', 1), ('2', 2), ('3', 3)))
    job.focused = ('2', 2)
    assert job.focused == ('2', 2)
    job.choices = (['0', 0], ['1', 1], ['2', 2], ['3', 3], ['4', 4])
    assert job.focused == ('2', 2)

@pytest.mark.parametrize('focused_choice', (('2', 2), '2', 2))
def test_choices_setter_defaults_focus_to_first_choice(focused_choice, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('1', 1), ('2', 2), ('3', 3)))
    job.focused = ('3', 3)
    assert job.focused == ('3', 3)
    job.choices = (['0', 0], ['1', 1], ['2', 2])
    assert job.focused == ('0', 0)

def test_choices_setter_emits_dialog_updated_signal(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('1', 1), ('2', 2), ('3', 3)))
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    job.choices = (['0', 0], ['1', 1], ['2', 2])
    assert cb.call_args_list == [call(job)]


def test_focused_getter_before_internal_state_is_defined(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    delattr(job, '_focused_index')
    assert job.focused is None

@pytest.mark.parametrize(
    argnames='focused_index, exp_focused',
    argvalues=(
        (0, ('1', '1')),
        (1, ('2', '2')),
        (2, ('3', '3')),
    ),
    ids=lambda v: str(v),
)
def test_focused_getter_after_internal_state_is_defined(focused_index, exp_focused, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    job._focused_index = focused_index
    assert job.focused == exp_focused

def test_focused_setter_with_None(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    job.focused = '3'
    assert job._focused_index == 2
    job.focused = None
    assert job._focused_index == 0

@pytest.mark.parametrize(
    argnames='index, exp_focused_index',
    argvalues=(
        (-1, 0),
        (0, 0),
        (1, 1),
        (2, 2),
        (3, 2),
    ),
    ids=lambda v: str(v),
)
def test_focused_setter_with_integer(index, exp_focused_index, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    job.focused = index
    assert job._focused_index == exp_focused_index

@pytest.mark.parametrize(
    argnames='choice, exp_focused_index',
    argvalues=(
        (('1', '1'), 0),
        (('2', '2'), 1),
        (('3', '3'), 2),
    ),
    ids=lambda v: str(v),
)
def test_focused_setter_with_choice_tuple(choice, exp_focused_index, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    job.focused = choice
    assert job._focused_index == exp_focused_index

@pytest.mark.parametrize(
    argnames='item, exp_focused_index',
    argvalues=(
        ('a', 0),
        ('b', 1),
        ('c', 2),
        ('x', 0),
        ('y', 1),
        ('z', 2),
    ),
    ids=lambda v: str(v),
)
def test_focused_setter_with_choice_item(item, exp_focused_index, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 'x'), ('b', 'y'), ('c', 'z')))
    job.focused = item
    assert job._focused_index == exp_focused_index

def test_focused_setter_with_invalid_choice(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    with pytest.raises(ValueError, match=r"^Invalid choice: 'nope'$"):
        job.focused = 'nope'
    assert job._focused_index == 0

def test_focused_setter_emits_dialog_updated_signal(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    job.focused = '3'
    assert cb.call_args_list == [call(job)]


@pytest.mark.parametrize(
    argnames='focused, exp_focused_index',
    argvalues=(
        ('1', 0),
        ('2', 1),
        ('3', 2),
    ),
    ids=lambda v: str(v),
)
def test_focused_index(focused, exp_focused_index, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=('1', '2', '3'))
    cb = Mock()
    job.signal.register('dialog_updated', cb)
    assert job.focused_index == 0
    job.focused = focused
    assert job.focused_index == exp_focused_index
    assert cb.call_args_list == [call(job)]


def test_choice_getter_without_setting_choice(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    assert job.choice is None
    job.finish()
    assert job.choice is None

def test_choice_getter_with_setting_choice(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    assert not job.is_finished
    job.choice = 'b'
    assert job.choice == 2
    assert job.is_finished

@pytest.mark.parametrize(
    argnames='item, exp_choice',
    argvalues=(
        (('a', 1), 1),
        (('b', 2), 2),
        (('c', 3), 3),
    ),
    ids=lambda v: str(v),
)
def test_choice_setter_with_item_from_choices(item, exp_choice, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    assert not job.is_finished
    job.choice = item
    assert job.choice == exp_choice
    assert job.is_finished

@pytest.mark.parametrize(
    argnames='index, exp_choice',
    argvalues=(
        (0, 1),
        (1, 2),
        (2, 3),
    ),
    ids=lambda v: str(v),
)
def test_choice_setter_with_valid_index(index, exp_choice, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    assert not job.is_finished
    job.choice = index
    assert job.choice == exp_choice
    assert job.is_finished

def test_choice_setter_with_invalid_index(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    assert not job.is_finished
    with pytest.raises(ValueError, match=r'^Invalid choice: 3$'):
        job.choice = 3
    assert job.choice is None
    assert not job.is_finished

@pytest.mark.parametrize(
    argnames='item, exp_choice',
    argvalues=(
        ('a', 'x'),
        ('b', 'y'),
        ('c', 'z'),
        ('x', 'x'),
        ('y', 'y'),
        ('z', 'z'),
    ),
    ids=lambda v: str(v),
)
def test_choice_setter_with_valid_item_from_choice(item, exp_choice, make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 'x'), ('b', 'y'), ('c', 'z')))
    assert not job.is_finished
    job.choice = item
    assert job.choice == exp_choice
    assert job.is_finished

def test_choice_setter_with_invalid_item_from_choice(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 'x'), ('b', 'y'), ('c', 'z')))
    assert not job.is_finished
    with pytest.raises(ValueError, match=r"^Invalid choice: 'foo'$"):
        job.choice = 'foo'
    assert job.choice is None
    assert not job.is_finished

def test_choice_setter_with_invalid_choice(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 'x'), ('b', 'y'), ('c', 'z')))
    assert not job.is_finished
    with pytest.raises(ValueError, match=r"^Invalid choice: \(1, 2, 3\)$"):
        job.choice = (1, 2, 3)
    assert job.choice is None
    assert not job.is_finished

def test_choice_setter_emits_chose_signal(make_ChoiceJob):
    job = make_ChoiceJob(name='foo', label='Foo', choices=(('a', 1), ('b', 2), ('c', 3)))
    cb = Mock()
    job.signal.register('chosen', cb.chosen)
    job.signal.register('dialog_updated', cb.dialog_updated)
    job.choice = 'b'
    assert cb.mock_calls == [call.chosen(2)]
