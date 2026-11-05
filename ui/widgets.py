"""Custom UI widgets for YT-DLP WebUI.

All widgets accept an optional theme manager and restyle themselves when
the theme changes. Colors come from the ThemeManager palette.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .theme import ThemeManager


# --------------------------------------------------------------------------- #
# Buttons
# --------------------------------------------------------------------------- #
class PrimaryButton(QPushButton):
    """Accent-colored primary action button."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class GhostButton(QPushButton):
    """Transparent button with border, for secondary actions."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class IconButton(QPushButton):
    """Square icon-only button."""

    def __init__(
        self,
        icon: Optional[QIcon] = None,
        text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(icon, text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(32, 32)
        self.setStyleSheet("QPushButton { border: none; border-radius: 6px; }")


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
class SearchBar(QLineEdit):
    """Rounded search input with optional clear button."""

    def __init__(
        self,
        placeholder: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(32)
        self.setStyleSheet(
            "QLineEdit { border-radius: 16px; padding: 4px 16px; }"
        )


# --------------------------------------------------------------------------- #
# Cards
# --------------------------------------------------------------------------- #
class MediaCard(QFrame):
    """Card showing artwork, title, and optional hover actions.

    Emits `clicked` when the card body is clicked (not the action buttons).
    """

    clicked = pyqtSignal()

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        artwork: Optional[QPixmap] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.art = QLabel()
        self.art.setFixedSize(120, 68)
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art.setStyleSheet(
            "QLabel { background: #181825; border-radius: 4px; }"
        )
        if artwork:
            self.art.setPixmap(
                artwork.scaled(
                    120,
                    68,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        lay.addWidget(self.art)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            "QLabel { font-weight: bold; font-size: 13px; }"
        )
        self.title_lbl.setWordWrap(True)
        lay.addWidget(self.title_lbl)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet(
            "QLabel { color: #a0a0a8; font-size: 11px; }"
        )
        self.sub_lbl.setWordWrap(True)
        lay.addWidget(self.sub_lbl)

        self.actions: QWidget = QWidget()
        self.actions.setVisible(False)
        actions_lay = QHBoxLayout(self.actions)
        actions_lay.setContentsMargins(0, 4, 0, 0)
        actions_lay.setSpacing(6)
        lay.addWidget(self.actions)

    def set_artwork(self, pixmap: QPixmap) -> None:
        self.art.setPixmap(
            pixmap.scaled(
                120,
                68,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def add_action(self, widget: QWidget) -> None:
        self.actions.layout().addWidget(widget)  # type: ignore[union-attr]
        self.actions.setVisible(True)

    def mousePressEvent(self, event: Any) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event: Any) -> None:  # type: ignore[override]
        self.actions.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:  # type: ignore[override]
        self.actions.setVisible(False)
        super().leaveEvent(event)


# --------------------------------------------------------------------------- #
# Sliders
# --------------------------------------------------------------------------- #
class ThemedSlider(QSlider):
    """Slider that picks up theme colors from the parent stylesheet."""

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(orientation, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# --------------------------------------------------------------------------- #
# Checkbox
# --------------------------------------------------------------------------- #
class ThemedCheckBox(QCheckBox):
    """Checkbox with theme-aware styling."""

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
