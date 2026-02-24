"""CLI channel implementation for unified routing."""

from typing import Any, Callable, Awaitable

from nanofolks.channels.base import BaseChannel
from nanofolks.bus.events import MessageEnvelope


class CLIChannel(BaseChannel):
    """CLI channel that sends/receives messages via the bus."""

    name = "cli"

    def __init__(self, config: Any, bus, send_callback: Callable[[MessageEnvelope], Awaitable[None]]):
        super().__init__(config, bus)
        self._send_callback = send_callback

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: MessageEnvelope) -> None:
        await self._send_callback(msg)
