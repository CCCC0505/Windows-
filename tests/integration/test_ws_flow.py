import base64

import numpy as np
from fastapi.testclient import TestClient

from app.config import AppConfig, AudioConfig, HotkeyConfig, LoggingConfig, OfflineASRConfig, ProviderConfig, SubtitleConfig
from app.server.app import create_backend_app
from app.storage import HistoryStore


def _audio_b64(amp: int, n: int = 320) -> str:
    arr = np.full((n,), amp, dtype=np.int16)
    return base64.b64encode(arr.tobytes()).decode("ascii")


def test_ws_start_to_translation_final(tmp_path) -> None:
    history = HistoryStore(tmp_path / "history.db")
    config = AppConfig(
        audio=AudioConfig(vad_energy_threshold=100, vad_silence_ms=40, max_segment_ms=1000),
        subtitle=SubtitleConfig(),
        provider=ProviderConfig(mode="mock"),
        offline_asr=OfflineASRConfig(),
        logging=LoggingConfig(),
        hotkeys=HotkeyConfig(),
    )
    app = create_backend_app(config=config, history=history)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "session.start", "payload": {"target_language": "zh"}})
        _ = ws.receive_json()

        ws.send_json({"type": "audio.chunk", "payload": {"timestamp": 0.00, "pcm16_b64": _audio_b64(300)}})
        ws.send_json({"type": "audio.chunk", "payload": {"timestamp": 0.02, "pcm16_b64": _audio_b64(300)}})
        ws.send_json({"type": "audio.chunk", "payload": {"timestamp": 0.04, "pcm16_b64": _audio_b64(0)}})
        ws.send_json({"type": "audio.chunk", "payload": {"timestamp": 0.06, "pcm16_b64": _audio_b64(0)}})

        found_final = False
        for _ in range(8):
            msg = ws.receive_json()
            if msg["type"] == "translation.final":
                found_final = True
                assert "translated_text" in msg["payload"]
                break

        assert found_final
        assert len(history.list_recent(limit=5)) >= 1
