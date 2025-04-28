"""
A module implementing common pathing utilities.
"""

# built-in
from contextlib import suppress as _suppress
from os import stat_result as _stat_result
from pathlib import Path as _Path
from typing import Optional as _Optional
from typing import Union as _Union

Pathlike = _Union[_Path, str, None]


def normalize(
    path: Pathlike, *parts: str | _Path, require: bool = False
) -> _Path:
    """Normalize an input that could be a path into a path."""
    path = (
        _Path("." if path is None else path)
        if not isinstance(path, _Path)
        else path
    )
    path = path.joinpath(*parts)

    if require:
        assert path.exists(), f"Path '{path}' doesn't exist!"

    return path


def rel(path: Pathlike, base: Pathlike = None) -> _Path:
    """
    Attempt to make 'path' relative to base (which is the current-working
    directory, if not provided).
    """

    path = normalize(path)
    with _suppress(ValueError):
        path = path.relative_to(normalize(base).resolve())
    return path


def set_exec_flags(path: Pathlike) -> None:
    """Set the executable bits, but respect the 'read' bits."""

    path = normalize(path)
    mode = path.stat().st_mode
    path.chmod(mode | ((mode & 0o444) >> 2))


def stats(path: Pathlike) -> _Optional[_stat_result]:
    """Get stats for a file on disk if it exists."""

    result = None
    path = normalize(path)
    if path.exists():
        result = path.stat()
    return result


def get_file_name(path: Pathlike, maxsplit: int = -1) -> str:
    """
    From a path to a file, get the name of the file. Use 'maxsplit' to control
    how many suffixes are considered part of the name or the extension.
    """
    split = normalize(path).name.split(".", maxsplit=maxsplit)
    if len(split) > 1:
        pieces = split[:-1]
    else:
        pieces = [split[0]]
    return ".".join(pieces)


def get_file_ext(path: Pathlike, maxsplit: int = -1) -> str:
    """
    From a path to a file, get the file's extension. Use 'maxsplit' to control
    how many suffixes are considered part of the name or the extension.
    """
    return normalize(path).name.split(".", maxsplit=maxsplit)[-1]
