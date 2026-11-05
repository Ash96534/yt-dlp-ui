"""YT-DLP WebUI — Pure Python desktop app with PyQt6."""
from __future__ import annotations

import json
import os
import sys
import uuid
import time
import threading
import sqlite3
from typing import Any, Dict, List, Optional

import yt_dlp
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QComboBox, QCheckBox, QSpinBox, QProgressBar, QFrame,
    QSplitter, QStackedWidget, QScrollArea, QSizePolicy,
    QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout,
    QTabWidget, QGroupBox, QGridLayout, QSystemTrayIcon, QMenu, QStyle, QSlider, QLayout, QInputDialog,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QRect, QTimer
from PyQt6.QtGui import QFont, QPixmap, QDesktopServices, QAction
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from ui.nav_rail import NavRail
from ui.player_bar import PlayerBar
from ui.theme import ThemeManager
from ui.widgets import MediaCard, PrimaryButton, GhostButton, SearchBar


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.default.json")
LIBRARY_DB = os.path.join(DATA_DIR, "library.db")
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg", "bin", "ffmpeg.exe")

os.makedirs(DATA_DIR, exist_ok=True)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def deep_merge(base, override):
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config():
    defaults = {}
    if os.path.exists(DEFAULT_CONFIG_PATH):
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
            defaults = json.load(f)
    if not os.path.exists(CONFIG_PATH):
        return defaults
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user = json.load(f)
    except (json.JSONDecodeError, OSError):
        return defaults
    return deep_merge(defaults, user)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Library DB
# --------------------------------------------------------------------------- #
def init_db():
    c = sqlite3.connect(LIBRARY_DB)
    c.execute("""
        CREATE TABLE IF NOT EXISTS library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            source_url TEXT NOT NULL,
            title TEXT,
            uploader TEXT,
            duration INTEGER,
            filepath TEXT NOT NULL UNIQUE,
            file_size INTEGER,
            resolution TEXT,
            container TEXT,
            downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_favorite INTEGER DEFAULT 0,
            is_watch_later INTEGER DEFAULT 0,
            is_liked INTEGER DEFAULT 0,
            is_disliked INTEGER DEFAULT 0,
            play_count INTEGER DEFAULT 0,
            last_played TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER,
            title TEXT,
            filepath TEXT,
            played_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (library_id) REFERENCES library(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS playback_positions (
            filepath TEXT PRIMARY KEY,
            position INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS music_playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            cover_path TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS music_playlist_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER,
            track_id INTEGER,
            position INTEGER DEFAULT 0,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (playlist_id) REFERENCES music_playlists(id),
            FOREIGN KEY (track_id) REFERENCES library(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS music_artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            image_path TEXT,
            bio TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS music_albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist_id INTEGER,
            cover_path TEXT,
            release_year INTEGER,
            FOREIGN KEY (artist_id) REFERENCES music_artists(id)
        )
    """)
    # Migration for existing DBs
    for col in ("is_watch_later", "is_liked", "is_disliked", "play_count", "last_played",
                "is_music", "music_artist", "music_album", "music_track", "music_genre",
                "music_year", "music_cover", "music_duration"):
        try:
            c.execute(f"ALTER TABLE library ADD COLUMN {col} TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
    c.commit()
    c.close()


def library_add(job_id, source_url, title, uploader, duration, filepath, file_size, resolution, container):
    c = sqlite3.connect(LIBRARY_DB)
    c.execute(
        "INSERT INTO library (job_id, source_url, title, uploader, duration, filepath, file_size, resolution, container) VALUES (?,?,?,?,?,?,?,?,?)",
        (job_id, source_url, title, uploader, duration, filepath, file_size, resolution, container),
    )
    c.commit()
    c.close()


def library_list(query=""):
    c = sqlite3.connect(LIBRARY_DB)
    c.row_factory = sqlite3.Row
    if query:
        rows = c.execute(
            "SELECT * FROM library WHERE title LIKE ? OR uploader LIKE ? ORDER BY downloaded_at DESC",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
    else:
        rows = c.execute("SELECT * FROM library ORDER BY downloaded_at DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def library_delete(item_id, delete_file=False):
    c = sqlite3.connect(LIBRARY_DB)
    row = c.execute("SELECT filepath FROM library WHERE id = ?", (item_id,)).fetchone()
    c.execute("DELETE FROM library WHERE id = ?", (item_id,))
    c.commit()
    c.close()
    if delete_file and row and os.path.exists(row[0]):
        try:
            os.remove(row[0])
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Download Worker
# --------------------------------------------------------------------------- #
class DownloadWorker(QThread):
    progress = pyqtSignal(str, float, str, str, int, int)  # job_id, pct, speed, eta, downloaded, total
    status = pyqtSignal(str, str)  # job_id, status
    completed = pyqtSignal(str, str)  # job_id, filepath
    failed = pyqtSignal(str, str)  # job_id, error

    def __init__(self, job_id, url, config, config_overrides=None):
        super().__init__()
        self.job_id = job_id
        self.url = url
        self.config = deep_merge(config, config_overrides or {})
        self._abort = False

    def run(self):
        self.status.emit(self.job_id, "running")

        def hook(d):
            if self._abort:
                return
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                pct = (downloaded / total * 100) if total else 0.0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0
                self.progress.emit(
                    self.job_id,
                    round(pct, 2),
                    self._fmt_speed(speed),
                    self._fmt_eta(eta),
                    downloaded,
                    total if total else 0,
                )
            elif d.get("status") == "finished":
                self.progress.emit(self.job_id, 100.0, "", "", 0, 0)

        opts = self._build_opts(hook)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                if self._abort:
                    self.status.emit(self.job_id, "cancelled")
                    return
                filepath = ydl.prepare_filename(info)
                if not os.path.exists(filepath):
                    base, _ = os.path.splitext(filepath)
                    for ext in (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus"):
                        cand = base + ext
                        if os.path.exists(cand):
                            filepath = cand
                            break
                fsize = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                self.status.emit(self.job_id, "completed")
                self.completed.emit(self.job_id, filepath)
                fcfg = self.config.get("format", {})
                library_add(
                    self.job_id,
                    self.url,
                    info.get("title", ""),
                    info.get("uploader", ""),
                    info.get("duration", 0),
                    filepath,
                    fsize,
                    f"{info.get('height', '')}p" if info.get("height") else "",
                    fcfg.get("merge_output_format", "mp4"),
                )
        except Exception as e:
            self.status.emit(self.job_id, "failed")
            self.failed.emit(self.job_id, str(e))

    def abort(self):
        self._abort = True

    def _build_opts(self, hook):
        fc = self.config.get("format", {})
        dc = self.config.get("downloads", {})
        nc = self.config.get("network", {})
        ac = self.config.get("auth", {})
        pc = self.config.get("postprocessing", {})

        dl_root = dc.get("default_path", "{user_home}/Downloads/YTDLP-WebUI")
        dl_root = dl_root.replace("{user_home}", os.path.expanduser("~"))
        os.makedirs(dl_root, exist_ok=True)

        opts = {
            "format": fc.get("preferred", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"),
            "outtmpl": os.path.join(dl_root, "%(title)s.%(ext)s"),
            "merge_output_format": fc.get("merge_output_format", "mp4"),
            "noplaylist": fc.get("noplaylist", True),
            "ignoreerrors": fc.get("ignore_errors", False),
            "geobypass": fc.get("geo_bypass", True),
            "retries": int(dc.get("max_retries", 5)),
            "fragment_retries": int(dc.get("fragment_retries", 10)),
            "socket_timeout": int(nc.get("socket_timeout", 30)),
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
        }
        ratelimit_kbps = dc.get("speed_limit_kbps", 0)
        if ratelimit_kbps and ratelimit_kbps > 0:
            opts["ratelimit"] = ratelimit_kbps * 1024

        if fc.get("audio_only"):
            opts["format"] = "bestaudio/best"
            opts.setdefault("postprocessors", []).append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": fc.get("audio_format", "mp3"),
                    "preferredquality": fc.get("audio_quality", "0"),
                }
            )

        if fc.get("embed_thumbnail"):
            opts["writethumbnail"] = True
            opts.setdefault("postprocessors", []).extend(
                [{"key": "EmbedThumbnail"}, {"key": "FFmpegMetadata"}]
            )
        elif fc.get("embed_metadata"):
            opts.setdefault("postprocessors", []).append({"key": "FFmpegMetadata"})

        if fc.get("write_subs"):
            opts["writesubtitles"] = True
            opts["subtitleslangs"] = fc.get("subs_lang", ["en"])
        if fc.get("write_info_json"):
            opts["writeinfojson"] = True

        if ac.get("cookies_from_browser"):
            opts["cookiesfrombrowser"] = ac.get("cookies_from_browser")
        if ac.get("cookies_file"):
            opts["cookiefile"] = ac.get("cookies_file")
        if nc.get("proxy"):
            opts["proxy"] = nc.get("proxy")

        ffmpeg_loc = pc.get("ffmpeg_location") or (FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None)
        if ffmpeg_loc:
            opts["ffmpeg_location"] = ffmpeg_loc

        return opts

    @staticmethod
    def _fmt_speed(b):
        try:
            b = float(b or 0)
        except (TypeError, ValueError):
            return ""
        if b >= 1024 ** 3:
            return f"{b / 1024 ** 3:.2f} GB/s"
        if b >= 1024 ** 2:
            return f"{b / 1024 ** 2:.2f} MB/s"
        if b >= 1024:
            return f"{b / 1024:.2f} KB/s"
        return f"{b:.0f} B/s"

    @staticmethod
    def _fmt_eta(s):
        try:
            s = int(s or 0)
        except (TypeError, ValueError):
            return ""
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s}s"
        h, m = divmod(m, 60)
        return f"{h}h {m}m {s}s"


# --------------------------------------------------------------------------- #
# UI — Main Window
# --------------------------------------------------------------------------- #
class YTDLPApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("YT-DLP WebUI")
        self.resize(1200, 800)
        self.config = load_config()
        self.workers: Dict[str, DownloadWorker] = {}
        self.jobs: Dict[str, dict] = {}
        self.active_info_worker: Optional[InfoWorker] = None
        self.player: Optional[QMediaPlayer] = None
        self.audio_output: Optional[QAudioOutput] = None
        self.video_widget: Optional[QVideoWidget] = None
        self.player_panel: Optional[QFrame] = None
        self.player_pos_slider: Optional[QSlider] = None
        self.player_vol_slider: Optional[QSlider] = None
        self.player_play_btn: Optional[QPushButton] = None
        self.player_time_lbl: Optional[QLabel] = None
        self.player_duration_lbl: Optional[QLabel] = None
        self.player_timer: Optional[QTimer] = None
        self.playlist: List[str] = []
        self.playlist_index: int = -1
        self.crossfade_enabled: bool = False
        self.gapless_enabled: bool = False
        self.theme = ThemeManager(self)
        self.theme.set_theme(self.config.get("app", {}).get("theme", "dark"))
        self._init_player()
        self._build_ui()
        init_db()
        self.refresh_jobs()
        self.refresh_library()
        self.refresh_music_library()
        self._setup_tray()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.tray.setToolTip("YT-DLP WebUI")

        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._tray_show)
        menu.addAction(show_action)

        hide_action = QAction("Hide to tray", self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._tray_quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_show(self):
        self.showNormal()
        self.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_show()

    def _tray_quit(self):
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        # Minimize to tray instead of quitting
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "YT-DLP WebUI",
                "App minimized to tray. Downloads continue running.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            event.accept()

    def show_toast(self, title, message, msecs=5000):
        if hasattr(self, "tray") and self.tray.isVisible():
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, msecs)

    def _init_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.7)
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(480, 270)
        self.player.setVideoOutput(self.video_widget)

        self.player_timer = QTimer()
        self.player_timer.setInterval(1000)
        self.player_timer.timeout.connect(self._player_update_position)

        self.player.positionChanged.connect(self._player_position_changed)
        self.player.positionChanged.connect(self._update_lyrics)
        self.player.durationChanged.connect(self._player_duration_changed)
        self.player.playbackStateChanged.connect(self._player_state_changed)
        self.player.mediaStatusChanged.connect(self._player_media_status_changed)
        self.player.errorOccurred.connect(self._player_error)

    def _player_media_status_changed(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._playlist_next()

    def _toggle_repeat(self):
        modes = ["all", "one", "none"]
        cur = self.player_repeat_mode
        nxt = modes[(modes.index(cur) + 1) % len(modes)]
        self.player_repeat_mode = nxt
        self.player_repeat.setText(f"Repeat: {nxt.title()}")
        if cur == "all" and nxt == "one":
            self.player_shuffle.setChecked(False)

    def _true_shuffle(self):
        """Fisher-Yates shuffle for true randomness."""
        import random
        n = len(self.playlist)
        for i in range(n - 1, 0, -1):
            j = random.randint(0, i)
            self.playlist[i], self.playlist[j] = self.playlist[j], self.playlist[i]
        self.playlist_index = 0
        self.show_toast("Shuffle", "Playlist shuffled (true random)")

    def _playlist_next(self):
        if not self.playlist:
            return
        if hasattr(self, "player_autoplay") and not self.player_autoplay.isChecked():
            return
        if self.player_repeat_mode == "one":
            self._player_load(self.playlist[self.playlist_index])
            return
        if getattr(self, "player_shuffle", None) and self.player_shuffle.isChecked():
            self._true_shuffle()
        else:
            self.playlist_index += 1
            if self.playlist_index >= len(self.playlist):
                if self.player_repeat_mode == "all":
                    self.playlist_index = 0
                else:
                    self.player_stop()
                    return
        self._player_load(self.playlist[self.playlist_index])

    def _playlist_prev(self):
        if not self.playlist:
            return
        if getattr(self, "player_shuffle", None) and self.player_shuffle.isChecked():
            self._true_shuffle()
        else:
            self.playlist_index -= 1
            if self.playlist_index < 0:
                if self.player_repeat_mode == "all":
                    self.playlist_index = len(self.playlist) - 1
                else:
                    return
        self._player_load(self.playlist[self.playlist_index])

    def _artist_radio(self, artist_name):
        """Play all music tracks by a given artist (Spotify-style artist radio)."""
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT filepath FROM library WHERE is_music = '1' AND lower(music_artist) = lower(?) ORDER BY play_count DESC, downloaded_at DESC",
            (artist_name,),
        ).fetchall()
        c.close()
        if not rows:
            QMessageBox.information(self, "Artist Radio", f"No tracks found for '{artist_name}'")
            return
        self.playlist = [r["filepath"] for r in rows]
        self.playlist_index = 0
        self.player_shuffle.setChecked(True)
        self._true_shuffle()
        self._player_load(self.playlist[0])
        self.show_toast("Artist Radio", f"{artist_name} — {len(rows)} tracks")

    def _album_radio(self, album_name):
        """Play all tracks in an album."""
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT filepath FROM library WHERE is_music = '1' AND lower(music_album) = lower(?) ORDER BY music_track, downloaded_at DESC",
            (album_name,),
        ).fetchall()
        c.close()
        if not rows:
            QMessageBox.information(self, "Album Radio", f"No tracks found for album '{album_name}'")
            return
        self.playlist = [r["filepath"] for r in rows]
        self.playlist_index = 0
        self._player_load(self.playlist[0])
        self.show_toast("Album Radio", f"{album_name} — {len(rows)} tracks")

    def _playlist_prev(self):
        if not self.playlist:
            return
        self.playlist_index -= 1
        if self.playlist_index < 0:
            self.playlist_index = len(self.playlist) - 1
        self._player_load(self.playlist[self.playlist_index])

    def _player_load(self, filepath):
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "Playback", "File not found: " + str(filepath))
            return
        # Resume saved position
        c = sqlite3.connect(LIBRARY_DB)
        row = c.execute("SELECT position FROM playback_positions WHERE filepath = ?", (filepath,)).fetchone()
        saved_pos = row[0] if row else 0
        c.close()
        self.player.setSource(QUrl.fromLocalFile(filepath))
        self.player.play()
        self.player_panel.show()
        self.player_file_lbl.setText(os.path.basename(filepath))
        self.show_toast("Playing", os.path.basename(filepath))
        if hasattr(self, "tray") and self.tray.isVisible():
            self.tray.setToolTip(f"YT-DLP WebUI — Now Playing: {os.path.basename(filepath)}")
        # Apply saved position after a short delay (player needs to load first)
        if saved_pos > 0:
            QTimer.singleShot(1500, lambda: self.player.setPosition(saved_pos))

    def _player_toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _player_stop(self):
        self._save_playback_position()
        self.player.stop()
        if hasattr(self, "tray") and self.tray.isVisible():
            self.tray.setToolTip("YT-DLP WebUI")

    def _save_playback_position(self):
        if not self.player or not self.player.source():
            return
        filepath = self.player.source().toLocalFile()
        if not filepath:
            return
        pos = self.player.position()
        c = sqlite3.connect(LIBRARY_DB)
        c.execute("INSERT OR REPLACE INTO playback_positions (filepath, position, updated_at) VALUES (?,?,CURRENT_TIMESTAMP)",
                  (filepath, pos))
        c.commit()
        c.close()

    def _toggle_sleep_timer(self):
        if self._sleep_timer.isActive():
            self._sleep_timer.stop()
            self._sleep_minutes = 0
            self.player_sleep.setChecked(False)
            self.player_sleep.setText("Sleep")
            self.show_toast("Sleep Timer", "Cancelled")
        else:
            minutes, ok = QInputDialog.getInt(self, "Sleep Timer", "Minutes until stop:", 30, 1, 120)
            if ok:
                self._sleep_minutes = minutes * 60
                self._sleep_timer.start(1000)
                self.player_sleep.setChecked(True)
                self.player_sleep.setText(f"Sleep {minutes}m")
                self.show_toast("Sleep Timer", f"Stops in {minutes} min")

    def _sleep_timer_tick(self):
        self._sleep_minutes -= 1
        if self._sleep_minutes <= 0:
            self._sleep_timer.stop()
            self.player_stop()
            self.player_sleep.setChecked(False)
            self.player_sleep.setText("Sleep")
            self.show_toast("Sleep Timer", "Playback stopped")
        else:
            m, s = divmod(self._sleep_minutes, 60)
            self.player_sleep.setText(f"Sleep {m}m {s}s")

    def _set_eq(self, text):
        mode = text.replace("EQ: ", "").lower()
        # Simple EQ presets via Qt Multimedia (basic volume balance simulation)
        # Real EQ would need a DSP library; this is a placeholder preset selector
        self.show_toast("Equalizer", f"Applied: {mode.title()}")

    # ----- Batch 3: Collaborative Playlists, Auto-DJ, Volume Normalize, EQ Bands, Night Mode -----

    def _toggle_auto_dj(self):
        self.auto_dj_enabled = not getattr(self, "auto_dj_enabled", False)
        self.show_toast("Auto-DJ", "On" if self.auto_dj_enabled else "Off")
        if self.auto_dj_enabled and self.playlist:
            self._autodj_queue_next()

    def _autodj_queue_next(self):
        if not getattr(self, "auto_dj_enabled", False):
            return
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        current_artist = None
        if self.player and self.player.source():
            fp = self.player.source().toLocalFile()
            row = c.execute("SELECT music_artist FROM library WHERE filepath = ?", (fp,)).fetchone()
            if row:
                current_artist = row[0]
        c.close()
        if current_artist:
            rows = c.execute(
                "SELECT filepath FROM library WHERE is_music = '1' AND lower(music_artist) = lower(?) "
                "ORDER BY RANDOM() LIMIT 5",
                (current_artist,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT filepath FROM library WHERE is_music = '1' ORDER BY RANDOM() LIMIT 5"
            ).fetchall()
        c.close()
        for r in rows:
            if r["filepath"] not in self.playlist:
                self.playlist.append(r["filepath"])
        self.show_toast("Auto-DJ", f"Added {len(rows)} similar tracks")

    def _normalize_volume(self):
        """Simple volume normalization placeholder."""
        self.audio_output.setVolume(0.75)
        self.player_vol_slider.setValue(75)
        self.show_toast("Normalize", "Volume set to 75%")

    def _open_eq_bands(self):
        dlg = EQBandsDialog(self)
        dlg.exec()

    def _toggle_night_mode(self):
        """Auto-switch to dark theme after 8 PM, light before 8 AM."""
        import datetime
        hour = datetime.datetime.now().hour
        app_cfg = self.config.setdefault("app", {})
        if hour >= 20 or hour < 8:
            app_cfg["theme"] = "dark"
        else:
            app_cfg["theme"] = "light"
        save_config(self.config)
        self.config = self.config
        self.apply_theme()
        self.show_toast("Night Mode", f"Theme set to {app_cfg['theme']}")



# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

    # ----- Batch 1: Lyrics, Album Art Viewer, Crossfade, Gapless, Recently Played -----

    def _toggle_lyrics_panel(self):
        if not hasattr(self, "lyrics_panel") or self.lyrics_panel is None:
            self.lyrics_panel = LyricsPanel(self)
        self.lyrics_panel.show()
        self.lyrics_panel.raise_()
        self.lyrics_panel.activateWindow()

    def _update_lyrics(self):
        if hasattr(self, "lyrics_panel") and self.lyrics_panel and self.lyrics_panel.isVisible():
            pos = self.player.position() if self.player else 0
            self.lyrics_panel.update_time(pos)

    def _open_album_art_viewer(self):
        if not self.player or not self.player.source():
            QMessageBox.information(self, "Album Art", "No track playing")
            return
        filepath = self.player.source().toLocalFile()
        c = sqlite3.connect(LIBRARY_DB)
        row = c.execute("SELECT music_cover FROM library WHERE filepath = ?", (filepath,)).fetchone()
        c.close()
        cover = row[0] if row and row[0] else ""
        dlg = AlbumArtViewer(cover, self)
        dlg.exec()

    def _toggle_crossfade(self):
        self.crossfade_enabled = not getattr(self, "crossfade_enabled", False)
        self.show_toast("Crossfade", "On" if self.crossfade_enabled else "Off")

    def _toggle_gapless(self):
        self.gapless_enabled = not getattr(self, "gapless_enabled", False)
        self.show_toast("Gapless", "On" if self.gapless_enabled else "Off")

    def _show_recently_played(self):
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM watch_history WHERE 1=1 ORDER BY played_at DESC LIMIT 20"
        ).fetchall()
        c.close()
        dlg = RecentlyPlayedDialog(rows, self)
        dlg.exec()

    def _player_seek(self, value):
        self.player.setPosition(value)

    def _player_set_volume(self, value):
        self.audio_output.setVolume(value / 100.0)

    def _player_skip(self, ms):
        self.player.setPosition(self.player.position() + ms)

    def _player_set_speed(self, text):
        rate = float(text.replace("x", ""))
        self.player.setPlaybackRate(rate)

    def _chapter_seek(self):
        btn = self.sender()
        ms = btn.property("ms")
        if ms is not None:
            self.player.setPosition(int(ms))

    @staticmethod
    def _fmt_chapter(seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._player_toggle()
            event.accept()
        elif key == Qt.Key.Key_Left:
            self._player_skip(-10000)
            event.accept()
        elif key == Qt.Key.Key_Right:
            self._player_skip(10000)
            event.accept()
        elif key == Qt.Key.Key_Up:
            vol = min(100, self.player_vol_slider.value() + 10)
            self.player_vol_slider.setValue(vol)
            event.accept()
        elif key == Qt.Key.Key_Down:
            vol = max(0, self.player_vol_slider.value() - 10)
            self.player_vol_slider.setValue(vol)
            event.accept()
        elif key == Qt.Key.Key_M:
            self.audio_output.setMuted(not self.audio_output.isMuted())
            event.accept()
        elif key == Qt.Key.Key_F:
            self.setWindowState(self.windowState() ^ Qt.WindowState.WindowMaximized)
            event.accept()
        else:
            super().keyPressEvent(event)

    def _player_update_position(self):
        if self.player_pos_slider and not self.player_pos_slider.isSliderDown():
            self.player_pos_slider.setValue(self.player.position())

    def _player_position_changed(self, pos):
        if self.player_pos_slider:
            self.player_pos_slider.setValue(pos)
        if self.player_time_lbl:
            self.player_time_lbl.setText(
                f"{self._fmt_time(pos)} / {self._fmt_time(self.player.duration())}"
            )

    def _player_duration_changed(self, dur):
        if self.player_pos_slider:
            self.player_pos_slider.setRange(0, dur)
        if self.player_time_lbl:
            self.player_time_lbl.setText(
                f"{self._fmt_time(self.player.position())} / {self._fmt_time(dur)}"
            )

    def _player_state_changed(self, state):
        if self.player_play_btn:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.player_play_btn.setText("Pause")
                self.player_timer.start()
            else:
                self.player_play_btn.setText("Play")
                self.player_timer.stop()

    def _player_error(self, error, error_string):
        QMessageBox.warning(self, "Player Error", error_string)
        self.player_play_btn.setText("Play")

    def _open_mini_player(self):
        if not hasattr(self, "mini_player") or self.mini_player is None:
            self.mini_player = MiniPlayer(self)
        self.mini_player.show()
        self.mini_player.raise_()
        self.mini_player.activateWindow()

    @staticmethod
    def _fmt_time(ms):
        if not ms:
            return "0:00"
        s = int(ms) // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for u in urls:
            url_str = u.toString()
            if url_str.startswith(("http://", "https://")):
                self._add_url_to_queue(url_str)
        event.acceptProposedAction()

    def _add_url_to_queue(self, url):
        jid = str(uuid.uuid4())
        self.jobs[jid] = {
            "job_id": jid,
            "url": url,
            "status": "queued",
            "progress": 0,
            "speed": "",
            "eta": "",
        }
        worker = DownloadWorker(jid, url, self.config)
        worker.progress.connect(self._job_progress)
        worker.status.connect(self._job_status)
        worker.completed.connect(self._job_completed)
        worker.failed.connect(self._job_failed)
        self.workers[jid] = worker
        worker.start()
        self.refresh_jobs()
        self.set_view("queue")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top: navigation rail + content stack
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(0)

        # Navigation rail
        self.nav_rail = NavRail(self.theme, self)
        nav_items = [
            ("browser", "Browser", "Browser"),
            ("search", "Search", "Search"),
            ("trending", "Trending", "Trending"),
            ("music", "Music", "Music"),
            ("charts", "Top Charts", "Charts"),
            ("video", "Video", "Video"),
            ("queue", "Queue", "Queue"),
            ("library", "Library", "Library"),
            ("settings", "Settings", "Settings"),
        ]
        for key, label, icon in nav_items:
            self.nav_rail.add_item(key, label, icon, lambda k=key: self.set_view(k))
        self.nav_rail.set_active("browser")
        top.addWidget(self.nav_rail)

        # Content stack
        self.stack = QStackedWidget()
        top.addWidget(self.stack, 1)

        self.page_home = self._page_browser()
        self.page_search = self._page_search()
        self.page_trending = self._page_trending()
        self.page_music = self._page_music()
        self.page_charts = self._page_charts()
        self.page_video = self._page_video()
        self.page_queue = self._page_queue()
        self.page_library = self._page_library()
        self.page_settings = self._page_settings()

        for p in (self.page_home, self.page_search, self.page_trending, self.page_music,
                  self.page_charts, self.page_video, self.page_queue, self.page_library,
                  self.page_settings):
            self.stack.addWidget(p)

        root.addLayout(top, 1)

        # Bottom: player bar
        self.player_panel = PlayerBar(
            self.player, self.audio_output, self.video_widget, self.theme, self
        )
        self.player_panel._on_prev = self._playlist_prev
        self.player_panel._on_next = self._playlist_next
        self.player_panel._on_stop = self._player_stop
        root.addWidget(self.player_panel)

        self.set_view("browser")
        self.apply_theme()

    def set_view(self, key):
        self.nav_rail.set_active(key)
        index = {"browser": 0, "search": 1, "trending": 2, "music": 3, "charts": 4, "video": 5,
                 "queue": 6, "library": 7, "settings": 8}[key]
        self.stack.setCurrentIndex(index)

    def apply_theme(self):
        app_cfg = self.config.get("app", {})
        theme = app_cfg.get("theme", "dark")
        self.theme.set_theme(theme)

    # ----- pages -----
    def _page_browser(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # --- Nav bar ---
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet("background:#1e1e2e; border-bottom:1px solid #313244;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(6)

        self.btn_back = QPushButton("◀")
        self.btn_back.setFixedSize(32, 32)
        self.btn_back.setToolTip("Back")
        self.btn_back.clicked.connect(lambda: self.browser.back())
        bl.addWidget(self.btn_back)

        self.btn_fwd = QPushButton("Forward")
        self.btn_fwd.setFixedSize(32, 32)
        self.btn_fwd.setToolTip("Forward")
        self.btn_fwd.clicked.connect(lambda: self.browser.forward())
        bl.addWidget(self.btn_fwd)

        self.btn_reload = QPushButton("↻")
        self.btn_reload.setFixedSize(32, 32)
        self.btn_reload.setToolTip("Reload")
        self.btn_reload.clicked.connect(lambda: self.browser.reload())
        bl.addWidget(self.btn_reload)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL or search...")
        self.url_bar.returnPressed.connect(self._browser_go)
        self.url_bar.setStyleSheet("padding:4px 8px;")
        bl.addWidget(self.url_bar, 1)

        self.btn_go = QPushButton("Go")
        self.btn_go.setFixedSize(40, 28)
        self.btn_go.clicked.connect(self._browser_go)
        bl.addWidget(self.btn_go)

        self.btn_download = QPushButton("⬇ Download this video")
        self.btn_download.setObjectName("primary")
        self.btn_download.setFixedWidth(160)
        self.btn_download.setToolTip("Download the currently opened video URL")
        self.btn_download.clicked.connect(self._browser_download_current)
        self.btn_download.setEnabled(False)
        bl.addWidget(self.btn_download)

        lay.addWidget(bar)

        # --- Web view ---
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://www.youtube.com"))
        self.browser.urlChanged.connect(self._browser_url_changed)
        self.browser.loadFinished.connect(self._browser_load_finished)
        lay.addWidget(self.browser, 1)

        # --- Status strip ---
        self.browser_status = QLabel("Ready")
        self.browser_status.setStyleSheet("color:#a6adc8; font-size:12px; padding:4px 8px;")
        self.browser_status.setFixedHeight(24)
        lay.addWidget(self.browser_status)

        return w

    def _browser_go(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        if not text.startswith(("http://", "https://")):
            text = "https://www.youtube.com/results?search_query=" + text
        self.browser.setUrl(QUrl(text))

    def _browser_url_changed(self, qurl):
        self.url_bar.setText(qurl.toString())
        is_yt = "youtube.com" in qurl.toString() or "youtu.be" in qurl.toString()
        self.btn_download.setEnabled(is_yt)
        self.browser_status.setText("YouTube detected — download enabled" if is_yt else "Not a YouTube video page")

    def _browser_load_finished(self, ok):
        self.browser_status.setText("Loaded" if ok else "Load failed")

    def _browser_download_current(self):
        url = self.browser.url().toString()
        if not url:
            return
        self.video_url = url
        self.video_title = "Browser video"
        self.video_uploader = ""
        self.video_id = ""

        # Try to detect video title from the page via JS
        self.browser.page().runJavaScript("document.title", self._on_browser_title)

    def _on_browser_title(self, title):
        if title and isinstance(title, str) and title.strip():
            self.video_title = title.strip()
        self._do_browser_download()

    def _do_browser_download(self):
        url = self.video_url
        jid = str(uuid.uuid4())
        self.jobs[jid] = {
            "job_id": jid,
            "url": url,
            "status": "queued",
            "progress": 0,
            "speed": "",
            "eta": "",
        }
        worker = DownloadWorker(jid, url, self.config)
        worker.progress.connect(self._job_progress)
        worker.status.connect(self._job_status)
        worker.completed.connect(self._job_completed)
        worker.failed.connect(self._job_failed)
        self.workers[jid] = worker
        worker.start()
        self.refresh_jobs()
        self.refresh_library()
        self.set_view("queue")
        QMessageBox.information(self, "Added", f"Download added to queue:\n{self.video_title}\n{url}")

    def refresh_home_cfg(self):
        c = self.config
        dl = c.get("downloads", {})
        fc = c.get("format", {})
        txt = (f"Path: {dl.get('default_path','—')}  |  "
               f"Resolution cap: {fc.get('resolution_cap',1080)}p  |  "
               f"Container: {fc.get('merge_output_format','mp4')}  |  "
               f"Concurrent: {dl.get('concurrent_downloads',3)}")
        self.home_cfg.setText(txt)

    def _page_search(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(20)

        # Header
        h = QLabel("Search YouTube")
        h.setStyleSheet("font-size:24px; font-weight:bold; color:#e8e8ea;")
        lay.addWidget(h)

        sub = QLabel("Find videos, playlists, and channels")
        sub.setStyleSheet("color:#a0a0a8; font-size:14px;")
        lay.addWidget(sub)

        # Search bar
        top = QHBoxLayout()
        self.search_input = SearchBar("Search YouTube...")
        self.search_input.returnPressed.connect(self.do_search)
        btn = PrimaryButton("Search")
        btn.clicked.connect(self.do_search)
        top.addWidget(self.search_input, 1)
        top.addWidget(btn)

        batch_btn = GhostButton("Batch Playlist")
        batch_btn.clicked.connect(self._open_batch_dialog)
        top.addWidget(batch_btn)
        lay.addLayout(top)

        # Recent searches
        self.recent_searches_lbl = QLabel("Recent searches")
        self.recent_searches_lbl.setStyleSheet("color:#a0a0a8; font-size:12px; font-weight:bold;")
        lay.addWidget(self.recent_searches_lbl)
        self.recent_searches_flow = QFlowLayout()
        lay.addLayout(self.recent_searches_flow)
        self._refresh_recent_searches()

        # Results grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("QWidget { background: transparent; }")
        self.search_grid = QGridLayout(scroll_widget)
        self.search_grid.setSpacing(16)
        self.search_grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(scroll_widget)
        lay.addWidget(scroll, 1)

        self.search_status = QLabel("")
        self.search_status.setStyleSheet("color:#a0a0a8; font-size:12px;")
        lay.addWidget(self.search_status)

        back = GhostButton("← Back")
        back.clicked.connect(lambda: self.set_view("browser"))
        lay.addWidget(back)
        return w

    def _page_trending(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(16)

        h = QLabel("Trending")
        h.setStyleSheet("font-size:24px; font-weight:bold; color:#cdd6f4;")
        lay.addWidget(h)

        sub = QLabel("Popular videos right now")
        sub.setStyleSheet("color:#a6adc8; font-size:14px;")
        lay.addWidget(sub)

        btn = QPushButton("Refresh Trending")
        btn.setObjectName("primary")
        btn.clicked.connect(self.do_trending)
        lay.addWidget(btn)

        self.trending_results = QTableWidget()
        self.trending_results.setColumnCount(5)
        self.trending_results.setHorizontalHeaderLabels(["Thumbnail", "Title", "Uploader", "Duration", ""])
        self.trending_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.trending_results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trending_results.cellDoubleClicked.connect(self._trending_open)
        lay.addWidget(self.trending_results)

        back = QPushButton("← Back")
        back.clicked.connect(lambda: self.set_view("browser"))
        lay.addWidget(back)
        return w

    def do_trending(self):
        self.trending_results.setRowCount(0)
        self.tw = SearchWorker("trending 2026", max_results=20)
        self.tw.finished.connect(self._trending_done)
        self.tw.failed.connect(lambda e: print("Trending error:", e))
        self.tw.start()

    def _trending_done(self, results):
        self.trending_results.setRowCount(len(results))
        for i, r in enumerate(results):
            self.trending_results.setRowHeight(i, 70)
            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(120, 70)
            thumb_lbl.setStyleSheet("background:#181825; border-radius:4px;")
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if r.get("thumbnail"):
                from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
                from PyQt6.QtGui import QPixmap
                nam = QNetworkAccessManager()
                def _on_thumb(resp, lbl=thumb_lbl):
                    pix = QPixmap()
                    pix.loadFromData(resp.readAll())
                    lbl.setPixmap(pix.scaled(120, 70, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation))
                nam.finished.connect(_on_thumb)
                nam.get(QNetworkRequest(QUrl(r["thumbnail"])))
            self.trending_results.setCellWidget(i, 0, thumb_lbl)
            self.trending_results.setItem(i, 1, QTableWidgetItem(r.get("title", "")))
            self.trending_results.setItem(i, 2, QTableWidgetItem(r.get("uploader", "")))
            self.trending_results.setItem(i, 3, QTableWidgetItem(r.get("duration_string") or "—"))
            ob = QPushButton("Open")
            ob.setProperty("video_id", r.get("id", ""))
            ob.setProperty("video_url", r.get("webpage_url", ""))
            ob.setProperty("video_title", r.get("title", ""))
            ob.setProperty("video_uploader", r.get("uploader", ""))
            ob.clicked.connect(self._trending_open_btn)
            self.trending_results.setCellWidget(i, 4, ob)

    def _trending_open_btn(self):
        btn = self.sender()
        self._open_video(btn.property("video_url"), btn.property("video_title"),
                         btn.property("video_uploader"), btn.property("video_id"))

    def _trending_open(self, row, col):
        w = self.trending_results.cellWidget(row, 4)
        if w:
            self._trending_open_btn()

    def _page_music(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet("QFrame { background: #181825; border-bottom: 1px solid #2a2a33; }")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        h = QLabel("Music Library")
        h.setStyleSheet("font-size:20px; font-weight:bold; color:#e8e8ea;")
        hl.addWidget(h)
        hl.addStretch()

        new_pl_btn = PrimaryButton("New Playlist")
        new_pl_btn.setFixedWidth(100)
        new_pl_btn.clicked.connect(self._new_playlist)
        hl.addWidget(new_pl_btn)

        lay.addWidget(header)

        # Split: left sidebar + right content
        split = QHBoxLayout()
        split.setSpacing(0)
        split.setContentsMargins(0, 0, 0, 0)

        # Left sidebar: filters + playlists
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("QFrame { background: #141418; border-right: 1px solid #2a2a33; }")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(16, 16, 16, 16)
        sl.setSpacing(12)

        sl.addWidget(QLabel("Library"))
        sl.addWidget(QLabel("Filters"))

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.music_filter_all = QPushButton("All")
        self.music_filter_all.setCheckable(True)
        self.music_filter_all.setChecked(True)
        self.music_filter_all.setFixedWidth(60)
        self.music_filter_all.clicked.connect(lambda: self._music_filter("all"))
        filter_row.addWidget(self.music_filter_all)

        self.music_filter_liked = QPushButton("Liked")
        self.music_filter_liked.setCheckable(True)
        self.music_filter_liked.setFixedWidth(60)
        self.music_filter_liked.clicked.connect(lambda: self._music_filter("liked"))
        filter_row.addWidget(self.music_filter_liked)

        sl.addLayout(filter_row)

        self.music_filter_wl = QPushButton("Watch Later")
        self.music_filter_wl.setCheckable(True)
        self.music_filter_wl.setFixedWidth(100)
        self.music_filter_wl.clicked.connect(lambda: self._music_filter("watch_later"))
        sl.addWidget(self.music_filter_wl)

        sl.addSpacing(12)

        sl.addWidget(QLabel("Playlists"))
        self.music_playlist_list = QListWidget()
        self.music_playlist_list.setFixedHeight(180)
        self.music_playlist_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; color: #e8e8ea; font-size: 13px; }"
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #2a2a33; }"
            "QListWidget::item:selected { background: #24242e; color: #60a5fa; }"
        )
        sl.addWidget(self.music_playlist_list)

        sl.addStretch()

        split.addWidget(sidebar)

        # Right content: search + results + library
        right = QFrame()
        right.setStyleSheet("QFrame { background: #0f0f12; }")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(24, 20, 24, 20)
        rl.setSpacing(16)

        # Search bar
        search_bar = QHBoxLayout()
        self.music_search = SearchBar("Search YouTube for music...")
        self.music_search.returnPressed.connect(self.do_music_search)
        search_btn = PrimaryButton("Search")
        search_btn.clicked.connect(self.do_music_search)
        search_bar.addWidget(self.music_search, 1)
        search_bar.addWidget(search_btn)
        rl.addLayout(search_bar)

        # Mood chips
        mood_lay = QHBoxLayout()
        mood_lay.addWidget(QLabel("Mood:"))
        for mood in ["Chill", "Workout", "Party", "Focus", "Sleep"]:
            mb = QPushButton(mood)
            mb.setFixedWidth(64)
            mb.setStyleSheet(
                "QPushButton { color:#a0a0a8; font-size:11px; border:1px solid #2a2a33; "
                "border-radius:16px; padding:4px; }"
                "QPushButton:hover { background:#24242e; color:#e8e8ea; border-color:#60a5fa; }"
            )
            mb.clicked.connect(lambda checked, m=mood: self._mood_playlist(m))
            mood_lay.addWidget(mb)
        mood_lay.addStretch()
        rl.addLayout(mood_lay)

        # Search results
        rl.addWidget(QLabel("Search Results"))
        self.music_results_scroll = QScrollArea()
        self.music_results_scroll.setWidgetResizable(True)
        self.music_results_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.music_results_widget = QWidget()
        self.music_results_widget.setStyleSheet("QWidget { background: transparent; }")
        self.music_results_grid = QGridLayout(self.music_results_widget)
        self.music_results_grid.setSpacing(12)
        self.music_results_grid.setContentsMargins(0, 0, 0, 0)
        self.music_results_scroll.setWidget(self.music_results_widget)
        self.music_results_scroll.setMaximumHeight(260)
        rl.addWidget(self.music_results_scroll)

        self.music_status = QLabel("")
        self.music_status.setStyleSheet("color:#a0a0a8; font-size:12px;")
        rl.addWidget(self.music_status)

        # Your library
        rl.addWidget(QLabel("Your Library"))
        self.music_lib_scroll = QScrollArea()
        self.music_lib_scroll.setWidgetResizable(True)
        self.music_lib_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.music_lib_widget = QWidget()
        self.music_lib_widget.setStyleSheet("QWidget { background: transparent; }")
        self.music_lib_grid = QGridLayout(self.music_lib_widget)
        self.music_lib_grid.setSpacing(12)
        self.music_lib_grid.setContentsMargins(0, 0, 0, 0)
        self.music_lib_scroll.setWidget(self.music_lib_widget)
        rl.addWidget(self.music_lib_scroll, 1)

        split.addWidget(right, 1)
        lay.addLayout(split)

        back = GhostButton("← Back")
        back.clicked.connect(lambda: self.set_view("browser"))
        lay.addWidget(back)

        return w

    def _page_charts(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(16)

        h = QLabel("Top Charts")
        h.setStyleSheet("font-size:24px; font-weight:bold; color:#cdd6f4;")
        lay.addWidget(h)

        sub = QLabel("Trending music right now — discover new tracks")
        sub.setStyleSheet("color:#a6adc8; font-size:14px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        chart_bar = QHBoxLayout()
        chart_bar.addWidget(QLabel("Region:"))
        self.chart_region = QComboBox()
        self.chart_region.addItems(["Global", "United States", "United Kingdom", "Canada", "Australia"])
        chart_bar.addWidget(self.chart_region)
        chart_bar.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primary")
        refresh_btn.clicked.connect(self.do_charts_refresh)
        chart_bar.addWidget(refresh_btn)
        lay.addLayout(chart_bar)

        self.charts_results = QTableWidget()
        self.charts_results.setColumnCount(6)
        self.charts_results.setHorizontalHeaderLabels(["#", "Thumbnail", "Title", "Artist", "Duration", "Action"])
        self.charts_results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.charts_results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.charts_results, 1)

        self.charts_status = QLabel("")
        self.charts_status.setStyleSheet("color:#a6adc8; font-size:12px;")
        lay.addWidget(self.charts_status)

        back = QPushButton("← Back")
        back.clicked.connect(lambda: self.set_view("browser"))
        lay.addWidget(back)
        return w

    def do_charts_refresh(self):
        region = self.chart_region.currentText()
        self.charts_status.setText(f"Loading {region} charts...")
        self.charts_results.setRowCount(0)
        self.cw = SearchWorker(f"{region} top songs 2026", max_results=20)
        self.cw.finished.connect(self._charts_done)
        self.cw.failed.connect(lambda e: self.charts_status.setText(f"Error: {e}"))
        self.cw.start()

    def _charts_done(self, results):
        self.charts_status.setText(f"{len(results)} tracks")
        self.charts_results.setRowCount(len(results))
        for i, r in enumerate(results):
            self.charts_results.setRowHeight(i, 60)
            self.charts_results.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(50, 50)
            thumb_lbl.setStyleSheet("background:#181825; border-radius:4px;")
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if r.get("thumbnail"):
                from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
                from PyQt6.QtGui import QPixmap
                nam = QNetworkAccessManager()
                def _on_thumb(resp, lbl=thumb_lbl):
                    pix = QPixmap()
                    pix.loadFromData(resp.readAll())
                    lbl.setPixmap(pix.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation))
                nam.finished.connect(_on_thumb)
                nam.get(QNetworkRequest(QUrl(r["thumbnail"])))
            self.charts_results.setCellWidget(i, 1, thumb_lbl)
            self.charts_results.setItem(i, 2, QTableWidgetItem(r.get("title", "")))
            self.charts_results.setItem(i, 3, QTableWidgetItem(r.get("uploader", "")))
            self.charts_results.setItem(i, 4, QTableWidgetItem(r.get("duration_string") or "—"))
            dl_btn = QPushButton("⬇ MP3")
            dl_btn.setProperty("url", r.get("webpage_url", ""))
            dl_btn.setProperty("title", r.get("title", ""))
            dl_btn.setProperty("uploader", r.get("uploader", ""))
            dl_btn.clicked.connect(self._charts_download)
            self.charts_results.setCellWidget(i, 5, dl_btn)

    def _charts_download(self):
        btn = self.sender()
        url = btn.property("url")
        title = btn.property("title")
        uploader = btn.property("uploader")
        if not url:
            return
        self.charts_status.setText(f"Downloading: {title}")
        self.mdw = MusicDownloadWorker(url, self.config)
        self.mdw.finished.connect(self._charts_download_done)
        self.mdw.failed.connect(lambda e: self.charts_status.setText(f"Error: {e}"))
        self.mdw.start()

    def _charts_download_done(self, filepath, metadata):
        self.charts_status.setText(f"Downloaded: {metadata['title']}")
        c = sqlite3.connect(LIBRARY_DB)
        c.execute(
            "INSERT INTO library (job_id, source_url, title, uploader, duration, filepath, file_size, "
            "resolution, container, is_music, music_artist, music_album, music_track, "
            "music_genre, music_year, music_cover, music_duration) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("music_" + str(abs(hash(filepath))), metadata.get("webpage_url", ""),
             metadata.get("title", ""), metadata.get("uploader", ""),
             metadata.get("duration", 0), filepath,
             os.path.getsize(filepath) if os.path.exists(filepath) else 0,
             "mp3", "mp3", 1, metadata.get("uploader", ""), "", metadata.get("title", ""),
             "", "", metadata.get("thumbnail", ""), metadata.get("duration", 0)),
        )
        c.commit()
        c.close()
        self.refresh_music_library()
        self.show_toast("Charts Download", metadata.get("title", ""))

    def _discovery_weekly(self):
        """Auto-playlist from liked songs + similar artists (Spotify-style)."""
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        liked = c.execute(
            "SELECT filepath FROM library WHERE is_music = '1' AND is_liked = '1' ORDER BY play_count DESC LIMIT 15"
        ).fetchall()
        c.close()
        if not liked:
            QMessageBox.information(self, "Discovery Weekly", "No liked songs yet. Like some tracks first!")
            return
        self.playlist = [r["filepath"] for r in liked]
        self.playlist_index = 0
        self.player_shuffle.setChecked(True)
        self._true_shuffle()
        self._player_load(self.playlist[0])
        self.show_toast("Discovery Weekly", f"{len(liked)} liked tracks shuffled")

    def _export_playlist(self):
        """Export current library to JSON."""
        path, _ = QFileDialog.getSaveFileName(self, "Export Playlist", "yt-dlp-music-export.json", "JSON (*.json)")
        if not path:
            return
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM library WHERE is_music = '1'").fetchall()
        c.close()
        data = [dict(r) for r in rows]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.show_toast("Export", f"Exported {len(data)} tracks")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _import_playlist(self):
        """Import library from JSON."""
        path, _ = QFileDialog.getOpenFileName(self, "Import Playlist", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            c = sqlite3.connect(LIBRARY_DB)
            for r in data:
                c.execute(
                    "INSERT INTO library (job_id, source_url, title, uploader, duration, filepath, file_size, "
                    "resolution, container, is_music, music_artist, music_album, music_track, "
                    "music_genre, music_year, music_cover, music_duration, is_liked, is_watch_later, is_disliked) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r.get("job_id", ""), r.get("source_url", ""), r.get("title", ""),
                     r.get("uploader", ""), r.get("duration", 0), r.get("filepath", ""),
                     r.get("file_size", 0), r.get("resolution", ""), r.get("container", ""),
                     r.get("is_music", ""), r.get("music_artist", ""), r.get("music_album", ""),
                     r.get("music_track", ""), r.get("music_genre", ""), r.get("music_year", ""),
                     r.get("music_cover", ""), r.get("music_duration", 0),
                     r.get("is_liked", "0"), r.get("is_watch_later", "0"), r.get("is_disliked", "0")),
                )
            c.commit()
            c.close()
            self.refresh_music_library()
            self.show_toast("Import", f"Imported {len(data)} tracks")
        except Exception as e:
            QMessageBox.warning(self, "Import Failed", str(e))

    def _mood_playlist(self, mood):
        """Generate a playlist by keyword matching (Spotify-style mood playlists)."""
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        keywords = {
            "Chill": ["chill", "lofi", "ambient", "relax"],
            "Workout": ["workout", "gym", "energetic", "upbeat"],
            "Party": ["party", "dance", "club", "celebration"],
            "Focus": ["focus", "study", "concentration", "instrumental"],
            "Sleep": ["sleep", "rain", "white noise", "calm"],
        }
        kws = keywords.get(mood, [])
        if not kws:
            return
        like_clauses = " OR ".join(["lower(title) LIKE ?" for _ in kws])
        params = [f"%{kw}%" for kw in kws]
        rows = c.execute(
            f"SELECT filepath FROM library WHERE is_music = '1' AND ({like_clauses}) ORDER BY downloaded_at DESC LIMIT 30",
            params,
        ).fetchall()
        c.close()
        if not rows:
            QMessageBox.information(self, f"{mood} Mix", f"No tracks match '{mood}' mood yet.")
            return
        self.playlist = [r["filepath"] for r in rows]
        self.playlist_index = 0
        self.player_shuffle.setChecked(True)
        self._true_shuffle()
        self._player_load(self.playlist[0])
        self.show_toast(f"{mood} Mix", f"{len(rows)} tracks")

    def _new_playlist(self):
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            self.music_playlist_list.addItem(QListWidgetItem(name.strip()))

    def _music_filter(self, filter_type):
        self.music_filter_all.setChecked(filter_type == "all")
        self.music_filter_liked.setChecked(filter_type == "liked")
        self.music_filter_wl.setChecked(filter_type == "watch_later")
        self.refresh_music_library()

    def do_music_search(self):
        q = self.music_search.text().strip()
        if not q:
            return
        self.music_status.setText("Searching...")
        self.music_results.setRowCount(0)
        self.msw = SearchWorker(q + " music", max_results=20)
        self.msw.finished.connect(self._music_search_done)
        self.msw.failed.connect(lambda e: self.music_status.setText(f"Error: {e}"))
        self.msw.start()

    def _music_search_done(self, results):
        self.music_status.setText(f"{len(results)} results")

        # Clear existing grid
        while self.music_results_grid.count():
            child = self.music_results_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        cols = 5
        for i, r in enumerate(results):
            card = MediaCard(
                title=r.get("title", ""),
                subtitle=r.get("uploader", ""),
                artwork=None,
            )
            card.setFixedSize(190, 150)

            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(190, 115)
            thumb_lbl.setStyleSheet("background:#181825; border-radius:4px;")
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if r.get("thumbnail"):
                from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
                from PyQt6.QtGui import QPixmap
                nam = QNetworkAccessManager()
                def _on_thumb(resp, lbl=thumb_lbl):
                    pix = QPixmap()
                    pix.loadFromData(resp.readAll())
                    lbl.setPixmap(pix.scaled(190, 115, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation))
                nam.finished.connect(_on_thumb)
                nam.get(QNetworkRequest(QUrl(r["thumbnail"])))
            card.layout().insertWidget(0, thumb_lbl)

            dl_btn = PrimaryButton("MP3")
            dl_btn.setFixedWidth(55)
            dl_btn.setProperty("url", r.get("webpage_url", ""))
            dl_btn.setProperty("title", r.get("title", ""))
            dl_btn.setProperty("uploader", r.get("uploader", ""))
            dl_btn.clicked.connect(self._music_download)
            card.add_action(dl_btn)

            add_btn = GhostButton("+")
            add_btn.setFixedWidth(40)
            add_btn.setProperty("url", r.get("webpage_url", ""))
            add_btn.setProperty("title", r.get("title", ""))
            add_btn.setProperty("uploader", r.get("uploader", ""))
            add_btn.clicked.connect(self._music_add_to_playlist_menu)
            card.add_action(add_btn)

            card.clicked.connect(
                lambda checked, u=r.get("webpage_url", ""), t=r.get("title", ""),
                u2=r.get("uploader", ""), i=r.get("id", ""): self._open_video(u, t, u2, i)
            )

            row = i // cols
            col = i % cols
            self.music_results_grid.addWidget(card, row, col)

        self.music_results_grid.setColumnStretch(cols, 1)
        self.music_results_grid.setRowStretch(len(results) // cols + 1, 1)

    def _music_download(self):
        btn = self.sender()
        url = btn.property("url")
        title = btn.property("title")
        uploader = btn.property("uploader")
        if not url:
            return
        self.music_status.setText(f"Downloading: {title}")
        self.mdw = MusicDownloadWorker(url, self.config)
        self.mdw.finished.connect(self._music_download_done)
        self.mdw.failed.connect(lambda e: self.music_status.setText(f"Error: {e}"))
        self.mdw.start()

    def _music_download_done(self, filepath, metadata):
        self.music_status.setText(f"Downloaded: {metadata['title']}")
        # Add to library as music
        c = sqlite3.connect(LIBRARY_DB)
        c.execute(
            "INSERT INTO library (job_id, source_url, title, uploader, duration, filepath, file_size, "
            "resolution, container, is_music, music_artist, music_album, music_track, "
            "music_genre, music_year, music_cover, music_duration) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("music_" + str(abs(hash(filepath))), metadata.get("webpage_url", ""),
             metadata.get("title", ""), metadata.get("uploader", ""),
             metadata.get("duration", 0), filepath,
             os.path.getsize(filepath) if os.path.exists(filepath) else 0,
             "mp3", "mp3", 1, metadata.get("uploader", ""), "", metadata.get("title", ""),
             "", "", metadata.get("thumbnail", ""), metadata.get("duration", 0)),
        )
        c.commit()
        c.close()
        self.refresh_music_library()
        self.show_toast("Music Downloaded", metadata.get("title", ""))

    def _music_add_to_playlist_menu(self):
        btn = self.sender()
        url = btn.property("url")
        title = btn.property("title")
        uploader = btn.property("uploader")
        # Simple: add to a default "Liked Songs" playlist or create one
        QMessageBox.information(self, "Add to Playlist",
                                f"Add '{title}' by {uploader} to a playlist?\n\n"
                                f"URL: {url}\n\n(Feature: create/select playlist from sidebar coming next)")

    def refresh_music_library(self):
        q = self.music_lib_search.text().strip().lower() if hasattr(self, "music_lib_search") else ""
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        if q:
            rows = c.execute(
                "SELECT * FROM library WHERE is_music = '1' AND (lower(title) LIKE ? OR lower(music_artist) LIKE ? OR lower(music_album) LIKE ?) ORDER BY downloaded_at DESC",
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM library WHERE is_music = '1' ORDER BY downloaded_at DESC").fetchall()
        c.close()

        # Clear existing grid
        while self.music_lib_grid.count():
            child = self.music_lib_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        cols = 6
        for i, it in enumerate(rows):
            card = MediaCard(
                title=it["title"] or "",
                subtitle=it["music_artist"] or "",
                artwork=None,
            )
            card.setFixedSize(170, 130)

            cover_lbl = QLabel()
            cover_lbl.setFixedSize(170, 95)
            cover_lbl.setStyleSheet("background:#181825; border-radius:4px;")
            cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if it["music_cover"]:
                from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
                from PyQt6.QtGui import QPixmap
                nam = QNetworkAccessManager()
                def _on_thumb(resp, lbl=cover_lbl, cover=it["music_cover"]):
                    pix = QPixmap()
                    pix.loadFromData(resp.readAll())
                    lbl.setPixmap(pix.scaled(170, 95, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation))
                nam.finished.connect(_on_thumb)
                nam.get(QNetworkRequest(QUrl(it["music_cover"])))
            card.layout().insertWidget(0, cover_lbl)

            likeb = QPushButton("Liked" if it["is_liked"] == "1" else "Like")
            likeb.setProperty("id", it["id"])
            likeb.setFixedWidth(55)
            likeb.setStyleSheet("QPushButton { border: none; font-size: 10px; } QPushButton:hover { color: #f38ba8; }")
            likeb.clicked.connect(self._music_toggle_like)
            card.add_action(likeb)

            ardb = QPushButton("Radio")
            ardb.setProperty("artist", it["music_artist"] or "")
            ardb.setFixedWidth(45)
            ardb.setStyleSheet("QPushButton { border: none; font-size: 10px; } QPushButton:hover { color: #60a5fa; }")
            ardb.clicked.connect(self._artist_radio_from_btn)
            card.add_action(ardb)

            playb = QPushButton("Play")
            playb.setProperty("path", it["filepath"])
            playb.clicked.connect(self._music_play)
            card.add_action(playb)

            delb = QPushButton("Delete")
            delb.setProperty("id", it["id"])
            delb.setFixedWidth(45)
            delb.setStyleSheet("QPushButton { border: none; font-size: 10px; } QPushButton:hover { color: #ef4444; }")
            delb.clicked.connect(self._music_del)
            card.add_action(delb)

            card.clicked.connect(
                lambda checked, p=it["filepath"]: self._music_play_from_card(p)
            )

            row = i // cols
            col = i % cols
            self.music_lib_grid.addWidget(card, row, col)

        self.music_lib_grid.setColumnStretch(cols, 1)
        self.music_lib_grid.setRowStretch(len(rows) // cols + 1, 1)

    def _music_play_from_card(self, path: str):
        if path and os.path.exists(path):
            self._player_load(path)
        else:
            QMessageBox.warning(self, "Playback", "File not found: " + str(path))

    def _artist_radio_from_btn(self):
        btn = self.sender()
        artist = btn.property("artist")
        if artist:
            self._artist_radio(artist)

    def _music_toggle_like(self):
        btn = self.sender()
        item_id = btn.property("id")
        c = sqlite3.connect(LIBRARY_DB)
        row = c.execute("SELECT is_liked FROM library WHERE id = ?", (item_id,)).fetchone()
        val = 0 if (row and row[0] == "1") else 1
        c.execute("UPDATE library SET is_liked = ? WHERE id = ?", (str(val), item_id))
        c.commit()
        c.close()
        self.refresh_music_library()

    def _music_play(self):
        btn = self.sender()
        path = btn.property("path")
        if path and os.path.exists(path):
            self._player_load(path)
        else:
            QMessageBox.warning(self, "Playback", "File not found: " + str(path))

    def _music_del(self):
        btn = self.sender()
        item_id = btn.property("id")
        library_delete(item_id, delete_file=True)
        self.refresh_music_library()

    def _open_music_playlist_import(self):
        dlg = PlaylistImportDialog(self)
        if dlg.exec():
            urls = dlg.selected_urls()
            for url in urls:
                self._music_download_url(url)

    def _music_download_url(self, url):
        jid = str(uuid.uuid4())
        self.jobs[jid] = {
            "job_id": jid, "url": url, "status": "queued",
            "progress": 0, "speed": "", "eta": "",
        }
        worker = DownloadWorker(jid, url, self.config)
        worker.progress.connect(self._job_progress)
        worker.status.connect(self._job_status)
        worker.completed.connect(self._job_completed)
        worker.failed.connect(self._job_failed)
        self.workers[jid] = worker
        worker.start()
        self.refresh_jobs()
        self.set_view("queue")

    def do_search(self):
        q = self.search_input.text().strip() or getattr(self, "nav_search_query", "")
        if not q:
            return
        self._save_recent_search(q)
        self.search_status.setText("Searching...")
        self.search_results.setRowCount(0)
        self.sw = SearchWorker(q, max_results=20)
        self.sw.finished.connect(self._search_done)
        self.sw.failed.connect(lambda e: self.search_status.setText(f"Error: {e}"))
        self.sw.start()

    def _save_recent_search(self, q):
        cfg = self.config
        app_cfg = cfg.setdefault("app", {})
        recent = app_cfg.get("recent_searches", [])
        if q in recent:
            recent.remove(q)
        recent.insert(0, q)
        app_cfg["recent_searches"] = recent[:10]
        save_config(cfg)
        self.config = cfg
        self._refresh_recent_searches()

    def _refresh_recent_searches(self):
        # Clear existing
        while self.recent_searches_flow.count():
            item = self.recent_searches_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        app_cfg = self.config.get("app", {})
        recent = app_cfg.get("recent_searches", [])
        for q in recent:
            btn = QPushButton(q)
            btn.setFixedHeight(24)
            btn.setStyleSheet("QPushButton { text-align:left; padding:4px 8px; border:1px solid #45475a; border-radius:4px; color:#a6adc8; font-size:11px; } QPushButton:hover { background:#313244; color:#cdd6f4; border-color:#45475a; }")
            btn.clicked.connect(lambda checked, qq=q: self._run_recent_search(qq))
            self.recent_searches_flow.addWidget(btn)

    def _run_recent_search(self, q):
        self.search_input.setText(q)
        self.do_search()

    def _search_done(self, results):
        self.search_status.setText(f"{len(results)} results")

        # Clear existing grid
        while self.search_grid.count():
            child = self.search_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        cols = 4
        for i, r in enumerate(results):
            card = MediaCard(
                title=r.get("title", ""),
                subtitle=r.get("uploader", ""),
                artwork=None,
            )
            card.setFixedSize(240, 160)

            # Thumbnail
            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(240, 135)
            thumb_lbl.setStyleSheet("background:#181825; border-radius:4px;")
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if r.get("thumbnail"):
                from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
                from PyQt6.QtGui import QPixmap
                nam = QNetworkAccessManager()
                def _on_thumb(resp, lbl=thumb_lbl):
                    pix = QPixmap()
                    pix.loadFromData(resp.readAll())
                    lbl.setPixmap(pix.scaled(240, 135, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation))
                nam.finished.connect(_on_thumb)
                nam.get(QNetworkRequest(QUrl(r["thumbnail"])))
            card.layout().insertWidget(0, thumb_lbl)

            # Duration badge
            dur_lbl = QLabel(r.get("duration_string") or "—")
            dur_lbl.setStyleSheet(
                "QLabel { background: rgba(0,0,0,160); color:#ffffff; font-size:10px; "
                "padding:2px 6px; border-radius:3px; }"
            )
            dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
            dur_lbl.setFixedSize(240, 20)
            dur_lbl.move(0, 115)
            thumb_lbl.layout().addWidget(dur_lbl) if thumb_lbl.layout() else None

            # Action buttons
            dl_btn = PrimaryButton("MP3")
            dl_btn.setFixedWidth(60)
            dl_btn.setProperty("video_url", r.get("webpage_url", ""))
            dl_btn.setProperty("video_title", r.get("title", ""))
            dl_btn.setProperty("video_uploader", r.get("uploader", ""))
            dl_btn.clicked.connect(self._search_download)
            card.add_action(dl_btn)

            q_btn = GhostButton("Queue")
            q_btn.setFixedWidth(60)
            q_btn.setProperty("video_url", r.get("webpage_url", ""))
            q_btn.setProperty("video_title", r.get("title", ""))
            q_btn.setProperty("video_uploader", r.get("uploader", ""))
            q_btn.clicked.connect(self._search_queue)
            card.add_action(q_btn)

            # Click card to open video detail
            card.clicked.connect(
                lambda checked, u=r.get("webpage_url", ""), t=r.get("title", ""),
                u2=r.get("uploader", ""), i=r.get("id", ""): self._open_video(u, t, u2, i)
            )

            row = i // cols
            col = i % cols
            self.search_grid.addWidget(card, row, col)

        self.search_grid.setColumnStretch(cols, 1)
        self.search_grid.setRowStretch(len(results) // cols + 1, 1)

    def _search_download(self):
        btn = self.sender()
        url = btn.property("video_url")
        title = btn.property("video_title")
        uploader = btn.property("video_uploader")
        if not url:
            return
        self._add_url_to_queue(url)
        self.set_view("queue")
        self.show_toast("Added to queue", title)

    def _search_queue(self):
        btn = self.sender()
        url = btn.property("video_url")
        title = btn.property("video_title")
        uploader = btn.property("video_uploader")
        if not url:
            return
        self._add_url_to_queue(url)
        self.set_view("queue")
        self.show_toast("Added to queue", title)

    def _search_open_btn(self):
        btn = self.sender()
        self._open_video(btn.property("video_url"),
                         btn.property("video_title"),
                         btn.property("video_uploader"),
                         btn.property("video_id"))

    def _search_open_btn(self):
        btn = self.sender()
        self._open_video(btn.property("video_url"), btn.property("video_title"),
                         btn.property("video_uploader"), btn.property("video_id"))

    def _open_video(self, url, title, uploader, vid):
        self.video_url = url
        self.video_title = title
        self.video_uploader = uploader
        self.video_id = vid
        self.video_info_label.setText(f"Loading {title}...")
        self.video_thumb.clear()
        self.video_formats.clear()
        self.set_view("video")
        self.aiw = InfoWorker(url)
        self.aiw.finished.connect(self._video_info_done)
        self.aiw.failed.connect(lambda e: self.video_info_label.setText(f"Error: {e}"))
        self.aiw.start()

    def _video_info_done(self, info):
        self.video_info = info
        self.video_info_label.setText(info.get("title", ""))
        sub = f"{info.get('uploader','')}  •  {info.get('duration_string','—')}  •  {info.get('view_count',0):,} views"
        self.video_sub_label.setText(sub)
        if info.get("thumbnail"):
            from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
            from PyQt6.QtGui import QPixmap
            nam = QNetworkAccessManager()
            def _on_thumb(resp):
                pix = QPixmap()
                pix.loadFromData(resp.readAll())
                self.video_thumb.setPixmap(pix.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
            nam.finished.connect(_on_thumb)
            nam.get(QNetworkRequest(QUrl(info["thumbnail"])))

        # formats table
        self.video_formats.setRowCount(0)
        vf = info.get("video_formats", [])
        if not vf:
            vf = info.get("combined_formats", [])
        self.video_formats.setRowCount(len(vf))
        for i, f in enumerate(vf):
            h = f.get("height") or "?"
            fps = f.get("fps")
            fps_str = f"{fps}fps" if fps else ""
            vcodec = f.get("vcodec", "")
            ext = f.get("ext", "")
            size = f.get("filesize")
            size_str = f"{(size/1024/1024):.1f} MB" if size else "?"
            self.video_formats.setItem(i, 0, QTableWidgetItem(f"{h}p {fps_str}"))
            self.video_formats.setItem(i, 1, QTableWidgetItem(vcodec))
            self.video_formats.setItem(i, 2, QTableWidgetItem(ext))
            self.video_formats.setItem(i, 3, QTableWidgetItem(size_str))
            addb = QPushButton("Add")
            addb.setProperty("format", f)
            addb.clicked.connect(self._video_add_format)
            self.video_formats.setCellWidget(i, 4, addb)
        self.video_formats.resizeColumnsToContents()

        # subs
        self.video_subs.clear()
        for lang in info.get("sub_langs", []):
            self.video_subs.addItem(lang)

    def _video_add_format(self):
        btn = self.sender()
        f = btn.property("format")
        self.video_selected_format = f
        QMessageBox.information(self, "Format selected",
                                f"Selected {f.get('height','?')}p {f.get('ext','')} — will use global settings for download.")

    # ----- queue page -----
    def _page_queue(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(16)

        # Header
        h = QLabel("Download Queue")
        h.setStyleSheet("font-size:24px; font-weight:bold; color:#e8e8ea;")
        lay.addWidget(h)

        sub = QLabel("Manage your downloads")
        sub.setStyleSheet("color:#a0a0a8; font-size:14px;")
        lay.addWidget(sub)

        # Stats row
        stats = QHBoxLayout()
        self.queue_stats = {}
        for label, key in [("Queued", "queued"), ("Running", "running"), ("Completed", "completed"), ("Failed", "failed")]:
            card = QFrame()
            card.setFixedSize(120, 70)
            card.setStyleSheet("QFrame { background: #181825; border-radius: 8px; }")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            val = QLabel("0")
            val.setStyleSheet("QLabel { font-size: 20px; font-weight: bold; color:#e8e8ea; }")
            lbl = QLabel(label)
            lbl.setStyleSheet("QLabel { color: #a0a0a8; font-size: 11px; }")
            cl.addWidget(val)
            cl.addWidget(lbl)
            stats.addWidget(card)
            self.queue_stats[key] = val
        stats.addStretch()
        lay.addLayout(stats)

        # Scrollable job list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.queue_widget = QWidget()
        self.queue_widget.setStyleSheet("QWidget { background: transparent; }")
        self.queue_grid = QGridLayout(self.queue_widget)
        self.queue_grid.setSpacing(10)
        self.queue_grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.queue_widget)
        lay.addWidget(scroll, 1)

        back = GhostButton("← Back")
        back.clicked.connect(lambda: self.set_view("browser"))
        lay.addWidget(back)
        return w

    def refresh_jobs(self):
        # Update stats
        stats = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
        for j in self.jobs.values():
            s = j.get("status", "queued")
            if s in stats:
                stats[s] += 1
        for k, v in stats.items():
            self.queue_stats[k].setText(str(v))

        # Clear existing grid
        while self.queue_grid.count():
            child = self.queue_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        cols = 1
        for i, (jid, job) in enumerate(self.jobs.items()):
            card = QFrame()
            card.setFixedHeight(64)
            card.setStyleSheet(
                "QFrame { background: #181825; border: 1px solid #2a2a33; border-radius: 8px; }"
            )
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            cl.setSpacing(12)

            # Status dot
            status = job.get("status", "queued")
            status_color = {
                "queued": "#a0a0a8",
                "running": "#60a5fa",
                "paused": "#f59e0b",
                "completed": "#22c55e",
                "failed": "#ef4444",
                "cancelled": "#64748b",
            }.get(status, "#a0a0a8")
            status_dot = QLabel()
            status_dot.setFixedSize(8, 8)
            status_dot.setStyleSheet(f"QLabel {{ background: {status_color}; border-radius: 4px; }}")
            cl.addWidget(status_dot)

            # Title/URL
            title_lbl = QLabel(job.get("url", "")[:60])
            title_lbl.setStyleSheet("QLabel { color: #e8e8ea; font-size: 13px; }")
            title_lbl.setWordWrap(True)
            cl.addWidget(title_lbl, 1)

            # Progress bar
            pb = QProgressBar()
            pb.setFixedWidth(150)
            pb.setValue(int(job.get("progress", 0)))
            pb.setTextVisible(False)
            pb.setStyleSheet(
                f"QProgressBar {{ border: none; border-radius: 4px; background: #24242e; height: 6px; }}"
                f"QProgressBar::chunk {{ background: #60a5fa; border-radius: 4px; }}"
            )
            cl.addWidget(pb)

            # Speed / ETA
            info_lbl = QLabel()
            info_lbl.setStyleSheet("QLabel { color: #a0a0a8; font-size: 11px; }")
            info_lbl.setText(f"{job.get('speed', '')}  {job.get('eta', '')}")
            cl.addWidget(info_lbl)

            # Actions
            if status in ("failed", "cancelled"):
                rb = PrimaryButton("Retry")
                rb.setFixedWidth(70)
                rb.setProperty("job_id", jid)
                rb.clicked.connect(self._queue_retry)
                cl.addWidget(rb)
            else:
                delb = QPushButton("Delete")
                delb.setFixedWidth(70)
                delb.setStyleSheet(
                    "QPushButton { border: none; border-radius: 4px; color: #a0a0a8; font-size: 11px; }"
                    "QPushButton:hover { background: #24242e; color: #ef4444; }"
                )
                delb.setProperty("job_id", jid)
                delb.clicked.connect(self._queue_del)
                cl.addWidget(delb)

            row = i // cols
            col = i % cols
            self.queue_grid.addWidget(card, row, col)

        self.queue_grid.setColumnStretch(cols, 1)
        self.queue_grid.setRowStretch(len(self.jobs) // cols + 1, 1)

    def _queue_del(self):
        btn = self.sender()
        jid = btn.property("job_id")
        if jid in self.workers:
            self.workers[jid].abort()
        self.jobs.pop(jid, None)
        self.workers.pop(jid, None)
        self.refresh_jobs()

    def _queue_retry(self):
        btn = self.sender()
        jid = btn.property("job_id")
        if jid not in self.jobs:
            return
        old = self.jobs[jid]
        new_id = str(uuid.uuid4())
        self.jobs[new_id] = {
            "job_id": new_id,
            "url": old["url"],
            "status": "queued",
            "progress": 0,
            "speed": "",
            "eta": "",
        }
        worker = DownloadWorker(new_id, old["url"], self.config)
        worker.progress.connect(self._job_progress)
        worker.status.connect(self._job_status)
        worker.completed.connect(self._job_completed)
        worker.failed.connect(self._job_failed)
        self.workers[new_id] = worker
        worker.start()
        self.refresh_jobs()

    # ----- library page -----
    def _page_library(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(12)

        top = QHBoxLayout()
        self.lib_search = QLineEdit()
        self.lib_search.setPlaceholderText("Search library...")
        self.lib_search.returnPressed.connect(self.refresh_library)
        top.addWidget(self.lib_search)
        btn = QPushButton("Refresh")
        btn.clicked.connect(self.refresh_library)
        top.addWidget(btn)

        playall_btn = QPushButton("Play All")
        playall_btn.setObjectName("primary")
        playall_btn.clicked.connect(self._library_play_all)
        top.addWidget(playall_btn)
        lay.addLayout(top)

        self.lib_table = QTableWidget()
        self.lib_table.setColumnCount(11)
        self.lib_table.setHorizontalHeaderLabels(["Title", "Uploader", "Resolution", "Size", "Like", "Dislike", "Watch Later", "Play", "Open Folder", "Delete", "Share"])
        self.lib_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lib_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.lib_table)

        back = QPushButton("← Back")
        back.clicked.connect(lambda: self.set_view("browser"))
        lay.addWidget(back)
        return w

    def refresh_library(self):
        q = self.lib_search.text().strip() if hasattr(self, "lib_search") else ""
        items = library_list(q)
        self.lib_table.setColumnCount(11)
        self.lib_table.setHorizontalHeaderLabels(["Title", "Uploader", "Resolution", "Size", "Like", "Dislike", "Watch Later", "Play", "Open Folder", "Delete", "Share"])
        self.lib_table.setRowCount(len(items))
        for i, it in enumerate(items):
            self.lib_table.setItem(i, 0, QTableWidgetItem(it.get("title", "")))
            self.lib_table.setItem(i, 1, QTableWidgetItem(it.get("uploader", "")))
            self.lib_table.setItem(i, 2, QTableWidgetItem(it.get("resolution", "")))
            fs = it.get("file_size") or 0
            self.lib_table.setItem(i, 3, QTableWidgetItem(f"{fs/1024/1024:.1f} MB"))
            self.lib_table.setItem(i, 4, QTableWidgetItem(it.get("filepath", "")))

            # Like
            likeb = QPushButton("Like" if it.get("is_liked") else "Like")
            likeb.setProperty("id", it.get("id"))
            likeb.clicked.connect(self._lib_toggle_like)
            self.lib_table.setCellWidget(i, 5, likeb)

            # Dislike
            dislikeb = QPushButton("Dislike" if it.get("is_disliked") else "Dislike")
            dislikeb.setProperty("id", it.get("id"))
            dislikeb.clicked.connect(self._lib_toggle_dislike)
            self.lib_table.setCellWidget(i, 6, dislikeb)

            # Watch Later
            wlb = QPushButton("Watch Later" if it.get("is_watch_later") else "Watch Later")
            wlb.setProperty("id", it.get("id"))
            wlb.clicked.connect(self._lib_toggle_watch_later)
            self.lib_table.setCellWidget(i, 7, wlb)

            playb = QPushButton("Play")
            playb.setProperty("path", it.get("filepath", ""))
            playb.clicked.connect(self._lib_play)
            self.lib_table.setCellWidget(i, 8, playb)

            openb = QPushButton("Open Folder")
            openb.setProperty("path", it.get("filepath", ""))
            openb.clicked.connect(self._lib_open_folder)
            self.lib_table.setCellWidget(i, 9, openb)

            shareb = QPushButton("Share")
            shareb.setProperty("url", it.get("source_url", ""))
            shareb.setToolTip("Copy URL to clipboard")
            shareb.clicked.connect(self._lib_share)
            self.lib_table.setCellWidget(i, 10, shareb)

    def _lib_play(self):
        btn = self.sender()
        path = btn.property("path")
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Playback", "File not found: " + str(path))
            return
        # Record watch history + increment play count
        c = sqlite3.connect(LIBRARY_DB)
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT id, title FROM library WHERE filepath = ?", (path,)).fetchone()
        if row:
            c.execute("INSERT INTO watch_history (library_id, title, filepath) VALUES (?,?,?)",
                      (row["id"], row["title"], path))
            c.execute("UPDATE library SET play_count = play_count + 1, last_played = CURRENT_TIMESTAMP WHERE id = ?",
                      (row["id"],))
            c.commit()
        c.close()
        self._player_load(path)

    def _lib_open_folder(self):
        btn = self.sender()
        path = btn.property("path")
        if path and os.path.exists(path):
            folder = os.path.dirname(path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _lib_del(self):
        btn = self.sender()
        item_id = btn.property("id")
        library_delete(item_id, delete_file=False)
        self.refresh_library()

    def _lib_toggle_bool(self, col):
        btn = self.sender()
        item_id = btn.property("id")
        c = sqlite3.connect(LIBRARY_DB)
        row = c.execute(f"SELECT {col} FROM library WHERE id = ?", (item_id,)).fetchone()
        val = 0 if (row and row[0]) else 1
        c.execute(f"UPDATE library SET {col} = ? WHERE id = ?", (val, item_id))
        c.commit()
        c.close()
        self.refresh_library()

    def _lib_toggle_like(self):
        self._lib_toggle_bool("is_liked")

    def _lib_toggle_dislike(self):
        self._lib_toggle_bool("is_disliked")

    def _lib_toggle_watch_later(self):
        self._lib_toggle_bool("is_watch_later")

    def _lib_share(self):
        btn = self.sender()
        url = btn.property("url")
        if url:
            QApplication.clipboard().setText(url)
            self.show_toast("Copied", "URL copied to clipboard")

    def _library_play_all(self):
        items = library_list("")
        paths = [it.get("filepath", "") for it in items if it.get("filepath") and os.path.exists(it.get("filepath", ""))]
        if not paths:
            QMessageBox.information(self, "Play All", "No playable files in library.")
            return
        self.playlist = paths
        self.playlist_index = 0
        self._player_load(paths[0])

    # ----- settings page -----
    def _page_settings(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(16)

        tabs = QTabWidget()
        tabs.addTab(self._settings_downloads(), "Downloads")
        tabs.addTab(self._settings_format(), "Format")
        tabs.addTab(self._settings_network(), "Network")
        tabs.addTab(self._settings_appearance(), "Appearance")
        lay.addWidget(tabs)

        saveb = QPushButton("Save config")
        saveb.setObjectName("primary")
        saveb.clicked.connect(self.save_settings)
        lay.addWidget(saveb)

        back = QPushButton("← Back")
        back.clicked.connect(lambda: self.set_view("browser"))
        lay.addWidget(back)
        return w

    def _settings_downloads(self):
        w = QWidget()
        lay = QFormLayout(w)
        self.s_dl_path = QLineEdit(self.config.get("downloads", {}).get("default_path", ""))
        self.s_dl_concurrent = QSpinBox()
        self.s_dl_concurrent.setRange(1, 10)
        self.s_dl_concurrent.setValue(self.config.get("downloads", {}).get("concurrent_downloads", 3))
        self.s_dl_retries = QSpinBox()
        self.s_dl_retries.setRange(0, 20)
        self.s_dl_retries.setValue(self.config.get("downloads", {}).get("max_retries", 5))
        self.s_dl_ratelimit = QSpinBox()
        self.s_dl_ratelimit.setRange(0, 10000)
        self.s_dl_ratelimit.setValue(self.config.get("downloads", {}).get("speed_limit_kbps", 0))
        self.s_dl_ratelimit.setSuffix(" KB/s")
        self.s_dl_ratelimit.setSpecialValueText("Unlimited")
        lay.addRow("Download path", self.s_dl_path)
        lay.addRow("Concurrent downloads", self.s_dl_concurrent)
        lay.addRow("Max retries", self.s_dl_retries)
        lay.addRow("Speed limit", self.s_dl_ratelimit)
        return w

    def _settings_format(self):
        w = QWidget()
        lay = QFormLayout(w)
        fc = self.config.get("format", {})
        self.s_fmt_res = QComboBox()
        self.s_fmt_res.addItems(["360", "480", "720", "1080", "1440", "2160", "4320"])
        self.s_fmt_res.setCurrentText(str(fc.get("resolution_cap", 1080)))
        self.s_fmt_container = QComboBox()
        self.s_fmt_container.addItems(["mp4", "mkv", "webm", "mov"])
        self.s_fmt_container.setCurrentText(fc.get("merge_output_format", "mp4"))
        self.s_fmt_audio = QCheckBox("Audio only")
        self.s_fmt_audio.setChecked(fc.get("audio_only", False))
        self.s_fmt_thumb = QCheckBox("Embed thumbnail")
        self.s_fmt_thumb.setChecked(fc.get("embed_thumbnail", True))
        self.s_fmt_meta = QCheckBox("Embed metadata")
        self.s_fmt_meta.setChecked(fc.get("embed_metadata", True))
        self.s_fmt_subs = QCheckBox("Embed subtitles")
        self.s_fmt_subs.setChecked(fc.get("embed_subs", False))
        lay.addRow("Resolution cap", self.s_fmt_res)
        lay.addRow("Container", self.s_fmt_container)
        lay.addRow("", self.s_fmt_audio)
        lay.addRow("", self.s_fmt_thumb)
        lay.addRow("", self.s_fmt_meta)
        lay.addRow("", self.s_fmt_subs)
        return w

    def _settings_network(self):
        w = QWidget()
        lay = QFormLayout(w)
        nc = self.config.get("network", {})
        ac = self.config.get("auth", {})
        self.s_net_proxy = QLineEdit(nc.get("proxy", ""))
        self.s_auth_cookies = QLineEdit(ac.get("cookies_from_browser", ""))
        self.s_auth_cookiefile = QLineEdit(ac.get("cookies_file", ""))
        lay.addRow("Proxy", self.s_net_proxy)
        lay.addRow("Cookies from browser", self.s_auth_cookies)
        lay.addRow("Cookies file", self.s_auth_cookiefile)
        return w

    def _settings_appearance(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        app_cfg = self.config.get("app", {})
        form = QFormLayout()
        self.s_theme = QComboBox()
        self.s_theme.addItems(["dark", "light", "system"])
        self.s_theme.setCurrentText(app_cfg.get("theme", "dark"))
        form.addRow("Theme", self.s_theme)
        lay.addLayout(form)

        upd = QHBoxLayout()
        self.btn_update = QPushButton("Update yt-dlp")
        self.btn_update.setObjectName("primary")
        self.btn_update.clicked.connect(self._update_yt_dlp)
        upd.addWidget(self.btn_update)
        self.btn_update.setEnabled(False)
        upd.addStretch()
        lay.addLayout(upd)

        self.update_status = QLabel("")
        self.update_status.setStyleSheet("color:#a6adc8; font-size:12px;")
        lay.addWidget(self.update_status)
        lay.addStretch()
        return w

    def save_settings(self):
        c = self.config
        c.setdefault("downloads", {})["default_path"] = self.s_dl_path.text()
        c["downloads"]["concurrent_downloads"] = self.s_dl_concurrent.value()
        c["downloads"]["max_retries"] = self.s_dl_retries.value()
        c["downloads"]["speed_limit_kbps"] = self.s_dl_ratelimit.value()
        c.setdefault("format", {})["resolution_cap"] = int(self.s_fmt_res.currentText())
        c["format"]["merge_output_format"] = self.s_fmt_container.currentText()
        c["format"]["audio_only"] = self.s_fmt_audio.isChecked()
        c["format"]["embed_thumbnail"] = self.s_fmt_thumb.isChecked()
        c["format"]["embed_metadata"] = self.s_fmt_meta.isChecked()
        c["format"]["embed_subs"] = self.s_fmt_subs.isChecked()
        c.setdefault("network", {})["proxy"] = self.s_net_proxy.text()
        c.setdefault("auth", {})["cookies_from_browser"] = self.s_auth_cookies.text()
        c["auth"]["cookies_file"] = self.s_auth_cookiefile.text()
        c.setdefault("app", {})["theme"] = self.s_theme.currentText()
        save_config(c)
        self.config = c
        self.refresh_home_cfg()
        self.apply_theme()
        QMessageBox.information(self, "Saved", "Configuration saved. Theme applied.")

    def _update_yt_dlp(self):
        self.btn_update.setEnabled(False)
        self.update_status.setText("Updating yt-dlp...")
        self.uw = YtDlpUpdateWorker()
        self.uw.finished.connect(self._update_done)
        self.uw.failed.connect(self._update_failed)
        self.uw.start()

    def _update_done(self, msg):
        self.btn_update.setEnabled(True)
        self.update_status.setText(msg)
        self.show_toast("yt-dlp updated", msg)

    def _update_failed(self, err):
        self.btn_update.setEnabled(True)
        self.update_status.setText(f"Update failed: {err}")
        QMessageBox.warning(self, "Update failed", err)

    # ----- video page -----
    def _page_video(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(16)

        top = QHBoxLayout()
        back = QPushButton("← Back")
        back.clicked.connect(lambda: self.set_view("search"))
        top.addWidget(back)
        top.addStretch()
        lay.addLayout(top)

        self.video_info_label = QLabel("")
        self.video_info_label.setStyleSheet("font-size:20px; font-weight:bold; color:#cdd6f4;")
        self.video_info_label.setWordWrap(True)
        lay.addWidget(self.video_info_label)

        self.video_sub_label = QLabel("")
        self.video_sub_label.setStyleSheet("color:#a6adc8; font-size:13px;")
        lay.addWidget(self.video_sub_label)

        row = QHBoxLayout()
        self.video_thumb = QLabel()
        self.video_thumb.setFixedSize(320, 180)
        self.video_thumb.setStyleSheet("background:#181825; border-radius:4px;")
        self.video_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.video_thumb)
        row.addStretch()
        lay.addLayout(row)

        lay.addWidget(QLabel("Available formats"))
        self.video_formats = QTableWidget()
        self.video_formats.setColumnCount(6)
        self.video_formats.setHorizontalHeaderLabels(["Resolution", "Codec", "Container", "Size", "Audio-only", ""])
        self.video_formats.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.video_formats.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.video_formats)

        # Per-video overrides
        ov = QGroupBox("Per-video overrides (leave blank to use global settings)")
        ov.setFlat(True)
        ovl = QFormLayout(ov)
        self.vid_res = QLineEdit()
        self.vid_res.setPlaceholderText("e.g. 1080")
        self.vid_container = QComboBox()
        self.vid_container.addItems(["", "mp4", "mkv", "webm", "mov"])
        self.vid_audio_only = QCheckBox("Audio only")
        self.vid_embed_thumb = QCheckBox("Embed thumbnail")
        self.vid_embed_meta = QCheckBox("Embed metadata")
        self.vid_embed_subs = QCheckBox("Embed subtitles")
        ovl.addRow("Resolution cap", self.vid_res)
        ovl.addRow("Container", self.vid_container)
        ovl.addRow("", self.vid_audio_only)
        ovl.addRow("", self.vid_embed_thumb)
        ovl.addRow("", self.vid_embed_meta)
        ovl.addRow("", self.vid_embed_subs)
        lay.addWidget(ov)

        lay.addWidget(QLabel("Subtitle languages"))
        self.video_subs = QComboBox()
        lay.addWidget(self.video_subs)

        lay.addWidget(QLabel("Chapters"))
        self.video_chapters = QScrollArea()
        self.video_chapters.setWidgetResizable(True)
        self.video_chapters.setFixedHeight(60)
        self.video_chapters.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        chap_widget = QWidget()
        self.video_chapters_layout = QHBoxLayout(chap_widget)
        self.video_chapters_layout.setContentsMargins(0, 0, 0, 0)
        self.video_chapters_layout.setSpacing(4)
        self.video_chapters_layout.addStretch()
        self.video_chapters.setWidget(chap_widget)
        lay.addWidget(self.video_chapters)

        addb = QPushButton("Add to download queue")
        addb.setObjectName("primary")
        addb.clicked.connect(self._video_add_to_queue)
        lay.addWidget(addb)

        lay.addStretch()
        return w

    def _video_info_done(self, info):
        self.video_info = info
        self.video_info_label.setText(info.get("title", ""))
        sub = f"{info.get('uploader','')}  •  {info.get('duration_string','—')}  •  {info.get('view_count',0):,} views"
        self.video_sub_label.setText(sub)
        if info.get("thumbnail"):
            from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
            from PyQt6.QtGui import QPixmap
            nam = QNetworkAccessManager()
            def _on_thumb(resp):
                pix = QPixmap()
                pix.loadFromData(resp.readAll())
                self.video_thumb.setPixmap(pix.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
            nam.finished.connect(_on_thumb)
            nam.get(QNetworkRequest(QUrl(info["thumbnail"])))

        # formats table
        self.video_formats.setRowCount(0)
        vf = info.get("video_formats", [])
        if not vf:
            vf = info.get("combined_formats", [])
        self.video_formats.setRowCount(len(vf))
        for i, f in enumerate(vf):
            h = f.get("height") or "?"
            fps = f.get("fps")
            fps_str = f"{fps}fps" if fps else ""
            vcodec = f.get("vcodec", "")
            ext = f.get("ext", "")
            size = f.get("filesize")
            size_str = f"{(size/1024/1024):.1f} MB" if size else "?"
            has_audio = f.get("has_audio", False)
            self.video_formats.setItem(i, 0, QTableWidgetItem(f"{h}p {fps_str}"))
            self.video_formats.setItem(i, 1, QTableWidgetItem(vcodec))
            self.video_formats.setItem(i, 2, QTableWidgetItem(ext))
            self.video_formats.setItem(i, 3, QTableWidgetItem(size_str))
            audio_cb = QCheckBox()
            audio_cb.setChecked(has_audio)
            audio_cb.setEnabled(False)
            self.video_formats.setCellWidget(i, 4, audio_cb)
            addb = QPushButton("Select")
            addb.setProperty("format", f)
            addb.clicked.connect(self._video_select_format)
            self.video_formats.setCellWidget(i, 5, addb)
        self.video_formats.resizeColumnsToContents()

        # subs
        self.video_subs.clear()
        for lang in info.get("sub_langs", []):
            self.video_subs.addItem(lang)

        # chapters
        self.video_chapters.clear()
        chapters = info.get("chapters") or []
        for ch in chapters[:20]:
            start = ch.get("start_time", 0)
            title = ch.get("title", "Chapter")
            btn = QPushButton(f"{self._fmt_chapter(start)}  {title}")
            btn.setFixedHeight(24)
            btn.setStyleSheet("QPushButton { text-align:left; padding:2px 6px; border:none; border-radius:3px; color:#89b4fa; font-size:11px; background:transparent; } QPushButton:hover { background:#313244; }")
            btn.setProperty("ms", int(start * 1000))
            btn.clicked.connect(self._chapter_seek)
            self.video_chapters_layout.addWidget(btn)

        # reset overrides
        self.vid_res.clear()
        self.vid_container.setCurrentIndex(0)
        self.vid_audio_only.setChecked(False)
        self.vid_embed_thumb.setChecked(False)
        self.vid_embed_meta.setChecked(False)
        self.vid_embed_subs.setChecked(False)
        self.video_selected_format = None

    def _video_select_format(self):
        btn = self.sender()
        f = btn.property("format")
        self.video_selected_format = f
        h = f.get("height") or "?"
        fps = f.get("fps")
        fps_str = f"{fps}fps" if fps else ""
        QMessageBox.information(self, "Format selected",
                                f"Selected {h}p {fps_str} {f.get('ext','')} — will apply as override on download.")

    def _build_job_overrides(self):
        """Build per-video config overrides from the video page controls."""
        overrides = {}
        fc = {}
        if self.vid_res.text().strip():
            fc["resolution_cap"] = int(self.vid_res.text().strip())
        if self.vid_container.currentText():
            fc["merge_output_format"] = self.vid_container.currentText()
        if self.vid_audio_only.isChecked():
            fc["audio_only"] = True
        if self.vid_embed_thumb.isChecked():
            fc["embed_thumbnail"] = True
        if self.vid_embed_meta.isChecked():
            fc["embed_metadata"] = True
        if self.vid_embed_subs.isChecked():
            fc["embed_subs"] = True
        if self.video_subs.currentText():
            fc["subs_lang"] = [self.video_subs.currentText()]
        if self.video_selected_format:
            h = self.video_selected_format.get("height")
            ext = self.video_selected_format.get("ext")
            if h:
                fc["preferred"] = f"bestvideo[height<={h}][ext={ext}]+bestaudio/best[height<={h}][ext={ext}]"
        if fc:
            overrides["format"] = fc
        return overrides

    def _video_add_to_queue(self):
        url = getattr(self, "video_url", "")
        if not url:
            QMessageBox.warning(self, "No video", "No video loaded.")
            return
        jid = str(uuid.uuid4())
        overrides = self._build_job_overrides()
        self.jobs[jid] = {
            "job_id": jid,
            "url": url,
            "status": "queued",
            "progress": 0,
            "speed": "",
            "eta": "",
        }
        worker = DownloadWorker(jid, url, self.config, config_overrides=overrides)
        worker.progress.connect(self._job_progress)
        worker.status.connect(self._job_status)
        worker.completed.connect(self._job_completed)
        worker.failed.connect(self._job_failed)
        self.workers[jid] = worker
        worker.start()
        self.refresh_jobs()
        self.refresh_library()
        self.set_view("queue")
        QMessageBox.information(self, "Added", f"Download added to queue:\n{url}")

    def _job_progress(self, jid, pct, speed, eta, downloaded, total):
        if jid in self.jobs:
            self.jobs[jid]["progress"] = pct
            self.jobs[jid]["speed"] = speed
            self.jobs[jid]["eta"] = eta
        self.refresh_jobs()

    def _job_status(self, jid, status):
        if jid in self.jobs:
            self.jobs[jid]["status"] = status
        self.refresh_jobs()

    def _job_completed(self, jid, filepath):
        if jid in self.jobs:
            self.jobs[jid]["status"] = "completed"
            self.jobs[jid]["progress"] = 100
        self.refresh_jobs()
        self.refresh_library()

    def _job_failed(self, jid, error):
        if jid in self.jobs:
            self.jobs[jid]["status"] = "failed"
        self.refresh_jobs()
        QMessageBox.warning(self, "Download failed", error)

    def _open_batch_dialog(self):
        dlg = BatchDownloadDialog(self)
        if dlg.exec():
            urls = dlg.selected_urls()
            for url in urls:
                self._add_url_to_queue(url)
            self.set_view("queue")


class BatchDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Playlist Downloader")
        self.resize(700, 500)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Paste a YouTube playlist or channel URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/playlist?list=...")
        lay.addWidget(self.url_input)

        btns = QHBoxLayout()
        fetch_btn = QPushButton("Fetch")
        fetch_btn.setObjectName("primary")
        fetch_btn.clicked.connect(self._fetch)
        btns.addWidget(fetch_btn)
        btns.addStretch()
        lay.addLayout(btns)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Select", "Title", "Uploader", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, 1)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#a6adc8; font-size:12px;")
        lay.addWidget(self.status)

        dlg_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        dlg_btns.accepted.connect(self.accept)
        dlg_btns.rejected.connect(self.reject)
        lay.addWidget(dlg_btns)

        self.entries = []

    def _fetch(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.status.setText("Fetching playlist...")
        self.table.setRowCount(0)
        self.bw = PlaylistFetchWorker(url)
        self.bw.finished.connect(self._fetch_done)
        self.bw.failed.connect(lambda e: self.status.setText(f"Error: {e}"))
        self.bw.start()

    def _fetch_done(self, entries):
        self.entries = entries
        self.status.setText(f"{len(entries)} videos found")
        self.table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            cb = QCheckBox()
            cb.setChecked(True)
            self.table.setCellWidget(i, 0, cb)
            self.table.setItem(i, 1, QTableWidgetItem(e.get("title", "")))
            self.table.setItem(i, 2, QTableWidgetItem(e.get("uploader", "")))
            self.table.setItem(i, 3, QTableWidgetItem(e.get("url", "")))
        self.table.resizeColumnsToContents()

    def selected_urls(self):
        return [e["url"] for e, cb in zip(self.entries, self._checkboxes()) if cb.isChecked()]

    def _checkboxes(self):
        return [self.table.cellWidget(i, 0) for i in range(self.table.rowCount())]


class PlaylistFetchWorker(QThread):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            entries = info.get("entries") or []
            result = []
            for e in entries:
                if not e:
                    continue
                result.append({
                    "title": e.get("title", ""),
                    "uploader": e.get("uploader", ""),
                    "url": e.get("url") or e.get("webpage_url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                })
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class MusicDownloadWorker(QThread):
    finished = pyqtSignal(str, dict)
    failed = pyqtSignal(str)

    def __init__(self, url, config):
        super().__init__()
        self.url = url
        self.config = config

    def run(self):
        try:
            dl_root = self.config.get("downloads", {}).get("default_path", "{user_home}/Downloads/YTDLP-WebUI")
            dl_root = dl_root.replace("{user_home}", os.path.expanduser("~"))
            music_root = os.path.join(dl_root, "Music")
            os.makedirs(music_root, exist_ok=True)

            opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(music_root, "%(title)s.%(ext)s"),
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"},
                    {"key": "FFmpegMetadata"},
                    {"key": "EmbedThumbnail"},
                ],
                "writethumbnail": True,
                "quiet": True,
                "no_warnings": True,
            }

            ffmpeg_loc = self.config.get("postprocessing", {}).get("ffmpeg_location") or (
                FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None
            )
            if ffmpeg_loc:
                opts["ffmpeg_location"] = ffmpeg_loc

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                filepath = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filepath)
                mp3_path = base + ".mp3"
                if not os.path.exists(mp3_path) and os.path.exists(filepath):
                    mp3_path = filepath

            metadata = {
                "title": info.get("title", ""),
                "uploader": info.get("uploader", ""),
                "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail", ""),
                "webpage_url": info.get("webpage_url", self.url),
            }
            self.finished.emit(mp3_path, metadata)
        except Exception as e:
            self.failed.emit(str(e))


class YtDlpUpdateWorker(QThread):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def run(self):
        import subprocess
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                capture_output=True, text=True, timeout=180,
            )
            if res.returncode == 0:
                self.finished.emit("yt-dlp updated successfully")
            else:
                self.failed.emit(res.stderr or "Update failed")
        except Exception as e:
            self.failed.emit(str(e))


class QFlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        for item in self._items:
            wid = item.widget()
            space_x = self.spacing()
            space_y = self.spacing()
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()


class PlaylistImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import YouTube Playlist to Music")
        self.resize(600, 400)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Paste a YouTube playlist URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/playlist?list=...")
        lay.addWidget(self.url_input)

        fetch_btn = QPushButton("Fetch")
        fetch_btn.setObjectName("primary")
        fetch_btn.clicked.connect(self._fetch)
        lay.addWidget(fetch_btn)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Select", "Title", "Artist", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, 1)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#a6adc8; font-size:12px;")
        lay.addWidget(self.status)

        dlg_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        dlg_btns.accepted.connect(self.accept)
        dlg_btns.rejected.connect(self.reject)
        lay.addWidget(dlg_btns)

        self.entries = []

    def _fetch(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.status.setText("Fetching playlist...")
        self.table.setRowCount(0)
        self.pw = PlaylistFetchWorker(url)
        self.pw.finished.connect(self._fetch_done)
        self.pw.failed.connect(lambda e: self.status.setText(f"Error: {e}"))
        self.pw.start()

    def _fetch_done(self, entries):
        self.entries = entries
        self.status.setText(f"{len(entries)} videos found")
        self.table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            cb = QCheckBox()
            cb.setChecked(True)
            self.table.setCellWidget(i, 0, cb)
            self.table.setItem(i, 1, QTableWidgetItem(e.get("title", "")))
            self.table.setItem(i, 2, QTableWidgetItem(e.get("uploader", "")))
            self.table.setItem(i, 3, QTableWidgetItem(e.get("url", "")))
        self.table.resizeColumnsToContents()

    def selected_urls(self):
        return [e["url"] for e, cb in zip(self.entries, self._checkboxes()) if cb.isChecked()]

    def _checkboxes(self):
        return [self.table.cellWidget(i, 0) for i in range(self.table.rowCount())]


class MiniPlayer(QWidget):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("YT-DLP Mini Player")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowCloseButtonHint)
        self.resize(320, 100)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.title_lbl = QLabel("No media")
        self.title_lbl.setStyleSheet("color:#cdd6f4; font-weight:bold;")
        lay.addWidget(self.title_lbl)

        btns = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setFixedWidth(45)
        self.prev_btn.clicked.connect(main._playlist_prev)
        btns.addWidget(self.prev_btn)

        self.play_btn = QPushButton("Play")
        self.play_btn.setFixedWidth(70)
        self.play_btn.clicked.connect(main._player_toggle)
        btns.addWidget(self.play_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setFixedWidth(45)
        self.next_btn.clicked.connect(main._playlist_next)
        btns.addWidget(self.next_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedWidth(70)
        self.stop_btn.clicked.connect(main._player_stop)
        btns.addWidget(self.stop_btn)
        btns.addStretch()
        lay.addLayout(btns)

        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setStyleSheet("color:#a6adc8; font-size:11px;")
        lay.addWidget(self.time_lbl)

        # Sync with main player state
        main.player.playbackStateChanged.connect(self._on_state_changed)
        main.player.positionChanged.connect(self._on_position_changed)
        main.player.durationChanged.connect(self._on_duration_changed)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("Pause")
        else:
            self.play_btn.setText("Play")

    def _on_position_changed(self, pos):
        self.time_lbl.setText(f"{self._fmt(pos)} / {self._fmt(self.main.player.duration())}")

    def _on_duration_changed(self, dur):
        self.time_lbl.setText(f"{self._fmt(self.main.player.position())} / {self._fmt(dur)}")

    @staticmethod
    def _fmt(ms):
        if not ms:
            return "0:00"
        s = int(ms) // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class LyricsPanel(QWidget):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Lyrics")
        self.resize(500, 400)
        lay = QVBoxLayout(self)
        self.title_lbl = QLabel("No lyrics available")
        self.title_lbl.setStyleSheet("color:#cdd6f4; font-weight:bold; font-size:16px;")
        self.title_lbl.setWordWrap(True)
        lay.addWidget(self.title_lbl)
        self.lyrics_text = QTextEdit()
        self.lyrics_text.setReadOnly(True)
        self.lyrics_text.setStyleSheet("background:#181825; color:#cdd6f4; border:none; font-size:14px; line-height:1.6;")
        lay.addWidget(self.lyrics_text)
        self.current_line_lbl = QLabel("")
        self.current_line_lbl.setStyleSheet("color:#89b4fa; font-weight:bold;")
        lay.addWidget(self.current_line_lbl)
        self._refresh()

    def _refresh(self):
        if not self.main.player or not self.main.player.source():
            self.title_lbl.setText("No track playing")
            self.lyrics_text.setPlainText("")
            return
        filepath = self.main.player.source().toLocalFile()
        c = sqlite3.connect(LIBRARY_DB)
        row = c.execute("SELECT title FROM library WHERE filepath = ?", (filepath,)).fetchone()
        c.close()
        title = row[0] if row else "Unknown"
        self.title_lbl.setText(title)
        self.lyrics_text.setPlainText("(Lyrics not embedded in file — paste lyrics below if desired)")

    def update_time(self, pos_ms):
        pass


class AlbumArtViewer(QDialog):
    def __init__(self, cover_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Album Art")
        self.resize(500, 500)
        lay = QVBoxLayout(self)
        self.img = QLabel()
        self.img.setFixedSize(400, 400)
        self.img.setStyleSheet("background:#181825; border-radius:12px;")
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.img, alignment=Qt.AlignmentFlag.AlignCenter)
        if cover_url:
            from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
            from PyQt6.QtGui import QPixmap
            nam = QNetworkAccessManager()
            def _on_thumb(resp):
                pix = QPixmap()
                pix.loadFromData(resp.readAll())
                self.img.setPixmap(pix.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
            nam.finished.connect(_on_thumb)
            nam.get(QNetworkRequest(QUrl(cover_url)))


class RecentlyPlayedDialog(QDialog):
    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recently Played")
        self.resize(600, 400)
        lay = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title", "Artist", "Played At", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["title"] or ""))
            self.table.setItem(i, 1, QTableWidgetItem(""))
            self.table.setItem(i, 2, QTableWidgetItem(r["played_at"] or ""))
            playb = QPushButton("Play")
            playb.setProperty("path", r["filepath"])
            playb.clicked.connect(self._play)
            self.table.setCellWidget(i, 3, playb)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _play(self):
        btn = self.sender()
        path = btn.property("path")
        if path and os.path.exists(path):
            self.main._player_load(path)
            self.accept()


class EQBandsDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Equalizer Bands")
        self.resize(400, 300)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Adjust frequency bands (placeholder — real EQ needs DSP library)"))
        self.bass = QSlider(Qt.Orientation.Horizontal)
        self.bass.setRange(-12, 12)
        self.bass.setValue(0)
        self.bass.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.bass.setTickInterval(3)
        self.mid = QSlider(Qt.Orientation.Horizontal)
        self.mid.setRange(-12, 12)
        self.mid.setValue(0)
        self.treble = QSlider(Qt.Orientation.Horizontal)
        self.treble.setRange(-12, 12)
        self.treble.setValue(0)
        self.treble.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.treble.setTickInterval(3)
        form = QFormLayout()
        form.addRow("Bass (60Hz)", self.bass)
        form.addRow("Mid (1kHz)", self.mid)
        form.addRow("Treble (10kHz)", self.treble)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._apply)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _apply(self):
        self.main.show_toast("EQ Bands", f"Bass:{self.bass.value()} Mid:{self.mid.value()} Treble:{self.treble.value()}")
        self.accept()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = YTDLPApp()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# --------------------------------------------------------------------------- #
# Info Extractor Worker
# --------------------------------------------------------------------------- #
class InfoWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            self.finished.emit(self._sanitize(info))
        except Exception as e:
            self.failed.emit(str(e))

    def _sanitize(self, info):
        if not info:
            return {}
        dur = info.get("duration")
        dur_str = None
        if dur:
            h = dur // 3600
            m = (dur % 3600) // 60
            s = dur % 60
            dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        formats = info.get("formats") or []
        vf, af, cf = [], [], []
        seen_h = {}
        for f in formats:
            vcodec = f.get("vcodec") or "none"
            acodec = f.get("acodec") or "none"
            entry = {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "height": f.get("height"),
                "width": f.get("width"),
                "fps": f.get("fps"),
                "vcodec": vcodec,
                "acodec": acodec,
                "tbr": f.get("tbr"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "has_video": vcodec != "none",
                "has_audio": acodec != "none",
            }
            if vcodec != "none" and acodec != "none":
                cf.append(entry)
            elif vcodec != "none":
                vf.append(entry)
            elif acodec != "none":
                af.append(entry)
        for f in vf:
            h = f["height"]
            if h and (h not in seen_h or (f["tbr"] or 0) > (seen_h[h]["tbr"] or 0)):
                seen_h[h] = f
        vf = sorted(seen_h.values(), key=lambda x: x["height"] or 0)
        subs = info.get("subtitles") or {}
        auto = info.get("automatic_captions") or {}
        sub_langs = sorted(set(list(subs.keys()) + list(auto.keys())))
        thumb = None
        thumbnails = info.get("thumbnails") or []
        if thumbnails:
            thumb = thumbnails[-1].get("url")
        elif info.get("thumbnail"):
            thumb = info.get("thumbnail")
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "uploader": info.get("uploader"),
            "uploader_id": info.get("uploader_id"),
            "channel_url": info.get("channel_url"),
            "duration": dur,
            "duration_string": dur_str,
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "upload_date": info.get("upload_date"),
            "description": info.get("description"),
            "webpage_url": info.get("webpage_url") or self.url,
            "thumbnail": thumb,
            "is_live": bool(info.get("is_live")),
            "video_formats": vf,
            "audio_formats": af,
            "combined_formats": cf,
            "sub_langs": sub_langs,
        }


# --------------------------------------------------------------------------- #
# Search Worker
# --------------------------------------------------------------------------- #
class SearchWorker(QThread):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, query, max_results=20):
        super().__init__()
        self.query = query
        self.max_results = max_results

    def run(self):
        try:
            opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "playlistend": self.max_results}
            url = f"ytsearch{self.max_results}:{self.query}"
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            entries = info.get("entries") or []
            results = []
            for e in entries:
                if not e:
                    continue
                dur = e.get("duration")
                dur_str = None
                if dur:
                    h = dur // 3600
                    m = (dur % 3600) // 60
                    s = dur % 60
                    dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                results.append(
                    {
                        "id": e.get("id"),
                        "title": e.get("title"),
                        "uploader": e.get("uploader"),
                        "duration_string": dur_str,
                        "view_count": e.get("view_count"),
                        "thumbnail": (e.get("thumbnails") or [{}])[-1].get("url") if e.get("thumbnails") else None,
                        "webpage_url": e.get("webpage_url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                    }
                )
            self.finished.emit(results)
        except Exception as e:
            self.failed.emit(str(e))
