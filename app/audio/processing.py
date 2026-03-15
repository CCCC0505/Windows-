from __future__ import annotations

import numpy as np


def to_mono(signal: np.ndarray) -> np.ndarray:
    if signal.ndim == 1:
        return signal
    return signal.mean(axis=1)


def resample_linear(signal: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return signal
    if signal.size == 0:
        return signal

    ratio = dst_rate / src_rate
    dst_len = int(round(signal.shape[0] * ratio))
    if dst_len <= 1:
        return signal[:1]

    src_idx = np.linspace(0.0, signal.shape[0] - 1, num=dst_len)
    left = np.floor(src_idx).astype(np.int64)
    right = np.clip(left + 1, 0, signal.shape[0] - 1)
    frac = src_idx - left
    return (1.0 - frac) * signal[left] + frac * signal[right]


def float32_to_pcm16_bytes(signal: np.ndarray) -> bytes:
    clipped = np.clip(signal, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    return pcm.tobytes()

