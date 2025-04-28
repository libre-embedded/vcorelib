"""
Math utilities involving units of time and other conversions.
"""

# built-in
from contextlib import contextmanager
from io import StringIO
from logging import INFO as _INFO
from logging import Logger as _Logger
from logging import LoggerAdapter as _LoggerAdapter
from math import floor as _floor
from time import perf_counter_ns as _perf_counter_ns
from typing import Any as _Any
from typing import Iterator as _Iterator
from typing import Union as _Union

# internal
from vcorelib.math.constants import to_nanos
from vcorelib.math.keeper import SimulatedTime as _SimulatedTime
from vcorelib.math.keeper import TIME as _TIME
from vcorelib.math.unit import KIBI_UNITS as _KIBI_UNITS
from vcorelib.math.unit import SI_UNITS as _SI_UNITS
from vcorelib.math.unit import UnitSystem as _UnitSystem
from vcorelib.math.unit import unit_traverse as _unit_traverse


def default_time_ns() -> int:
    """Get a timestamp value using a default method."""
    return _TIME()


def metrics_time_ns() -> int:
    """Get a timestamp suitable for runtime performance metrics."""
    return _perf_counter_ns()


def set_simulated_source(source: _SimulatedTime) -> None:
    """Set a simulated time source for the global clock."""
    _TIME.source = source


def restore_time_source() -> None:
    """Restore the original global time source."""
    _TIME.restore()


@contextmanager
def simulated_time(
    step_dt_ns: int = 1, start_ns: int = None
) -> _Iterator[_SimulatedTime]:
    """Take control over the default time source as a managed context."""

    with _TIME.simulated(
        step_dt_ns=step_dt_ns, start_ns=start_ns
    ) as simulated:
        yield simulated


def seconds_str(seconds: int) -> tuple[str, int]:
    """
    Attempt to characterize a large amount of seconds into a string describing
    hours and minutes, returning the string (may be empty) and the seconds
    left over.
    """

    result = ""

    minutes = 0
    if seconds >= 60:
        minutes = seconds // 60
        seconds = seconds % 60
        result = f"{minutes}m"

    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        result = f"{hours}h {minutes}m"

    return result, seconds


def nano_str(
    nanos: int,
    is_time: bool = False,
    max_prefix: int = 3,
    unit: _UnitSystem = _SI_UNITS,
    prefix_space: bool = False,
    iteration: int = 0,
) -> str:
    """
    Convert an arbitrary value in a 10^-9 domain into as concise of a string
    as possible.
    """

    decimal, fractional, prefix = _unit_traverse(
        nanos, unit, max_prefix, iteration
    )

    with StringIO() as stream:
        if not prefix and is_time:
            result, decimal = seconds_str(decimal)
            stream.write(result)
            if result:
                stream.write(" ")

        # Normalize the fractional component if necessary.
        if unit.divisor != 1000 and fractional != 0:
            fractional = _floor(float(fractional / unit.divisor) * 1000.0)

        stream.write(str(decimal))
        if fractional:
            stream.write(f".{fractional:03}")
        if prefix_space:
            stream.write(" ")
        stream.write(prefix)
        return stream.getvalue()


def rate_str(period_s: float) -> str:
    """Get a string representing a rate in Hz."""

    period_str = nano_str(to_nanos(period_s))
    freq_str = nano_str(to_nanos(1.0 / period_s), prefix_space=True)
    return f"{freq_str}Hz ({period_str}s)"


def byte_count_str(byte_count: int) -> str:
    """Get a string representing a number of bytes."""
    return nano_str(byte_count, False, 99, _KIBI_UNITS, True) + "B"


LoggerType = _Union[_Logger, _LoggerAdapter[_Any]]


class Timer:
    """A class for measuring and logging how long events take."""

    def __init__(self) -> None:
        """Initialize this timer."""

        self.curr: int = 0
        self.data: dict[int, int] = {}

    @contextmanager
    def measure_ns(self) -> _Iterator[int]:
        """
        Compute the time that the caller's context takes, provides an integer
        token that can be used to query for the result afterwards.
        """

        curr = self.curr
        self.curr += 1
        start = metrics_time_ns()
        try:
            yield curr
        finally:
            self.data[curr] = metrics_time_ns() - start

    def result(self, token: int) -> int:
        """Get the timer result."""
        return self.data.pop(token, -1)

    @contextmanager
    def log(
        self,
        log: LoggerType,
        message: str,
        *args,
        level: int = _INFO,
        reminder: bool = False,
        **kwargs,
    ) -> _Iterator[None]:
        """Log how long the caller's context took to execute."""

        if reminder:
            log.log(level, message + " is executing.", *args, **kwargs)

        with self.measure_ns() as token:
            yield
        result = self.result(token)

        # Log the duration spent yielded.
        log.log(
            level,
            message + " completed in %ss.",
            *args,
            nano_str(result, True),
            **kwargs,
        )


TIMER = Timer()
