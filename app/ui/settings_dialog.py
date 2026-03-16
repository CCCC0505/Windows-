from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import tomli_w
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
)

from app.config import AppConfig


class SettingsDialog(QDialog):
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

    def __init__(self, config: AppConfig, config_path: str = "config.toml") -> None:
        super().__init__()
        self.setWindowTitle("设置")
        self.config = config
        self.config_path = Path(config_path)

        self.target_lang_combo = QComboBox()
        for label, code in self.LANGUAGE_OPTIONS:
            self.target_lang_combo.addItem(f"{label} ({code})", code)
        idx = self.target_lang_combo.findData(config.subtitle.target_language)
        if idx < 0:
            self.target_lang_combo.addItem(
                f"{config.subtitle.target_language} ({config.subtitle.target_language})",
                config.subtitle.target_language,
            )
            idx = self.target_lang_combo.findData(config.subtitle.target_language)
        self.target_lang_combo.setCurrentIndex(idx)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 40)
        self.font_size_spin.setValue(config.subtitle.font_size)
        self.auto_scroll_check = QCheckBox()
        self.auto_scroll_check.setChecked(config.subtitle.auto_scroll)
        self.always_on_top_check = QCheckBox()
        self.always_on_top_check.setChecked(config.subtitle.always_on_top)

        form = QFormLayout()
        form.addRow("目标语言", self.target_lang_combo)
        form.addRow("字体大小", self.font_size_spin)
        form.addRow("自动滚动", self.auto_scroll_check)
        form.addRow("字幕置顶", self.always_on_top_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)
        self.setLayout(form)

    def _save(self) -> None:
        self.config.subtitle.target_language = str(self.target_lang_combo.currentData() or "zh")
        self.config.subtitle.font_size = int(self.font_size_spin.value())
        self.config.subtitle.auto_scroll = self.auto_scroll_check.isChecked()
        self.config.subtitle.always_on_top = self.always_on_top_check.isChecked()
        self._write_config()
        self.accept()

    def _write_config(self) -> None:
        payload = {
            "audio": asdict(self.config.audio),
            "subtitle": asdict(self.config.subtitle),
            "provider": asdict(self.config.provider),
            "offline_asr": asdict(self.config.offline_asr),
            "offline_translate": asdict(self.config.offline_translate),
            "logging": asdict(self.config.logging),
            "hotkeys": asdict(self.config.hotkeys),
        }
        self.config_path.write_text(tomli_w.dumps(payload), encoding="utf-8")
