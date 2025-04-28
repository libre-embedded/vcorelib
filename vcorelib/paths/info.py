"""
A module implementing a data structure for tracking information about files
in a file-system.
"""

# built-in
from collections.abc import Mapping as _Mapping
from enum import Enum as _Enum
from enum import auto as _auto
from os import stat_result as _stat_result
from pathlib import Path as _Path
from typing import NamedTuple
from typing import Optional as _Optional
from typing import cast as _cast

# internal
from vcorelib.io.types import JsonObject as _JsonObject
from vcorelib.math import byte_count_str
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import file_md5_hex as _file_md5_hex
from vcorelib.paths import normalize as _normalize
from vcorelib.paths import rel as _rel
from vcorelib.paths import stats as _stats


class FileChangeEvent(_Enum):
    """An enumeration describing possible file-change events."""

    CREATED = _auto()
    REMOVED = _auto()
    UPDATED = _auto()


class FileInfo(NamedTuple):
    """A collection of data to describe an identity of a file."""

    path: _Path
    size: int
    md5_hex: str
    modified_ns: int

    def __str__(self) -> str:
        """Get this instance as a string."""
        return f"{_rel(self.path)} ({byte_count_str(self.size)})"

    def __eq__(self, other: object) -> bool:
        """Determine if two file info's are equivalent."""
        return self.path.samefile(_cast(FileInfo, other).path)

    def __hash__(self) -> int:
        """Get a hash for this file info based on the file name."""
        return hash(str(self.path.resolve()))

    def same(self, other: "FileInfo") -> bool:
        """Check if two file info contents match."""
        return other.size == self.size and other.md5_hex == self.md5_hex

    @staticmethod
    def from_file(path: _Pathlike, stats: _stat_result = None) -> "FileInfo":
        """Create file info from a file."""

        path = _normalize(path).resolve()
        if stats is None:
            stats = _stats(path)
        assert stats is not None
        md5_hex = _file_md5_hex(path)
        return FileInfo(path, stats.st_size, md5_hex, stats.st_mtime_ns)

    def poll(
        self, check_contents: bool = True
    ) -> tuple[_Optional[FileChangeEvent], _Optional["FileInfo"]]:
        """Determine if this file is in a new state or not."""

        if not self.path.is_file():
            return FileChangeEvent.REMOVED, None

        # Skip checking file contents if specified.
        if not check_contents:
            return None, self

        # If the file hasn't been modified, skip re-reading it for a new
        # checksum.
        stats = _stats(self.path)
        if stats is not None and stats.st_mtime_ns == self.modified_ns:
            return None, self

        new_info = FileInfo.from_file(self.path, stats)
        return (
            FileChangeEvent.UPDATED if not self.same(new_info) else None,
            new_info,
        )

    def to_json(self, data: _JsonObject = None) -> _JsonObject:
        """Get JSON data for this instance."""

        # Create a dictionary to write data to if one wasn't provided.
        if data is None:
            data = {}

        # Write data to a dictionary underneath the string-key of this file's
        # name (create it, if it's not already present).
        path_str = str(self.path.resolve())
        if path_str not in data:
            data[path_str] = {}

        to_update = _cast(_JsonObject, data[path_str])
        to_update["size"] = self.size
        to_update["md5_hex"] = self.md5_hex
        to_update["modified_ns"] = self.modified_ns

        return data

    @staticmethod
    def from_json(
        data: _JsonObject, force: bool = False
    ) -> dict[_Path, "FileInfo"]:
        """Create file info from JSON data."""

        result = {}
        for key, info in data.items():
            assert isinstance(info, _Mapping)
            path = _Path(key)
            if path.is_file() or force:
                result[path] = FileInfo(
                    path,
                    _cast(int, info["size"]),
                    _cast(str, info["md5_hex"]),
                    _cast(int, info["modified_ns"]),
                )
        return result
