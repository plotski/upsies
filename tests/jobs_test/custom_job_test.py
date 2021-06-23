import asyncio
from unittest.mock import Mock, call

import pytest

from upsies.jobs.custom import CustomJob


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@pytest.fixture
def make_CustomJob(tmp_path):
    def make_CustomJob(**kwargs):
        return CustomJob(home_directory=tmp_path, cache_directory=tmp_path, **kwargs)
    return make_CustomJob


def test_name(make_CustomJob):
    job = make_CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job.name == 'foo'


def test_label(make_CustomJob):
    job = make_CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job.label == 'Foo'


def test_initialize(make_CustomJob):
    worker = AsyncMock()
    job = make_CustomJob(name='foo', label='Foo', worker=worker)
    assert job._worker is worker
    assert job._task is None


@pytest.mark.asyncio
async def test_execute(mocker, make_CustomJob):
    mocker.patch('upsies.jobs.custom.CustomJob.add_task')
    mocker.patch('upsies.jobs.custom.CustomJob._catch_errors', Mock())
    worker = Mock()
    job = make_CustomJob(name='foo', label='Foo', worker=worker)
    job.execute()
    assert job._task is job.add_task.return_value
    assert job.add_task.call_args_list == [call(
        job._catch_errors.return_value,
        callback=job._handle_worker_done,
    )]
    assert job._catch_errors.call_args_list == [call(worker.return_value)]
    assert worker.call_args_list == [call(job)]


@pytest.mark.asyncio
async def test_CancelledError_from_worker_is_ignored(make_CustomJob):
    worker = AsyncMock(side_effect=asyncio.CancelledError())
    job = make_CustomJob(name='foo', label='Foo', worker=worker)
    job.execute()
    # Does not raise CancelledError
    await job._task

@pytest.mark.asyncio
async def test_expected_exceptions_from_worker_are_caught(mocker, make_CustomJob):
    worker = AsyncMock(side_effect=ValueError('ouch'))
    job = make_CustomJob(name='foo', label='Foo', worker=worker, catch=[ValueError])
    job.execute()
    await job._task
    assert isinstance(job.errors[0], ValueError)
    assert str(job.errors[0]) == 'ouch'
    assert len(job.errors) == 1

@pytest.mark.asyncio
async def test_unexpected_exceptions_from_worker_are_raised(mocker, make_CustomJob):
    worker = AsyncMock(side_effect=ValueError('ouch'))
    job = make_CustomJob(name='foo', label='Foo', worker=worker, catch=[TypeError])
    job.execute()
    mocker.patch.object(job, 'exception')
    await job.await_tasks()
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
async def test_return_value_from_worker_is_output(return_value, exp_output, mocker, make_CustomJob):
    worker = AsyncMock(return_value=return_value)
    job = make_CustomJob(name='foo', label='Foo', worker=worker)
    job.execute()
    await job.wait()
    assert job.output == exp_output


@pytest.mark.asyncio
async def test_wait_before_job_was_executed(mocker, make_CustomJob):
    job = make_CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job._task is None
    job.finish()
    await job.wait()
    assert job._task is None
    assert job.is_finished

@pytest.mark.asyncio
async def test_wait_after_job_was_executed(mocker, make_CustomJob):
    job = make_CustomJob(name='foo', label='Foo', worker=lambda job: asyncio.sleep(10))
    job.execute()
    # Allow worker to start
    for _ in range(5):
        await asyncio.sleep(0)
    assert not job._task.done()
    job.finish()
    await job.wait()
    assert job._task.done()
    assert job.is_finished


@pytest.mark.asyncio
async def test_finish_before_job_was_executed(mocker, make_CustomJob):
    job = make_CustomJob(name='foo', label='Foo', worker=AsyncMock())
    assert job._task is None
    job.finish()
    assert job._task is None
    assert job.is_finished

@pytest.mark.asyncio
async def test_finish_after_job_was_executed(mocker, make_CustomJob):
    worker = asyncio.ensure_future(asyncio.sleep(100))
    job = make_CustomJob(name='foo', label='Foo', worker=lambda job: worker)
    job.execute()
    # Allow worker to start
    for _ in range(5):
        await asyncio.sleep(0)
    assert not worker.cancelled()
    job.finish()
    await job.wait()
    assert worker.cancelled()
    assert job.is_finished
