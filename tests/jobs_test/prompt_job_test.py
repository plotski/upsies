import re

import pytest

from upsies.jobs import prompt


def test_Choice_choices_argument_is_shorter_than_two(tmp_path):
    choices = ('foo',)
    with pytest.raises(ValueError, match=(r'^choices must contain at least 2 items: '
                                          rf'{re.escape(str(choices))}$')):
        prompt.ChoiceJob(
            home_directory=tmp_path,
            ignore_cache=True,
            name='foo',
            label='Foo',
            choices=choices,
        )

def test_Choice_focused_argument_is_None(tmp_path):
    choices = ('foo', 'bar', 'baz')
    job = prompt.ChoiceJob(
        home_directory=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=choices,
    )
    assert job.focused == 'foo'

def test_Choice_focused_argument_is_valid(tmp_path):
    choices = ('foo', 'bar', 'baz')
    job = prompt.ChoiceJob(
        home_directory=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=choices,
        focused='bar',
    )
    assert job.focused == 'bar'

def test_Choice_focused_argument_is_invalid(tmp_path):
    choices = ('foo', 'bar', 'baz')
    with pytest.raises(ValueError, match=(r'^Invalid choice: asdf$')):
        prompt.ChoiceJob(
            home_directory=tmp_path,
            ignore_cache=True,
            name='foo',
            label='Foo',
            choices=choices,
            focused='asdf',
        )


def test_Choice_properties(tmp_path):
    job = prompt.ChoiceJob(
        home_directory=tmp_path,
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


def test_Choice_choice_selected_value_is_valid(tmp_path):
    job = prompt.ChoiceJob(
        home_directory=tmp_path,
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
    assert job.errors == ()
    assert job.exit_code == 0

@pytest.mark.asyncio
async def test_Choice_choice_selected_value_is_invalid(tmp_path):
    job = prompt.ChoiceJob(
        home_directory=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=(1, 2, 3),
        focused=2,
    )
    assert not job.is_finished
    job.choice_selected('4')
    assert job.is_finished
    assert job.output == ()
    assert job.errors == ()
    assert job.exit_code > 0
    with pytest.raises(ValueError, match=r'^Invalid value: 4$'):
        await job.wait()

def test_Choice_choice_selected_index_is_valid(tmp_path):
    job = prompt.ChoiceJob(
        home_directory=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=('a', 'b', 'c'),
        focused='a',
    )
    assert not job.is_finished
    job.choice_selected(1)
    assert job.is_finished
    assert job.output == ('b',)
    assert job.errors == ()
    assert job.exit_code == 0

@pytest.mark.asyncio
async def test_Choice_choice_selected_index_is_invalid(tmp_path):
    job = prompt.ChoiceJob(
        home_directory=tmp_path,
        ignore_cache=True,
        name='foo',
        label='Foo',
        choices=('a', 'b', 'c'),
        focused='b',
    )
    assert not job.is_finished
    job.choice_selected(3)
    assert job.is_finished
    assert job.output == ()
    assert job.errors == ()
    assert job.exit_code > 0
    with pytest.raises(ValueError, match=r'^Invalid index: 3$'):
        await job.wait()
