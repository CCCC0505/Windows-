import pytest

from app.config import OfflineASRConfig, OfflineTranslateConfig, ProviderConfig
from app.providers.factory import build_providers
from app.providers.mock_provider import MockASRProvider, MockTranslateProvider
from app.providers.offline_local_provider import OfflineLocalASRProvider, PlaceholderTranslateProvider
from app.providers.offline_translate_provider import OfflineArgosTranslateProvider
from app.providers.tencent_provider import TencentTranslateProvider


def test_factory_mock_mode() -> None:
    asr, mt = build_providers(ProviderConfig(mode="mock"))
    assert isinstance(asr, MockASRProvider)
    assert isinstance(mt, MockTranslateProvider)


def test_factory_tencent_requires_credentials() -> None:
    with pytest.raises(ValueError):
        build_providers(ProviderConfig(mode="tencent", tencent_secret_id="", tencent_secret_key=""))


def test_factory_offline_local_mode() -> None:
    asr, mt = build_providers(ProviderConfig(mode="offline_local"), OfflineASRConfig(model_size="small"))
    assert isinstance(asr, OfflineLocalASRProvider)
    assert isinstance(mt, OfflineArgosTranslateProvider)


def test_factory_offline_local_placeholder_mode() -> None:
    asr, mt = build_providers(
        ProviderConfig(mode="offline_local"),
        OfflineASRConfig(model_size="small", translate_backend="placeholder"),
        OfflineTranslateConfig(enabled=False),
    )
    assert isinstance(asr, OfflineLocalASRProvider)
    assert isinstance(mt, PlaceholderTranslateProvider)


def test_factory_offline_local_tencent_translate() -> None:
    asr, mt = build_providers(
        ProviderConfig(
            mode="offline_local",
            tencent_secret_id="sid",
            tencent_secret_key="skey",
            tencent_region="ap-guangzhou",
            tencent_project_id=0,
        ),
        OfflineASRConfig(model_size="small", translate_backend="tencent"),
    )
    assert isinstance(asr, OfflineLocalASRProvider)
    assert isinstance(mt, TencentTranslateProvider)
