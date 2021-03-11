import asyncio
import queue
import time
from unittest.mock import Mock, call

import pytest

from upsies.utils.daemon import DaemonProcess, MsgType

# DaemonProcess targets must be picklable and nested functions aren't.

def target_raising_exception(output_queue, input_queue):
    raise ValueError('Kaboom!')

def target_sending_to_init_callback(output_queue, input_queue):
    for i in range(3):
        output_queue.put((MsgType.init, i))

def target_sending_to_info_callback(output_queue, input_queue):
    for i in range(4):
        output_queue.put((MsgType.info, i))

def target_sending_to_error_callback(output_queue, input_queue):
    for i in range(2):
        output_queue.put((MsgType.error, i))

def target_sending_result_to_finished_callback(output_queue, input_queue):
    output_queue.put((MsgType.result, 'foo'))

def target_sending_no_result_to_finished_callback(output_queue, input_queue):
    pass

def target_never_terminating(output_queue, input_queue):
    output_queue.put((MsgType.info, 'something'))

    while True:
        try:
            typ, msg = input_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if typ is MsgType.terminate:
                break

        time.sleep(1)

def target_taking_arguments(output_queue, input_queue, foo, bar, *, baz):
    output_queue.put((MsgType.info, foo))
    output_queue.put((MsgType.info, bar))
    output_queue.put((MsgType.info, baz))


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
async def test_exceptions_from_target_are_reraised_when_process_is_joined():
    error_callback = Mock()
    proc = DaemonProcess(
        target=target_raising_exception,
        error_callback=error_callback,
    )
    proc.start()
    with pytest.raises(ValueError, match=r'^Kaboom!$') as exc_info:
        await proc.join()
    assert exc_info.value.original_traceback.startswith('Subprocess traceback:\n')
    assert 'target_raising_exception' in exc_info.value.original_traceback
    assert exc_info.value.original_traceback.endswith('ValueError: Kaboom!')
    assert len(error_callback.call_args_list) == 1
    assert isinstance(error_callback.call_args_list[0][0][0], ValueError)
    assert str(error_callback.call_args_list[0][0][0]) == 'Kaboom!'


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
async def test_stop_sends_termination_signal_to_running_process():
    info_callback = Mock()
    proc = DaemonProcess(
        target=target_never_terminating,
        info_callback=info_callback,
    )
    proc.start()
    await asyncio.sleep(1)
    assert proc.is_alive
    proc.stop()
    await proc.join()
    assert info_callback.call_args_list == [call('something')]


@pytest.mark.asyncio
async def test_is_alive_property():
    proc = DaemonProcess(
        target=target_never_terminating,
    )
    assert proc.is_alive is False
    proc.start()
    assert proc.is_alive is True
    proc.stop()
    await proc.join()
    assert proc.is_alive is False


@pytest.mark.asyncio
async def test_init_callback_raises_exception():
    exception = RuntimeError('Boo!')
    init_callback = Mock(side_effect=exception)
    error_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_to_init_callback,
        init_callback=init_callback,
        error_callback=error_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert init_callback.call_args_list == [call(0)]
    assert proc.exception is exception
    assert error_callback.call_args_list == [call(exception)]

@pytest.mark.asyncio
async def test_info_callback_raises_exception():
    exception = RuntimeError('Boo!')
    info_callback = Mock(side_effect=exception)
    error_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_to_info_callback,
        info_callback=info_callback,
        error_callback=error_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert info_callback.call_args_list == [call(0)]
    assert proc.exception is exception
    assert error_callback.call_args_list == [call(exception)]

@pytest.mark.asyncio
async def test_error_callback_raises_exception():
    exception = RuntimeError('Boo!')
    error_callback = Mock(side_effect=exception)
    proc = DaemonProcess(
        target=target_sending_to_error_callback,
        error_callback=error_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert proc.exception is exception
    assert error_callback.call_args_list == [call(0), call(exception)]

@pytest.mark.asyncio
async def test_finished_callback_raises_exception():
    exception = RuntimeError('Boo!')
    finished_callback = Mock(side_effect=exception)
    error_callback = Mock()
    proc = DaemonProcess(
        target=target_sending_result_to_finished_callback,
        finished_callback=finished_callback,
        error_callback=error_callback,
    )
    proc.start()
    with pytest.raises(RuntimeError, match=r'^Boo!$'):
        await proc.join()
    assert finished_callback.call_args_list == [call('foo')]
    assert proc.exception is exception
    assert error_callback.call_args_list == [call(proc.exception)]
