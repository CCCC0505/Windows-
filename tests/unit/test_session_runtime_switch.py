from __future__ import annotations

import pytest
from starlette.websockets import WebSocketState

from app.config import (
    AppConfig,
    AudioConfig,
    HotkeyConfig,
    LoggingConfig,
    OfflineASRConfig,
    OfflineTranslateConfig,
    ProviderConfig,
    SubtitleConfig,
)
from app.providers.base import TranslateProvider
from app.providers.offline_local_provider import OfflineLocalASRProvider, PlaceholderTranslateProvider
from app.server.session import TranslationSession
from app.storage import HistoryStore


class _DummyWebSocket:
    def __init__(self) -> None:
        self.application_state = WebSocketState.CONNECTED
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


class _FailingTranslateProvider(TranslateProvider):
    async def translate(self, text: str, source_lang: str | None, target_lang: str) -> str:
        raise RuntimeError("argostranslate_not_installed")


@pytest.mark.asyncio
async def test_session_start_rebuilds_offline_asr_provider_when_source_model_changes(tmp_path) -> None:
    config = AppConfig(
        audio=AudioConfig(),
        subtitle=SubtitleConfig(),
        provider=ProviderConfig(mode="offline_local"),
        offline_asr=OfflineASRConfig(source_model="en", model_path="", output_dir=str(tmp_path / "exports")),
        logging=LoggingConfig(),
        hotkeys=HotkeyConfig(),
        offline_translate=OfflineTranslateConfig(enabled=False),
    )
    history = HistoryStore(tmp_path / "history.db")
    ws = _DummyWebSocket()
    session = TranslationSession(
        websocket=ws,
        config=config,
        asr_provider=OfflineLocalASRProvider(source_model="en"),
        translate_provider=PlaceholderTranslateProvider(),
        history=history,
    )

    await session.handle(
        {
            "type": "session.start",
            "payload": {
                "target_language": "zh",
                "source_model": "zh",
            },
        }
    )

    assert isinstance(session.asr_provider, OfflineLocalASRProvider)
    assert session.asr_provider.source_model == "zh"
    assert config.offline_asr.source_model == "zh"

    await session.shutdown(ts_seconds=0.0)
    history.close()


@pytest.mark.asyncio
async def test_session_offline_translate_falls_back_to_passthrough(tmp_path) -> None:
    config = AppConfig(
        audio=AudioConfig(),
        subtitle=SubtitleConfig(),
        provider=ProviderConfig(mode="offline_local"),
        offline_asr=OfflineASRConfig(source_model="en", output_dir=str(tmp_path / "exports")),
        logging=LoggingConfig(),
        hotkeys=HotkeyConfig(),
        offline_translate=OfflineTranslateConfig(enabled=True),
    )
    history = HistoryStore(tmp_path / "history.db")
    ws = _DummyWebSocket()
    session = TranslationSession(
        websocket=ws,
        config=config,
        asr_provider=OfflineLocalASRProvider(source_model="en"),
        translate_provider=_FailingTranslateProvider(),
        history=history,
    )

    translated, backend = await session._run_translate("hello world")
    assert translated == "hello world"
    assert backend == "passthrough"

    await session.shutdown(ts_seconds=0.0)
    history.close()
