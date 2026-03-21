"""
A module implementing a message bus interface.
"""

# built-in
import asyncio
from logging import INFO
from typing import Any, Awaitable, Callable

# internal
from vcorelib.dict import GenericStrDict
from vcorelib.logging import LoggerMixin

# async def handler(payload: GenericStrDict, outbox: GenericStrDict) -> None:
#     """Handle a bus message."""
BusMessageHandler = Callable[[GenericStrDict, GenericStrDict], Awaitable[None]]
BusMessageResponse = dict[str, GenericStrDict]
# When the scoped handler returns false, it is unregistered.
BusScopedMessageHandler = Callable[
    [GenericStrDict, GenericStrDict], Awaitable[bool]
]


# async def ro_handler(payload: GenericStrDict) -> None:
#     """Handle a bus message."""
BusRoMessageHandler = Callable[[GenericStrDict], Awaitable[None]]
# When the scoped handler returns false, it is unregistered.
BusScopedRoMessageHandler = Callable[[GenericStrDict], Awaitable[bool]]


class AsyncMessageBus(LoggerMixin):
    """A class implementing a runtime message bus interface."""

    def __init__(self) -> None:
        """Initialize this instance."""

        super().__init__()
        self.handlers: dict[str, dict[str, BusMessageHandler]] = {}
        self.ro_handlers: dict[str, list[BusRoMessageHandler]] = {}
        self.scoped_ro_handlers: dict[
            str, dict[int, BusScopedRoMessageHandler]
        ] = {}
        self.scoped_ro_ident: int = 0

        # Standard interfaces.

        async def log_handler(payload: GenericStrDict) -> None:
            """Handle a bus message."""

            self.logger.log(
                payload.get("level", INFO),
                payload.get("msg", ""),
                *payload.get("args", []),
                **payload.get("kwargs", {}),
            )

        self.register_ro("log", log_handler)

    def register_ro(self, key: str, handler: BusRoMessageHandler) -> None:
        """Register a bus message handler."""
        self.ro_handlers.setdefault(key, [])
        self.ro_handlers[key].append(handler)

    def register_scoped_ro(
        self, key: str, handler: BusScopedRoMessageHandler
    ) -> int:
        """Register a bus message handler."""

        self.scoped_ro_handlers.setdefault(key, {})
        result = self.scoped_ro_ident
        self.scoped_ro_handlers[key][result] = handler
        self.scoped_ro_ident += 1
        return result

    def remove_scoped_ro(self, key: str, ident: int) -> bool:
        """Remove a scoped read only handler."""
        return self.scoped_ro_handlers[key].pop(ident, None) is not None

    def register(
        self, key: str, ident: str, handler: BusMessageHandler
    ) -> None:
        """Register a bus message handler."""

        self.handlers.setdefault(key, {})
        assert ident not in self.handlers[key], (key, ident)
        self.handlers[key][ident] = handler

    async def send_ro(
        self, key: str, payload: GenericStrDict, null_ok: bool = False
    ) -> int:
        """
        Send a message to read-only handlers, returns the number of handlers
        called.
        """

        count = 0

        has_regular = key in self.ro_handlers
        if has_regular:
            count = len(self.ro_handlers[key])
        has_scoped = key in self.scoped_ro_handlers
        if has_scoped:
            count += len(self.scoped_ro_handlers[key])

        if count:
            # Regular handlers.
            if has_regular:
                await asyncio.gather(
                    *(x(payload) for x in self.ro_handlers[key]),
                )

            # Scoped handlers.
            if has_scoped:
                handlers = self.scoped_ro_handlers[key]
                for result, ident in zip(
                    await asyncio.gather(
                        *(x(payload) for x in handlers.values()),
                    ),
                    list(handlers.keys()),
                ):
                    if not result:
                        del handlers[ident]

        elif not null_ok:
            self.logger.warning(
                "No recipient for read-only bus message '%s' %s.", key, payload
            )

        return count

    async def send(
        self,
        key: str,
        payload: GenericStrDict,
        send_ro: bool = True,
        null_ok: bool = False,
    ) -> BusMessageResponse:
        """Send a message and gather responses."""

        result: BusMessageResponse = {}

        # Regular handlers.
        tasks: list[Awaitable[Any]] = [
            handler(payload, result.setdefault(ident, {}))
            for ident, handler in self.handlers.get(key, {}).items()
        ]

        # Scoped handlers.

        if send_ro:
            tasks.append(self.send_ro(key, payload))
        elif not tasks and not null_ok:
            self.logger.warning(
                "No recipient for bus message '%s' %s.", key, payload
            )

        await asyncio.gather(*tasks)

        return result


BUS = AsyncMessageBus()
