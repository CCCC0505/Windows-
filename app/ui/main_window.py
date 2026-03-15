from __future__ import annotations

import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.audio.capture import CaptureChunk, SystemAudioCapturer
from app.config import AppConfig
from app.storage import HistoryStore
from app.ui.client import BackendClient
from app.ui.overlay_window import OverlayWindow
from app.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    LANGUAGE_OPTIONS = [
        ("中文", "zh"),
        ("English", "en"),
        ("日本語", "ja"),
        ("한국어", "ko"),
        ("Français", "fr"),
        ("Deutsch", "de"),
        ("Español", "es"),
        ("Русский", "ru"),
    ]
    SOURCE_MODEL_OPTIONS = [
        ("English model", "en"),
        ("中文模型", "zh"),
    ]

    def __init__(self, config: AppConfig, history: HistoryStore, ws_url: str) -> None:
        super().__init__()
        self.setWindowTitle("Windows 实时翻译 V1")
        self.resize(1000, 720)
        self.config = config
        self.history = history
        self.running = False
        self._last_activity_monotonic = 0.0

        self.client = BackendClient(ws_url)
        self.client.connected.connect(lambda: self._set_status("connected", "green"))
        self.client.disconnected.connect(lambda: self._set_status("disconnected", "gray"))
        self.client.status_changed.connect(self._on_status_changed)
        self.client.session_started.connect(self._on_session_started)
        self.client.transcript_partial.connect(self._on_transcript_partial)
        self.client.translation_partial.connect(self._on_translation_partial)
        self.client.translation_final.connect(self._on_translation_final)
        self.client.session_error.connect(self._on_error)

        self.capturer = SystemAudioCapturer(
            target_sample_rate=self.config.audio.sample_rate,
            frame_ms=self.config.audio.frame_ms,
            on_chunk=self._on_capture_chunk,
        )
        self.overlay = OverlayWindow(
            font_size=self.config.subtitle.font_size,
            opacity=self.config.subtitle.overlay_opacity,
        )
        if self.config.subtitle.always_on_top:
            self.overlay.show()

        self._build_ui()
        self._bind_hotkeys()
        self._load_history()
        self.health_timer = QTimer(self)
        self.health_timer.setInterval(2000)
        self.health_timer.timeout.connect(self._check_capture_health)
        self.health_timer.start()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout()

        top = QHBoxLayout()
        self.start_btn = QPushButton("开始")
        self.start_btn.clicked.connect(self._toggle_start)
        self.overlay_btn = QPushButton("切换置顶字幕窗")
        self.overlay_btn.clicked.connect(self._toggle_overlay)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self._open_settings)
        self.source_model_label = QLabel("识别模型")
        self.source_model_combo = QComboBox()
        for label, code in self.SOURCE_MODEL_OPTIONS:
            self.source_model_combo.addItem(label, code)
        self._set_source_model_combo(self.config.offline_asr.source_model)
        self.source_model_combo.currentIndexChanged.connect(self._on_source_model_changed)
        self.target_lang_label = QLabel("目标语言")
        self.target_lang_combo = QComboBox()
        for label, code in self.LANGUAGE_OPTIONS:
            self.target_lang_combo.addItem(f"{label} ({code})", code)
        self._set_target_lang_combo(self.config.subtitle.target_language)
        self.target_lang_combo.currentIndexChanged.connect(self._on_target_language_changed)
        self.desktop_shortcut_btn = QPushButton("创建桌面一键启动")
        self.desktop_shortcut_btn.clicked.connect(self._create_desktop_shortcut)
        self.export_txt_btn = QPushButton("导出 TXT")
        self.export_txt_btn.clicked.connect(self._export_txt)
        self.export_srt_btn = QPushButton("导出 SRT")
        self.export_srt_btn.clicked.connect(self._export_srt)
        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.clicked.connect(self._clear_history)

        self.status_dot = QLabel("●")
        self.status_text = QLabel("idle")
        self.latency_text = QLabel("延迟: -")
        self.error_text = QLabel("")
        self.error_text.setStyleSheet("color: #c53030;")

        top.addWidget(self.start_btn)
        top.addWidget(self.overlay_btn)
        top.addWidget(self.settings_btn)
        top.addWidget(self.source_model_label)
        top.addWidget(self.source_model_combo)
        top.addWidget(self.target_lang_label)
        top.addWidget(self.target_lang_combo)
        top.addWidget(self.desktop_shortcut_btn)
        top.addWidget(self.export_txt_btn)
        top.addWidget(self.export_srt_btn)
        top.addWidget(self.clear_btn)
        top.addStretch(1)
        top.addWidget(self.status_dot)
        top.addWidget(self.status_text)
        top.addWidget(self.latency_text)

        self.partial_text = QLabel("识别中...")
        self.partial_text.setStyleSheet("color: #4a5568;")
        self.partial_text.setWordWrap(True)
        self.record_path_text = QLabel("记录文件: -")
        self.record_path_text.setStyleSheet("color: #2b6cb0;")
        self.record_path_text.setWordWrap(True)
        self.subtitle_text = QTextEdit()
        self.subtitle_text.setReadOnly(True)

        self.history_table = QTableWidget(0, 3)
        self.history_table.setHorizontalHeaderLabels(["开始", "结束", "字幕"])
        self.history_table.horizontalHeader().setStretchLastSection(True)

        main.addLayout(top)
        main.addWidget(self.error_text)
        main.addWidget(QLabel("临时字幕"))
        main.addWidget(self.partial_text)
        main.addWidget(self.record_path_text)
        main.addWidget(QLabel("实时字幕"))
        main.addWidget(self.subtitle_text, stretch=2)
        main.addWidget(QLabel("历史记录"))
        main.addWidget(self.history_table, stretch=3)
        root.setLayout(main)

    def _bind_hotkeys(self) -> None:
        start_stop = QShortcut(QKeySequence(self.config.hotkeys.start_stop), self)
        start_stop.activated.connect(self._toggle_start)
        toggle_overlay = QShortcut(QKeySequence(self.config.hotkeys.toggle_overlay), self)
        toggle_overlay.activated.connect(self._toggle_overlay)

    def _toggle_start(self) -> None:
        if self.running:
            self._stop_stream()
        else:
            self._start_stream()

    def _start_stream(self) -> None:
        try:
            self.config.subtitle.target_language = self._selected_target_language()
            self.client.start()
            self.client.start_session(
                target_language=self.config.subtitle.target_language,
                source_model=self._selected_source_model(),
            )
            self.capturer.start()
            self.running = True
            self._last_activity_monotonic = time.monotonic()
            self.start_btn.setText("停止")
            self._set_status("running", "green")
            self.error_text.setText("")
            self.partial_text.setText(
                f"已启动: capture={self.capturer.capture_mode}, provider={self.config.provider.mode}"
            )
        except Exception as exc:  # noqa: BLE001
            try:
                self.capturer.stop()
            except Exception:  # noqa: BLE001
                pass
            try:
                self.client.stop_session()
            except Exception:  # noqa: BLE001
                pass
            self.running = False
            self.start_btn.setText("开始")
            self._on_error(str(exc))

    def _stop_stream(self) -> None:
        self.capturer.stop()
        self.client.stop_session()
        self.running = False
        self.start_btn.setText("开始")
        self._set_status("stopped", "gray")

    def _on_capture_chunk(self, chunk: CaptureChunk) -> None:
        if not self.running:
            return
        self.client.send_audio_chunk(chunk.ts, chunk.pcm16)

    def _on_status_changed(self, status: str) -> None:
        if self.running and status == "connected":
            self._set_status("running", "green")
            return
        if self.running and status == "reconnecting":
            self._set_status("running-reconnecting", "orange")
            return

        color = "gray"
        if status == "connected":
            color = "green"
        elif status in {"connecting", "reconnecting"}:
            color = "orange"
        self._set_status(status, color)

    def _on_session_started(self, payload: dict) -> None:
        provider_mode = str(payload.get("provider_mode", self.config.provider.mode))
        translate_backend = str(payload.get("translate_backend", "unknown"))
        source_model = str(payload.get("source_model", self._selected_source_model()))
        md_path = str(payload.get("record_md_path", "")).strip()
        txt_path = str(payload.get("record_txt_path", "")).strip()
        if md_path or txt_path:
            self.record_path_text.setText(f"记录文件: md={md_path or '-'} | txt={txt_path or '-'}")
        else:
            self.record_path_text.setText("记录文件: -")
        self.partial_text.setText(
            f"已启动: capture={self.capturer.capture_mode}, provider={provider_mode}, source_model={source_model}, translate={translate_backend}"
        )

    def _set_status(self, text: str, color: str) -> None:
        self.status_text.setText(text)
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 18px;")

    def _on_transcript_partial(self, text: str, is_final: bool) -> None:
        self._last_activity_monotonic = time.monotonic()
        if self.error_text.text().startswith("运行中但未检测到可翻译音频"):
            self.error_text.setText("")
        prefix = "最终识别" if is_final else "识别中"
        self.partial_text.setText(f"{prefix}: {text}")

    def _on_translation_partial(self, text: str) -> None:
        self._last_activity_monotonic = time.monotonic()
        if self.error_text.text().startswith("运行中但未检测到可翻译音频"):
            self.error_text.setText("")
        self.partial_text.setText(f"翻译中: {text}")

    def _on_translation_final(self, payload: dict) -> None:
        translated = str(payload.get("translated_text", ""))
        source = str(payload.get("source_text", ""))
        start_ts = float(payload.get("start_ts", 0.0))
        end_ts = float(payload.get("end_ts", 0.0))
        backend = str(payload.get("translation_backend_used", "unknown"))
        line = f"[{start_ts:.2f}-{end_ts:.2f}] ({backend}) {translated}"
        self.subtitle_text.append(line)
        self.overlay.set_text(translated)
        self._append_history_row(start_ts, end_ts, f"({backend}) {translated}", source)
        self._last_activity_monotonic = time.monotonic()
        if self.error_text.text().startswith("运行中但未检测到可翻译音频"):
            self.error_text.setText("")
        latency_ms = float(payload.get("latency_ms", 0.0))
        self.latency_text.setText(f"延迟: {latency_ms / 1000.0:.2f}s")
        if self.config.subtitle.auto_scroll:
            cursor = self.subtitle_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.subtitle_text.setTextCursor(cursor)

    def _on_error(self, message: str) -> None:
        self.error_text.setText(message)
        self._set_status("error", "red")

    def _append_history_row(self, start_ts: float, end_ts: float, translated: str, source: str) -> None:
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        self.history_table.setItem(row, 0, QTableWidgetItem(f"{start_ts:.2f}"))
        self.history_table.setItem(row, 1, QTableWidgetItem(f"{end_ts:.2f}"))
        self.history_table.setItem(row, 2, QTableWidgetItem(f"{translated}\n(src: {source})"))

    def _load_history(self) -> None:
        rows = list(reversed(self.history.list_recent(limit=200)))
        for item in rows:
            self._append_history_row(item.start_ts, item.end_ts, item.translated_text, item.source_text)

    def _clear_history(self) -> None:
        if QMessageBox.question(self, "确认", "确定清空本地历史吗？") != QMessageBox.StandardButton.Yes:
            return
        self.history.clear()
        self.history_table.setRowCount(0)
        self.subtitle_text.clear()

    def _export_txt(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出 TXT", str(Path("exports/history.txt")), "Text (*.txt)")
        if not path:
            return
        self.history.export_txt(path)

    def _export_srt(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出 SRT", str(Path("exports/history.srt")), "SRT (*.srt)")
        if not path:
            return
        self.history.export_srt(path)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config)
        if dialog.exec():
            self.overlay.setWindowOpacity(self.config.subtitle.overlay_opacity)
            self._set_target_lang_combo(self.config.subtitle.target_language)

    def _create_desktop_shortcut(self) -> None:
        script_path = Path(__file__).resolve().parents[2] / "create_desktop_shortcut.ps1"
        if not script_path.exists():
            QMessageBox.critical(self, "错误", f"未找到脚本: {script_path}")
            return

        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(script_path.parent),
            shell=False,
        )
        if result.returncode == 0:
            message = result.stdout.strip() or "桌面快捷方式创建成功。"
            QMessageBox.information(self, "成功", message)
            return

        error_text = result.stderr.strip() or result.stdout.strip() or "创建失败"
        QMessageBox.critical(self, "失败", f"无法创建桌面快捷方式。\n\n{error_text}")

    def _toggle_overlay(self) -> None:
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()

    def _on_target_language_changed(self, _index: int) -> None:
        lang = self._selected_target_language()
        self.config.subtitle.target_language = lang
        if self.running:
            self.client.start_session(target_language=lang, source_model=self._selected_source_model())
            self.partial_text.setText(f"目标语言已切换为: {lang}")

    def _on_source_model_changed(self, _index: int) -> None:
        self.config.offline_asr.source_model = self._selected_source_model()
        if self.running:
            self.client.start_session(
                target_language=self._selected_target_language(),
                source_model=self._selected_source_model(),
            )
            self.partial_text.setText(f"识别模型已切换为: {self._selected_source_model()}")

    def _selected_target_language(self) -> str:
        current = self.target_lang_combo.currentData()
        if isinstance(current, str) and current:
            return current
        return self.config.subtitle.target_language or "zh"

    def _set_target_lang_combo(self, lang: str) -> None:
        idx = self.target_lang_combo.findData(lang)
        if idx < 0:
            self.target_lang_combo.addItem(f"{lang} ({lang})", lang)
            idx = self.target_lang_combo.findData(lang)
        self.target_lang_combo.setCurrentIndex(idx)

    def _selected_source_model(self) -> str:
        current = self.source_model_combo.currentData()
        if isinstance(current, str) and current:
            return current
        return self.config.offline_asr.source_model or "en"

    def _set_source_model_combo(self, source_model: str) -> None:
        idx = self.source_model_combo.findData(source_model)
        if idx < 0:
            self.source_model_combo.addItem(source_model, source_model)
            idx = self.source_model_combo.findData(source_model)
        self.source_model_combo.setCurrentIndex(idx)

    def _check_capture_health(self) -> None:
        if not self.running:
            return
        if self._last_activity_monotonic <= 0:
            return
        idle_seconds = time.monotonic() - self._last_activity_monotonic
        if idle_seconds >= 6.0:
            self.error_text.setText(
                "运行中但未检测到可翻译音频。请确认正在播放系统声音，且系统回采设备可用。"
            )

    def closeEvent(self, event):  # type: ignore[override]
        self._stop_stream()
        self.client.stop()
        super().closeEvent(event)
