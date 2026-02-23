"""
A module implementing a simple task-polling interface.
"""

# built-in
import asyncio
from contextlib import suppress
from inspect import iscoroutinefunction
from typing import Awaitable, Callable


async def repeat_until(
    task: Callable[[], None | Awaitable[None]],
    event: asyncio.Event,
    period: float,
    timeout: float,
) -> bool:
    """
    Repeat a task until the provided event is set. Returns True if the
    event triggered this function to clean up and exit.
    """

    async def poller() -> None:
        """Poll the task at the requested period."""

        eloop = asyncio.get_running_loop()

        do_await = iscoroutinefunction(task)

        with suppress(asyncio.CancelledError):
            while not event.is_set():
                start = eloop.time()

                if do_await:
                    await task()  # type: ignore
                else:
                    task()

                await asyncio.sleep(max(0, period - (eloop.time() - start)))

    poll_task = asyncio.create_task(poller())

    # Determine if the event was set externally (success) or if this method
    # timed out waiting for it.
    result = False
    with suppress(TimeoutError):
        await asyncio.wait_for(event.wait(), timeout)
        result = event.is_set()

    # Clean up.
    if not poll_task.done():
        poll_task.cancel()
        with suppress(asyncio.CancelledError):
            await poll_task

    return result
