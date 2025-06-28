"""
Test the 'io.bus' module.
"""

# third-party
from pytest import mark

from vcorelib.dict import GenericStrDict

# module under test
from vcorelib.io.bus import BUS


@mark.asyncio
async def test_message_bus_basic():
    """Test basic interactions with a message bus."""

    async def ro_handler1(payload: GenericStrDict) -> None:
        """Handle a bus message."""
        del payload

    async def ro_handler2(payload: GenericStrDict) -> None:
        """Handle a bus message."""
        del payload

    BUS.register_ro("test", ro_handler1)
    BUS.register_ro("test", ro_handler2)
    assert await BUS.send_ro("test", {}) == 2

    async def handler(payload: GenericStrDict, outbox: GenericStrDict) -> None:
        """Handle a bus message."""
        outbox.update(payload)

    BUS.register("test", "a", handler)
    BUS.register("test", "b", handler)
    BUS.register("test", "c", handler)
    assert (await BUS.send("test", {"d": 4})) == {
        "a": {"d": 4},
        "b": {"d": 4},
        "c": {"d": 4},
    }
