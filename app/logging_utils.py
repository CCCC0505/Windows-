from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import LoggingConfig


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def setup_logging(config: LoggingConfig) -> None:
    level = getattr(logging, config.level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    if config.json:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    log_path = Path(config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

