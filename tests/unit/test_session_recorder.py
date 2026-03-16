from app.session_recorder import SessionRecordEntry, SessionRecorder


def test_session_recorder_writes_md_and_txt(tmp_path) -> None:
    recorder = SessionRecorder(output_dir=tmp_path)
    recorder.append(
        SessionRecordEntry(
            start_ts=1.0,
            end_ts=2.5,
            source_text="hello world",
            translated_text="translated: hello world",
            source_lang_model="en",
            translation_backend_used="argos",
            created_at="2026-03-14T20:00:00",
        )
    )
    recorder.close()

    md = recorder.md_path.read_text(encoding="utf-8")
    txt = recorder.txt_path.read_text(encoding="utf-8")
    assert "hello world" in md
    assert "translated: hello world" in txt
    assert "translation_backend: argos" in txt
    assert "Segments: 1" in md
