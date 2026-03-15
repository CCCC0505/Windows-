from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ASREvent:
    text: str
    is_final: bool
    start_ts: float
    end_ts: float


class ASRProvider(ABC):
    @abstractmethod
    async def transcribe_segment(self, pcm16: bytes, sample_rate: int, start_ts: float, end_ts: float) -> list[ASREvent]:
        raise NotImplementedError


class TranslateProvider(ABC):
    @abstractmethod
    async def translate(self, text: str, source_lang: str | None, target_lang: str) -> str:
        raise NotImplementedError
