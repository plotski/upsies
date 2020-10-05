from upsies.jobs import prompt


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
