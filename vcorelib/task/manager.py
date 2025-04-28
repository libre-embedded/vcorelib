"""
A simple task management interface.
"""

# built-in
from asyncio import gather
from asyncio import new_event_loop as _new_event_loop
from collections import defaultdict
from typing import Any as _Any
from typing import Callable as _Callable
from typing import Coroutine as _Coroutine
from typing import Iterable as _Iterable
from typing import cast

# internal
from vcorelib.asyncio import run_handle_interrupt as _run_handle_interrupt
from vcorelib.asyncio import shutdown_loop as _shutdown_loop
from vcorelib.dict import merge
from vcorelib.script import ScriptableMixin
from vcorelib.target import TargetMatch
from vcorelib.target.resolver import TargetResolver
from vcorelib.task import Task, TaskFailed

BasicCoroutine = _Callable[[], _Coroutine[_Any, _Any, None]]


class TaskManager(ScriptableMixin):
    """
    A class for managing concurrent execution of tasks and also interfacing
    them via names.
    """

    def __init__(self, resolver: TargetResolver = None) -> None:
        """Initialize this task manager."""

        super().__init__()
        self.tasks: dict[str, Task] = {}
        self.dependencies: dict[str, set[str]] = defaultdict(set)
        self.finalized: bool = False
        if resolver is None:
            resolver = TargetResolver()
        self.resolver = resolver
        self.eloop = _new_event_loop()

    def register(
        self,
        task: Task,
        dependencies: _Iterable[str] = None,
        target: str = None,
    ) -> bool:
        """Register a new task and apply any requested dependencies."""

        new_task = False

        # Register this target so that it will return the provided task if
        # matched.
        if target is None:
            target = task.name

        # Don't take any action if we didn't actually register the task.
        if self.resolver.register(target, task):
            self.tasks[task.name] = task
            new_task = True

        # If we're adding more dependencies, make sure it's for the same task.
        else:
            assert self.tasks[task.name] == task

        if dependencies is None:
            dependencies = set()

        self.dependencies[task.name].update(dependencies)

        # Also add this task's default requirements, if there are any.
        self.dependencies[task.name].update(task.default_requirements)

        self.finalized = False
        return new_task

    def register_to(self, target: str, dependencies: _Iterable[str]) -> bool:
        """Register dependencies to a task by name."""
        return self.register(self.tasks[target], dependencies)

    def finalize(self, **kwargs) -> None:
        """Register task dependencies while the event loop is running."""

        if not self.finalized:
            for task, deps in self.dependencies.items():
                task_obj = self.tasks[task]
                task_obj.dependencies = []
                for dep in deps:
                    # If the dependency points to a task by name, add it.
                    if dep in self.tasks:
                        task_obj.depend_on(
                            self.tasks[dep], eloop=self.eloop, **kwargs
                        )
                        continue

                    # Ensure the dependency can be matched to a task otherwise.
                    resolution = self.resolver.evaluate(dep)
                    assert (
                        resolution
                    ), f"Couldn't match '{dep}' to task '{task}'!"

                    assert resolution.data is not None

                    # Make sure the substitutions from the target resolution
                    # make it to the dependency registration.
                    assert resolution.result.substitutions is not None
                    task_obj.depend_on(
                        cast(Task, resolution.data),
                        eloop=self.eloop,
                        **merge(
                            {**kwargs},
                            resolution.result.substitutions,
                            expect_overwrite=True,
                        ),
                    )

            self.finalized = True

    def evaluate(
        self, tasks: _Iterable[str], **kwargs
    ) -> tuple[list[tuple[Task, TargetMatch]], set[str]]:
        """
        Iterate over task strings and provide a list of tasks that can be
        executed (plus relevant data from matching the target) as well as
        the set of tasks that can't be resolved.
        """

        # Ensure task dependencies are added.
        self.finalize(**kwargs)

        unresolved: set[str] = set()
        task_objs: list[tuple[Task, TargetMatch]] = []
        for resolved in self.resolver.evaluate_all(tasks):
            if isinstance(resolved, str):
                unresolved.add(resolved)
                continue
            task_objs.append((cast(Task, resolved.data), resolved.result))

        return task_objs, unresolved

    def prepare_execute(
        self, tasks: _Iterable[str], **kwargs
    ) -> tuple[set[str], BasicCoroutine]:
        """
        Gather tasks that can and can't be executed to prepare a function that
        can execute tasks and also return the task strings that wouldn't be
        resolved.
        """

        task_objs, unresolved = self.evaluate(tasks, **kwargs)

        async def executor() -> None:
            """Wait for all of the configured tasks to complete."""

            # Run all tasks together in the event loop.
            await gather(
                *[
                    x[0].dispatch(substitutions=x[1].substitutions, **kwargs)
                    for x in task_objs
                ]
            )

        return unresolved, executor

    def execute(self, tasks: _Iterable[str], **kwargs) -> set[str]:
        """
        Execute some set of provided tasks. Return the tasks that don't get
        resolved.
        """

        unresolved, executor = self.prepare_execute(tasks, **kwargs)
        try:
            _run_handle_interrupt(executor(), eloop=self.eloop)

        # Ensure that tasks are cancelled on failure.
        except TaskFailed:
            _shutdown_loop(self.eloop)
            raise

        return unresolved
