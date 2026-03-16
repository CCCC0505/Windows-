from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.providers.base import ASREvent, ASRProvider, TranslateProvider

try:
    from vosk import KaldiRecognizer, Model  # type: ignore
except Exception:  # noqa: BLE001
    KaldiRecognizer = None
    Model = None


def _segment_placeholder(pcm16: bytes, sample_rate: int) -> str:
    seconds = len(pcm16) / 2.0 / max(sample_rate, 1)
    return f"[audio_segment {seconds:.1f}s]"


@dataclass
class OfflineLocalASRProvider(ASRProvider):
    model_size: str = "small"
    language: str = "auto"
    device: str = "cpu"
    source_model: str = "en"
    model_path: str = ""

    def __post_init__(self) -> None:
        self._model = None
        self._model_error: str | None = None
        # Optional Vosk integration. If unavailable, we still produce stable segment placeholders.
        if Model is None or KaldiRecognizer is None:
            self._model_error = "vosk_not_installed"
            return
        try:
            # Prefer explicit local model path to avoid runtime network downloads.
            candidate_path = self._resolve_model_path()
            if candidate_path:
                self._model = Model(str(candidate_path))
            else:
                self._model_error = "vosk_model_path_not_found"
                self._model = None
                return
        except Exception as exc:  # noqa: BLE001
            self._model_error = str(exc)
            self._model = None

    async def transcribe_segment(self, pcm16: bytes, sample_rate: int, start_ts: float, end_ts: float) -> list[ASREvent]:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, self._transcribe_sync, pcm16, sample_rate)
        if not text:
            return []
        return [ASREvent(text=text, is_final=True, start_ts=start_ts, end_ts=end_ts)]

    def _transcribe_sync(self, pcm16: bytes, sample_rate: int) -> str:
        if self._model is None or KaldiRecognizer is None:
            return _segment_placeholder(pcm16, sample_rate)
        try:
            rec = KaldiRecognizer(self._model, float(sample_rate))
            rec.SetWords(False)
            rec.AcceptWaveform(pcm16)
            result_raw = rec.FinalResult()
            result = json.loads(result_raw) if result_raw else {}
            text = str(result.get("text", "")).strip()
            return text or _segment_placeholder(pcm16, sample_rate)
        except Exception:  # noqa: BLE001
            return _segment_placeholder(pcm16, sample_rate)

    def _resolve_model_path(self) -> Path | None:
        # 1) explicit config path
        if self.model_path:
            explicit = Path(self.model_path)
            if explicit.exists() and explicit.is_dir():
                normalized = self._normalize_model_root(explicit)
                if normalized is not None:
                    return normalized

        # 2) language-based defaults
        source = (self.source_model or "").strip().lower()
        default_candidates: list[Path]
        if source == "zh":
            default_candidates = [
                Path("models/vosk-model-cn-0.22"),
                Path("models/vosk-model-small-cn-0.22"),
            ]
        else:
            default_candidates = [
                Path("models/vosk-model-en-us-0.22"),
                Path("models/vosk-model-small-en-us-0.15"),
            ]
        for p in default_candidates:
            if p.exists() and p.is_dir():
                normalized = self._normalize_model_root(p)
                if normalized is not None:
                    return normalized

        # 3) final fallback: deterministically pick the best local model.
        models_dir = Path("models")
        if models_dir.exists():
            candidates = [child for child in models_dir.iterdir() if child.is_dir() and child.name.startswith("vosk-model")]
            if not candidates:
                return None
            preferred_tokens = ("cn", "zh") if source == "zh" else ("en-us", "en")

            def _score(path: Path) -> tuple[int, int, int, int]:
                name = path.name.lower()
                source_match = 1 if any(token in name for token in preferred_tokens) else 0
                full_model = 0 if "small" in name else 1
                version_major = 0
                version_minor = 0
                version_match = re.search(r"(\d+)\.(\d+)", name)
                if version_match:
                    version_major = int(version_match.group(1))
                    version_minor = int(version_match.group(2))
                return (source_match, full_model, version_major, version_minor)

            candidates.sort(key=_score, reverse=True)
            for candidate in candidates:
                normalized = self._normalize_model_root(candidate)
                if normalized is not None:
                    return normalized
        return None

    @staticmethod
    def _is_vosk_model_root(path: Path) -> bool:
        has_acoustic = (path / "am" / "final.mdl").exists() or (path / "final.mdl").exists()
        has_config = (path / "conf" / "model.conf").exists()
        has_graph = (path / "graph").exists() or (path / "words.txt").exists()
        return has_acoustic and (has_config or has_graph)

    def _normalize_model_root(self, path: Path) -> Path | None:
        if self._is_vosk_model_root(path):
            return path
        # Some zip extractions produce a wrapper directory containing the real model directory.
        for child in path.iterdir():
            if child.is_dir() and self._is_vosk_model_root(child):
                return child
        return None


@dataclass
class PlaceholderTranslateProvider(TranslateProvider):
    prefix: str = "待翻译"

    async def translate(self, text: str, source_lang: str | None, target_lang: str) -> str:
        if not self.prefix.strip():
            return text
        return f"{self.prefix}: {text}"
