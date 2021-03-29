from unittest.mock import Mock, call

import pytest

from upsies import errors
from upsies.jobs.config import SetJob


def config_mock(dct):
    def getitem(self, name):
        return dct[name]

    def setitem(self, name, value):
        dct[name] = value

    return Mock(
        paths=tuple(dct),
        __getitem__=getitem,
        __setitem__=setitem,
        keys=lambda: dct.keys(),
        values=lambda: dct.values(),
    )


def test_cache_id():
    job = SetJob(config=config_mock({'foo': 'bar'}))
    assert job.cache_id is None


def test_output_is_hidden():
    job = SetJob(config=config_mock({'foo': 'bar'}))
    assert job.hidden is True


def test_execute_finishes():
    job = SetJob(config=config_mock({'foo': 'bar'}))
    assert not job.is_finished
    job.execute()
    assert job.is_finished


def test_no_arguments(mocker):
    mocker.patch('upsies.jobs.config.SetJob._display_option')
    cfg = config_mock({'foo': '1', 'bar': '2', 'baz': '3'})
    job = SetJob(config=cfg)
    job.execute()
    assert job._display_option.call_args_list == [call('foo'), call('bar'), call('baz')]


@pytest.mark.parametrize('option', ('foo', 'bar', 'baz'))
def test_arguments_option(option, mocker):
    mocker.patch('upsies.jobs.config.SetJob._display_option')
    values = {'foo': '1', 'bar': '2', 'baz': '3'}
    cfg = config_mock(values)
    job = SetJob(config=cfg, option=option)
    job.execute()
    assert cfg.reset.call_args_list == []
    assert cfg.write.call_args_list == []
    assert job._display_option.call_args_list == [call(option)]
    assert dict(cfg) == values

@pytest.mark.parametrize('option', ('foo', 'bar', 'baz'))
def test_arguments_option_and_value(option, mocker):
    mocker.patch('upsies.jobs.config.SetJob._display_option')
    values = {'foo': '1', 'bar': '2', 'baz': '3'}
    cfg = config_mock(values)
    job = SetJob(config=cfg, option=option, value='hello')
    job.execute()
    assert cfg.reset.call_args_list == []
    assert cfg.write.call_args_list == [call(option)]
    assert job._display_option.call_args_list == [call(option)]
    assert dict(cfg) == {**values, option: 'hello'}

@pytest.mark.parametrize('option', ('foo', 'bar', 'baz'))
def test_arguments_option_and_reset(option, mocker):
    mocker.patch('upsies.jobs.config.SetJob._display_option')
    values = {'foo': '1', 'bar': '2', 'baz': '3'}
    cfg = config_mock(values)
    job = SetJob(config=cfg, option=option, reset=True)
    job.execute()
    assert cfg.reset.call_args_list == [call(option)]
    assert cfg.write.call_args_list == [call(option)]
    assert job._display_option.call_args_list == [call(option)]
    assert dict(cfg) == values

def test_arguments_reset(mocker):
    mocker.patch('upsies.jobs.config.SetJob._display_option')
    values = {'foo': '1', 'bar': '2', 'baz': '3'}
    cfg = config_mock(values)
    job = SetJob(config=cfg, reset=True)
    job.execute()
    assert cfg.reset.call_args_list == [call('foo'), call('bar'), call('baz')]
    assert cfg.write.call_args_list == [call('foo'), call('bar'), call('baz')]
    assert job._display_option.call_args_list == [call('foo'), call('bar'), call('baz')]
    assert dict(cfg) == values

def test_arguments_value():
    with pytest.raises(RuntimeError, match=r'^Argument "value" needs argument "option"\.$'):
        SetJob(config=config_mock({'foo': 'bar'}), value='foo')

def test_arguments_value_and_reset():
    with pytest.raises(RuntimeError, match=r'^Arguments "value" and "reset" are mutually exclusive\.$'):
        SetJob(config=config_mock({'foo': 'bar'}), value='foo', reset=True)

def test_arguments_option_and_value_and_reset():
    with pytest.raises(RuntimeError, match=r'^Arguments "value" and "reset" are mutually exclusive\.$'):
        SetJob(config=config_mock({'foo': 'bar'}), value='foo', reset=True)


@pytest.mark.parametrize(
    argnames=('mode', 'kwargs'),
    argvalues=(
        ('_reset_mode', {'reset': True}),
        ('_set_mode', {'option': 'foo', 'value': 'bar'}),
        ('_display_mode', {}),
    ),
    ids=lambda v: str(v),
)
def test_ConfigError_is_handled(mode, kwargs, mocker):
    mocker.patch('upsies.jobs.config.SetJob._display_option')
    mocker.patch(f'upsies.jobs.config.SetJob.{mode}', side_effect=errors.ConfigError('no!'))
    values = {'foo': '1', 'bar': '2', 'baz': '3'}
    cfg = config_mock(values)
    job = SetJob(config=cfg, **kwargs)
    job.execute()
    assert job.errors == (errors.ConfigError('no!'),)
    assert job.is_finished
    assert job.exit_code != 0
    assert cfg.reset.call_args_list == []
    assert cfg.write.call_args_list == []
    assert job._display_option.call_args_list == []
    assert dict(cfg) == values


@pytest.mark.parametrize(
    argnames=('name', 'value', 'exp_output'),
    argvalues=(
        ('foo', 'asdf', 'foo = asdf'),
        ('bar', 'a sd f', 'bar = a sd f'),
        ('baz', 123, 'baz = 123'),
        ('foo', ['a', 'b', 'c'], 'foo = a b c'),
        ('foo', [1, 2, 3, 'd'], 'foo = 1 2 3 d'),
    ),
    ids=lambda v: str(v),
)
def test_display_option(name, value, exp_output):
    job = SetJob(config=config_mock({name: value}))
    job.execute()
    assert job.output == (exp_output,)
