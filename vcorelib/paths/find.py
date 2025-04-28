"""
A module implementing interfaces for finding files.
"""

# built-in
from pathlib import Path as _Path
from typing import Callable as _Callable
from typing import Iterable as _Iterable
from typing import Optional as _Optional
from urllib.parse import ParseResult as _ParseResult
from urllib.parse import urlparse as _urlparse

# third-party
import importlib_resources as _importlib_resources

# internal
from vcorelib import PKG_NAME
from vcorelib.logging import LoggerType
from vcorelib.paths.base import Pathlike, normalize

PACKAGE_SEARCH: list[str] = [PKG_NAME]


def _populate_package_search_paths(
    to_check: list[Pathlike],
    package: str,
    package_subdir: str = "data",
    logger: LoggerType = None,
) -> None:
    """Get candidate package directories to search."""

    checked = []

    for pkg in [package] + PACKAGE_SEARCH:
        # Avoid double searching any package.
        if pkg not in checked:
            try:
                checked.append(pkg)
                to_check.append(
                    _importlib_resources.files(pkg).joinpath(package_subdir)
                )
            except ModuleNotFoundError:
                if logger is not None:
                    logger.warning(
                        "Can't search package '%s', not found.", pkg
                    )


def _construct_search_path(
    search_paths: _Iterable[Pathlike] = None,
    include_cwd: bool = False,
    relative_to: Pathlike = None,
    package: str = None,
    package_subdir: str = "data",
    logger: LoggerType = None,
) -> list[Pathlike]:
    """Construct a list of paths to search for a resource."""

    to_check: list[Pathlike] = []

    # iterate over entire package search path

    # Add a package resource to the search path if a package name was provided.
    if package is not None:
        _populate_package_search_paths(
            to_check, package, package_subdir=package_subdir, logger=logger
        )

    if search_paths:
        to_check += list(search_paths)

    # Check the working directory if it was specified.
    if include_cwd:
        to_check.append(_Path.cwd())

    # Check if the provided path exists relative to some other path.
    if relative_to is not None:
        relative_to = normalize(relative_to)
        to_check.append(
            relative_to if relative_to.is_dir() else relative_to.parent
        )

    return to_check


FileFinder = _Callable[
    [_ParseResult, str, _Optional[LoggerType]], _Optional[_Path]
]
FINDERS: dict[str, FileFinder] = {}


def find_package_file(
    parsed: _ParseResult, package_subdir: str, logger: _Optional[LoggerType]
) -> _Optional[_Path]:
    """Find a file from a package."""

    return find_file(
        parsed.path[1:],
        package=parsed.hostname,
        logger=logger,
        package_subdir=package_subdir,
    )


def register_file_finder(scheme: str, finder: FileFinder) -> None:
    """Register a custom, runtime file finder (for URI paths)."""

    assert scheme not in FINDERS, scheme
    FINDERS[scheme] = finder


register_file_finder("package", find_package_file)


def find_file(
    path: Pathlike,
    *parts: str | _Path,
    search_paths: _Iterable[Pathlike] = None,
    include_cwd: bool = False,
    relative_to: Pathlike = None,
    package: str = None,
    package_subdir: str = "data",
    logger: LoggerType = None,
    strict: bool = False,
) -> _Optional[_Path]:
    """Combines a few simple strategies to locate a file on disk."""

    # Attempt to handle a URI first.
    if isinstance(path, str):
        parsed = _urlparse(path)

        if parsed.scheme in FINDERS:
            # Validate arguments, because some things aren't passed to custom
            # handlers.
            assert not parts, parts
            assert package is None or package == parsed.hostname

            return FINDERS[parsed.scheme](parsed, package_subdir, logger)

    path = normalize(path, *parts)

    # If path is absolute we can't search for it.
    if path.is_absolute():
        if path.exists():
            return path

        assert not strict, f"Couldn't find '{path}'!"
        return None

    candidates_checked: list[str] = []

    # Return the first file we find on the search path, if we find one.
    for search in [
        normalize(x)
        for x in _construct_search_path(
            search_paths=search_paths,
            include_cwd=include_cwd,
            relative_to=relative_to,
            package=package,
            package_subdir=package_subdir,
            logger=logger,
        )
    ]:
        if search.is_dir():
            candidate = search.joinpath(path)
            if candidate.exists():
                if logger is not None:
                    logger.debug("Found '%s' at '%s'.", path, search)
                return candidate

            if logger is not None:
                logger.debug("Didn't find '%s' at '%s'.", path, search)

            candidates_checked.append(str(candidate))

    assert (
        not strict
    ), f"Couldn't find '{path}'! (checked: {candidates_checked})"

    return None
