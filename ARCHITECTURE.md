# YT-DLP WebUI — Architecture

## Overview

YT-DLP WebUI is a single-file Python desktop application (`main.py`, ~3,600 lines) that wraps the `yt-dlp` library in a native PyQt6 GUI. It provides a YouTube browser, download queue, media player, music library, and multi-output audio support — all without Electron, React, or Node.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YT-DLP WebUI Window                      │
│                                                             │
│  ┌─────────────┐  ┌─────────────────────────────────────┐  │
│  │ Nav Rail    │  │ Content Stack (QStackedWidget)      │  │
│  │             │  │                                       │  │
│  │ • Browser   │  │ • Browser View (QWebEngineView)     │  │
│  │ • Search    │  │ • Search View (Card Grid)           │  │
│  │ • Trending  │  │ • Music View (Split: Sidebar+Grid)  │  │
│  │ • Music     │  │ • Charts View (Ranked List)         │  │
│  │ • Charts    │  │ • Video View (Hero + Format Chips)  │  │
│  │ • Video     │  │ • Queue View (Status Cards)         │  │
│  │ • Queue     │  │ • Library View (Card Grid)          │  │
│  │ • Library   │  │ • Settings View (Tabbed)            │  │
│  │ • Settings  │  │                                       │  │
│  └─────────────┘  └─────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Player Bar (always visible, collapsed/expanded)       │  │
│  │  [Art] [Prev] [Play] [Next] [Stop] [Skip] [Speed]     │  │
│  │  [Autoplay] [Shuffle] [Repeat] [Sleep] [EQ] [Mini]    │  │
│  │  [Lyrics] [Art] [Crossfade] [Gapless] [Recent]        │  │
│  │  [Progress] [Volume] [Title]                          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Reference

### `main.py` — Application Core (~3,600 lines)

The single-file entry point containing:

| Class | Purpose |
|-------|---------|
| `YTDLPApp(QMainWindow)` | Main window, owns all views, workers, and state |
| `DownloadWorker(QThread)` | yt-dlp download engine with progress hooks |
| `MusicDownloadWorker(QThread)` | MP3-optimized downloads |
| `PlaylistFetchWorker(QThread)` | Extract playlist entries without downloading |
| `InfoWorker(QThread)` | Video metadata extraction |
| `SearchWorker(QThread)` | YouTube search |
| `YtDlpUpdateWorker(QThread)` | Background yt-dlp updates |
| `BatchDownloadDialog(QDialog)` | Batch playlist downloader dialog |
| `PlaylistImportDialog(QDialog)` | Import playlist from URL dialog |
| `MiniPlayer(QWidget)` | Floating always-on-top mini player |
| `LyricsPanel(QWidget)` | Lyrics display panel |
| `AlbumArtViewer(QDialog)` | Full-size album art viewer |
| `RecentlyPlayedDialog(QDialog)` | Playback history dialog |
| `EQBandsDialog(QDialog)` | Equalizer bands dialog |

**Key instance attributes:**
- `self.config` — User configuration dict
- `self.workers` — Active download worker threads (`{job_id: DownloadWorker}`)
- `self.jobs` — Job state (`{job_id: {status, progress, speed, eta, ...}}`)
- `self.player` — `MultiOutputManager` instance
- `self.playlist` — Current playback queue (`[filepath, ...]`)
- `self.playlist_index` — Current index in playlist
- `self.theme` — `ThemeManager` instance

---

### `ui/theme.py` — Theme Engine

**`ThemeManager(QApplication)`**

Manages application-wide theming with instant QSS generation.

| Method | Description |
|--------|-------------|
| `set_theme(theme)` | Set theme: `"dark"`, `"light"`, `"system"`, or `"night"` |
| `current_theme()` | Return current theme name |
| `palette()` | Return color palette dict |
| `color(key)` | Return single color value |

**Palettes:**
- `DARK_PALETTE` — `#0f0f12` bg, `#1a1a1e` surface, `#3b82f6` accent
- `LIGHT_PALETTE` — `#fafafa` bg, `#ffffff` surface, `#3b82f6` accent

**Night mode:** Automatically switches to dark between 8pm–8am local time.

---

### `ui/nav_rail.py` — Navigation Rail

**`NavRail(QFrame)`**

Collapsible vertical navigation sidebar.

| Method | Description |
|--------|-------------|
| `add_item(key, label, icon_text, on_click)` | Add a nav item |
| `set_active(key)` | Mark item as active |
| `toggle()` | Toggle collapsed/expanded |
| `is_expanded()` | Return expanded state |

**Modes:**
- **Expanded:** Full labels visible (~220px wide)
- **Collapsed:** Icons only (~60px wide)

---

### `ui/player_bar.py` — Player Bar

**`PlayerBar(QFrame)`**

Always-visible media player bar docked at the bottom.

| State | Height | Contents |
|-------|--------|----------|
| Hidden | 0 | No media loaded |
| Collapsed | 64px | Compact controls |
| Expanded | 110px | Full controls (speed, volume, progress) |

**Controls:** Play/Pause, Previous, Next, Stop, Skip ±10s, Speed, Volume, Autoplay, Shuffle, Repeat, Sleep Timer, EQ, Mini Player, Lyrics, Art, Crossfade, Gapless, Recent.

**Signals:** None — communicates via direct method calls to `YTDLPApp`.

---

### `ui/audio_devices.py` — Multi-Output Audio

**`MultiOutputManager(QObject)`**

Manages simultaneous playback to multiple audio output devices.

| Signal | Emitted When |
|--------|-------------|
| `playbackStateChanged(state)` | Playback state changes |
| `positionChanged(ms)` | Playback position changes |
| `durationChanged(ms)` | Duration changes |
| `mediaStatusChanged(status)` | Media status changes |

| Method | Description |
|--------|-------------|
| `available_output_devices()` | List all audio output devices |
| `default_output_device()` | Return system default device |
| `set_outputs(device_ids)` | Set active output devices |
| `set_source(filepath)` | Load media into all outputs |
| `play() / pause() / stop()` | Playback control |
| `set_position(ms)` | Seek all outputs |
| `set_volume(vol)` | Set volume (0.0–1.0) for all outputs |
| `set_output_volume(device_id, vol)` | Set volume for specific device |
| `set_position(ms)` | Seek all outputs |

**Architecture:** Each output device gets its own `QMediaPlayer` + `QAudioOutput` pair. All players are kept in sync — same source, same position, same playback state.

---

### `ui/widgets.py` — Reusable Widgets

| Class | Base | Description |
|-------|------|-------------|
| `PrimaryButton(QPushButton)` | QPushButton | Accent-colored primary action |
| `GhostButton(QPushButton)` | QPushButton | Transparent secondary action |
| `IconButton(QPushButton)` | QPushButton | Square icon-only button |
| `SearchBar(QLineEdit)` | QLineEdit | Rounded search input |
| `MediaCard(QFrame)` | QFrame | Card with thumbnail, title, subtitle, hover actions |
| `ThemedSlider(QSlider)` | QSlider | Theme-aware slider |
| `ThemedCheckBox(QCheckBox)` | QCheckBox | Theme-aware checkbox |

---

### `ui/nav_rail.py` — Navigation

**`NavRail(QFrame)`**

Collapsible navigation sidebar with icon-only collapsed mode.

**`NavItem`** — Data class with `key`, `label`, `icon_text`, `on_click`.

---

### `ui/player_bar.py` — Player Bar

**`PlayerBar(QFrame)`**

Bottom docked player bar. Supports collapsed (64px) and expanded (110px) heights. Contains artwork, title, playback controls, progress bar, volume, and utility buttons (mini player, lyrics, album art, crossfade, gapless, recent).

---

## Data Flow

### Download Flow
1. User clicks "Download" on a video
2. `DownloadWorker(QThread)` is created with `yt-dlp` options
3. Worker calls `yt-dlp.YoutubeDL.extract_info(url, download=True)`
4. Progress hook emits `progress` signal with pct/speed/eta
5. `YTDLPApp` updates queue table row
6. On completion, `library_add()` inserts row into SQLite
7. Job moves to "completed" state

### Playback Flow
1. User clicks "Play" on a library item
2. `MultiOutputManager.set_source(filepath)` loads file into all active outputs
3. `MultiOutputManager.play()` starts playback
4. `QMediaPlayer.positionChanged` updates progress bar every second
5. `mediaStatusChanged` with `EndOfMedia` triggers `_playlist_next()`
6. Position saved to `playback_positions` table on stop

### Search Flow
1. User types query, presses Enter
2. `SearchWorker(QThread)` calls `yt-dlp` with `ytsearchN:query`
3. Results returned as list of dicts
4. Rendered as `MediaCard` grid in search view
5. Clicking card opens `VideoDetail` view via `InfoWorker`

---

## Database Schema (`data/library.db`)

### `library` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `job_id` | TEXT | Download job ID |
| `source_url` | TEXT | Original YouTube URL |
| `title` | TEXT | Video title |
| `uploader` | TEXT | Channel/uploader name |
| `duration` | INTEGER | Duration in seconds |
| `filepath` | TEXT UNIQUE | Local file path |
| `file_size` | INTEGER | File size in bytes |
| `resolution` | TEXT | Video resolution (e.g. "1080p") |
| `container` | TEXT | File container (mp4, mkv, etc.) |
| `downloaded_at` | TEXT | Download timestamp |
| `is_favorite` | INTEGER | 0/1 boolean |
| `is_watch_later` | INTEGER | 0/1 boolean |
| `is_liked` | INTEGER | 0/1 boolean |
| `is_disliked` | INTEGER | 0/1 boolean |
| `play_count` | INTEGER | Number of plays |
| `last_played` | TEXT | Last played timestamp |
| `is_music` | INTEGER | 0/1 boolean |
| `music_artist` | TEXT | Artist name (music only) |
| `music_album` | TEXT | Album name (music only) |
| `music_track` | TEXT | Track name (music only) |
| `music_genre` | TEXT | Genre (music only) |
| `music_year` | TEXT | Release year (music only) |
| `music_cover` | TEXT | Cover art URL (music only) |
| `music_duration` | INTEGER | Duration (music only) |

### `watch_history` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `library_id` | INTEGER | FK to library.id |
| `title` | TEXT | Video title |
| `filepath` | TEXT | File path |
| `played_at` | TEXT | Play timestamp |

### `playback_positions` table

| Column | Type | Description |
|--------|------|-------------|
| `filepath` | TEXT PK | File path |
| `position` | INTEGER | Playback position in ms |
| `updated_at` | TEXT | Last update timestamp |

### `music_playlists` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT | Playlist name |
| `description` | TEXT | Playlist description |
| `created_at` | TEXT | Creation timestamp |
| `cover_path` | TEXT | Cover art path |

### `music_playlist_tracks` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `playlist_id` | INTEGER | FK to music_playlists.id |
| `track_id` | INTEGER | FK to library.id |
| `position` | INTEGER | Track position in playlist |
| `added_at` | TEXT | Added timestamp |

---

## Key Design Decisions

### Single-File Architecture
All application logic lives in `main.py` (~3,600 lines). This simplifies distribution — no package management, no import issues, just run `python main.py`.

### In-Process yt-dlp
yt-dlp is used as a Python library (`import yt_dlp`), not shelling out to the CLI. This gives direct access to progress hooks, post-processors, and format selection without parsing CLI output.

### In-Process Download Workers
Downloads run in `QThread` subclasses so the UI never blocks. Each job gets its own worker thread with its own `yt-dlp` instance.

### Multi-Output Audio
Each output device gets its own `QMediaPlayer` + `QAudioOutput` pair. All players share the same source file and are kept in sync — same play/pause state, same position. Volume can be set per-device.

### Theme Engine
QSS is generated dynamically from color palettes. Theme changes apply instantly without restart via `QApplication.setStyleSheet()`.

---

## Development

### Running
```bash
python main.py
```

### Adding a New View
1. Create `_page_X(self)` method returning a `QWidget`
2. Add nav item in `_build_ui()`
3. Add page to `self.stack`
4. Add navigation entry in `set_view()` index map

### Adding a Download Worker
Subclass `QThread`, implement `run()` with `yt-dlp.YoutubeDL`, emit progress/status signals.

### Adding a Settings Tab
1. Create `_settings_X(self)` method returning `QWidget`
2. Add tab tab in `_page_settings()`
3. Add save logic in `save_settings()`

---

## License

MIT — use it, break it, remix it.

## Disclaimer

For personal use with content you own or have rights to. Respect YouTube's Terms of Service and applicable copyright law. The author is not responsible for misuse.
