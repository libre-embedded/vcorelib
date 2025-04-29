"""
Test the 'DataArbiter' class.
"""

# built-in
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

# third-party
from pytest import mark

# internal
from tests.resources import resource

# module under test
from vcorelib.io import ARBITER, FileExtension, encode_if_different
from vcorelib.io.mapping import DataMapping
from vcorelib.paths.context import tempfile


def verify_can_encode(data: Any, ext: FileExtension) -> None:
    """Test that we can encode data in multiple formats."""

    for ext_str in set([str(ext), "json", "yaml", "ini", "toml"]):
        with tempfile(suffix=f".{ext_str}") as tfile:
            ARBITER.encode(tfile, data)


def test_encode_if_different_basic():
    """Test the 'encode_if_different' method."""

    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        out = base.joinpath("out.json")

        data = {"a": 1, "b": 2, "c": 3}

        assert encode_if_different(out, data)
        assert encode_if_different(out, data)


@mark.asyncio
async def test_arbiter_encode_decode_basic():
    """Verify that we can load data of every file type."""

    base = resource("simple_decode")

    # Verify we can load data of all mapped file types.
    for ext in DataMapping.mapping:
        ext_root = Path(base, str(ext))

        # Verify that we can decode the entire directory at once.
        data = ARBITER.decode_directory(ext_root, require_success=True).data

        # Verify we can encode data.
        verify_can_encode(data, ext)

        # Verify we can encode an entire directory at once.
        with TemporaryDirectory() as tmpdir:
            assert ARBITER.encode_directory(tmpdir, data, ext=str(ext))[0]
            assert (
                await ARBITER.encode_directory_async(
                    tmpdir, data, ext=str(ext)
                )
            )[0]
            assert not ARBITER.encode_directory(tmpdir, data, ext="unknown")[0]

        # Verify we can load each file.
        for fname in "abc":
            path = ext.apply(Path(ext_root, fname))
            expected = {f"{fname}_section_1": {"a": "a", "b": "b", "c": "c"}}

            data = ARBITER.decode(
                path, require_success=True, preprocessor=lambda x: x
            ).data
            assert (
                await ARBITER.decode_async(
                    path, require_success=True, preprocessor=lambda x: x
                )
            ).data == data
            with suppress(KeyError):
                del data["DEFAULT"]

            assert data == expected

            # Verify we can encode data.
            verify_can_encode(data, ext)


@mark.asyncio
async def test_arbiter_decode_empty():
    """Verify we can decode certain kinds of empty files."""

    empty = resource("simple_decode").joinpath("empty")
    counter = 0

    for ext in DataMapping.mapping:
        candidate = ext.apply(empty.joinpath("empty"))
        if candidate.is_file():
            data = ARBITER.decode(candidate).data
            assert not data
            assert not (await ARBITER.decode_async(candidate)).data
            counter += 1

    assert counter == 2


@mark.asyncio
async def test_arbiter_decode_failures():
    """Test various invalid loading scenarios."""

    base = resource("simple_decode", valid=False)

    # Verify we can't load data of all mapped file types.
    for ext in list(DataMapping.mapping.keys()) + [FileExtension.UNKNOWN]:
        ext_root = Path(base, str(ext))
        for fname in "abc":
            path = ext.apply(Path(ext_root, fname))
            assert not ARBITER.decode(path)
            assert not await ARBITER.decode_async(path)

            if ext is FileExtension.UNKNOWN:
                with path.open(encoding="utf-8") as path_fd:
                    assert not ARBITER.decode_stream(str(ext), path_fd).success


@mark.asyncio
async def test_arbiter_decode_directory_recurse():
    """Ensure we can successfully recurse a directory."""

    expected = {
        "a_section_1": {"a": "a", "b": "b", "c": "c"},
        "b_section_1": {"a": "a", "b": "b", "c": "c"},
        "c_section_1": {"a": "a", "b": "b", "c": "c"},
    }

    path = resource("simple_decode").joinpath("recurse")

    assert (
        ARBITER.decode_directory(path, require_success=True, recurse=True).data
        == expected
    )
    assert (
        await ARBITER.decode_directory_async(
            path, require_success=True, recurse=True
        )
    ).data == expected


@mark.asyncio
async def test_arbiter_decode_includes():
    """Test that we can load data via the 'includes' key."""

    expected = {
        "a_section_1": {"a": "a", "b": "b", "c": "c"},
        "b_section_1": {"a": "a", "b": "b", "c": "c"},
        "c_section_1": {"a": "a", "b": "b", "c": "c"},
    }
    path = resource("simple_decode").joinpath("includes")

    assert (
        ARBITER.decode_directory(
            path, require_success=True, includes_key="includes"
        ).data
        == expected
    )

    assert (
        await ARBITER.decode_directory_async(
            path, require_success=True, includes_key="includes"
        )
    ).data == expected


@mark.asyncio
async def test_arbiter_decode_includes_left():
    """Test that we can load data via the 'includes_left' key."""

    expected = {
        "a": [2, 0, 1],
        "b": [2, 0, 1],
        "c": [2, 0, 1],
    }

    path = resource("simple_decode").joinpath("includes_left", "test.yaml")

    assert (
        ARBITER.decode(
            path, require_success=True, includes_key="includes"
        ).data
        == expected
    )
    assert (
        await ARBITER.decode_async(
            path, require_success=True, includes_key="includes"
        )
    ).data == expected
