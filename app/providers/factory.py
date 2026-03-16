from __future__ import annotations

from app.config import OfflineASRConfig, OfflineTranslateConfig, ProviderConfig
from app.providers.base import ASRProvider, TranslateProvider
from app.providers.cloud_provider import CloudASRProvider, CloudTranslateProvider
from app.providers.mock_provider import MockASRProvider, MockTranslateProvider
from app.providers.offline_local_provider import OfflineLocalASRProvider, PlaceholderTranslateProvider
from app.providers.offline_translate_provider import OfflineArgosTranslateProvider
from app.providers.tencent_provider import TencentASRProvider, TencentTranslateProvider


def build_providers(
    config: ProviderConfig,
    offline_config: OfflineASRConfig | None = None,
    offline_translate: OfflineTranslateConfig | None = None,
) -> tuple[ASRProvider, TranslateProvider]:
    if config.mode == "offline_local":
        off = offline_config or OfflineASRConfig()
        tr = offline_translate or OfflineTranslateConfig()
        backend = str(off.translate_backend or "auto").strip().lower()
        if backend == "auto":
            backend = "offline" if tr.enabled else "placeholder"

        if backend == "tencent":
            if not config.tencent_secret_id or not config.tencent_secret_key:
                raise ValueError(
                    "offline_local translate_backend=tencent requires credentials "
                    "(tencent_secret_id/tencent_secret_key or env vars)."
                )
            translate_provider: TranslateProvider = TencentTranslateProvider(
                secret_id=config.tencent_secret_id,
                secret_key=config.tencent_secret_key,
                region=config.tencent_region,
                project_id=int(config.tencent_project_id),
                timeout_seconds=config.timeout_seconds,
            )
        elif backend == "offline":
            translate_provider = OfflineArgosTranslateProvider(
                source_lang=tr.source_lang,
                target_lang=tr.target_lang,
                model_path=tr.model_path,
                max_chars_per_chunk=int(tr.max_chars_per_chunk),
                timeout_ms=int(tr.timeout_ms),
            )
        elif backend == "placeholder":
            translate_provider = PlaceholderTranslateProvider(prefix="待翻译")
        else:
            raise ValueError(f"Unsupported offline translate backend: {backend}")

        return (
            OfflineLocalASRProvider(
                model_size=off.model_size,
                language=off.language,
                device=off.device,
                source_model=off.source_model,
                model_path=off.model_path,
            ),
            translate_provider,
        )

    if config.mode == "tencent":
        if not config.tencent_secret_id or not config.tencent_secret_key:
            raise ValueError(
                "Tencent mode requires credentials. Set provider.tencent_secret_id/tencent_secret_key "
                "or env vars TENCENT_SECRET_ID/TENCENT_SECRET_KEY."
            )
        return (
            TencentASRProvider(
                secret_id=config.tencent_secret_id,
                secret_key=config.tencent_secret_key,
                region=config.tencent_region,
                project_id=int(config.tencent_project_id),
                eng_service_type=config.tencent_asr_engine,
                timeout_seconds=config.timeout_seconds,
            ),
            TencentTranslateProvider(
                secret_id=config.tencent_secret_id,
                secret_key=config.tencent_secret_key,
                region=config.tencent_region,
                project_id=int(config.tencent_project_id),
                timeout_seconds=config.timeout_seconds,
            ),
        )

    if config.mode == "cloud":
        if not config.api_key:
            raise ValueError(f"Cloud mode requires API key in env {config.api_key_env}")
        return (
            CloudASRProvider(
                base_url=config.asr_base_url,
                model=config.asr_model,
                api_key=config.api_key,
                timeout_seconds=config.timeout_seconds,
            ),
            CloudTranslateProvider(
                base_url=config.translate_base_url,
                model=config.translate_model,
                api_key=config.api_key,
                timeout_seconds=config.timeout_seconds,
            ),
        )
    return MockASRProvider(), MockTranslateProvider()
