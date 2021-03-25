import asyncio
from unittest.mock import Mock

import pytest

from upsies.jobs.custom import CustomJob


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


def test_name():
    job = CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job.name == 'foo'


def test_label():
    job = CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job.label == 'Foo'


def test_initialize():
    worker = AsyncMock()
    job = CustomJob(name='foo', label='Foo', worker=worker)
    assert job._worker is worker
    assert job._task is None


@pytest.mark.asyncio
async def test_execute(mocker):
    async def worker(job):
        assert isinstance(job, CustomJob)
        worker_calls.append('called')

    worker_calls = []
    job = CustomJob(name='foo', label='Foo', worker=worker)
    mocker.patch.object(job, '_handle_worker_done')
    job.execute()
    await job._task
    assert worker_calls == ['called']
    assert job._handle_worker_done.called


@pytest.mark.asyncio
async def test_CancelledError_from_worker_is_ignored():
    worker = AsyncMock(side_effect=asyncio.CancelledError())
    job = CustomJob(name='foo', label='Foo', worker=worker)
    job.execute()
    # Does not raise CancelledError
    await job._task

@pytest.mark.asyncio
async def test_other_exceptions_from_worker_are_caught(mocker):
    worker = AsyncMock(side_effect=ValueError('ouch'))
    job = CustomJob(name='foo', label='Foo', worker=worker)
    job.execute()
    mocker.patch.object(job, 'exception')
    with pytest.raises(ValueError, match=r'^ouch$'):
        await job._task
    assert isinstance(job.exception.call_args_list[0][0][0], ValueError)
    assert str(job.exception.call_args_list[0][0][0]) == 'ouch'

@pytest.mark.parametrize(
    argnames='return_value, exp_output',
    argvalues=(
        ('foo', ('foo',)),
        (None, ()),
    ),
    ids=lambda v: str(v),
)
@pytest.mark.asyncio
async def test_return_value_from_worker_is_output(return_value, exp_output, mocker):
    worker = AsyncMock(return_value=return_value)
    job = CustomJob(name='foo', label='Foo', worker=worker)
    job.execute()
    await job.wait()
    assert job.output == exp_output


@pytest.mark.asyncio
async def test_wait_before_job_was_executed(mocker):
    job = CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job._task is None
    job.finish()
    await job.wait()
    assert job._task is None
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_after_job_was_executed(mocker):
    job = CustomJob(name='foo', label='Foo', worker=lambda job: asyncio.sleep(10))
    job.execute()
    # Allow worker to start
    await asyncio.sleep(0)
    assert not job._task.done()
    job.finish()
    await job.wait()
    assert job._task.done()
    assert job.is_finished


@pytest.mark.asyncio
async def test_finish_before_job_was_executed(mocker):
    job = CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job._task is None
    job.finish()
    assert job._task is None
    assert job.is_finished

@pytest.mark.asyncio
async def test_finish_after_job_was_executed(mocker):
    worker = asyncio.ensure_future(asyncio.sleep(100))
    job = CustomJob(name='foo', label='Foo', worker=lambda job: worker)
    job.execute()
    # Allow worker to start
    await asyncio.sleep(0)
    assert not worker.cancelled()
    job.finish()
    await job.wait()
    assert worker.cancelled()
    assert job.is_finished