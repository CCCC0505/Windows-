from __future__ import annotations

import asyncio
import base64
import io
import json
import uuid
import wave
from dataclasses import dataclass

from tencentcloud.asr.v20190614 import asr_client, models as asr_models
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tmt.v20180321 import tmt_client, models as tmt_models

from app.providers.base import ASREvent, ASRProvider, TranslateProvider


def _pcm16_to_wav(pcm16: bytes, sample_rate: int, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16)
    return buffer.getvalue()


def _normalize_lang(lang: str | None) -> str:
    if not lang:
        return "auto"
    value = lang.strip().lower().replace("_", "-")
    mapping = {
        "zh-cn": "zh",
        "zh-hans": "zh",
        "zh-hant": "zh-TW",
        "jp": "ja",
    }
    return mapping.get(value, value)


@dataclass
class TencentASRProvider(ASRProvider):
    secret_id: str
    secret_key: str
    region: str
    project_id: int
    eng_service_type: str
    timeout_seconds: int

    def __post_init__(self) -> None:
        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "asr.tencentcloudapi.com"
        http_profile.reqTimeout = self.timeout_seconds
        profile = ClientProfile()
        profile.httpProfile = http_profile
        self.client = asr_client.AsrClient(cred, self.region, profile)

    async def transcribe_segment(self, pcm16: bytes, sample_rate: int, start_ts: float, end_ts: float) -> list[ASREvent]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._transcribe_sync,
            pcm16,
            sample_rate,
            start_ts,
            end_ts,
        )

    def _transcribe_sync(self, pcm16: bytes, sample_rate: int, start_ts: float, end_ts: float) -> list[ASREvent]:
        wav_bytes = _pcm16_to_wav(pcm16, sample_rate=sample_rate, channels=1)
        req = asr_models.SentenceRecognitionRequest()
        params = {
            "ProjectId": self.project_id,
            "SubServiceType": 2,
            "EngSerViceType": self.eng_service_type,
            "SourceType": 1,
            "VoiceFormat": "wav",
            "UsrAudioKey": f"seg-{uuid.uuid4().hex[:16]}",
            "Data": base64.b64encode(wav_bytes).decode("ascii"),
            "DataLen": len(wav_bytes),
        }
        req.from_json_string(json.dumps(params, ensure_ascii=True))
        try:
            resp = self.client.SentenceRecognition(req)
        except TencentCloudSDKException as exc:
            raise RuntimeError(f"Tencent ASR failed: {exc}") from exc

        text = str(getattr(resp, "Result", "") or "").strip()
        if not text:
            return []
        return [ASREvent(text=text, is_final=True, start_ts=start_ts, end_ts=end_ts)]


@dataclass
class TencentTranslateProvider(TranslateProvider):
    secret_id: str
    secret_key: str
    region: str
    project_id: int
    timeout_seconds: int

    def __post_init__(self) -> None:
        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "tmt.tencentcloudapi.com"
        http_profile.reqTimeout = self.timeout_seconds
        profile = ClientProfile()
        profile.httpProfile = http_profile
        self.client = tmt_client.TmtClient(cred, self.region, profile)

    async def translate(self, text: str, source_lang: str | None, target_lang: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._translate_sync,
            text,
            source_lang,
            target_lang,
        )

    def _translate_sync(self, text: str, source_lang: str | None, target_lang: str) -> str:
        req = tmt_models.TextTranslateRequest()
        params = {
            "SourceText": text,
            "Source": _normalize_lang(source_lang),
            "Target": _normalize_lang(target_lang),
            "ProjectId": self.project_id,
        }
        req.from_json_string(json.dumps(params, ensure_ascii=True))
        try:
            resp = self.client.TextTranslate(req)
        except TencentCloudSDKException as exc:
            raise RuntimeError(f"Tencent Translate failed: {exc}") from exc
        translated = str(getattr(resp, "TargetText", "") or "").strip()
        return translated or text
