"""
Utilities for logging information.
"""

# built-in
from contextlib import contextmanager
from logging import Formatter, Logger, LoggerAdapter, LogRecord
from logging import INFO as _INFO
from logging import getLogger as _GetLogger
from logging.handlers import QueueHandler
from queue import SimpleQueue
from typing import Iterator as _Iterator

# internal
from vcorelib.logging.args import (
    DEFAULT_FORMAT,
    DEFAULT_TIME_FORMAT,
    forward_flags,
    forward_logging_flags,
    init_logging,
    logging_args,
)
from vcorelib.logging.list import ListLogger
from vcorelib.logging.time import log_time
from vcorelib.math import RateLimiter
from vcorelib.math.time import TIMER, LoggerType

__all__ = [
    "ListLogger",
    "LoggerType",
    "log_time",
    "LoggerMixin",
    "TIMER",
    "LogRecordQueue",
    "normalize",
    "DEFAULT_FORMAT",
    "DEFAULT_TIME_FORMAT",
    "init_logging",
    "logging_args",
    "forward_flags",
    "forward_logging_flags",
]

LogRecordQueue = SimpleQueue[LogRecord]


def normalize(logger: LoggerType) -> Logger:
    """Normalize a logger instance."""

    if isinstance(logger, LoggerAdapter):
        logger = logger.logger

    assert isinstance(logger, Logger)
    return logger


def queue_handler(
    logger: LoggerType,
    queue: LogRecordQueue = None,
    handler: QueueHandler = None,
    root_formatter: bool = True,
) -> tuple[LogRecordQueue, QueueHandler]:
    """
    Set up and return a simple queue and logging queue handler. Use the
    provided objects if they already exist.
    """

    if queue is None:
        queue = SimpleQueue()
    if handler is None:
        handler = QueueHandler(queue)

    if root_formatter:
        # There may not be an existing handler, so use a sane default.
        handler.setFormatter(
            Logger.root.handlers[0].formatter
            if Logger.root.handlers
            else Formatter(DEFAULT_TIME_FORMAT)
        )

    normalize(logger).addHandler(handler)

    return queue, handler


class LoggerMixin:
    """A class that provides an inheriting class a logger attribute."""

    logger: LoggerType

    def __init__(
        self, logger: LoggerType = None, logger_name: str = None
    ) -> None:
        """Initialize this object with logging capabilities."""

        if not hasattr(self, "logger"):
            # Set a logger for this class instance.
            if logger is None:
                if logger_name is None:
                    logger_name = self.__class__.__module__
                logger = _GetLogger(logger_name)
            self.logger = logger

    def governed_log(
        self,
        limiter: RateLimiter,
        message: str,
        *args,
        level: int = _INFO,
        time_ns: int = None,
        **kwargs,
    ) -> None:
        """Log a message but limit the rate."""

        if limiter(time_ns=time_ns):
            skips = limiter.skips
            if skips:
                message += f" ({skips} messages skipped)"
            self.logger.log(level, message, *args, **kwargs)

    @contextmanager
    def log_time(
        self,
        message: str,
        *args,
        level: int = _INFO,
        reminder: bool = False,
        **kwargs,
    ) -> _Iterator[None]:
        """A simple wrapper."""

        with log_time(
            self.logger,
            message,
            *args,
            level=level,
            reminder=reminder,
            **kwargs,
        ):
            yield
