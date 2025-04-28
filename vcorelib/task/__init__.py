"""
A module for implementing tasks in a dependency tree.
"""

from __future__ import annotations

# built-in
import asyncio as _asyncio
from contextlib import ExitStack as _ExitStack
from json import dumps as _dumps
from logging import Logger, getLogger
from os import linesep as _linesep
from typing import Any as _Any
from typing import Callable as _Callable
from typing import Coroutine as _Coroutine
from typing import Iterable as _Iterable
from typing import Optional as _Optional

# internal
from vcorelib.dict import merge_dicts
from vcorelib.logging import LoggerMixin
from vcorelib.math.time import Timer, nano_str
from vcorelib.target import Substitutions, Target

Outbox = dict[str, _Any]
Inbox = dict[str, Outbox]
TaskExecute = _Callable[[Inbox, Outbox], _Coroutine[_Any, _Any, bool]]
TaskGenerator = _Callable[..., _asyncio.Task[_Any]]


class TaskFailed(Exception):
    """A custom exception to indicate that a task failed."""


class Task(LoggerMixin):  # pylint: disable=too-many-instance-attributes
    """A basic task interface definition."""

    stages = ["run_enter", "run", "run_exit"]
    default_requirements: set[str] = set()

    def __init__(
        self,
        name: str,
        *args,
        execute: TaskExecute = None,
        log: Logger = None,
        timer: Timer = None,
        target: Target = None,
        **kwargs,
    ) -> None:
        """Initialize this task."""

        self.name = name
        self.inbox: Inbox = {}
        self.outbox: Outbox = {}
        self.dependencies: list[TaskGenerator] = []
        self._stack: _Optional[_ExitStack] = None

        # Dependency resolution state.
        self._resolved = False
        self.literals: set[str] = set()

        # Invocation state.
        self._continue = True
        self._running: set[str] = set()
        self._to_signal: int = 0
        self._sem: _Optional[_asyncio.Semaphore] = None

        # Metrics.
        self.times_invoked: int = 0
        self.dependency_time: int = 0
        self.execute_time: int = 0
        if timer is None:
            timer = Timer()
        self.timer = timer

        # Initialize logging.
        super().__init__(logger=log if log is not None else getLogger(name))
        self.log = self.logger

        # Create an execute function if none was provided.
        if execute is None:
            execute = self.create_execute(*args, **kwargs)
        self.execute = execute

        # Create a target if one wasn't provided.
        if target is None:
            target = Target(self.name)
        self.target: Target = target

    def __str__(self) -> str:
        """Convert this task into a string."""
        return self.name

    @property
    def stack(self) -> _ExitStack:
        """Get this task's execution stack."""
        assert self._stack is not None
        return self._stack

    def resolved(
        self, compiled: str, substitutions: Substitutions = None
    ) -> bool:
        """Override this in a derived task to implement more complex logic."""

        # Only a literal target has a boolean resolved state.
        if self.target.literal:
            return self._resolved

        # This task is only resolved if the compiled literal appears in the
        # completed set.
        assert substitutions is not None
        return compiled in self.literals

    def resolve(
        self, log: Logger, compiled: str, substitutions: Substitutions = None
    ) -> None:
        """Mark this task resolved."""

        self._running.remove(compiled)
        self.literals.add(compiled)

        # A literal target only needs to be resovled once.
        if self.target.literal:
            self._resolved = True

        # A non-literal task must have valid substitutions.
        else:
            assert substitutions is not None

        # Signal to any other active tasks that this is complete.
        assert self._sem is not None
        for _ in range(self._to_signal):
            self._sem.release()
        if self._to_signal:
            log.debug("Signaled %d waiting tasks.", self._to_signal)
        self._to_signal = 0

    async def run_enter(
        self, _inbox: Inbox, _outbox: Outbox, *_args, **_kwargs
    ) -> bool:
        """A default enter method."""
        assert self
        return True

    async def run_exit(
        self, _inbox: Inbox, _outbox: Outbox, *_args, **_kwargs
    ) -> bool:
        """A default exit method."""
        assert self
        return True

    async def run(self, inbox: Inbox, outbox: Outbox, *args, **kwargs) -> bool:
        """Override this method to implement the task."""

        self.log.info(
            "inbox=%s, outbox=%s, args=%s, kwargs=%s",
            inbox,
            outbox,
            args,
            kwargs,
        )
        return True

    def create_execute(self, *args, **kwargs) -> TaskExecute:
        """Create a default execute function for this task."""

        async def wrapper(
            inbox: Inbox, outbox: Outbox, **substitutions
        ) -> bool:
            """A default implementation for a basic task. Override this."""

            merged = merge_dicts([{}, kwargs, substitutions], logger=self.log)

            # Run through all of the stages.
            result = True
            self._continue = True
            for stage in self.stages:
                if result and self._continue:
                    result = await getattr(self, stage)(
                        inbox, outbox, *args, **merged
                    )
            return result

        return wrapper

    def depend_on(
        self, task: "Task", eloop: _asyncio.AbstractEventLoop = None, **kwargs
    ) -> bool:
        """
        Register other tasks' output data to your input box. Return true
        if a new dependency was added.
        """

        def task_factory(**substitutions) -> _asyncio.Task[_Any]:
            """
            Create a task while injecting additional keyword arguments.
            """

            nonlocal eloop
            if eloop is None:
                eloop = _asyncio.get_running_loop()

            return eloop.create_task(
                task.dispatch(
                    self,
                    substitutions={**substitutions},
                    **kwargs,
                )
            )

        self.inbox[task.name] = task.outbox
        self.dependencies.append(task_factory)

        return True

    def depend_on_all(self, tasks: _Iterable["Task"], **kwargs) -> int:
        """
        Register multiple dependencies. Return the number of dependencies
        added.
        """

        added_count = 0
        for task in tasks:
            added_count += int(self.depend_on(task, **kwargs))
        return added_count

    async def resolve_dependencies(self, **substitutions) -> None:
        """
        A default dependency resolver for tasks. Note that the default
        dependency resolver cannot propagate current-task substitutions to
        its dependencies as they've already been explicitly registered.
        """
        await _asyncio.gather(*[x(**substitutions) for x in self.dependencies])

    def task_fail(
        self,
        compiled: str,
        substitutions: Substitutions,
        caller: "Task" = None,
        indent: int = 4,
    ) -> TaskFailed:
        """Build an exception message for when this task fails."""

        lines = [
            f"Task '{compiled}' failed in {nano_str(self.execute_time)}s."
        ]
        if caller is not None:
            lines.append(f"Called by: '{caller}'")
        lines.append(_dumps(substitutions, indent=indent))
        return TaskFailed(_linesep.join(lines))

    def dispatch_init(
        self,
        caller: "Task" = None,
        substitutions: Substitutions = None,
        **kwargs,
    ) -> tuple[Substitutions, str]:
        """Perform some dispatch initialization."""

        self.times_invoked += 1

        if caller is not None:
            self.log.debug("triggered by '%s'", caller)

        if substitutions is None:
            substitutions = {}

        # Merge substitutions in with other command-line arguments.
        merged = merge_dicts([{}, substitutions, kwargs], logger=self.log)
        compiled = self.target.compile(merged)

        # Wire our outbox to the caller's inbox.
        if caller is not None:
            caller.inbox[compiled] = self.outbox

        return merged, compiled

    async def dispatch(
        self,
        caller: "Task" = None,
        init_only: bool = False,
        substitutions: Substitutions = None,
        **kwargs,
    ) -> None:
        """Dispatch this task and return whether or not it succeeded."""

        merged, compiled = self.dispatch_init(
            caller=caller, substitutions=substitutions, **kwargs
        )

        # Return early if this task has already been executed.
        if self.resolved(compiled, merged):
            return

        if self._sem is None:
            self._sem = _asyncio.Semaphore(0)

        log = getLogger(compiled)
        if merged and self.times_invoked == 1:
            log.debug("substitutions: '%s'", merged)

        try:
            # If this task is already running, wait for it to complete.
            if compiled in self._running:
                self._to_signal += 1
                log.debug("Waiting for existing '%s' to resolve.", compiled)
                await self._sem.acquire()
                return

            # Signal to other task invocations that this instance is running.
            self._running.add(compiled)

            # Reset the outbox for this execution. Don't re-assign it or it
            # will lose its association with anything depending on it.
            for key in list(self.outbox.keys()):
                self.outbox.pop(key)

            # Wait for dependencies to finish processing.
            with self.timer.measure_ns() as token:
                await self.resolve_dependencies(**merged)
            self.dependency_time = self.timer.result(token)
            log.debug("dependencies: %ss", nano_str(self.dependency_time))

            # Allow a dry-run pass get only this far (before executing).
            if init_only:
                return

            with self.timer.measure_ns() as token:
                # Execute this task and don't propagate to tasks if this task
                # failed.
                with _ExitStack() as stack:
                    self._stack = stack
                    result = await self.execute(
                        self.inbox, self.outbox, **merged
                    )
            self.execute_time = self.timer.result(token)

            # Raise an exception if this task failed.
            if not result:
                raise self.task_fail(compiled, merged, caller)

            log.debug("execute: %ss", nano_str(self.execute_time))

            # Track that this task was resolved.
            self.resolve(log, compiled, merged)

        # Handle cancellation to simplify cleaning up the event loop.
        except _asyncio.CancelledError:
            log.warning("Task '%s' was cancelled!", self.name)


class Phony(Task):
    """
    A task stub that doesn't do anything. Useful for top-level targets that
    depend on other concrete tasks.
    """

    async def run(self, inbox: Inbox, outbox: Outbox, *args, **kwargs) -> bool:
        """Override this method to implement the task."""

        # Pass the inbox items through to the outbox. This makes phony tasks
        # much more useful.
        for key, value in inbox.items():
            outbox[key] = value
        return True


class FailTask(Task):
    """A task that always fails."""

    async def run(self, inbox: Inbox, outbox: Outbox, *args, **kwargs) -> bool:
        """Task fails by default."""
        assert self.stack
        return False
