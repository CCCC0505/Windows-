from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class SessionRecordEntry:
    start_ts: float
    end_ts: float
    source_text: str
    translated_text: str
    source_lang_model: str
    translation_backend_used: str
    created_at: str


class SessionRecorder:
    def __init__(self, output_dir: str | Path = "exports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.base_name = f"session-{stamp}"
        self.md_path = self.output_dir / f"{self.base_name}.md"
        self.txt_path = self.output_dir / f"{self.base_name}.txt"
        self._lock = threading.Lock()
        self._count = 0
        self._started_at = _now_iso()
        self._closed = False
        self._init_files()

    @property
    def count(self) -> int:
        return self._count

    def _init_files(self) -> None:
        md_header = "\n".join(
            [
                f"# Offline Session Record ({self.base_name})",
                "",
                f"Started: {self._started_at}",
                "",
                "| start_ts | end_ts | source_text | translated_text | source_lang_model | translation_backend_used | created_at |",
                "|---|---|---|---|---|---|---|",
                "",
            ]
        )
        txt_header = "\n".join(
            [
                f"Offline Session Record ({self.base_name})",
                f"Started: {self._started_at}",
                "",
            ]
        )
        self.md_path.write_text(md_header, encoding="utf-8")
        self.txt_path.write_text(txt_header, encoding="utf-8")

    def append(self, entry: SessionRecordEntry) -> None:
        if self._closed:
            return
        md_row = "| {s:.2f} | {e:.2f} | {src} | {tr} | {sm} | {tb} | {at} |\n".format(
            s=entry.start_ts,
            e=entry.end_ts,
            src=_md_escape(entry.source_text),
            tr=_md_escape(entry.translated_text),
            sm=_md_escape(entry.source_lang_model),
            tb=_md_escape(entry.translation_backend_used),
            at=entry.created_at,
        )
        txt_row = (
            "[{s:.2f}-{e:.2f}] source: {src}\n"
            "translated: {tr}\n"
            "source_model: {sm}\n"
            "translation_backend: {tb}\n"
            "created_at: {at}\n\n"
        ).format(
            s=entry.start_ts,
            e=entry.end_ts,
            src=entry.source_text,
            tr=entry.translated_text,
            sm=entry.source_lang_model,
            tb=entry.translation_backend_used,
            at=entry.created_at,
        )
        with self._lock:
            with self.md_path.open("a", encoding="utf-8") as f:
                f.write(md_row)
            with self.txt_path.open("a", encoding="utf-8") as f:
                f.write(txt_row)
            self._count += 1

    def close(self) -> None:
        if self._closed:
            return
        ended_at = _now_iso()
        summary = "\n".join(
            [
                "",
                f"Ended: {ended_at}",
                f"Segments: {self._count}",
                "",
            ]
        )
        with self._lock:
            with self.md_path.open("a", encoding="utf-8") as f:
                f.write(summary)
            with self.txt_path.open("a", encoding="utf-8") as f:
                f.write(summary)
            self._closed = True


def _md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
