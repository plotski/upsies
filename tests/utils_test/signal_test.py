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
    assert s._record_signals == []
    s.add('foo')
    assert s.signals == {'foo': []}
    assert s._record_signals == []
    s.add('bar', record=True)
    assert s.signals == {'foo': [], 'bar': []}
    assert s._record_signals == ['bar']
    s.add('baz', record=False)
    assert s.signals == {'foo': [], 'bar': [], 'baz': []}
    assert s._record_signals == ['bar']


def test_record():
    s = Signal('foo', 'bar')
    assert s.recording == []
    s.record('foo')
    assert s.recording == ['foo']
    s.record('bar')
    assert s.recording == ['foo', 'bar']
    with pytest.raises(ValueError, match=r"^Unknown signal: 'baz'$"):
        s.record('baz')
    assert s.recording == ['foo', 'bar']


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

def test_emit_records_call():
    s = Signal()
    s.add('foo', record=True)
    s.add('bar', record=True)
    s.add('baz', record=False)
    assert s.emissions == ()
    s.emit('foo', 123)
    s.emit('bar', 'hello', 'world')
    s.emit('foo', 'and', this='that')
    s.emit('baz', 0)
    s.emit('bar', four=56)
    assert s.emissions == (
        ('foo', {'args': (123,), 'kwargs': {}}),
        ('bar', {'args': ('hello', 'world'), 'kwargs': {}}),
        ('foo', {'args': ('and',), 'kwargs': {'this': 'that'}}),
        ('bar', {'args': (), 'kwargs': {'four': 56}}),
    )

def test_replay_emits():
    emissions = (
        ('foo', {'args': (123,), 'kwargs': {}}),
        ('bar', {'args': ('hello', 'world'), 'kwargs': {}}),
        ('foo', {'args': ('and',), 'kwargs': {'this': 'that'}}),
        ('bar', {'args': (), 'kwargs': {'four': 56}}),
    )
    s = Signal('foo', 'bar', 'baz')
    cb = Mock()
    s.register('foo', cb.foo)
    s.register('bar', cb.bar)
    s.register('baz', cb.baz)
    s.replay(emissions)
    assert cb.mock_calls == [
        call.foo(123),
        call.bar('hello', 'world'),
        call.foo('and', this='that'),
        call.bar(four=56),
    ]


def test_suspend_blocks_emissions():
    s = Signal('foo', 'bar', 'baz')
    cb = Mock()
    s.register('foo', cb.foo)
    s.register('bar', cb.bar)
    s.register('baz', cb.baz)

    s.emit('foo', 123, this='that')
    s.emit('bar', 456, hey='ho')
    s.emit('baz', 789, zip='zop')
    assert cb.mock_calls == [
        call.foo(123, this='that'),
        call.bar(456, hey='ho'),
        call.baz(789, zip='zop'),
    ]
    cb.reset_mock()

    with s.suspend('bar', 'foo'):
        s.emit('foo', 123, this='that')
        s.emit('bar', 456, hey='ho')
        s.emit('baz', 789, zip='zop')
    assert cb.mock_calls == [
        call.baz(789, zip='zop'),
    ]
    cb.reset_mock()

    s.emit('foo', 123, this='that')
    s.emit('bar', 456, hey='ho')
    s.emit('baz', 789, zip='zop')
    assert cb.mock_calls == [
        call.foo(123, this='that'),
        call.bar(456, hey='ho'),
        call.baz(789, zip='zop'),
    ]

def test_suspend_handles_unknown_signals():
    s = Signal('foo', 'bar', 'baz')
    with pytest.raises(ValueError, match=r"Unknown signal: 'boo'"):
        with s.suspend('bar', 'boo'):
            pass
