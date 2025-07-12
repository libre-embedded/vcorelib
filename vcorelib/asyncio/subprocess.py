"""
A module implementing utilities for working with asyncio subprocesses.
"""

# built-in
from asyncio import create_subprocess_exec
from asyncio.subprocess import Process as _Process
from logging import INFO as _INFO

# internal
from vcorelib.logging import LoggerType
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import rel as _rel
from vcorelib.platform import reconcile_platform


def log_process_info(
    program: str, *args: str, base: _Pathlike = None
) -> tuple[str, str]:
    """
    Get a relative-path program string and a space-delimeted string of the
    arguments, which have also been shortened against a possible relative path.
    """

    return (
        str(_rel(program, base=base)),
        " ".join(str(_rel(x, base=base)) for x in args),
    )


async def create_subprocess_exec_log(
    logger: LoggerType,
    program: str,
    *args: str,
    stdout: int = None,
    stderr: int = None,
    rel: tuple[str, str] = None,
    level: int = _INFO,
    **kwargs,
) -> _Process:
    """
    Create a subprocess and log information about the created process.
    Reconcile subtle platform differences in running simple commands.
    """

    if rel is None:
        rel = log_process_info(program, *args)

    # Use relative paths when logging to reduce output.
    logger.log(level, "exec '%s': %s", rel[0], rel[1])

    program, list_args = reconcile_platform(program, args)
    proc = await create_subprocess_exec(
        program, *list_args, stdout=stdout, stderr=stderr, **kwargs
    )
    return proc
