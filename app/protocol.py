from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any


MESSAGE_TYPES = {
    "session.start",
    "audio.chunk",
    "transcript.partial",
    "translation.partial",
    "translation.final",
    "session.error",
    "session.end",
    "session.heartbeat",
}


@dataclass
class Message:
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        if self.type not in MESSAGE_TYPES:
            raise ValueError(f"Unsupported message type: {self.type}")
        return {"type": self.type, "payload": self.payload}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Message":
        msg_type = raw.get("type")
        if msg_type not in MESSAGE_TYPES:
            raise ValueError(f"Unsupported message type: {msg_type}")
        payload = raw.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        return cls(type=msg_type, payload=payload)


def encode_audio_chunk(pcm16: bytes) -> str:
    return base64.b64encode(pcm16).decode("ascii")


def decode_audio_chunk(encoded: str) -> bytes:
    return base64.b64decode(encoded.encode("ascii"))
