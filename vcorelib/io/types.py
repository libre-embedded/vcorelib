"""
Common type definitions for data encoding and decoding interfaces.
"""

# built-in
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Callable as _Callable
from typing import Iterator as _Iterator
from typing import NamedTuple
from typing import Optional as _Optional
from typing import TextIO
from typing import Union as _Union

# third-party
from ruamel.yaml import YAML

# internal
from vcorelib.dict import merge
from vcorelib.logging import LoggerType
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import get_file_ext, normalize

DEFAULT_ARCHIVE_EXT = "tar.gz"
DEFAULT_DATA_EXT = "json"

# A simple type system for JSON.
JsonPrimitive = _Union[str, int, float, bool, None]
JsonValue = _Union[
    JsonPrimitive, dict[str, JsonPrimitive], list[JsonPrimitive]
]
JsonArray = list[JsonValue]
JsonObject = dict[str, JsonValue]


class FileExtension(Enum):
    """A mapping of expected encoding type to file extensions."""

    UNKNOWN = ["unknown"]
    # Data formats.
    JSON = [DEFAULT_DATA_EXT]
    YAML = ["yaml", "yml", "eyaml"]
    INI = ["ini", "cfg"]
    TOML = ["toml"]
    # Archive formats.
    ZIP = ["zip"]
    TAR = [
        DEFAULT_ARCHIVE_EXT,
        "tgz",
        "tar",
        "tar.bz2",
        "tar.lzma",
        "tar.xz",
    ]
    # Template formats.
    JINJA = ["j2", "jinja", "j2_template", "j2_macro"]

    def __str__(self) -> str:
        """Get this extension as a string."""
        return self.value[0]

    def is_template(self) -> bool:
        """Determine if this extension is a kind of template."""
        return self in {FileExtension.JINJA}

    def is_archive(self) -> bool:
        """Determine if this extension is a kind of archive file."""
        return self in {FileExtension.ZIP, FileExtension.TAR}

    @staticmethod
    def has_archive(path: _Pathlike) -> _Optional[Path]:
        """Determine if a path has an associated archive file."""

        path = normalize(path)

        for ext in [FileExtension.ZIP, FileExtension.TAR]:
            for ext_str in ext.value:  # pylint: disable=not-an-iterable
                check_path = path.with_suffix(f".{ext_str}")
                if check_path.is_file():
                    return check_path

        return None

    def is_data(self) -> bool:
        """Determine if this etension is a kind of data file."""
        return self in {
            FileExtension.JSON,
            FileExtension.YAML,
            FileExtension.INI,
        }

    @staticmethod
    def from_ext(ext_str: str) -> _Optional["FileExtension"]:
        """Given a file extension, determine what kind of file it is."""

        result = FileExtension.UNKNOWN
        for ext in FileExtension:
            if ext_str in ext.value:
                result = ext
                break
        return None if result is FileExtension.UNKNOWN else result

    @staticmethod
    def from_path(
        path: _Pathlike, maxsplit: int = 1
    ) -> _Optional["FileExtension"]:
        """Get a known file extension for a path, if it exists."""
        return FileExtension.from_ext(get_file_ext(path, maxsplit=maxsplit))

    def apply(self, path: Path) -> Path:
        """Apply this extension's suffix to the given path."""
        return path.with_suffix("." + str(self))

    def candidates(
        self, path: _Pathlike, exists_only: bool = False
    ) -> _Iterator[Path]:
        """
        For a given path, iterate over candidate paths that have the suffixes
        for this kind of file extension.
        """
        orig = normalize(path)
        for ext in self.value:
            path = orig.with_suffix(f".{ext}")
            if not exists_only or path.exists():
                yield path

    @staticmethod
    def archive_candidates(
        path: _Pathlike, exists_only: bool = False
    ) -> _Iterator[Path]:
        """
        Iterate over all file extensions that could point to an archive file.
        """
        for file_ext in FileExtension:
            if file_ext.is_archive():
                yield from file_ext.candidates(path, exists_only)

    @staticmethod
    def data_candidates(
        path: _Pathlike, exists_only: bool = False
    ) -> _Iterator[Path]:
        """
        Iterate over all file extensions that could point to a data file.
        """
        for file_ext in FileExtension:
            if file_ext.is_data():
                yield from file_ext.candidates(path, exists_only)


class LoadResult(NamedTuple):
    """
    An encapsulation of the result of loading raw data, the data collected and
    whether or not it succeeded.
    """

    data: JsonObject
    success: bool
    time_ns: int = -1

    def __bool__(self) -> bool:
        """A simple wrapper."""
        return self.success

    def __eq__(self, other: object) -> bool:
        """Don't compare timing when checking equivalence."""
        assert isinstance(other, (LoadResult, tuple))
        return bool(self.data == other[0] and self.success == other[1])

    def require_success(self, path: Path | str) -> None:
        """Raise a canonical exception if this result is a failure."""
        assert self.success, f"Couldn't load '{path}'!"

    def merge(
        self, other: "LoadResult", is_left: bool = False, **kwargs
    ) -> "LoadResult":
        """Merge two load results."""

        # Add the time fields up if they're both positive.
        time_ns = self.time_ns
        if time_ns > 0 and other.time_ns > 0:
            time_ns += other.time_ns

        left = other.data if is_left else self.data
        right = self.data if is_left else other.data

        return LoadResult(
            merge(left, right, **kwargs),
            self.success and other.success,
            time_ns,
        )


EncodeResult = tuple[bool, int]
DataStream = _Union[TextIO, StringIO]
StreamProcessor = _Callable[[DataStream], DataStream]
DataDecoder = _Callable[[DataStream, LoggerType], LoadResult]
DataEncoder = _Callable[[JsonObject, DataStream, LoggerType], int]

# Only create the interface one so it's not re-created on every read and write
# attempt.
YAML_INTERFACE = YAML(typ="safe")
