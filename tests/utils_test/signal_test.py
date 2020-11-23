from unittest.mock import Mock, call

import pytest

from upsies.utils.signal import Signal


def test_keyword_arguments_are_added():
    s = Signal('foo', 'bar', 'baz')
    assert s.signals == {'foo': [], 'bar': [], 'baz': []}


def test_adding_unhashable_signal():
    s = Signal()
    with pytest.raises(TypeError, match=r'^Unhashable signal: \{\}$'):
        assert s.add({})

def test_adding_duplicate_signal():
    s = Signal('foo')
    with pytest.raises(RuntimeError, match=r"^Signal already added: 'foo'$"):
        s.add('foo')

def test_adding_adds_signal():
    s = Signal()
    assert s.signals == {}
    s.add('foo')
    assert s.signals == {'foo': []}
    s.add('bar')
    assert s.signals == {'foo': [], 'bar': []}
    s.add('baz')
    assert s.signals == {'foo': [], 'bar': [], 'baz': []}


def test_registering_for_unknown_signal():
    s = Signal('foo')
    with pytest.raises(ValueError, match=r"^Unknown signal: 'bar'$"):
        s.register('bar', lambda: None)

def test_registering_noncallable():
    s = Signal('foo')
    with pytest.raises(TypeError, match=r"^Not a callable: 'bar'$"):
        s.register('foo', 'bar')


@pytest.mark.parametrize('kwargs', ({}, {'1': 2}), ids=lambda v: str(v))
@pytest.mark.parametrize('args', ((), (1,), (1, 2)), ids=lambda v: str(v))
def test_emit_to_no_callback(args, kwargs):
    s = Signal('foo')
    s.emit('foo', *args, **kwargs)

@pytest.mark.parametrize('kwargs', ({}, {'1': 2}), ids=lambda v: str(v))
@pytest.mark.parametrize('args', ((), (1,), (1, 2)), ids=lambda v: str(v))
def test_emit_to_single_callback(args, kwargs):
    s = Signal('foo', 'bar')
    cb = Mock()
    s.register('foo', cb)
    s.emit('foo', *args, **kwargs)
    assert cb.call_args_list == [call(*args, **kwargs)]
    s.emit('bar', *args, **kwargs)
    assert cb.call_args_list == [call(*args, **kwargs)]

@pytest.mark.parametrize('kwargs', ({}, {'1': 2}), ids=lambda v: str(v))
@pytest.mark.parametrize('args', ((), (1,), (1, 2)), ids=lambda v: str(v))
def test_emit_to_multiple_callbacks(args, kwargs):
    s = Signal('foo', 'bar')
    cb = Mock()
    s.register('foo', cb.a)
    s.register('foo', cb.b)
    s.register('foo', cb.c)
    s.register('bar', cb.d)
    s.register('bar', cb.e)
    s.register('bar', cb.f)
    s.emit('foo', *args, **kwargs)
    assert cb.mock_calls == [
        call.a(*args, **kwargs),
        call.b(*args, **kwargs),
        call.c(*args, **kwargs),
    ]
    s.emit('bar')
    assert cb.mock_calls == [
        call.a(*args, **kwargs),
        call.b(*args, **kwargs),
        call.c(*args, **kwargs),
        call.d(),
        call.e(),
        call.f(),
    ]
