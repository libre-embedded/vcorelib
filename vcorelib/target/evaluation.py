"""
A module for target-evaluation interfaces.
"""

from __future__ import annotations

from abc import ABC as _ABC
from abc import abstractmethod as _abstractmethod

# built-in
import re
from typing import Generic as _Generic
from typing import Optional as _Optional
from typing import TypeVar as _TypeVar

Substitutions = dict[str, str | int]
T = _TypeVar("T", bound="TargetEvaluatorInterface")


class TargetEvaluatorInterface(_ABC):
    """An interface for evaluating targets."""

    def __init__(
        self, original: str, keys: list[str], markers: list[tuple[int, int]]
    ) -> None:
        """Initialize this evaluator."""

        self.original = original
        self.keys = keys
        self.markers = markers

    @_abstractmethod
    def compile_key(self, key: str, values: Substitutions) -> str:
        """Process the key based on substitution data."""

    def compile(self, values: Substitutions) -> str:
        """
        Build a string from this target with values replaced for keys that
        appeared in the original string.
        """

        result = ""
        orig_idx = 0

        for key, marker in zip(self.keys, self.markers):
            result += self.original[orig_idx : marker[0]]
            result += self.compile_key(key, values)
            orig_idx = marker[1] + 1

        return result + self.original[orig_idx:]


class TargetInterface(_ABC, _Generic[T]):
    """A generic interface for target implementations."""

    dynamic_start = "{"
    dynamic_end = "}"

    def __init__(self, data: str) -> None:
        """Initialize this target."""

        self.data = data
        self.evaluator = self.parse(self.data)
        self.literal = self.evaluator is None

    def __str__(self) -> str:
        """Get this target as a string."""
        return self.data

    def __eq__(self, other: object) -> bool:
        """Check if two targets are equal."""
        return str(self) == str(other)

    def __hash__(self) -> int:
        """Get the hash for this target."""
        return hash(str(self))

    @classmethod
    def is_literal(cls, data: str) -> bool:
        """Determine if a target is guaranteed to be literal or not."""
        return (
            data.count(cls.dynamic_start) == data.count(cls.dynamic_end) == 0
        )

    def compile(self, substitutions: Substitutions = None) -> str:
        """
        Attempt to get a target literal from this target and optional
        substitutions.
        """

        result = self.data
        if self.evaluator is not None:
            assert substitutions is not None, f"Can't compile '{self.data}'!"
            result = self.evaluator.compile(substitutions)
        return result

    @classmethod
    def segment_count(cls, data: str) -> int:
        """Count the number of dynamic segments and validate syntax."""

        result = 0
        if not cls.is_literal(data):
            result = data.count(cls.dynamic_start)
            assert result == data.count(cls.dynamic_end)
        return result

    @classmethod
    @_abstractmethod
    def parse(cls, data: str) -> _Optional[T]:
        """
        Obtain an expression target-evaluator from provided string data. If
        data doesn't contain any target-evaluation syntax, return None.
        """


class DynamicTargetEvaluator(TargetEvaluatorInterface):
    """
    A regular expression configured to match as many groups as in the provided
    keys. When the pattern matches some data, the names of the keys can become
    associated with the data that was matched inside each group.
    """

    def __init__(
        self,
        original: str,
        pattern: re.Pattern[str],
        keys: list[str],
        markers: list[tuple[int, int]],
    ) -> None:
        """Initialize this evaluator."""
        self.pattern = pattern
        super().__init__(original, keys, markers)

    def compile_key(self, key: str, values: Substitutions) -> str:
        """Process the key based on substitution data."""
        return str(values[key])
