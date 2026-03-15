from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class VADConfig:
    sample_rate: int
    frame_ms: int
    energy_threshold: int
    silence_ms: int
    max_segment_ms: int


class EnergyVADSegmenter:
    def __init__(self, config: VADConfig) -> None:
        self.config = config
        self._buffer = bytearray()
        self._current_start_ts: float | None = None
        self._last_voice_ts: float = 0.0

    def push(self, chunk_pcm16: bytes, ts_seconds: float) -> list[tuple[float, float, bytes]]:
        energy = self._rms_energy(chunk_pcm16)
        # Use a lower activation threshold so low-volume system audio can still start a segment.
        activation_threshold = max(6.0, float(self.config.energy_threshold) * 0.08)
        is_active = energy >= activation_threshold
        frame_seconds = self.config.frame_ms / 1000.0
        out: list[tuple[float, float, bytes]] = []

        if is_active and self._current_start_ts is None:
            self._current_start_ts = ts_seconds
            self._last_voice_ts = ts_seconds

        if self._current_start_ts is not None:
            self._buffer.extend(chunk_pcm16)
            if is_active:
                self._last_voice_ts = ts_seconds

            duration_ms = int(round(((ts_seconds + frame_seconds) - self._current_start_ts) * 1000.0))
            silence_ms = int(round((ts_seconds - self._last_voice_ts) * 1000.0))
            if duration_ms >= self.config.max_segment_ms or silence_ms >= self.config.silence_ms:
                out.append((self._current_start_ts, ts_seconds + frame_seconds, bytes(self._buffer)))
                self._buffer.clear()
                self._current_start_ts = None
                self._last_voice_ts = 0.0

        return out

    def flush(self, ts_seconds: float) -> tuple[float, float, bytes] | None:
        if self._current_start_ts is None or not self._buffer:
            return None
        frame_seconds = self.config.frame_ms / 1000.0
        segment = (self._current_start_ts, ts_seconds + frame_seconds, bytes(self._buffer))
        self._buffer.clear()
        self._current_start_ts = None
        self._last_voice_ts = 0.0
        return segment

    @staticmethod
    def _rms_energy(chunk_pcm16: bytes) -> float:
        if not chunk_pcm16:
            return 0.0
        data = np.frombuffer(chunk_pcm16, dtype=np.int16).astype(np.float32)
        if data.size == 0:
            return 0.0
        return float(math.sqrt(float(np.mean(np.square(data)))))
