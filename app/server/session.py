from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.audio.vad import EnergyVADSegmenter, VADConfig
from app.config import AppConfig
from app.protocol import Message, decode_audio_chunk
from app.providers.base import ASRProvider, TranslateProvider
from app.providers.offline_local_provider import OfflineLocalASRProvider
from app.session_recorder import SessionRecordEntry, SessionRecorder
from app.storage import HistoryStore
from app.utils.retry import CircuitBreaker, RetryPolicy, with_retry

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    target_language: str = "zh"
    source_language: str | None = None
    source_model: str = "en"
    active: bool = False


class TranslationSession:
    def __init__(
        self,
        websocket: WebSocket,
        config: AppConfig,
        asr_provider: ASRProvider,
        translate_provider: TranslateProvider,
        history: HistoryStore,
    ) -> None:
        self.websocket = websocket
        self.config = config
        self.asr_provider = asr_provider
        self.translate_provider = translate_provider
        self.history = history
        self.state = SessionState(
            target_language=config.subtitle.target_language,
            source_model=config.offline_asr.source_model,
        )
        segment_limit_ms = int(max(1.0, config.offline_asr.segment_seconds) * 1000.0)
        self.segmenter = EnergyVADSegmenter(
            VADConfig(
                sample_rate=config.audio.sample_rate,
                frame_ms=config.audio.frame_ms,
                energy_threshold=config.audio.vad_energy_threshold,
                silence_ms=config.audio.vad_silence_ms,
                max_segment_ms=min(config.audio.max_segment_ms, segment_limit_ms),
            )
        )
        self.retry_policy = RetryPolicy(max_retries=config.provider.max_retries)
        self.asr_breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=20)
        self.translate_breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=20)
        self._process_lock = asyncio.Lock()
        self.session_recorder: SessionRecorder | None = None
        self._segment_count = 0
        self._provider_mode = config.provider.mode

    async def handle(self, raw: dict[str, Any]) -> None:
        message = Message.from_dict(raw)
        if message.type == "session.start":
            await self._handle_start(message.payload)
            return
        if message.type == "audio.chunk":
            await self._handle_audio_chunk(message.payload)
            return
        if message.type == "session.end":
            self.state.active = False
            self._close_recorder()
            await self.send("session.end", {"reason": "client-ended"})
            return
        if message.type == "session.heartbeat":
            await self.send("session.heartbeat", {"ok": True})
            return

    async def _handle_start(self, payload: dict[str, Any]) -> None:
        self.state.target_language = str(payload.get("target_language", self.config.subtitle.target_language))
        self.state.source_model = str(payload.get("source_model", self.config.offline_asr.source_model or "en"))
        source = payload.get("source_language")
        if source:
            self.state.source_language = str(source)
        else:
            self.state.source_language = "zh" if self.state.source_model.lower() == "zh" else "en"
        self.state.active = True
        self._segment_count = 0
        self.asr_breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=20)
        self.translate_breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=20)

        if self._provider_mode == "offline_local":
            self._refresh_offline_source_model_provider()
            self._close_recorder()
            self.session_recorder = SessionRecorder(self.config.offline_asr.output_dir)

        payload_out: dict[str, Any] = {
            "status": "ok",
            "target_language": self.state.target_language,
            "source_model": self.state.source_model,
            "sample_rate": self.config.audio.sample_rate,
            "provider_mode": self._provider_mode,
            "translate_backend": self._detect_translate_backend(),
        }
        if self.session_recorder is not None:
            payload_out["record_md_path"] = str(self.session_recorder.md_path)
            payload_out["record_txt_path"] = str(self.session_recorder.txt_path)

        await self.send(
            "session.start",
            payload_out,
        )

    async def _handle_audio_chunk(self, payload: dict[str, Any]) -> None:
        if not self.state.active:
            await self.send("session.error", {"code": "not_started", "message": "session.start required"})
            return
        encoded = payload.get("pcm16_b64")
        ts_seconds = float(payload.get("timestamp", 0.0))
        if not isinstance(encoded, str):
            await self.send("session.error", {"code": "bad_audio", "message": "pcm16_b64 missing"})
            return

        segments = self.segmenter.push(decode_audio_chunk(encoded), ts_seconds)
        for start_ts, end_ts, pcm16 in segments:
            await self._process_segment(start_ts, end_ts, pcm16)

    async def _process_segment(self, start_ts: float, end_ts: float, pcm16: bytes) -> None:
        async with self._process_lock:
            started = time.perf_counter()
            try:
                asr_events = await self._run_asr(start_ts, end_ts, pcm16)
            except Exception as exc:  # noqa: BLE001
                logger.exception("asr failed")
                await self._emit_error("asr_failed", str(exc))
                return

            for event in asr_events:
                await self.send(
                    "transcript.partial",
                    {
                        "text": event.text,
                        "is_final": event.is_final,
                        "start_ts": event.start_ts,
                        "end_ts": event.end_ts,
                    },
                )
                if not event.is_final:
                    continue

                try:
                    translated, backend_used = await self._run_translate(event.text)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("translate failed")
                    await self._emit_error("translate_failed", str(exc))
                    translated = f"待翻译: {event.text}"
                    backend_used = "placeholder"

                await self.send(
                    "translation.partial",
                    {
                        "translated_text": translated,
                        "start_ts": event.start_ts,
                        "end_ts": event.end_ts,
                    },
                )
                await self.send(
                    "translation.final",
                    {
                        "source_text": event.text,
                        "translated_text": translated,
                        "start_ts": event.start_ts,
                        "end_ts": event.end_ts,
                        "latency_ms": (time.perf_counter() - started) * 1000.0,
                        "translation_backend_used": backend_used,
                    },
                )

                try:
                    self.history.insert(
                        start_ts=event.start_ts,
                        end_ts=event.end_ts,
                        source_text=event.text,
                        translated_text=translated,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("history write failed")
                    await self._emit_error("history_write_failed", str(exc))

                if self.session_recorder is not None:
                    try:
                        self.session_recorder.append(
                            SessionRecordEntry(
                                start_ts=event.start_ts,
                                end_ts=event.end_ts,
                                source_text=event.text,
                                translated_text=translated,
                                source_lang_model=self.state.source_model,
                                translation_backend_used=backend_used,
                                created_at=datetime.utcnow().isoformat(),
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("session record write failed")
                        await self._emit_error("record_write_failed", str(exc))

                self._segment_count += 1

    async def heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(10)
            try:
                await self.send("session.heartbeat", {"ok": True})
            except Exception:  # noqa: BLE001
                return

    async def flush(self, ts_seconds: float) -> None:
        segment = self.segmenter.flush(ts_seconds)
        if segment is None:
            return
        start_ts, end_ts, pcm16 = segment
        await self._process_segment(start_ts, end_ts, pcm16)

    async def shutdown(self, ts_seconds: float) -> None:
        try:
            await self.flush(ts_seconds=ts_seconds)
        finally:
            self._close_recorder()

    async def send(self, msg_type: str, payload: dict[str, Any]) -> None:
        if self.websocket.application_state != WebSocketState.CONNECTED:
            return
        await self.websocket.send_json(Message(type=msg_type, payload=payload).to_dict())

    async def _emit_error(self, code: str, message: str) -> None:
        await self.send("session.error", {"code": code, "message": message})

    async def _run_asr(self, start_ts: float, end_ts: float, pcm16: bytes):
        if self._provider_mode == "offline_local":
            return await self.asr_provider.transcribe_segment(
                pcm16=pcm16,
                sample_rate=self.config.audio.sample_rate,
                start_ts=start_ts,
                end_ts=end_ts,
            )
        return await with_retry(
            lambda: self.asr_provider.transcribe_segment(
                pcm16=pcm16,
                sample_rate=self.config.audio.sample_rate,
                start_ts=start_ts,
                end_ts=end_ts,
            ),
            policy=self.retry_policy,
            breaker=self.asr_breaker,
        )

    async def _run_translate(self, text: str) -> tuple[str, str]:
        if self._provider_mode == "offline_local":
            try:
                translated = await self.translate_provider.translate(
                    text=text,
                    source_lang=self.state.source_language,
                    target_lang=self.state.target_language,
                )
                return translated, self._detect_translate_backend()
            except Exception as exc:  # noqa: BLE001
                # Keep local speech-to-text usable even when translation backend is unavailable.
                logger.warning("offline translate unavailable, fallback to passthrough: %s", exc)
                return text, "passthrough"
        return await with_retry(
            lambda: self.translate_provider.translate(
                text=text,
                source_lang=self.state.source_language,
                target_lang=self.state.target_language,
            ),
            policy=self.retry_policy,
            breaker=self.translate_breaker,
        ), self._detect_translate_backend()

    def _close_recorder(self) -> None:
        if self.session_recorder is None:
            return
        try:
            self.session_recorder.close()
        finally:
            self.session_recorder = None

    def _refresh_offline_source_model_provider(self) -> None:
        if not isinstance(self.asr_provider, OfflineLocalASRProvider):
            return

        requested_source_model = (self.state.source_model or "en").strip().lower()
        current_source_model = (self.asr_provider.source_model or "").strip().lower()
        if requested_source_model == current_source_model:
            return

        configured_source_model = (self.config.offline_asr.source_model or "").strip().lower()
        # When runtime model choice differs from config default, fall back to language-based model discovery.
        model_path = self.config.offline_asr.model_path if requested_source_model == configured_source_model else ""

        self.asr_provider = OfflineLocalASRProvider(
            model_size=self.config.offline_asr.model_size,
            language=self.config.offline_asr.language,
            device=self.config.offline_asr.device,
            source_model=requested_source_model,
            model_path=model_path,
        )
        self.config.offline_asr.source_model = requested_source_model

    def _detect_translate_backend(self) -> str:
        name = type(self.translate_provider).__name__.lower()
        if "placeholder" in name:
            return "placeholder"
        if "argos" in name:
            return "argos"
        if "tencent" in name:
            return "tencent"
        if "cloud" in name:
            return "cloud"
        return "unknown"
