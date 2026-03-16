from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import AppConfig
from app.providers.factory import build_providers
from app.server.session import TranslationSession
from app.storage import HistoryStore

logger = logging.getLogger(__name__)


@dataclass
class BackendState:
    config: AppConfig
    history: HistoryStore


def create_backend_app(config: AppConfig, history: HistoryStore) -> FastAPI:
    app = FastAPI(title="Local Translator Orchestrator", version="0.1.0")
    app.state.backend = BackendState(config=config, history=history)
    asr_provider, mt_provider = build_providers(
        config.provider,
        config.offline_asr,
        config.offline_translate,
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/history/clear")
    async def clear_history() -> dict[str, bool]:
        history.clear()
        return {"ok": True}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        session = TranslationSession(
            websocket=websocket,
            config=config,
            asr_provider=asr_provider,
            translate_provider=mt_provider,
            history=history,
        )
        heartbeat_task = asyncio.create_task(session.heartbeat_loop())
        try:
            while True:
                raw = await websocket.receive_json()
                await session.handle(raw)
        except WebSocketDisconnect:
            logger.info("ws disconnected")
        except Exception as exc:  # noqa: BLE001
            logger.exception("ws exception")
            await session.send("session.error", {"code": "ws_exception", "message": str(exc)})
        finally:
            heartbeat_task.cancel()
            try:
                await session.shutdown(ts_seconds=0.0)
            except Exception:  # noqa: BLE001
                logger.exception("flush failure")
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001
                pass

    return app


def parse_message(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("message must be object")
    if "type" not in raw:
        raise ValueError("type missing")
    return raw
