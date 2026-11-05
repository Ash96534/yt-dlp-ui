"""Collapsible navigation rail for YT-DLP WebUI.

A vertical sidebar with icon-only collapsed state and labels when expanded.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QPropertyAnimation, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import ThemeManager


class NavItem:
    """A single navigation rail entry."""

    def __init__(
        self,
        key: str,
        label: str,
        icon_text: str,
        on_click: Optional[Callable[[], None]] = None,
    ) -> None:
        self.key = key
        self.label = label
        self.icon_text = icon_text
        self.on_click = on_click


class NavRail(QFrame):
    """Vertical navigation rail.

    Modes:
        - expanded: full labels visible
        - collapsed: icons only, fixed narrow width
    """

    def __init__(
        self,
        theme: ThemeManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self._items: List[NavItem] = []
        self._buttons: Dict[str, QPushButton] = {}
        self._expanded = True
        self._collapsed_width = 60
        self._expanded_width = 220

        self.setObjectName("navRail")
        self.setFixedWidth(self._expanded_width)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 16, 0, 16)
        self._lay.setSpacing(4)

        # App title
        self._title = QLabel("YT-DLP<br/><span style='color:#60a5fa;font-size:11px'>WebUI</span>")
        self._title.setStyleSheet("QLabel { color: #e8e8ea; font-size: 18px; font-weight: bold; }")
        self._title.setTextFormat(Qt.TextFormat.RichText)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lay.addWidget(self._title)
        self._lay.addSpacing(20)

        # Items container
        self._items_lay = QVBoxLayout()
        self._items_lay.setSpacing(2)
        self._lay.addLayout(self._items_lay)
        self._lay.addStretch()

        # Collapse toggle
        self._collapse_btn = QPushButton("‹")
        self._collapse_btn.setFixedSize(32, 32)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setStyleSheet(
            "QPushButton { border: none; border-radius: 6px; color: #a0a0a8; }"
            "QPushButton:hover { background: #24242e; }"
        )
        self._collapse_btn.clicked.connect(self.toggle)
        self._lay.addWidget(self._collapse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._apply_theme()

    def _apply_theme(self) -> None:
        p = self.theme.palette()
        self.setStyleSheet(
            f"QFrame#navRail {{ background: {p['surface']}; border-right: 1px solid {p['border']}; }}"
        )
        self._title.setStyleSheet(
            f"QLabel {{ color: {p['text']}; font-size: 18px; font-weight: bold; }}"
        )

    def add_item(self, key: str, label: str, icon_text: str, on_click: Optional[Callable[[], None]] = None) -> None:
        item = NavItem(key, label, icon_text, on_click)
        self._items.append(item)

        btn = QPushButton(f"{icon_text}  {label}" if self._expanded else icon_text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(True)
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 8px 12px; border: none; "
            "border-radius: 6px; color: #a0a0a8; font-size: 13px; }"
            "QPushButton:checked { background: #24242e; color: #60a5fa; }"
            "QPushButton:hover:!checked { background: #181825; color: #e8e8ea; }"
        )
        if item.on_click:
            btn.clicked.connect(item.on_click)

        self._items_lay.addWidget(btn)
        self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        width = self._expanded_width if self._expanded else self._collapsed_width
        self.setFixedWidth(width)

        for key, btn in self._buttons.items():
            item = next(i for i in self._items if i.key == key)
            if self._expanded:
                btn.setText(f"{item.icon_text}  {item.label}")
            else:
                btn.setText(item.icon_text)

        self._collapse_btn.setText("›" if self._expanded else "‹")

    def is_expanded(self) -> bool:
        return self._expanded
