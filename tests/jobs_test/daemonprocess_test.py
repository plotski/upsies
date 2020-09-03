import re
import time
from unittest.mock import Mock, call

import pytest

from upsies.jobs._common import DaemonProcess


# https://kalnytskyi.com/howto/assert-str-matches-regex-in-pytest/
class regex:
    def __init__(self, pattern, flags=0):
        self._regex = re.compile(pattern, flags)

    def __eq__(self, string):
        return bool(self._regex.match(string))

    def __repr__(self):
        return self._regex.pattern


# DaemonProcess' targets must be picklable and nested functions aren't.

def target_raising_exception(output_queue, input_queue):
    raise Exception('Kaboom!')

def target_sending_to_init_callback(output_queue, input_queue):
    for i in range(3):
        output_queue.put((DaemonProcess.INIT, i))

def target_sending_to_info_callback(output_queue, input_queue):
    for i in range(4):
        output_queue.put((DaemonProcess.INFO, i))

def target_sending_to_error_callback(output_queue, input_queue):
    for i in range(2):
        output_queue.put((DaemonProcess.ERROR, i))

def target_sending_result_to_finished_callback(output_queue, input_queue):
    output_queue.put((DaemonProcess.RESULT, 'foo'))

def target_sending_no_result_to_finished_callback(output_queue, input_queue):
    pass

def target_never_terminating(output_queue, input_queue):
    output_queue.put((DaemonProcess.INFO, 'something'))
    import time
    while True:
        time.sleep(1)

def target_taking_arguments(output_queue, input_queue, foo, bar, *, baz):
    output_queue.put((DaemonProcess.INFO, foo))
    output_queue.put((DaemonProcess.INFO, bar))
    output_queue.put((DaemonProcess.INFO, baz))


@pytest.mark.asyncio
async def test_target_gets_positional_and_keyword_arguments():
    info_callback = Mock()
    proc = DaemonProcess(
        target=target_taking_arguments,
        args=('Foo', 'Bar'),
        kwargs={'baz': 'Baz'},
        info_callback=info_callback,
    )
    proc.start()
    await proc.join()
    assert info_callback.call_args_list == [call('Foo'), call('Bar'), call('Baz')]


@pytest.mark.asyncio
async def test_exceptions_from_target_are_pushed_to_error_queue():
    error_callback = Mock()
    proc = DaemonProcess(
        target=target_raising_exception,
        error_callback=error_callback,
    )
    proc.start()
    await proc.join()
    msg = error_callback.call_args_list[0][0][0].split('\n')
    assert msg[0] == regex(r'^Traceback')
    assert msg[-1] == regex(r'Exception: Kaboom!$')


@pytest.mark.asyncio
async def test_target_sends_to_init_callback():
    init_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_to_init_callback,
        init_callback=init_callback,
    )
    proc.start()
    await proc.join()
    assert init_callback.call_args_list == [call(0), call(1), call(2)]


@pytest.mark.asyncio
async def test_target_sends_to_info_callback():
    info_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_to_info_callback,
        info_callback=info_callback,
    )
    proc.start()
    await proc.join()
    assert info_callback.call_args_list == [call(0), call(1), call(2), call(3)]


@pytest.mark.asyncio
async def test_target_sends_to_error_callback():
    error_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_to_error_callback,
        error_callback=error_callback,
    )
    proc.start()
    await proc.join()
    assert error_callback.call_args_list == [call(0), call(1)]


@pytest.mark.asyncio
async def test_target_sends_result_to_finished_callback():
    finished_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_result_to_finished_callback,
        finished_callback=finished_callback,
    )
    proc.start()
    await proc.join()
    assert finished_callback.call_args_list == [call('foo')]


@pytest.mark.asyncio
async def test_target_sends_no_result_to_finished_callback():
    finished_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_no_result_to_finished_callback,
        finished_callback=finished_callback,
    )
    proc.start()
    await proc.join()
    assert finished_callback.call_args_list == [call()]


@pytest.mark.asyncio
async def test_stop_terminates_running_process():
    info_callback = Mock()
    proc = DaemonProcess(
        target=target_never_terminating,
        info_callback=info_callback,
    )
    proc.start()
    time.sleep(5)
    assert proc.is_alive
    proc.stop()
    await proc.join()
    info_callback.call_args_list == [call('something')]


@pytest.mark.asyncio
async def test_process_terminates_gracefully_without_joining_it():
    finished_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_result_to_finished_callback,
        finished_callback=finished_callback,
    )
    proc.start()
    time.sleep(5)
    assert not proc.is_alive
    await proc.join()  # Await internal output reader task
    finished_callback.call_args_list == [call('foo')]


@pytest.mark.asyncio
async def test_is_alive_property():
    proc = DaemonProcess(
        target=target_never_terminating,
    )
    assert proc.is_alive is False
    proc.start()
    assert proc.is_alive is True
    time.sleep(1)
    assert proc.is_alive is True
    proc.stop()
    assert proc.is_alive is True
    await proc.join()
    assert proc.is_alive is False


@pytest.mark.asyncio
async def test_init_callback_raises_exception():
    init_callback = Mock(side_effect=RuntimeError('Boo!'))
    proc = DaemonProcess(
        target=target_sending_to_init_callback,
        init_callback=init_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert init_callback.call_args_list == [call(0)]

@pytest.mark.asyncio
async def test_info_callback_raises_exception():
    info_callback = Mock(side_effect=RuntimeError('Boo!'))
    proc = DaemonProcess(
        target=target_sending_to_info_callback,
        info_callback=info_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert info_callback.call_args_list == [call(0)]

@pytest.mark.asyncio
async def test_error_callback_raises_exception():
    error_callback = Mock(side_effect=RuntimeError('Boo!'))
    proc = DaemonProcess(
        target=target_sending_to_error_callback,
        error_callback=error_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert error_callback.call_args_list == [call(0)]

@pytest.mark.asyncio
async def test_finished_callback_raises_exception():
    finished_callback = Mock(side_effect=RuntimeError('Boo!'))
    proc = DaemonProcess(
        target=target_sending_result_to_finished_callback,
        finished_callback=finished_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert finished_callback.call_args_list == [call('foo')]
