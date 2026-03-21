"""
Test the 'io.bus' module.
"""

# third-party
from pytest import mark

from vcorelib.dict import GenericStrDict

# module under test
from vcorelib.io.bus import BUS


@mark.asyncio
async def test_message_bus_scoped():
    """Test basic interactions with a message bus."""

    counter = 0

    async def scoped_ro_handler(payload: GenericStrDict) -> bool:
        """Handle a bus message."""
        nonlocal counter
        counter += 1
        return payload.get("continue", True)  # type: ignore

    key = "scoped_test"
    ident = BUS.register_scoped_ro(key, scoped_ro_handler)
    for _ in range(10):
        assert await BUS.send_ro(key, {}) == 1
    assert counter == 10

    assert await BUS.send_ro(key, {"continue": False}) == 1
    assert await BUS.send_ro(key, {}) == 0

    assert not BUS.remove_scoped_ro(key, ident)
    ident = BUS.register_scoped_ro(key, scoped_ro_handler)
    assert BUS.remove_scoped_ro(key, ident)


@mark.asyncio
async def test_message_bus_basic():
    """Test basic interactions with a message bus."""

    assert (
        await BUS.send_ro(
            "log", {"msg": "%s, %s!", "args": ["hello", "world"]}
        )
        == 1
    )

    async def ro_handler1(payload: GenericStrDict) -> None:
        """Handle a bus message."""
        del payload

    async def ro_handler2(payload: GenericStrDict) -> None:
        """Handle a bus message."""
        del payload

    assert (await BUS.send("test", {"d": 4}, send_ro=False)) == {}
    assert await BUS.send_ro("test", {}) == 0

    BUS.register_ro("test", ro_handler1)
    BUS.register_ro("test", ro_handler2)
    assert await BUS.send_ro("test", {}) == 2

    async def handler(payload: GenericStrDict, outbox: GenericStrDict) -> None:
        """Handle a bus message."""
        outbox.update(payload)

    assert (await BUS.send("test", {"d": 4})) == {}

    BUS.register("test", "a", handler)
    BUS.register("test", "b", handler)
    BUS.register("test", "c", handler)
    assert (await BUS.send("test", {"d": 4})) == {
        "a": {"d": 4},
        "b": {"d": 4},
        "c": {"d": 4},
    }
