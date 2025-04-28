"""
A module implementing expression evaluation for targets.
"""

# built-in
from typing import Optional as _Optional

# internal
from vcorelib.target import Target as _Target
from vcorelib.target.evaluation import (
    TargetEvaluatorInterface as _TargetEvaluatorInterface,
)
from vcorelib.target.evaluation import Substitutions as _Substitutions
from vcorelib.target.evaluation import TargetInterface as _TargetInterface


class ExpressionTargetEvaluator(_TargetEvaluatorInterface):
    """An interface for evaluating expression targets."""

    def compile_key(self, key: str, values: _Substitutions) -> str:
        """Process the key based on substitution data."""
        return str(eval(key, {}, values))  # pylint: disable=eval-used


class ExpressionTarget(_TargetInterface[ExpressionTargetEvaluator]):
    """A class for evaluating expressions based on substitution data."""

    def compile_match(self, target: _Target, data: str) -> _Optional[str]:
        """
        If a target matches provided data, compile our expression and return
        the result.
        """

        result = None

        match = target.evaluate(data)
        if match.matched:
            result = self.compile(match.substitutions)

        return result

    @classmethod
    def parse(cls, data: str) -> _Optional[ExpressionTargetEvaluator]:
        """
        Obtain an expression target-evaluator from provided string data. If
        data doesn't contain any target-evaluation syntax, return None.
        """

        open_len = cls.segment_count(data)

        # The short-circuit case where this is not a dynamic target.
        if not open_len:
            return None

        live = data
        abs_idx = 0
        keys = []
        markers: list[tuple[int, int]] = []
        for _ in range(open_len):
            start = live.index(cls.dynamic_start)
            end = live.index(cls.dynamic_end)

            # Store the absolute index into the string that the control
            # characters appeared.
            markers.append((abs_idx + start, abs_idx + end))

            keys.append(live[start + 1 : end])
            live = live[end + 1 :]
            abs_idx += end + 1

        assert len(keys) == open_len
        return ExpressionTargetEvaluator(data, keys, markers)
