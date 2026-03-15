from __future__ import annotations

import logging
import platform
import inspect
import threading
import time
import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import sounddevice as sd
try:
    import soundcard as sc
except Exception:  # noqa: BLE001
    sc = None

from app.audio.processing import float32_to_pcm16_bytes, resample_linear, to_mono

logger = logging.getLogger(__name__)


@dataclass
class CaptureChunk:
    ts: float
    pcm16: bytes


class SystemAudioCapturer:
    def __init__(
        self,
        target_sample_rate: int,
        frame_ms: int,
        on_chunk: Callable[[CaptureChunk], None],
        allow_default_input_fallback: bool = False,
    ) -> None:
        self.target_sample_rate = target_sample_rate
        self.frame_ms = frame_ms
        self.on_chunk = on_chunk
        self.allow_default_input_fallback = allow_default_input_fallback
        self.stream: sd.InputStream | None = None
        self.src_rate: int = 48000
        self.capture_mode: str = "none"
        self._sc_thread: threading.Thread | None = None
        self._sc_stop = threading.Event()

    def start(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("WASAPI loopback capture is only supported on Windows")
        if self.stream is not None:
            return

        errors: list[str] = []
        # Prefer explicit loopback through soundcard when available.
        if sc is not None:
            try:
                self._start_soundcard_loopback()
                self.capture_mode = "soundcard_loopback"
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("soundcard loopback failed: %s", exc)
                errors.append(f"soundcard_loopback: {exc}")

        for device_idx, mode in self._build_candidates():
            try:
                info = sd.query_devices(device_idx)
                self.src_rate = int(info.get("default_samplerate", 48000))
                if mode == "wasapi_loopback":
                    channels = max(1, min(int(info.get("max_output_channels", 2)), 2))
                    extra_settings = sd.WasapiSettings(loopback=True)
                else:
                    channels = max(1, min(int(info.get("max_input_channels", 2)), 2))
                    extra_settings = None
                blocksize = int(self.src_rate * self.frame_ms / 1000)

                logger.info(
                    "starting capture mode=%s device=%s src_rate=%s channels=%s",
                    mode,
                    device_idx,
                    self.src_rate,
                    channels,
                )
                self.stream = sd.InputStream(
                    samplerate=self.src_rate,
                    channels=channels,
                    dtype="float32",
                    blocksize=blocksize,
                    device=device_idx,
                    extra_settings=extra_settings,
                    callback=self._callback,
                )
                self.stream.start()
                self.capture_mode = mode
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("capture candidate failed mode=%s device=%s error=%s", mode, device_idx, exc)
                errors.append(f"{mode}@{device_idx}: {exc}")
                self.stream = None

        detail = "; ".join(errors) if errors else "no capture candidates"
        raise RuntimeError(
            "无法启动系统音频采集。请先启用可用的系统回采设备（如立体声混音），"
            f"当前尝试详情: {detail}"
        )

    def stop(self) -> None:
        if self.capture_mode == "soundcard_loopback":
            self._stop_soundcard_loopback()
            self.capture_mode = "none"
            return
        if self.stream is None:
            return
        try:
            self.stream.stop()
            self.stream.close()
        finally:
            self.stream = None
            self.capture_mode = "none"

    def _callback(self, indata: np.ndarray, _frames: int, callback_time: Any, status: sd.CallbackFlags) -> None:
        if status:
            logger.warning("audio callback status=%s", status)

        mono = to_mono(indata)
        resampled = resample_linear(mono, src_rate=self.src_rate, dst_rate=self.target_sample_rate)
        pcm16 = float32_to_pcm16_bytes(resampled)
        ts = float(getattr(callback_time, "currentTime", 0.0))
        self.on_chunk(CaptureChunk(ts=ts, pcm16=pcm16))

    def _start_soundcard_loopback(self) -> None:
        if sc is None:
            raise RuntimeError("soundcard package is unavailable")
        speaker = sc.default_speaker()
        if speaker is None:
            raise RuntimeError("no default speaker found")

        loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        if loopback is None:
            raise RuntimeError("no loopback microphone found")

        self.src_rate = 48000
        frame_count = max(1, int(self.src_rate * self.frame_ms / 1000))
        self._sc_stop.clear()

        # Validate recorder creation before background thread starts.
        with loopback.recorder(samplerate=self.src_rate, channels=2) as recorder:
            _ = recorder.record(numframes=frame_count)

        def _worker() -> None:
            ole32 = ctypes.windll.ole32
            # COINIT_MULTITHREADED
            _ = ole32.CoInitializeEx(None, 0x0)
            try:
                with loopback.recorder(samplerate=self.src_rate, channels=2) as recorder:
                    while not self._sc_stop.is_set():
                        data = recorder.record(numframes=frame_count)
                        if data is None or len(data) == 0:
                            continue
                        arr = np.asarray(data, dtype=np.float32)
                        mono = to_mono(arr)
                        resampled = resample_linear(mono, src_rate=self.src_rate, dst_rate=self.target_sample_rate)
                        pcm16 = float32_to_pcm16_bytes(resampled)
                        ts = time.monotonic()
                        self.on_chunk(CaptureChunk(ts=ts, pcm16=pcm16))
            finally:
                ole32.CoUninitialize()

        self._sc_thread = threading.Thread(target=_worker, daemon=True)
        self._sc_thread.start()

    def _stop_soundcard_loopback(self) -> None:
        self._sc_stop.set()
        if self._sc_thread is not None:
            self._sc_thread.join(timeout=1.5)
        self._sc_thread = None

    def _build_candidates(self) -> list[tuple[int, str]]:
        candidates: list[tuple[int, str]] = []
        devices = sd.query_devices()

        if self._supports_wasapi_loopback():
            output_device_idx = sd.default.device[1]
            if output_device_idx is not None and output_device_idx >= 0:
                candidates.append((int(output_device_idx), "wasapi_loopback"))

        for idx, dev in enumerate(devices):
            max_input = int(dev.get("max_input_channels", 0))
            if max_input <= 0:
                continue
            name = str(dev.get("name", ""))
            lowered = name.lower()
            if "stereo mix" in lowered or "立体声混音" in name or "what u hear" in lowered:
                candidates.append((idx, "stereo_mix"))

        if self.allow_default_input_fallback:
            default_input_idx = sd.default.device[0]
            if default_input_idx is not None and default_input_idx >= 0:
                candidates.append((int(default_input_idx), "default_input"))

        # De-duplicate while preserving order.
        seen: set[int] = set()
        unique: list[tuple[int, str]] = []
        for idx, mode in candidates:
            if idx in seen:
                continue
            seen.add(idx)
            unique.append((idx, mode))
        return unique

    @staticmethod
    def _supports_wasapi_loopback() -> bool:
        try:
            sig = inspect.signature(sd.WasapiSettings)
        except Exception:  # noqa: BLE001
            return False
        return "loopback" in sig.parameters
