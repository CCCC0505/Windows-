from app.protocol import Message, decode_audio_chunk, encode_audio_chunk


def test_message_roundtrip() -> None:
    msg = Message(type="session.start", payload={"target_language": "zh"})
    raw = msg.to_dict()
    parsed = Message.from_dict(raw)
    assert parsed.type == "session.start"
    assert parsed.payload["target_language"] == "zh"


def test_audio_chunk_codec() -> None:
    source = b"\x00\x01\x02\x03"
    encoded = encode_audio_chunk(source)
    decoded = decode_audio_chunk(encoded)
    assert decoded == source

