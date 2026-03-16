import numpy as np

from app.audio.vad import EnergyVADSegmenter, VADConfig


def _pcm(amp: int, n: int = 320) -> bytes:
    arr = np.full((n,), amp, dtype=np.int16)
    return arr.tobytes()


def test_vad_segment_by_silence() -> None:
    segmenter = EnergyVADSegmenter(
        VADConfig(sample_rate=16000, frame_ms=20, energy_threshold=100, silence_ms=60, max_segment_ms=1000)
    )
    t = 0.0
    out = []
    out.extend(segmenter.push(_pcm(300), t))
    t += 0.02
    out.extend(segmenter.push(_pcm(300), t))
    t += 0.02
    out.extend(segmenter.push(_pcm(0), t))
    t += 0.02
    out.extend(segmenter.push(_pcm(0), t))
    t += 0.02
    out.extend(segmenter.push(_pcm(0), t))
    assert len(out) == 1
    start, end, data = out[0]
    assert start == 0.0
    assert end > start
    assert len(data) > 0

