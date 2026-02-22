"""
Test the 'asyncio.poll' module.
"""

# built-in
import asyncio

# third-party
from pytest import mark

# module under test
from vcorelib.asyncio.poll import repeat_until


@mark.asyncio
async def test_asyncio_repeat_until_basic():
    """Test basic repeat-until scenarios."""

    poll_event = asyncio.Event()

    def sample_task() -> None:
        """Does nothing."""
        poll_event.set()

    async def sample_async_task() -> None:
        """Does nothing."""
        poll_event.set()

    period = 0.1
    timeout = 1.0

    # Should complete right away.
    event = asyncio.Event()
    event.set()
    assert all(
        await asyncio.gather(
            repeat_until(sample_task, event, period, timeout),
            repeat_until(sample_async_task, event, period, timeout),
        )
    )

    # Should time out.
    event = asyncio.Event()
    assert all(
        not x
        for x in await asyncio.gather(
            repeat_until(sample_task, event, period, timeout),
            repeat_until(sample_async_task, event, period, timeout),
        )
    )

    # Clear poll event.
    poll_event.clear()

    event = asyncio.Event()
    tasks = [
        asyncio.create_task(repeat_until(sample_task, event, period, timeout)),
        asyncio.create_task(
            repeat_until(sample_async_task, event, period, timeout)
        ),
    ]

    # Wait for pollers to start.
    await poll_event.wait()

    # End test and clean up.
    event.set()
    for task in tasks:
        assert await task
