import collections
from unittest.mock import call, patch

import pytest

from upsies.jobs import JobBase
from upsies.utils.pipe import Pipe


class MockJob(JobBase):
    name = 'foo'
    label = 'Foo'

    def initialize(self):
        self.output_received = []
        self.pipe_closed_calls = []

    def execute(self):
        pass

    def pipe_input(self, output):
        self.output_received.append(output)

    def pipe_closed(self):
        self.pipe_closed_calls.append(call())


def test_sender_must_be_JobBase_instance(tmp_path):
    send = 123
    recv = MockJob(homedir=tmp_path, ignore_cache=False)
    with pytest.raises(TypeError, match=r'^Not a JobBase instance: 123'):
        Pipe(send, recv)

def test_receiver_must_be_JobBase_instance(tmp_path):
    send = MockJob(homedir=tmp_path, ignore_cache=False)
    recv = 123
    with pytest.raises(TypeError, match=r'^Not a JobBase instance: 123'):
        Pipe(send, recv)


def test_callbacks_are_registered(tmp_path, mocker):
    mocker.patch('upsies.utils.signal.Signal.register')
    send = MockJob(homedir=tmp_path, ignore_cache=False)
    recv = MockJob(homedir=tmp_path, ignore_cache=False)
    pipe = Pipe(send, recv)
    assert send.signal.register.call_args_list == [
        call('output', pipe._handle_sender_output),
        call('finished', pipe._handle_sender_finished),
    ]


def test_handle_sender_output(tmp_path):
    send = MockJob(homedir=tmp_path, ignore_cache=False)
    recv = MockJob(homedir=tmp_path, ignore_cache=False)
    pipe = Pipe(send, recv)
    with patch.object(pipe, '_flush') as flush_mock:
        send.send('foo')
        assert pipe._sender_output_cache == collections.deque(['foo'])
        assert flush_mock.call_args_list == [call()]


def test_handle_sender_finished(tmp_path):
    send = MockJob(homedir=tmp_path, ignore_cache=False)
    recv = MockJob(homedir=tmp_path, ignore_cache=False)
    pipe = Pipe(send, recv)
    with patch.object(pipe, '_flush') as flush_mock:
        send.finish()
        assert pipe._sender_output_cache == collections.deque([None])
        assert flush_mock.call_args_list == [call()]


def test_flush(tmp_path):
    send = MockJob(homedir=tmp_path, ignore_cache=False)
    recv = MockJob(homedir=tmp_path, ignore_cache=False)
    pipe = Pipe(send, recv)
    pipe._sender_output_cache.extend(['foo', 'bar', 'baz', None])
    assert pipe._flush() is None
    assert recv.output_received == ['foo', 'bar', 'baz']
    assert recv.pipe_closed_calls == [call()]
    pipe._sender_output_cache.append('asdf')
    with pytest.raises(RuntimeError, match=r'^Output received on closed pipe$'):
        pipe._flush()
