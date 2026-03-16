from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    frame_ms: int = 20
    chunk_queue_size: int = 200
    vad_energy_threshold: int = 280
    vad_silence_ms: int = 500
    max_segment_ms: int = 8000


@dataclass
class SubtitleConfig:
    target_language: str = "zh"
    font_size: int = 18
    auto_scroll: bool = True
    always_on_top: bool = True
    overlay_opacity: float = 0.82


@dataclass
class ProviderConfig:
    mode: str = "offline_local"
    asr_base_url: str = "https://example-asr.local"
    asr_model: str = "asr-realtime-v1"
    translate_base_url: str = "https://example-mt.local"
    translate_model: str = "translate-v1"
    api_key_env: str = "TRANSLATOR_API_KEY"
    api_key: str | None = None
    tencent_secret_id_env: str = "TENCENT_SECRET_ID"
    tencent_secret_key_env: str = "TENCENT_SECRET_KEY"
    tencent_secret_id: str | None = None
    tencent_secret_key: str | None = None
    tencent_region: str = "ap-guangzhou"
    tencent_project_id: int = 0
    tencent_asr_engine: str = "16k_en"
    timeout_seconds: int = 12
    max_retries: int = 2


@dataclass
class OfflineASRConfig:
    model_size: str = "small"
    segment_seconds: float = 2.5
    device: str = "cpu"
    language: str = "auto"
    source_model: str = "en"
    model_path: str = ""
    translate_backend: str = "auto"
    output_dir: str = "exports"


@dataclass
class OfflineTranslateConfig:
    backend: str = "argos"
    enabled: bool = True
    model_path: str = ""
    source_lang: str = "en"
    target_lang: str = "zh"
    max_chars_per_chunk: int = 300
    timeout_ms: int = 6000


@dataclass
class LoggingConfig:
    level: str = "INFO"
    json: bool = True
    log_file: str = "logs/app.log"


@dataclass
class HotkeyConfig:
    toggle_overlay: str = "Ctrl+Shift+O"
    start_stop: str = "Ctrl+Shift+S"


@dataclass
class AppConfig:
    audio: AudioConfig
    subtitle: SubtitleConfig
    provider: ProviderConfig
    offline_asr: OfflineASRConfig
    logging: LoggingConfig
    hotkeys: HotkeyConfig
    offline_translate: OfflineTranslateConfig = field(default_factory=OfflineTranslateConfig)


def _merge_dict(raw: dict[str, Any], section: str, defaults: dict[str, Any]) -> dict[str, Any]:
    return {**defaults, **raw.get(section, {})}


def load_config(path: str | Path = "config.toml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        example = Path("config.example.toml")
        if example.exists():
            config_path = example
        else:
            raise FileNotFoundError("config.toml not found and config.example.toml missing")

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    audio = AudioConfig(**_merge_dict(raw, "audio", asdict(AudioConfig())))
    subtitle = SubtitleConfig(**_merge_dict(raw, "subtitle", asdict(SubtitleConfig())))
    provider = ProviderConfig(**_merge_dict(raw, "provider", asdict(ProviderConfig())))
    offline_asr = OfflineASRConfig(**_merge_dict(raw, "offline_asr", asdict(OfflineASRConfig())))
    offline_translate = OfflineTranslateConfig(
        **_merge_dict(raw, "offline_translate", asdict(OfflineTranslateConfig()))
    )
    logging = LoggingConfig(**_merge_dict(raw, "logging", asdict(LoggingConfig())))
    hotkeys = HotkeyConfig(**_merge_dict(raw, "hotkeys", asdict(HotkeyConfig())))

    provider.api_key = os.getenv(provider.api_key_env, provider.api_key)
    provider.tencent_secret_id = os.getenv(provider.tencent_secret_id_env, provider.tencent_secret_id)
    provider.tencent_secret_key = os.getenv(provider.tencent_secret_key_env, provider.tencent_secret_key)
    return AppConfig(
        audio=audio,
        subtitle=subtitle,
        provider=provider,
        offline_asr=offline_asr,
        offline_translate=offline_translate,
        logging=logging,
        hotkeys=hotkeys,
    )
