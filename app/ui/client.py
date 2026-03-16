from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Awaitable
from concurrent.futures import Future

import websockets
from PySide6.QtCore import QObject, Signal

from app.protocol import Message, encode_audio_chunk


class BackendClient(QObject):
    connected = Signal()
    disconnected = Signal()
    session_started = Signal(dict)
    transcript_partial = Signal(str, bool)
    translation_partial = Signal(str)
    translation_final = Signal(dict)
    session_error = Signal(str)
    status_changed = Signal(str)

    def __init__(self, ws_url: str) -> None:
        super().__init__()
        self.ws_url = ws_url
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._socket: websockets.WebSocketClientProtocol | None = None
        self._stop_event = threading.Event()
        self._connected_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop is not None:
            self._submit(self._close_socket())
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._loop = None

    def start_session(self, target_language: str, source_model: str = "en") -> None:
        self._connected_event.wait(timeout=3.0)
        self._send(
            Message(
                type="session.start",
                payload={
                    "target_language": target_language,
                    "source_language": None,
                    "source_model": source_model,
                },
            ).to_dict()
        )

    def stop_session(self) -> None:
        self._send(Message(type="session.end", payload={}).to_dict())

    def send_audio_chunk(self, ts: float, pcm16: bytes) -> None:
        self._send(
            Message(type="audio.chunk", payload={"timestamp": ts, "pcm16_b64": encode_audio_chunk(pcm16)}).to_dict()
        )

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        loop.create_task(self._connect_forever())
        loop.run_forever()

    async def _connect_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.status_changed.emit("connecting")
                async with websockets.connect(self.ws_url, max_queue=512) as ws:
                    self._socket = ws
                    self._connected_event.set()
                    self.connected.emit()
                    self.status_changed.emit("connected")
                    while not self._stop_event.is_set():
                        raw = await ws.recv()
                        if isinstance(raw, bytes):
                            continue
                        self._handle_message(raw)
            except Exception as exc:  # noqa: BLE001
                self.session_error.emit(str(exc))
                self.status_changed.emit("reconnecting")
                await asyncio.sleep(1.0)
            finally:
                self._socket = None
                self._connected_event.clear()
                self.disconnected.emit()

    async def _close_socket(self) -> None:
        if self._socket is not None:
            await self._socket.close()

    def _handle_message(self, raw: str) -> None:
        try:
            message = Message.from_dict(json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            self.session_error.emit(f"message decode failed: {exc}")
            return

        if message.type == "transcript.partial":
            self.transcript_partial.emit(str(message.payload.get("text", "")), bool(message.payload.get("is_final", False)))
        elif message.type == "session.start":
            self.session_started.emit(message.payload)
        elif message.type == "translation.partial":
            self.translation_partial.emit(str(message.payload.get("translated_text", "")))
        elif message.type == "translation.final":
            self.translation_final.emit(message.payload)
        elif message.type == "session.error":
            code = str(message.payload.get("code", "unknown"))
            detail = str(message.payload.get("message", "unknown error"))
            self.session_error.emit(f"{_error_prefix(code)}{detail}")

    def _send(self, payload: dict) -> None:
        if self._loop is None:
            self.session_error.emit("backend loop not started")
            return
        self._submit(self._send_async(payload))

    async def _send_async(self, payload: dict) -> None:
        if self._socket is None:
            return
        await self._socket.send(json.dumps(payload, ensure_ascii=False))

    def _submit(self, coro: Awaitable[None]) -> Future | None:
        if self._loop is None:
            return None
        return asyncio.run_coroutine_threadsafe(coro, self._loop)


def _error_prefix(code: str) -> str:
    if code == "asr_failed":
        return "ASR错误: "
    if code == "translate_failed":
        return "翻译错误: "
    if code in {"record_write_failed", "history_write_failed"}:
        return "记录写入错误: "
    if code == "ws_exception":
        return "连接错误: "
    return ""
