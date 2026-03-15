from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.providers.base import TranslateProvider

# Keep Argos stanza-based segmentation enabled, but point model downloads to reachable endpoints.
os.environ.setdefault("STANZA_RESOURCES_URL", "stanford")
os.environ.setdefault(
    "STANZA_MODEL_URL",
    "https://hf-mirror.com/stanfordnlp/stanza-{lang}/resolve/v{resources_version}/models/{filename}",
)

try:
    import argostranslate.package  # type: ignore
    import argostranslate.translate  # type: ignore
except Exception:  # noqa: BLE001
    argostranslate = None


def _normalize_lang(value: str) -> str:
    v = value.strip().lower().replace("_", "-")
    mapping = {
        "zh-cn": "zh",
        "zh-hans": "zh",
        "zh-hant": "zh",
        "cn": "zh",
    }
    return mapping.get(v, v)


def _chunk_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    words = text.split(" ")
    out: list[str] = []
    buf = []
    current = 0
    for word in words:
        piece = (word + " ").strip()
        if current + len(piece) + 1 > max_chars and buf:
            out.append(" ".join(buf))
            buf = [word]
            current = len(word)
        else:
            buf.append(word)
            current += len(piece) + 1
    if buf:
        out.append(" ".join(buf))
    return [x for x in out if x.strip()]


@dataclass
class OfflineArgosTranslateProvider(TranslateProvider):
    source_lang: str = "en"
    target_lang: str = "zh"
    model_path: str = ""
    max_chars_per_chunk: int = 300
    timeout_ms: int = 6000

    def __post_init__(self) -> None:
        self._translations: dict[tuple[str, str], Any] = {}
        self._init_error: str | None = None

        if argostranslate is None:
            self._init_error = "argostranslate_not_installed"
            return

        # Stanza defaults to checking network updates on each Pipeline init.
        # Force local-only behavior to keep runtime fully offline once models are present.
        try:
            stanza_mod = getattr(argostranslate.translate, "stanza", None)
            if stanza_mod is not None and not getattr(stanza_mod, "_argos_no_download_patch", False):
                original_pipeline = stanza_mod.Pipeline

                def _pipeline_no_download(*args, **kwargs):
                    kwargs.setdefault("download_method", None)
                    return original_pipeline(*args, **kwargs)

                stanza_mod.Pipeline = _pipeline_no_download
                stanza_mod._argos_no_download_patch = True
        except Exception:  # noqa: BLE001
            pass

        # Optional: install a local .argosmodel package path if provided.
        if self.model_path:
            model_file = Path(self.model_path)
            if model_file.exists() and model_file.is_file():
                try:
                    argostranslate.package.install_from_path(str(model_file))
                except Exception as exc:  # noqa: BLE001
                    self._init_error = f"argos_model_install_failed:{exc}"
                    return
            elif model_file.exists() and model_file.is_dir():
                # Directory models are considered pre-installed externally.
                pass
            else:
                self._init_error = f"argos_model_path_not_found:{self.model_path}"
                return

        try:
            # Preload the default pair for fast first-call response and early validation.
            self._get_translation(source_lang=self.source_lang, target_lang=self.target_lang)
        except Exception as exc:  # noqa: BLE001
            self._init_error = f"argos_init_failed:{exc}"
            self._translations = {}

    async def translate(self, text: str, source_lang: str | None, target_lang: str) -> str:
        if not text.strip():
            return ""
        if argostranslate is None:
            raise RuntimeError(self._init_error or "argostranslate_not_installed")

        src = _normalize_lang(source_lang or self.source_lang)
        tgt = _normalize_lang(target_lang or self.target_lang)

        try:
            translation = self._get_translation(source_lang=src, target_lang=tgt)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"argos_translation_unavailable:{src}->{tgt}:{exc}") from exc

        chunks = _chunk_text(text, max(20, int(self.max_chars_per_chunk)))
        if not chunks:
            return ""
        task = asyncio.create_task(self._translate_chunks(chunks, translation))
        return await asyncio.wait_for(task, timeout=max(0.5, self.timeout_ms / 1000.0))

    def _get_translation(self, source_lang: str, target_lang: str) -> Any:
        key = (source_lang, target_lang)
        cached = self._translations.get(key)
        if cached is not None:
            return cached
        if argostranslate is None:
            raise RuntimeError("argostranslate_not_installed")

        installed = argostranslate.translate.get_installed_languages()
        from_lang = next((x for x in installed if x.code == source_lang), None)
        to_lang = next((x for x in installed if x.code == target_lang), None)
        if from_lang is None or to_lang is None:
            raise RuntimeError(f"argos_lang_not_installed:{source_lang}->{target_lang}")

        translation = from_lang.get_translation(to_lang)
        self._translations[key] = translation
        return translation

    async def _translate_chunks(self, chunks: list[str], translation: Any) -> str:
        loop = asyncio.get_running_loop()

        def _sync_translate() -> str:
            out = [translation.translate(c) for c in chunks]
            return " ".join(x.strip() for x in out if x and x.strip())

        return await loop.run_in_executor(None, _sync_translate)
