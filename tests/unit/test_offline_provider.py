import numpy as np
import pytest

from app.providers.offline_local_provider import OfflineLocalASRProvider, PlaceholderTranslateProvider


@pytest.mark.asyncio
async def test_offline_provider_returns_text_without_vosk_model() -> None:
    provider = OfflineLocalASRProvider(model_size="small", language="auto", device="cpu")
    pcm = np.full((16000,), 100, dtype=np.int16).tobytes()
    events = await provider.transcribe_segment(pcm, sample_rate=16000, start_ts=0.0, end_ts=1.0)
    assert len(events) == 1
    assert events[0].is_final
    assert events[0].text


@pytest.mark.asyncio
async def test_placeholder_translate_provider_without_prefix_returns_source_text() -> None:
    provider = PlaceholderTranslateProvider(prefix="")
    translated = await provider.translate("hello", source_lang="en", target_lang="zh")
    assert translated == "hello"
