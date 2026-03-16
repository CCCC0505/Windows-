import numpy as np

from app.audio.processing import float32_to_pcm16_bytes, resample_linear, to_mono


def test_to_mono_from_stereo() -> None:
    stereo = np.array([[1.0, -1.0], [0.5, 0.5]], dtype=np.float32)
    mono = to_mono(stereo)
    assert mono.shape == (2,)
    assert np.allclose(mono, [0.0, 0.5])


def test_resample_linear_downsample() -> None:
    src = np.sin(np.linspace(0, 3.14, 48000, dtype=np.float32))
    dst = resample_linear(src, src_rate=48000, dst_rate=16000)
    assert 15900 <= len(dst) <= 16100


def test_float32_pcm16_bounds() -> None:
    raw = np.array([-2.0, -1.0, 0.0, 1.0, 2.0], dtype=np.float32)
    pcm = float32_to_pcm16_bytes(raw)
    ints = np.frombuffer(pcm, dtype=np.int16)
    assert ints[0] == -32767
    assert ints[-1] == 32767

