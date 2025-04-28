"""
Dictionary manipulation utilities.
"""

# built-in
from contextlib import contextmanager as _contextmanager
from enum import Enum as _Enum
from enum import auto as _auto
from logging import getLogger
from typing import Any as _Any
from typing import Iterator as _Iterator

# internal
from vcorelib.logging import LoggerType

_LOG = getLogger(__name__)
GenericDict = dict[_Any, _Any]
GenericStrDict = dict[str, _Any]


def consume(data: GenericDict, key: _Any, default: _Any = None) -> _Any:
    """
    Attempt to obtain dictionary data via key, removing the data if it was
    present.
    """
    return data.pop(key, default)


def set_if_not(data: GenericDict, key: _Any, value: _Any = None) -> _Any:
    """
    Set a value in a dictionary if one wasn't already set and return the value
    that ends up at that key.
    """

    if key not in data:
        data[key] = value
    return data[key]


@_contextmanager
def limited(
    data: GenericDict, key: _Any, value: _Any = None
) -> _Iterator[None]:
    """Ensure that dictionary data is only temporarily added."""

    had_key = False
    orig_value = None

    # Provide the new value.
    if value is not None:
        had_key = key in data
        if had_key:
            orig_value = data[key]
        data[key] = value

    # If no value is provided, ensure that this key isn't already present
    # to prevent ambiguity.
    else:
        assert key not in data

    yield

    # Restore the dictionary to its initial state.
    if value is not None:
        del data[key]
        if had_key:
            data[key] = orig_value


class MergeStrategy(_Enum):
    """
    An enumeration describing strategies for combining various data structures.
    """

    RECURSIVE = _auto()
    UPDATE = _auto()


def merge_recursive(
    dict_a: GenericDict,
    dict_b: GenericDict,
    path: list[str] = None,
    expect_overwrite: bool = False,
    logger: LoggerType = None,
    strategy: MergeStrategy = MergeStrategy.RECURSIVE,
) -> GenericDict:
    """
    Combine two dictionaries recursively, prefers dict_a in a conflict. For
    values of the same key that are lists, the lists are combined. Otherwise
    the resulting dictionary is cleanly merged.
    """

    if path is None:
        path = []
    if logger is None:
        logger = _LOG

    for key, right_val in dict_b.items():
        if key not in dict_a:
            dict_a[key] = right_val
            continue

        # first try to coerce b's type into a's
        if not isinstance(right_val, type(dict_a[key])):
            try:
                right_val = type(dict_a[key])(right_val)
            except ValueError:
                pass

        # same leaf value
        if dict_a[key] == right_val:
            pass
        elif isinstance(dict_a[key], dict) and isinstance(right_val, dict):
            merge(
                dict_a[key],
                right_val,
                path + [str(key)],
                expect_overwrite,
                logger,
                strategy=strategy,
            )
        elif isinstance(dict_a[key], list) and isinstance(right_val, list):
            dict_a[key].extend(right_val)
        elif not isinstance(right_val, type(dict_a[key])):
            logger.error("Type mismatch at '%s'", ".".join(path + [str(key)]))
            logger.error("left:  %s (%s)", type(dict_a[key]), dict_a[key])
            logger.error("right: %s (%s)", type(right_val), right_val)
        elif not expect_overwrite:
            logger.error("Conflict at '%s'", ".".join(path + [str(key)]))
            logger.error("left:  %s", dict_a[key])
            logger.error("right: %s", right_val)
        else:
            dict_a[key] = right_val

    return dict_a


def merge(
    dict_a: GenericDict,
    dict_b: GenericDict,
    path: list[str] = None,
    expect_overwrite: bool = False,
    logger: LoggerType = None,
    strategy: MergeStrategy = MergeStrategy.RECURSIVE,
) -> GenericDict:
    """Combine two dictionaries based on a provided merge strategy."""

    if strategy is MergeStrategy.UPDATE:
        dict_a.update(dict_b)
        return dict_a

    return merge_recursive(
        dict_a,
        dict_b,
        path=path,
        expect_overwrite=expect_overwrite,
        logger=logger,
        strategy=strategy,
    )


def merge_dicts(
    dicts: list[GenericDict],
    expect_overwrite: bool = False,
    logger: LoggerType = None,
    strategy: MergeStrategy = MergeStrategy.RECURSIVE,
) -> GenericDict:
    """
    Merge a list of dictionary data into a single set (mutates the first
    element).
    """

    result = dicts[0]
    for right_dict in dicts[1:]:
        result = merge(
            result,
            right_dict,
            expect_overwrite=expect_overwrite,
            logger=logger,
            strategy=strategy,
        )
    return result
