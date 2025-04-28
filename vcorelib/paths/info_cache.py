"""
A module implementing a file-info cache.
"""

# built-in
from contextlib import ExitStack as _ExitStack
from contextlib import contextmanager as _contextmanager
import logging as _logging
from pathlib import Path as _Path
from typing import Callable as _Callable
from typing import Iterator as _Iterator
from typing import NamedTuple
from typing import Optional as _Optional

# internal
from vcorelib.dict.cache import FileCache
from vcorelib.io.types import JsonObject as _JsonObject
from vcorelib.math.time import LoggerType
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import normalize as _normalize
from vcorelib.paths import rel as _rel
from vcorelib.paths.info import FileChangeEvent, FileInfo


class FileChanged(NamedTuple):
    """Data provided to a file-changed callback."""

    new: _Optional[FileInfo]
    old: _Optional[FileInfo]
    event: FileChangeEvent


#
# new file (if still present), old file (if it was previously present), kind
# of file-change event
#
# return True if the callback succeeded, in this case an implementation using
# this callback should consider the new file info valid
#
# if False was returned, do not promote the new file info into any cache or
# runtime state
#
# this return-value signal is useful because software that acts on file changes
# can fail, and eventually retry later (such as in a completely new invocation
# of the program), without the file-change event being lost
#
FileChangedCallback = _Callable[[FileChanged], bool]

# Adds 'FileInfo' and 'FileChangeEvent' from the .info module.
__all__ = [
    "FileChanged",
    "FileChangedCallback",
    "FileInfoManager",
    "file_info_cache",
    "FileInfo",
    "FileChangeEvent",
]


def log_file_change_event(
    level: int, logger: LoggerType, change: FileChanged, base: _Pathlike = None
) -> None:
    """Log information based on a file-change event."""

    if change.event is FileChangeEvent.CREATED:
        assert change.new is not None
        logger.log(
            level,
            "File '%s' is newly created.",
            _rel(change.new.path, base=base),
        )
    elif change.event is FileChangeEvent.REMOVED:
        assert change.old is not None
        logger.log(
            level, "File '%s' was removed.", _rel(change.old.path, base=base)
        )
    else:
        assert change.new is not None
        assert change.old is not None

        logger.log(
            level,
            "File '%s' changed (%d bytes added/removed).",
            change.new.path,
            change.new.size - change.old.size,
        )


class FileInfoManager:
    """A class simplifying evaluation of changes to files on disk."""

    def __init__(
        self,
        poll_cb: FileChangedCallback,
        initial: dict[_Path, FileInfo] = None,
        logger: LoggerType = None,
        level: int = _logging.DEBUG,
        check_contents: bool = True,
    ) -> None:
        """Initialize this file-info manager."""

        self.poll = poll_cb

        if initial is None:
            initial = {}
        self.infos = initial

        self.logger = logger
        self.level = level
        self.check_contents = check_contents

        # If we have initial files, poll them all.
        self.poll_existing()

    def _handle_info(self, path: _Path, info: _Optional[FileInfo]) -> None:
        """Update our internal tracking."""

        if info is not None:
            self.infos[info.path] = info
        else:
            del self.infos[path]

    def poll_existing(self, base: _Pathlike = None) -> None:
        """
        Poll all existing files. This is the only way to detect files that have
        been deleted.
        """

        for path in list(self.infos.keys()):
            self.poll_file(path, base=base)

    def poll_directory(
        self, path: _Pathlike, recurse: bool = True, base: _Pathlike = None
    ) -> None:
        """
        Poll an entire directory for changes. If files previously in this
        directory were polled and are no longer present, they won't be polled
        and thus won't trigger the callback. Use 'poll_existing' for that
        behavior.
        """

        norm = _normalize(path).resolve()

        # Don't do anything if this isn't a directory.
        if norm.is_dir():
            for item in norm.iterdir():
                if item.is_file():
                    self.poll_file(item, base=base)
                elif recurse:
                    self.poll_directory(item, base=base)

    def _call_callback(
        self, change: FileChanged, base: _Pathlike = None
    ) -> bool:
        """
        Call the provided callback with the change event. Log information if
        a logger is provided.
        """

        # Log the event, if a logger was provided.
        if self.logger is not None:
            log_file_change_event(self.level, self.logger, change, base=base)

        return self.poll(change)

    def _poll_path(
        self, path: _Path
    ) -> tuple[_Optional[FileChangeEvent], _Optional[FileInfo]]:
        """Get information about a file-system path."""

        change = None
        file_info = None

        # If the path isn't in the mapping, it's a new file.
        if path not in self.infos:
            if path.is_file():
                change = FileChangeEvent.CREATED
                file_info = FileInfo.from_file(path)

            return change, file_info

        # Determine if the existing file has changed.
        return self.infos[path].poll(check_contents=self.check_contents)

    def poll_file(
        self,
        path: _Pathlike,
        base: _Pathlike = None,
    ) -> None:
        """Check if a file has changed and invoke the callback if so."""

        norm = _normalize(path).resolve()
        kind, info = self._poll_path(norm)

        # Invoke the callback if a change event occured. Update our internal
        # structure if the callback succeeds.
        if kind is not None and self._call_callback(
            FileChanged(info, self.infos.get(norm), kind),
            base=base,
        ):
            self._handle_info(norm, info)


@_contextmanager
def file_info_manager(
    data: _JsonObject, poll_cb: FileChangedCallback, **kwargs
) -> _Iterator[FileInfoManager]:
    """Create a file-info manager as a managed context."""

    manager = FileInfoManager(
        poll_cb, FileInfo.from_json(data, force=True), **kwargs
    )
    try:
        yield manager
    finally:
        # Update dictionary data with the current cache contents.
        data.clear()
        for info in manager.infos.values():
            info.to_json(data)


@_contextmanager
def file_info_cache(
    cache_path: _Pathlike,
    poll_cb: FileChangedCallback,
    logger: LoggerType = None,
    level: int = _logging.DEBUG,
    check_contents: bool = True,
) -> _Iterator[FileInfoManager]:
    """Obtain a file-info manager as a cached context."""

    path = _normalize(cache_path)
    assert not path.is_dir(), f"'{path}' is a directory!"

    with _ExitStack() as stack:
        with file_info_manager(
            stack.enter_context(FileCache(path).loaded()),
            poll_cb,
            logger=logger,
            level=level,
            check_contents=check_contents,
        ) as manager:
            yield manager
