"""
A module aggregating all data-arbiter capabilities.
"""

# built-in
from pathlib import Path
from typing import Any

# internal
from vcorelib.io.arbiter.context import DataArbiterContext


class DataArbiter(DataArbiterContext):
    """A class aggregating all data-arbiter capabilities."""


ARBITER = DataArbiter()


def encode_if_different(
    output: Path,
    data: dict[str, Any],
    encode_kwargs: dict[str, Any] = None,
    **decode_kwargs,
) -> bool:
    """Encode a data file if its contents are different."""

    if (
        output.is_file()
        and data
        == ARBITER.decode(output, require_success=True, **decode_kwargs).data
    ):
        return True

    return ARBITER.encode(
        output, data, **(encode_kwargs if encode_kwargs is not None else {})
    )[0]
