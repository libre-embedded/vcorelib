"""
A module implementing a message bus interface.
"""

# built-in
import asyncio
from typing import Any, Awaitable, Callable

# internal
from vcorelib.dict import GenericStrDict

# async def handler(payload: GenericStrDict, outbox: GenericStrDict) -> None:
#     """Handle a bus message."""
BusMessageHandler = Callable[[GenericStrDict, GenericStrDict], Awaitable[None]]
BusMessageResponse = dict[str, GenericStrDict]


# async def ro_handler(payload: GenericStrDict) -> None:
#     """Handle a bus message."""
BusRoMessageHandler = Callable[[GenericStrDict], Awaitable[None]]


class AsyncMessageBus:
    """A class implementing a runtime message bus interface."""

    def __init__(self) -> None:
        """Initialize this instance."""

        self.handlers: dict[str, dict[str, BusMessageHandler]] = {}
        self.ro_handlers: dict[str, list[BusRoMessageHandler]] = {}

    def register_ro(self, key: str, handler: BusRoMessageHandler) -> None:
        """Register a bus message handler."""
        self.ro_handlers.setdefault(key, [])
        self.ro_handlers[key].append(handler)

    def register(
        self, key: str, ident: str, handler: BusMessageHandler
    ) -> None:
        """Register a bus message handler."""

        self.handlers.setdefault(key, {})
        assert ident not in self.handlers[key], (key, ident)
        self.handlers[key][ident] = handler

    async def send_ro(self, key: str, payload: GenericStrDict) -> int:
        """
        Send a message to read-only handlers, returns the number of handlers
        called.
        """

        count = 0

        if key in self.ro_handlers:
            count = len(self.ro_handlers[key])
            await asyncio.gather(*(x(payload) for x in self.ro_handlers[key]))

        return count

    async def send(
        self,
        key: str,
        payload: GenericStrDict,
        send_ro: bool = True,
    ) -> BusMessageResponse:
        """Send a message and gather responses."""

        result: BusMessageResponse = {}

        tasks: list[Awaitable[Any]] = [
            handler(payload, result.setdefault(ident, {}))
            for ident, handler in self.handlers.get(key, {}).items()
        ]
        if send_ro:
            tasks.append(self.send_ro(key, payload))

        await asyncio.gather(*tasks)

        return result


BUS = AsyncMessageBus()
