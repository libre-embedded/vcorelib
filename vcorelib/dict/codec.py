"""
A module for implementing classes that can be loaded from dictionaries and
exported as dictionaries.
"""

# built-in
import abc as _abc
from contextlib import contextmanager as _contextmanager
from typing import Any as _Any
from typing import Iterator as _Iterator
from typing import Optional as _Optional
from typing import Type as _Type
from typing import TypeVar as _TypeVar

# internal
from vcorelib.io import ARBITER as _ARBITER
from vcorelib.io import DataArbiter as _DataArbiter
from vcorelib.io.types import EncodeResult as _EncodeResult
from vcorelib.io.types import JsonObject as _JsonObject
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.schemas.base import SchemaMap as _SchemaMap
from vcorelib.schemas.mixins import SchemaMixin

T = _TypeVar("T", bound="JsonCodec")


class JsonCodec(_abc.ABC, SchemaMixin):
    """A simple JSON codec interface."""

    @classmethod
    def normalize(cls: _Type[T], data: _JsonObject | T) -> T:
        """Ensure that some object is an instance of this class."""

        if not isinstance(data, cls):
            data = cls.create(data)  # type: ignore
        return data

    @classmethod
    @_abc.abstractmethod
    def create(
        cls: _Type[T],
        data: _JsonObject = None,
        schemas: _SchemaMap = None,
        dest_attr: str = "data",
        verify: bool = True,
    ) -> T:
        """A factory method to create an instance."""

    def __copy__(self: T) -> T:
        """Create another instance based on this instance's data."""
        return self.__class__.create(self.asdict())

    def __str__(self) -> str:
        """
        Use the dictionary representation of this instance for string
        representation.
        """
        return str(self.asdict())

    def __eq__(self, other) -> bool:
        """Determine if this instance is equal to another."""

        # Allow direct comparison with another dictionary, but not an arbitrary
        # mapping.
        if isinstance(other, dict):
            to_cmp = other
        else:
            to_cmp = other.asdict()

        return self.asdict() == to_cmp

    @_abc.abstractmethod
    def asdict(self) -> _JsonObject:
        """Obtain a dictionary representing this instance."""

    def encode(
        self, pathlike: _Pathlike, arbiter: _DataArbiter = _ARBITER, **kwargs
    ) -> _EncodeResult:
        """Encode this object instance to a file."""
        return arbiter.encode(pathlike, self.asdict(), **kwargs)

    @classmethod
    def decode(
        cls: _Type[T],
        pathlike: _Pathlike,
        arbiter: _DataArbiter = _ARBITER,
        schemas: _SchemaMap = None,
        dest_attr: str = "data",
        verify: bool = True,
        require_success: bool = True,
        default_data: _JsonObject = None,
        **kwargs,
    ) -> T:
        """Decode an object instance from data loaded from a file."""

        decoded = arbiter.decode(
            pathlike, require_success=require_success, **kwargs
        )

        return cls.create(
            decoded.data if decoded or not default_data else default_data,
            schemas=schemas,
            dest_attr=dest_attr,
            verify=verify,
        )

    @classmethod
    @_contextmanager
    def file_cache(
        cls: _Type[T],
        pathlike: _Pathlike,
        arbiter: _DataArbiter = _ARBITER,
        encode_kwargs: dict[str, _Any] = None,
        require_success: bool = False,
        **kwargs,
    ) -> _Iterator[T]:
        """Manage an instance of this class as a disk-backed file."""

        inst = cls.decode(
            pathlike,
            arbiter=arbiter,
            require_success=require_success,
            **kwargs,
        )
        try:
            yield inst
        finally:
            if encode_kwargs is None:
                encode_kwargs = {}
            inst.encode(pathlike, arbiter=arbiter, **encode_kwargs)


V = _TypeVar("V", bound="DictCodec")


class DictCodec(JsonCodec):
    """
    A class implementing an interface for objects that can be decoded from
    disk and encoded back to disk.
    """

    default_schemas: _Optional[_SchemaMap] = None

    def __init__(
        self,
        data: _JsonObject = None,
        schemas: _SchemaMap = None,
        dest_attr: str = "data",
        verify: bool = True,
    ) -> None:
        """Initialize this instance."""

        if data is None:
            data = {}
        setattr(self, dest_attr, data)

        # Validate the instance's dictionary data based on a schema.
        if schemas is None:
            schemas = self.default_schemas
        if schemas is not None:
            super().__init__(schemas, valid_attr=dest_attr)

        self.init(getattr(self, dest_attr))

        # After initialization, creating a new dictionary from this object
        # should be equivalent to the one provided to the constructor. This
        # can be disabled for special cases.
        if verify:
            assert self == data, f"'{self}' != '{data}' after initialization!"

    @_abc.abstractmethod
    def init(self, data: _JsonObject) -> None:
        """Perform implementation-specific initialization."""

    @classmethod
    def create(
        cls: _Type[V],
        data: _JsonObject = None,
        schemas: _SchemaMap = None,
        dest_attr: str = "data",
        verify: bool = True,
    ) -> V:
        """A factory method to create an instance."""
        return cls(data, schemas=schemas, dest_attr=dest_attr, verify=verify)


class BasicDictCodec(DictCodec):
    """The simplest possible dictionary codec implementation."""

    def init(self, data: _JsonObject) -> None:
        """Initialize this instance."""
        self.data = data

    def asdict(self) -> _JsonObject:
        """Obtain a dictionary representing this instance."""
        return self.data.copy()
