"""
A module for testing the interrupt-handling behavior of 'run_handle_interrupt'
and async sub-process management.
"""

# built-in
import asyncio
from contextlib import suppress
from os import remove
import signal
import sys
import tempfile
from textwrap import dedent

# module under test
from vcorelib.asyncio import (
    all_stop_signals,
    log_exceptions,
    run_handle_interrupt,
)
from vcorelib.task import TaskFailed
from vcorelib.task.subprocess.run import SubprocessExecStreamed


def interrupt_raiser(*_) -> None:
    """Un-conditionally raise a keyboard interrupt."""
    print("Got interrupt signal!")
    raise KeyboardInterrupt()


def task_runner() -> None:
    """Run an event-loop task that will spawn a process that sleeps."""

    for sig in list(all_stop_signals()):
        # Install signal handlers to translate terminations to
        # KeyboardInterrupt.
        with suppress(ValueError):
            signal.signal(sig, interrupt_raiser)

    program = """
    sleep_time = 2
    print(f"Starting {sleep_time} second sleep.")

    import time
    import sys
    try:
        time.sleep(sleep_time)
        print(f"Finished {sleep_time} second sleep.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Inline script got interrupted!")
        sys.exit(0)
    """

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as temp:
        temp.write(dedent(program).strip())
        temp.flush()
        name = temp.name

    try:
        task = SubprocessExecStreamed(
            "sleeper", name, args="", start_new_session=True
        )

        # Create an event-loop and ensure it's associated with the
        # main thread.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task_inst = loop.create_task(task.dispatch())
        try:
            run_handle_interrupt(task_inst, loop)

        # The task succeeds only if the command exited zero.
        except TaskFailed:
            sys.exit(1)

    finally:
        log_exceptions([task_inst])
        remove(name)

    sys.exit(0)


if __name__ == "__main__":
    task_runner()
