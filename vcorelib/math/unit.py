"""
A module for working with units.
"""

# built-in
from typing import NamedTuple, Sequence


class UnitSystem(NamedTuple):
    """
    A pairing of prefixes defining a unit, and the amount that indicates the
    multiplicative step-size between them.
    """

    prefixes: Sequence[str]
    divisor: int


SI_UNITS = UnitSystem(["n", "u", "m", "", "k", "M", "G", "T"], 1000)
KIBI_UNITS = UnitSystem(
    ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"], 1024
)


def unit_traverse(
    val: int,
    unit: UnitSystem = SI_UNITS,
    max_prefix: int = 3,
    iteration: int = 0,
) -> tuple[int, int, str]:
    """
    Given an initial value, traverse a unit system to get the largest
    representative unit prefix. Also return a fractional component, in units
    of the next-smallest prefix.
    """

    prefixes = unit.prefixes
    divisor = unit.divisor
    decimal = val
    fractional = 0

    max_iter = min(len(prefixes) - 1, max_prefix)
    while decimal >= divisor and iteration < max_iter:
        fractional = decimal % divisor
        decimal = decimal // divisor
        iteration += 1

    return decimal, fractional, prefixes[iteration]
