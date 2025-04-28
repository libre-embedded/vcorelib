"""
A module defining interfaces for schema enforcement.
"""

# built-in
import abc as _abc
from collections import UserDict
from typing import Any as _Any
from typing import Iterator as _Iterator
from typing import MutableMapping as _MutableMapping
from typing import TypeVar as _TypeVar

# internal
from vcorelib.io import ARBITER as _ARBITER
from vcorelib.io.types import JsonObject as _JsonObject
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import get_file_name as _get_file_name
from vcorelib.paths import normalize as _normalize
from vcorelib.paths import resource as _resource

T = _TypeVar("T", bound="Schema")


class SchemaValidationError(Exception):
    """An exception type for schema errors."""


class Schema(_abc.ABC):
    """A base class for schema enforcement."""

    def __init__(self, data: _JsonObject, **_) -> None:
        """Initialize this schema."""
        self.data = data

    @_abc.abstractmethod
    def __call__(self, data: _Any) -> _Any:
        """Validate input data and return the result."""

    @classmethod
    def from_path(
        cls: type[T], path: _Pathlike, includes_key: str = None, **kwargs
    ) -> T:
        """Load a schema from a data file on disk."""
        return cls(
            _ARBITER.decode(
                path, includes_key=includes_key, require_success=True
            ).data,
            **kwargs,
        )


V = _TypeVar("V", bound="SchemaMap")


class SchemaMap(
    UserDict,  # type: ignore
    _MutableMapping[str, Schema],
):
    """A class for managing multiple schema objects."""

    @classmethod
    @_abc.abstractmethod
    def kind(cls: type[V]) -> type[Schema]:
        """Implement this to determine the concrete schema type."""

    def __init__(self) -> None:
        """Initialize this schema map."""
        super().__init__(self)

    def load_file(
        self, path: _Pathlike, includes_key: str = None, **kwargs
    ) -> tuple[str, T]:
        """Load a schema file into the map."""

        path = _normalize(path)
        name = _get_file_name(path)
        assert name not in self, f"Duplicate schema '{name}'!"
        self[name] = self.kind().from_path(
            path, includes_key=includes_key, **kwargs
        )
        return name, self[name]

    def load_directory(
        self, path: _Pathlike, includes_key: str = None, **kwargs
    ) -> _Iterator[tuple[str, Schema]]:
        """Load a directory of schema files into the map."""

        path = _normalize(path)
        assert path.is_dir(), f"'{path}' isn't a directory!"
        for item in path.iterdir():
            yield self.load_file(item, includes_key=includes_key, **kwargs)

    def load_package(
        self,
        package: str,
        path: _Pathlike = "schemas",
        package_subdir: str = "data",
        includes_key: str = None,
        **kwargs,
    ) -> _Iterator[tuple[str, Schema]]:
        """Load schemas from package data."""

        path = _resource(path, package=package, package_subdir=package_subdir)
        assert (
            path is not None and path.is_dir()
        ), f"Can't find schema directory for package '{package}'!"

        yield from self.load_directory(
            path, includes_key=includes_key, **kwargs
        )

    @classmethod
    def from_package(
        cls: type[V],
        package: str,
        includes_key: str = None,
        **kwargs,
    ) -> V:
        """Create a new JSON-schema map from package data."""

        result = cls()
        list(result.load_package(package, includes_key=includes_key, **kwargs))
        return result
