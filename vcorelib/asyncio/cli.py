"""
A module implementing utilities to work with asyncio processes.
"""

# built-in
from asyncio import CancelledError as _CancelledError
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE as _PIPE
from asyncio.subprocess import Process as _Process
from contextlib import suppress
from logging import INFO as _INFO
import signal as _signal
from typing import NamedTuple, Optional

# internal
from vcorelib.asyncio.subprocess import (
    create_subprocess_exec_log,
    log_process_info,
)
from vcorelib.logging import LoggerType, log_time


class ProcessResult(NamedTuple):
    """A process result (after calling 'communicate')."""

    proc: _Process
    stdout: Optional[bytes] = None
    stderr: Optional[bytes] = None


async def handle_process_cancel(
    proc: _Process,
    name: str,
    logger: LoggerType,
    stdin: bytes = None,
    signal: int = None,
    level: int = _INFO,
) -> ProcessResult:
    """
    Communicate with a process and send a signal to it if this task gets
    cancelled.
    """

    stdout_data = None
    stderr_data = None

    # Default to a valid interrupt signal.
    if signal is None:
        signal = getattr(_signal, "CTRL_C_EVENT", _signal.SIGINT)
    assert signal is not None

    try:
        with log_time(
            logger, "Process '%s' (%d)", name, proc.pid, level=level
        ):
            stdout_data, stderr_data = await proc.communicate(input=stdin)

    except _CancelledError:
        with suppress(ProcessLookupError):
            # Send the process a signal and wait for it to terminate.
            proc.send_signal(signal)
            logger.warning(
                "Sending signal %d to process '%s' (%d).",
                signal,
                name,
                proc.pid,
            )
        await proc.wait()
        raise

    finally:
        if proc.returncode is not None:
            logger.log(
                level,
                "Process '%s' (%d) exited %d.",
                name,
                proc.pid,
                proc.returncode,
            )

    return ProcessResult(proc, stdout_data, stderr_data)


async def run_command(
    logger: LoggerType,
    *args: str,
    stdin: bytes = None,
    stdout: int = None,
    stderr: int = None,
    signal: int = None,
    level: int = _INFO,
    **kwargs,
) -> ProcessResult:
    """Run a subprocess and return the completed process."""

    rel = log_process_info(*args)

    with log_time(logger, "Command '%s'", rel[0], level=level):
        proc = await handle_process_cancel(
            await create_subprocess_exec_log(
                logger,
                *args,
                stdout=stdout,
                stderr=stderr,
                stdin=_PIPE if stdin else None,
                level=level,
                **kwargs,
            ),
            rel[0],
            logger,
            stdin=stdin,
            signal=signal,
            level=level,
        )

    return proc


async def create_subprocess_shell_log(
    logger: LoggerType,
    command: str,
    stdout: int = None,
    stderr: int = None,
    level: int = _INFO,
    **kwargs,
) -> _Process:
    """
    Create a shell process and log information about the created process.
    """

    logger.log(level, "shell: '%s'", command)
    return await create_subprocess_shell(
        command, stdout=stdout, stderr=stderr, **kwargs
    )


async def run_shell(
    logger: LoggerType,
    *args: str,
    stdin: bytes = None,
    stdout: int = None,
    stderr: int = None,
    signal: int = None,
    level: int = _INFO,
    **kwargs,
) -> ProcessResult:
    """Run a shell command and return the completed process."""

    rel = log_process_info(*args)

    with log_time(logger, "Shell '%s'", rel[0], level=level):
        proc = await handle_process_cancel(
            await create_subprocess_shell_log(
                logger,
                " ".join(args),
                stdout=stdout,
                stderr=stderr,
                stdin=_PIPE if stdin else None,
                level=level,
                **kwargs,
            ),
            rel[0],
            logger,
            stdin=stdin,
            signal=signal,
            level=level,
        )

    return proc
