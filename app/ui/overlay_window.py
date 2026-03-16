from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class OverlayWindow(QWidget):
    def __init__(self, font_size: int, opacity: float) -> None:
        super().__init__()
        self.setWindowTitle("实时字幕")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(opacity)

        self.label = QLabel("字幕将显示在这里")
        self.label.setStyleSheet(
            "background-color: rgba(15, 15, 15, 180); color: white; border-radius: 8px; padding: 12px;"
        )
        font = QFont()
        font.setPointSize(font_size)
        self.label.setFont(font)
        self.label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.resize(700, 120)

        self._drag_pos = None

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):  # type: ignore[override]
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):  # type: ignore[override]
        self._drag_pos = None

