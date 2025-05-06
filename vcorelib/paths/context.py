"""
A module for context managers related to file-system paths.
"""

# built-in
from contextlib import ExitStack, contextmanager, suppress
from io import StringIO as _StringIO
from os import chdir as _chdir
from os import makedirs as _makedirs
from pathlib import Path as _Path
from tempfile import NamedTemporaryFile as _NamedTemporaryFile
from typing import Callable as _Callable
from typing import Iterator as _Iterator
from typing import TextIO as _TextIO

# internal
from vcorelib import DEFAULT_ENCODING as _DEFAULT_ENCODING
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import normalize as _normalize


@contextmanager
def in_dir(
    path: _Pathlike, *parts: str | _Path, makedirs: bool = False
) -> _Iterator[_Path]:
    """Change the current working directory as a context manager."""

    cwd = _Path.cwd()
    try:
        path = _normalize(path, *parts)
        if makedirs:
            _makedirs(path, exist_ok=True)
        _chdir(path)
        yield path
    finally:
        _chdir(cwd)


PossiblePath = _Path | bytes | str


@contextmanager
def as_path(pathlike: PossiblePath, **kwargs) -> _Iterator[_Path]:
    """
    Write contents to a temporary file (and return it) if it's not already a
    path.
    """

    with ExitStack() as stack:
        if isinstance(pathlike, str):
            pathlike = pathlike.encode()

        # Write contents to a temporary file if necessary.
        if not isinstance(pathlike, _Path):
            tmp = stack.enter_context(tempfile(**kwargs))
            with tmp.open("wb") as path_fd:
                path_fd.write(pathlike)
            pathlike = tmp

        yield pathlike


@contextmanager
def linked_to(
    link: _Pathlike,
    target: _Pathlike,
    *parts: str | _Path,
    target_is_directory: bool = False,
) -> _Iterator[_Path]:
    """Provide a symbolic link as a managed context."""

    link = _normalize(link)
    link.symlink_to(
        _normalize(target, *parts), target_is_directory=target_is_directory
    )

    try:
        yield link
    finally:
        link.unlink()


@contextmanager
def tempfile(*args, **kwargs) -> _Iterator[_Path]:
    """
    Get a valid path to a temporary file and guarantee that its cleaned up
    afterwards.
    """

    with _NamedTemporaryFile(*args, **kwargs) as temp:
        path = _Path(temp.name)
    try:
        yield path
    finally:
        with suppress(FileNotFoundError):
            # Respect the 'delete' argument.
            if kwargs.get("delete", True):
                path.unlink()


def write_text_if_different(path: _Path, data: str) -> bool:
    """
    Writes the contents of a string stream if it differs from output path
    data.
    """

    do_write = False

    if path.is_file():
        with path.open("r", encoding=_DEFAULT_ENCODING) as path_fd:
            do_write = data != path_fd.read()
    else:
        do_write = True

    if do_write:
        with path.open("w", encoding=_DEFAULT_ENCODING) as path_fd:
            path_fd.write(data)

    return do_write


TextPreprocessor = _Callable[[str], str]


@contextmanager
def text_stream_if_different(
    path: _Path, preprocessor: TextPreprocessor = None
) -> _Iterator[_TextIO]:
    """
    Writes the contents of a string stream if it differs from output path
    data.
    """

    with _StringIO() as stream:
        try:
            yield stream
        finally:
            content = stream.getvalue()

    if preprocessor:
        content = preprocessor(content)

    write_text_if_different(path, content)
