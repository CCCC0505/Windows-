from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SubtitleLine:
    id: int
    start_ts: float
    end_ts: float
    source_text: str
    translated_text: str
    created_at: str


class HistoryStore:
    def __init__(self, db_path: str | Path = "data/history.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subtitle_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_ts REAL NOT NULL,
                end_ts REAL NOT NULL,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def insert(self, start_ts: float, end_ts: float, source_text: str, translated_text: str) -> None:
        created_at = datetime.utcnow().isoformat()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO subtitle_history (start_ts, end_ts, source_text, translated_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (start_ts, end_ts, source_text, translated_text, created_at),
            )
            self.conn.commit()

    def list_recent(self, limit: int = 200) -> list[SubtitleLine]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT id, start_ts, end_ts, source_text, translated_text, created_at
                FROM subtitle_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            SubtitleLine(
                id=row[0],
                start_ts=row[1],
                end_ts=row[2],
                source_text=row[3],
                translated_text=row[4],
                created_at=row[5],
            )
            for row in rows
        ]

    def clear(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM subtitle_history")
            self.conn.commit()

    def export_txt(self, out_path: str | Path) -> Path:
        output = Path(out_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = self.list_recent(limit=1_000_000)
        lines = [
            f"[{r.start_ts:.2f}-{r.end_ts:.2f}] {r.translated_text} (src: {r.source_text})"
            for r in reversed(rows)
        ]
        output.write_text("\n".join(lines), encoding="utf-8")
        return output

    def export_srt(self, out_path: str | Path) -> Path:
        output = Path(out_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = list(reversed(self.list_recent(limit=1_000_000)))
        blocks: list[str] = []
        for index, row in enumerate(rows, start=1):
            blocks.append(
                "\n".join(
                    [
                        str(index),
                        f"{_srt_ts(row.start_ts)} --> {_srt_ts(row.end_ts)}",
                        row.translated_text,
                    ]
                )
            )
        output.write_text("\n\n".join(blocks), encoding="utf-8")
        return output

    def close(self) -> None:
        with self._lock:
            self.conn.close()


def _srt_ts(value: float) -> str:
    total_ms = int(max(0.0, value) * 1000)
    hours = total_ms // 3_600_000
    mins = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{mins:02d}:{secs:02d},{ms:03d}"
