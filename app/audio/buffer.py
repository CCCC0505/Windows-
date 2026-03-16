from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class AudioChunk:
    ts: float
    pcm16: bytes


class BoundedAudioQueue:
    def __init__(self, maxsize: int) -> None:
        self._queue: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=maxsize)
        self._dropped = 0

    @property
    def dropped(self) -> int:
        return self._dropped

    async def put(self, chunk: AudioChunk) -> None:
        if self._queue.full():
            _ = self._queue.get_nowait()
            self._queue.task_done()
            self._dropped += 1
        await self._queue.put(chunk)

    async def get(self) -> AudioChunk:
        chunk = await self._queue.get()
        return chunk

    def task_done(self) -> None:
        self._queue.task_done()
