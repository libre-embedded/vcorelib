"""
A module defining an interface for dynamic task targets.
"""

from __future__ import annotations

# built-in
import re
from typing import NamedTuple
from typing import Optional as _Optional

# internal
from vcorelib.target.evaluation import (
    DynamicTargetEvaluator,
    Substitutions,
    TargetInterface,
)

__all__ = [
    "Substitutions",
    "TargetMatch",
    "LITERAL_MATCH",
    "NO_MATCH",
    "Target",
]


class TargetMatch(NamedTuple):
    """
    An encapsulation of results when attempting to patch a target name to a
    pattern. If a target was matched and had keyword substitutions, the actual
    values used will be set as match data.
    """

    matched: bool
    substitutions: _Optional[Substitutions] = None

    def get(self, data: str) -> str:
        """Get data for keys that matched the target."""
        subs = self.substitutions if self.substitutions is not None else {}
        return str(subs[data])


LITERAL_MATCH = TargetMatch(True)
NO_MATCH = TargetMatch(False)


def escape_regex_special(data: str) -> str:
    """Escape special characters that have meaning in a regular expression."""
    return data.replace(".", "\\.")


class Target(TargetInterface[DynamicTargetEvaluator]):
    """
    An interface for string targets that may encode data substitutions or
    otherwise be matched to only a single, literal string.
    """

    valid = "[a-zA-Z0-9-_.]+"

    @classmethod
    def parse(cls, data: str) -> _Optional[DynamicTargetEvaluator]:
        """
        Obtain a compiled target evaluator if data is a dynamic target, else
        None.
        """

        open_len = cls.segment_count(data)

        # The short-circuit case where this is not a dynamic target.
        if not open_len:
            return None

        pattern = "^"
        keys = []
        markers: list[tuple[int, int]] = []
        live = data
        abs_idx = 0
        for _ in range(open_len):
            start = live.index(cls.dynamic_start)
            end = live.index(cls.dynamic_end)

            # Store the absolute index into the string that the control
            # characters appeared.
            markers.append((abs_idx + start, abs_idx + end))

            pattern += escape_regex_special(live[:start])
            pattern += f"({cls.valid})"

            keys.append(live[start + 1 : end])
            live = live[end + 1 :]
            abs_idx += end + 1

        pattern += escape_regex_special(live) + "$"

        assert len(keys) == open_len
        return DynamicTargetEvaluator(data, re.compile(pattern), keys, markers)

    def evaluate(self, data: str) -> TargetMatch:
        """Attempt to match this target with some string data."""

        if self.literal:
            return TargetMatch(self.data == data)

        assert self.evaluator is not None
        result = self.evaluator.pattern.fullmatch(data)
        if result is None:
            return NO_MATCH

        return TargetMatch(
            True,
            {
                key: result.group(1 + idx)
                for idx, key in enumerate(self.evaluator.keys)
            },
        )
