"""Theme engine for YT-DLP WebUI.

Provides dark/light/system/night mode color palettes and QSS generation.
Theme changes apply instantly to the QApplication without restart.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication


# --------------------------------------------------------------------------- #
# Color palettes
# --------------------------------------------------------------------------- #
DARK_PALETTE: Dict[str, str] = {
    "bg": "#0f0f12",
    "surface": "#1a1a1e",
    "elevated": "#24242e",
    "border": "#2a2a33",
    "text": "#e8e8ea",
    "text_muted": "#a0a0a8",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "muted": "#4b4b55",
}

LIGHT_PALETTE: Dict[str, str] = {
    "bg": "#fafafa",
    "surface": "#ffffff",
    "elevated": "#f0f0f0",
    "border": "#d4d4d8",
    "text": "#111827",
    "text_muted": "#6b6b76",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "muted": "#9ca3af",
}


class ThemeManager:
    """Manages application theme and generates QSS stylesheets.

    Usage:
        tm = ThemeManager(app)
        tm.set_theme("dark")   # or "light", "system", "night"
    """

    def __init__(self, app: QApplication):
        self.app = app
        self._current_theme: str = "dark"
        self._palette: Dict[str, str] = DARK_PALETTE.copy()
        self._accent: Optional[str] = None

    def _with_accent(self, palette: Dict[str, str]) -> Dict[str, str]:
        """Return a copy of palette with the custom accent applied (if any)."""
        if not self._accent:
            return palette.copy()
        palette = palette.copy()
        palette["accent"] = self._accent
        c = QColor(self._accent)
        if c.isValid():
            # Lighten or darken depending on base accent luminance
            h, s, v, a = c.getHsv()
            hover = QColor.fromHsv(h, s, min(255, v + 30), a)
            palette["accent_hover"] = hover.name()
        return palette

    def set_theme(self, theme: str) -> None:
        """Set the application theme. Valid: dark, light, system, night."""
        if theme == "system":
            scheme = self.app.styleHints().colorScheme()
            resolved = "light" if scheme == Qt.ColorScheme.Light else "dark"
        elif theme == "night":
            import datetime

            hour = datetime.datetime.now().hour
            resolved = "dark" if hour >= 20 or hour < 8 else "light"
        else:
            resolved = theme

        self._current_theme = theme
        palette = DARK_PALETTE if resolved == "dark" else LIGHT_PALETTE
        self._palette = self._with_accent(palette)
        self.app.setStyleSheet(self._build_qss())

    def current_theme(self) -> str:
        return self._current_theme

    def palette(self) -> Dict[str, str]:
        return self._palette.copy()

    def set_accent(self, color: Optional[str]) -> None:
        """Set a custom accent color (hex string or None to use palette default)."""
        if color:
            c = QColor(color)
            if not c.isValid():
                raise ValueError(f"Invalid color: {color}")
            self._accent = c.name()
        else:
            self._accent = None
        # Rebuild with the current theme
        self.set_theme(self._current_theme)

    def accent_color(self) -> Optional[str]:
        return self._accent

    def color(self, key: str) -> str:
        return self._palette.get(key, "#000000")

    # ------------------------------------------------------------------ #
    # QSS generation
    # ------------------------------------------------------------------ #
    def _build_qss(self) -> str:
        p = self._palette
        return f"""
            QMainWindow {{
                background:{p['bg']};
                color:{p['text']};
            }}
            QFrame#card {{
                background:{p['surface']};
                border:1px solid {p['border']};
                border-radius:8px;
                padding:12px;
            }}
            QLabel {{
                color:{p['text']};
            }}
            QLineEdit, QTextEdit, QComboBox, QSpinBox {{
                background:{p['surface']};
                border:1px solid {p['border']};
                border-radius:4px;
                padding:6px;
                color:{p['text']};
            }}
            QPushButton {{
                background:{p['border']};
                border:none;
                border-radius:4px;
                padding:6px 12px;
                color:{p['text']};
            }}
            QPushButton:hover {{
                background:{p['elevated']};
            }}
            QPushButton#primary {{
                background:{p['accent']};
                color:#111827;
                font-weight:bold;
            }}
            QPushButton#primary:hover {{
                background:{p['accent_hover']};
            }}
            QPushButton#danger {{
                background:{p['error']};
                color:#ffffff;
            }}
            QPushButton#danger:hover {{
                background:#dc2626;
            }}
            QTableWidget {{
                background:{p['surface']};
                border:1px solid {p['border']};
                border-radius:4px;
                gridline-color:{p['border']};
            }}
            QHeaderView::section {{
                background:{p['elevated']};
                color:{p['text_muted']};
                border:none;
                padding:6px;
                font-weight:bold;
            }}
            QProgressBar {{
                border:1px solid {p['border']};
                border-radius:4px;
                text-align:center;
                background:{p['elevated']};
                color:{p['text']};
            }}
            QProgressBar::chunk {{
                background:{p['accent']};
                border-radius:4px;
            }}
            QTabWidget::pane {{
                border:1px solid {p['border']};
                border-radius:4px;
                background:{p['surface']};
            }}
            QTabBar::tab {{
                background:{p['surface']};
                color:{p['text_muted']};
                padding:8px 16px;
                border-top-left-radius:4px;
                border-top-right-radius:4px;
            }}
            QTabBar::tab:selected {{
                background:{p['border']};
                color:{p['text']};
            }}
            QScrollBar:vertical {{
                background:{p['bg']};
                width:10px;
                border:none;
                border-radius:4px;
            }}
            QScrollBar::handle:vertical {{
                background:{p['muted']};
                border-radius:4px;
                min-height:20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background:{p['text_muted']};
            }}
        """
