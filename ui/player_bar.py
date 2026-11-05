"""Always-visible media player bar for YT-DLP WebUI.

Docked at the bottom of the window. Supports collapsed (64px) and expanded
(110px) heights. Shows artwork, title, playback controls, progress, volume.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPropertyAnimation, Qt, QTimer, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .theme import ThemeManager


class PlayerBar(QFrame):
    """Bottom player bar.

    States:
        - hidden: no media loaded
        - collapsed: media loaded, compact view (64px)
        - expanded: media playing, full controls (110px)
    """

    def __init__(
        self,
        player,
        audio_output,
        video_widget: QVideoWidget,
        theme: ThemeManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.player = player
        self.audio_output = audio_output
        self.video_widget = video_widget
        self.theme = theme
        self._expanded = False
        self._collapsed_height = 64
        self._expanded_height = 110

        # Callback attributes (set by parent MainWindow)
        self._on_mini = None
        self._on_lyrics = None
        self._on_album_art = None
        self._on_crossfade = None
        self._on_gapless = None
        self._on_recent = None

        self.setObjectName("playerBar")
        self.setFixedHeight(self._collapsed_height)
        self.setVisible(False)

        self._build_ui()
        self._wire_signals()
        self._apply_theme()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        # Artwork
        self.art = QLabel()
        self.art.setFixedSize(44, 44)
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art.setStyleSheet(
            "QLabel { background: #181825; border-radius: 4px; }"
        )
        lay.addWidget(self.art)

        # Video widget (hidden by default, shown on hover or when playing video)
        self.video_widget.setFixedSize(44, 44)
        self.video_widget.hide()
        lay.addWidget(self.video_widget)

        # Controls column
        ctrl = QVBoxLayout()
        ctrl.setSpacing(2)

        # Row 1: play/pause/prev/next + skip + speed
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self.btn_prev = QPushButton("Previous")
        self.btn_prev.setFixedWidth(45)
        row1.addWidget(self.btn_prev)

        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedWidth(70)
        row1.addWidget(self.btn_play)

        self.btn_next = QPushButton("Next")
        self.btn_next.setFixedWidth(45)
        row1.addWidget(self.btn_next)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedWidth(70)
        row1.addWidget(self.btn_stop)

        self.btn_skip_back = QPushButton("Skip -10s")
        self.btn_skip_back.setFixedWidth(60)
        row1.addWidget(self.btn_skip_back)

        self.btn_skip_fwd = QPushButton("Skip +10s")
        self.btn_skip_fwd.setFixedWidth(60)
        row1.addWidget(self.btn_skip_fwd)

        self.speed = QComboBox()
        self.speed.addItems(["0.5x", "1x", "1.5x", "2x"])
        self.speed.setCurrentText("1x")
        self.speed.setFixedWidth(60)
        row1.addWidget(self.speed)

        self.autoplay = QCheckBox("Autoplay next")
        self.autoplay.setChecked(True)
        row1.addWidget(self.autoplay)

        row1.addStretch()
        ctrl.addLayout(row1)

        # Row 2: position slider + volume + title
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        row2.addWidget(QLabel("Pos:"))
        self.pos_slider = QSlider(Qt.Orientation.Horizontal)
        self.pos_slider.setRange(0, 0)
        row2.addWidget(self.pos_slider, 1)

        row2.addWidget(QLabel("Vol:"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setFixedWidth(100)
        row2.addWidget(self.vol_slider)

        self.title_lbl = QLabel("No media loaded")
        self.title_lbl.setStyleSheet(
            "QLabel { color: #a0a0a8; font-size: 11px; }"
        )
        self.title_lbl.setWordWrap(True)
        row2.addWidget(self.title_lbl, 1)

        ctrl.addLayout(row2)
        lay.addLayout(ctrl, 1)

        # Right column: mini / lyrics / art / crossfade / gapless / recent
        right = QVBoxLayout()
        right.setSpacing(4)

        self.btn_mini = QPushButton("Mini Player")
        self.btn_mini.setFixedWidth(70)
        right.addWidget(self.btn_mini)

        self.btn_lyrics = QPushButton("Lyrics")
        self.btn_lyrics.setFixedWidth(60)
        right.addWidget(self.btn_lyrics)

        self.btn_art = QPushButton("Art")
        self.btn_art.setFixedWidth(45)
        right.addWidget(self.btn_art)

        self.btn_crossfade = QPushButton("Crossfade")
        self.btn_crossfade.setCheckable(True)
        self.btn_crossfade.setFixedWidth(70)
        right.addWidget(self.btn_crossfade)

        self.btn_gapless = QPushButton("Gapless")
        self.btn_gapless.setCheckable(True)
        self.btn_gapless.setFixedWidth(60)
        right.addWidget(self.btn_gapless)

        self.btn_recent = QPushButton("Recent")
        self.btn_recent.setFixedWidth(55)
        right.addWidget(self.btn_recent)

        right.addStretch()
        lay.addLayout(right)

    def _wire_signals(self) -> None:
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.pos_slider.sliderMoved.connect(self._on_seek)
        self.vol_slider.valueChanged.connect(self._on_volume)
        self.speed.currentTextChanged.connect(self._on_speed)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_stop.clicked.connect(self._stop)

        self.btn_mini.clicked.connect(self._on_mini_clicked)
        self.btn_lyrics.clicked.connect(self._on_lyrics_clicked)
        self.btn_art.clicked.connect(self._on_art_clicked)
        self.btn_crossfade.clicked.connect(self._on_crossfade_clicked)
        self.btn_gapless.clicked.connect(self._on_gapless_clicked)
        self.btn_recent.clicked.connect(self._on_recent_clicked)

    def _on_mini_clicked(self) -> None:
        if self._on_mini:
            self._on_mini()

    def _on_lyrics_clicked(self) -> None:
        if self._on_lyrics:
            self._on_lyrics()

    def _on_art_clicked(self) -> None:
        if self._on_album_art:
            self._on_album_art()

    def _on_crossfade_clicked(self) -> None:
        if self._on_crossfade:
            self._on_crossfade()

    def _on_gapless_clicked(self) -> None:
        if self._on_gapless:
            self._on_gapless()

    def _on_recent_clicked(self) -> None:
        if self._on_recent:
            self._on_recent()

    def _apply_theme(self) -> None:
        p = self.theme.palette()
        self.setStyleSheet(
            f"QFrame#playerBar {{ background: {p['surface']}; border-top: 1px solid {p['border']}; }}"
        )
        self.art.setStyleSheet(
            f"QLabel {{ background: {p['elevated']}; border-radius: 4px; }}"
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def load(self, filepath: str, title: str = "", artwork: Optional[QPixmap] = None) -> None:
        """Load a media file into the player bar."""
        self.player.set_source(filepath)
        self.player.play()
        self.setVisible(True)
        self.title_lbl.setText(title or "Unknown")
        if artwork:
            self.art.setPixmap(
                artwork.scaled(
                    44,
                    44,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._expanded = True
        self.setFixedHeight(self._expanded_height)

    def stop(self) -> None:
        self.player.stop()
        self.setVisible(False)

    def set_title(self, title: str) -> None:
        self.title_lbl.setText(title)

    def set_artwork(self, pixmap: QPixmap) -> None:
        self.art.setPixmap(
            pixmap.scaled(
                44,
                44,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def toggle_expand(self) -> None:
        self._expanded = not self._expanded
        target = self._expanded_height if self._expanded else self._collapsed_height
        self._animate_height(target)

    def _animate_height(self, target: int) -> None:
        self._anim = QPropertyAnimation(self, b"maximumHeight")
        self._anim.setDuration(200)
        self._anim.setStartValue(self.height())
        self._anim.setEndValue(target)
        self._anim.start()

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("Pause")
        else:
            self.btn_play.setText("Play")

    def _on_position_changed(self, pos: int) -> None:
        self.pos_slider.setValue(pos)

    def _on_duration_changed(self, dur: int) -> None:
        self.pos_slider.setRange(0, dur)

    def _on_seek(self, value: int) -> None:
        self.player.set_position(value)

    def _on_volume(self, value: int) -> None:
        self.player.set_volume(value / 100.0)

    def _on_speed(self, text: str) -> None:
        rate = float(text.replace("x", ""))
        self.player.set_playback_rate(rate)

    def _toggle_play(self) -> None:
        if self.player.player_state() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _prev(self) -> None:
        # Emitted to parent via callback; handled by MainWindow
        if hasattr(self, "_on_prev"):
            self._on_prev()

    def _next(self) -> None:
        if hasattr(self, "_on_next"):
            self._on_next()

    def _stop(self) -> None:
        if hasattr(self, "_on_stop"):
            self._on_stop()
