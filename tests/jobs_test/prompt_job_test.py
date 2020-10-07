import re
import pytest

from upsies.jobs import prompt


def test_Choice_choices_argument_is_shorter_than_two(tmp_path):
    choices = ('foo',)
    with pytest.raises(ValueError, match=(r'^choices must contain at least 2 items: '
                                          rf'{re.escape(str(choices))}$')):
        job = prompt.ChoiceJob(
            homedir=tmp_path,
            ignore_cache=True,
            name='foo',
            label='Foo',
            choices=choices,
        )

def test_Choice_focused_argument_is_None(tmp_path):
    choices = ('foo', 'bar', 'baz')
    job = prompt.ChoiceJob(
        homedir=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=choices,
    )
    assert job.focused == 'foo'

def test_Choice_focused_argument_is_valid(tmp_path):
    choices = ('foo', 'bar', 'baz')
    job = prompt.ChoiceJob(
        homedir=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=choices,
        focused='bar',
    )
    assert job.focused == 'bar'

def test_Choice_focused_argument_is_in(tmp_path):
    choices = ('foo', 'bar', 'baz')
    with pytest.raises(ValueError, match=(r'^Invalid choice: asdf$')):
        job = prompt.ChoiceJob(
            homedir=tmp_path,
            ignore_cache=True,
            name='foo',
            label='Foo',
            choices=choices,
            focused='asdf',
        )


def test_Choice_properties(tmp_path):
    job = prompt.ChoiceJob(
        homedir=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=(1, 2, 3),
        focused=2,
    )
    assert job.name == 'foo'
    assert job.label == 'Foo'
    assert job.choices == ('1', '2', '3')
    assert job.focused == '2'


def test_Choice_choice_selected(tmp_path):
    job = prompt.ChoiceJob(
        homedir=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=(1, 2, 3),
        focused=2,
    )
    assert not job.is_finished
    job.choice_selected('3')
    assert job.is_finished
    assert job.output == ('3',)
