from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.providers.base import ASREvent, ASRProvider, TranslateProvider


@dataclass
class MockASRProvider(ASRProvider):
    async def transcribe_segment(self, pcm16: bytes, sample_rate: int, start_ts: float, end_ts: float) -> list[ASREvent]:
        await asyncio.sleep(0.05)
        seconds = len(pcm16) / 2 / max(sample_rate, 1)
        words = max(1, int(seconds * 2))
        text = " ".join(f"token{idx}" for idx in range(words))
        mid = (start_ts + end_ts) / 2
        return [
            ASREvent(text=text[: max(5, len(text) // 2)], is_final=False, start_ts=start_ts, end_ts=mid),
            ASREvent(text=text, is_final=True, start_ts=start_ts, end_ts=end_ts),
        ]


@dataclass
class MockTranslateProvider(TranslateProvider):
    async def translate(self, text: str, source_lang: str | None, target_lang: str) -> str:
        await asyncio.sleep(0.03)
        if target_lang.lower().startswith("zh"):
            return f"模拟翻译：{text}"
        return f"mock translation: {text}"
