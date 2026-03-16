from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.providers.base import ASREvent, ASRProvider, TranslateProvider


@dataclass
class CloudASRProvider(ASRProvider):
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int

    async def transcribe_segment(self, pcm16: bytes, sample_rate: int, start_ts: float, end_ts: float) -> list[ASREvent]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "audio_b64": pcm16.hex(),
            "sample_rate": sample_rate,
            "start_ts": start_ts,
            "end_ts": end_ts,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(f"{self.base_url.rstrip('/')}/asr", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        text = str(data.get("text", "")).strip()
        return [ASREvent(text=text, is_final=True, start_ts=start_ts, end_ts=end_ts)]


@dataclass
class CloudTranslateProvider(TranslateProvider):
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int

    async def translate(self, text: str, source_lang: str | None, target_lang: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(f"{self.base_url.rstrip('/')}/translate", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return str(data.get("translation", "")).strip()
