"""
A module for working with asyncio.
"""

# built-in
import asyncio as _asyncio
from contextlib import contextmanager
from contextlib import suppress as _suppress
from logging import getLogger as _getLogger
import signal as _signal
import time as _time
from types import FrameType as _FrameType
from typing import Any as _Any
from typing import Awaitable as _Awaitable
from typing import Callable as _Callable
from typing import Coroutine as _Coroutine
from typing import Iterable as _Iterable
from typing import Iterator
from typing import Optional as _Optional
from typing import TypeVar as _TypeVar

# internal
from vcorelib.logging import LoggerType as _LoggerType

T = _TypeVar("T")
LOG = _getLogger(__name__)


def log_task_exception(
    task: _asyncio.Task[_Any], logger: _LoggerType = None
) -> None:
    """If a task is done and raised an exception, log it."""

    if logger is None:
        logger = LOG

    if task.done():
        with _suppress(_asyncio.CancelledError):
            exc = task.exception()
            if (
                exc is not None
                and not isinstance(exc, _asyncio.CancelledError)
                and not isinstance(exc, KeyboardInterrupt)
            ):
                logger.exception("Task raised exception:", exc_info=exc)


def log_exceptions(
    tasks: _Iterable[_asyncio.Task[T]], logger: _LoggerType = None
) -> list[_asyncio.Task[T]]:
    """Log task exception and return the list of tasks that aren't complete."""

    for task in tasks:
        log_task_exception(task, logger=logger)
    return [x for x in tasks if not x.done()]


def new_eloop(set_current: bool = True) -> _asyncio.AbstractEventLoop:
    """Get a new event loop."""

    eloop = _asyncio.new_event_loop()
    if set_current:
        _asyncio.set_event_loop(eloop)
    return eloop


def normalize_eloop(
    eloop: _asyncio.AbstractEventLoop = None,
) -> _asyncio.AbstractEventLoop:
    """Get the active event loop if one isn't provided explicitly."""

    if eloop is None:
        try:
            eloop = _asyncio.get_running_loop()
        except RuntimeError:
            eloop = new_eloop()
    return eloop


def shutdown_loop(
    eloop: _asyncio.AbstractEventLoop = None, logger: _LoggerType = None
) -> None:
    """Attempt to shut down an event loop."""

    eloop = normalize_eloop(eloop)
    eloop.run_until_complete(eloop.shutdown_asyncgens())

    tasks = log_exceptions(_asyncio.all_tasks(loop=eloop), logger=logger)
    if tasks:
        # Cancel all tasks running in the event loop.
        for task in tasks:
            task.cancel()

            # Give all tasks a chance to complete.
            with _suppress(KeyboardInterrupt, _asyncio.CancelledError):
                eloop.run_until_complete(task)
                log_task_exception(task, logger=logger)


def run_handle_interrupt(
    to_run: _Awaitable[T],
    eloop: _asyncio.AbstractEventLoop = None,
    enable_uvloop: bool = True,
) -> _Optional[T]:
    """
    Run a task in an event loop and gracefully handle keyboard interrupts.

    Return the result of the awaitable or None if execution was interrupted.
    """

    with try_uvloop_runner(eloop=eloop, enable=enable_uvloop) as loop:
        result = None
        try:
            result = loop.run_until_complete(to_run)
        except KeyboardInterrupt:
            shutdown_loop(loop)

    return result


SignalHandler = _Callable[[int, _Optional[_FrameType]], None]


def event_setter(
    stop_sig: _asyncio.Event,
    eloop: _asyncio.AbstractEventLoop = None,
    logger: _LoggerType = None,
) -> SignalHandler:
    """Create a function that sets an event."""

    if logger is None:
        logger = LOG

    def setter(sig: int, _: _Optional[_FrameType]) -> None:
        """Set the signal."""

        rep = f"{sig} ({_signal.Signals(sig).name})"
        LOG.info("Received signal %s.", rep)

        # Ensure scheduling 'stop_sig.set' is a nominal reaction to this
        # signal.
        normalize_eloop(eloop).call_soon_threadsafe(stop_sig.set)

    return setter


def all_stop_signals() -> set[int]:
    """Get a set of all stop signals on this platform."""

    return {
        _signal.SIGINT,
        getattr(_signal, "SIGBREAK", _signal.SIGINT),
        getattr(_signal, "CTRL_C_EVENT", _signal.SIGINT),
        getattr(_signal, "CTRL_BREAK_EVENT", _signal.SIGINT),
        _signal.SIGTERM,
    }


def run_handle_stop(
    stop_sig: _asyncio.Event,
    task: _Coroutine[None, None, T],
    eloop: _asyncio.AbstractEventLoop = None,
    signals: _Iterable[int] = None,
    enable_uvloop: bool = True,
) -> _Optional[T]:
    """
    Publish the stop signal on keyboard interrupt and wait for the task to
    complete.
    """

    result = None

    with try_uvloop_runner(eloop=eloop, enable=enable_uvloop) as loop:
        to_run = loop.create_task(task)

        # Register signal handlers if signals were provided.
        if signals is not None:
            setter = event_setter(stop_sig, eloop=loop)
            for signal in signals:
                _signal.signal(signal, setter)

        while not to_run.done() and not loop.is_closed():
            try:
                if not loop.is_running():
                    loop.run_until_complete(to_run)
                else:  # pragma: nocover
                    _time.sleep(0.1)
            except KeyboardInterrupt:
                with _suppress(KeyboardInterrupt):
                    loop.call_soon_threadsafe(stop_sig.set)

        if to_run.done():
            result = to_run.result()

    return result


@contextmanager
def try_uvloop_runner(
    eloop: _asyncio.AbstractEventLoop = None, enable: bool = True
) -> Iterator[_asyncio.AbstractEventLoop]:
    """Try to set up an asyncio runner using uvloop."""

    if enable and eloop is None:
        with _suppress(ImportError):
            # pylint: disable=import-outside-toplevel
            import uvloop

            # pylint: enable=import-outside-toplevel

            eloop = uvloop.new_event_loop()

    yield normalize_eloop(eloop)
