from __future__ import annotations

import logging
import threading
import time

import uvicorn
from PySide6.QtWidgets import QApplication

from app.config import load_config
from app.logging_utils import setup_logging
from app.server.app import create_backend_app
from app.storage import HistoryStore
from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class BackendThread(threading.Thread):
    def __init__(self, app) -> None:
        super().__init__(daemon=True)
        self.server = uvicorn.Server(
            uvicorn.Config(app=app, host="127.0.0.1", port=8765, log_level="info", access_log=False)
        )

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


def main() -> None:
    config = load_config("config.toml")
    setup_logging(config.logging)

    history = HistoryStore()
    backend_app = create_backend_app(config, history)
    backend_thread = BackendThread(backend_app)
    backend_thread.start()
    time.sleep(0.5)
    logger.info("backend started")

    qt_app = QApplication([])
    window = MainWindow(config=config, history=history, ws_url="ws://127.0.0.1:8765/ws")
    window.show()
    code = qt_app.exec()

    backend_thread.stop()
    history.close()
    raise SystemExit(code)


if __name__ == "__main__":
    main()

