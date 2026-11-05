# YT-DLP Integrated YouTube Browser — Detailed Project Plan

**Project:** `yt-dlp-webui`  
**Goal:** A desktop (Electron/Python hybrid) YouTube browsing application with a fully integrated `yt-dlp` downloader and granular custom configuration (download location, resolution, format, subtitles, cookies, proxies, queue management, and more).  
**Status:** Greenfield — planning phase

---

## 1. Product Vision

A single-window application that lets a user:

- Browse/search YouTube (channels, playlists, search results, trending) without opening a browser
- Inspect video metadata (title, uploader, duration, view count, available formats, subtitles)
- Configure per-download or global settings: download folder, resolution cap, container format, audio-only, embed thumbnails/metadata, subtitles language, cookies/auth, proxy, speed limit, concurrent downloads
- Queue, pause, resume, retry, and cancel downloads with real-time progress
- Play downloaded media locally
- Maintain a download history/library with re-download and delete

---

## 2. Architecture Overview

```
+-----------------------------------------------------------------------+
|                         UI LAYER (PyQt6)                              |
|  [Browser] [Search] [Video Detail] [Queue] [Library] [Settings]       |
+-----------------------------------------------------------------------+
|                    APPLICATION LAYER (Python + yt-dlp)                |
|  - YouTube extractor wrapper (yt-dlp extractor, no API key needed)    |
|  - Download engine (yt-dlp Python API)                                |
|  - Configuration manager (JSON/YAML + env overrides)                  |
|  - Job queue manager (priority, concurrency, retry, state machine)    |
|  - Metadata indexer (SQLite library of downloaded media)              |
+-----------------------------------------------------------------------+
|                     yt-dlp / ffmpeg (system dependencies)             |
+-----------------------------------------------------------------------+
|                     Storage: downloads dir, config, sqlite DB         |
+-----------------------------------------------------------------------+
```

**Why this split:**  
- `yt-dlp` is a Python library; keeping it in-process via its Python API gives us direct access to progress hooks, format selection, postprocessors, and error handling without shelling out.  
- Electron gives a modern, themable UI with full control over downloads, notifications, and system tray.  
- SQLite keeps a local library index (downloaded files, metadata, source URL, download date, file hash).

---

## 3. Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| UI | PyQt6 (Qt Widgets + QWebEngineView Chromium) | Pure Python, native desktop UI, no Node/Electron bloat. Single-file `main.py`. |
| Backend | Python 3.10+ | `yt-dlp` is Python-native; rich ecosystem. |
| yt-dlp integration | `yt_dlp` Python library (in-process) | Direct API access, progress hooks, postprocessors |
| FFmpeg | System binary (bundled or user-installed) | Required for merge, convert, thumbnail embed, metadata, audio extraction |
| Config | JSON + optional env vars / CLI flags | Simple, human-editable, portable |
| Local DB | SQLite | Zero-config, file-based, stores library index + job history |
| IPC | Direct in-process Python calls (`main.py` ↔ `backend/` modules) | No Electron IPC needed; UI and backend share the same process. |
| Packaging | PyInstaller (`*.spec`) | Single executable for Windows/macOS/Linux. |

---

## 4. Project Structure

```
yt-dlp-webui/
├── main.py                 # PyQt6 application entry point (~3,600 lines, single file)
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Python packaging metadata
├── README.md
├── PROJECT_PLAN.md         # Original project plan
├── UI_OVERHAUL_PLAN.md     # UI redesign documentation
├── config/
│   └── config.default.json # Default application settings
├── backend/                # Pure Python service modules (config, extractor, downloader, library, job_queue)
│   ├── app.py              # JSON-RPC backend entry point (standalone)
│   ├── config.py
│   ├── extractor.py
│   ├── downloader.py
│   ├── library.py
│   └── job_queue.py
├── ui/                     # PyQt6 UI component package
│   ├── __init__.py
│   ├── theme.py            # Dark/light/system/night theme engine
│   ├── nav_rail.py         # Collapsible navigation sidebar
│   ├── player_bar.py       # Always-visible media player bar
│   ├── audio_devices.py    # Multi-output audio manager
│   └── widgets.py          # Reusable widgets (MediaCard, buttons, etc.)
├── crosspost/              # Social cross-posting (reddit, twitter, devto)
├── ffmpeg/                 # FFmpeg binaries (Windows)
│   └── bin/
├── data/                   # Created at runtime (config.json, library.db)
├── build-linux.sh          # PyInstaller + AppImage build
├── build-windows.ps1       # PyInstaller + NSIS build
├── yt-dlp-webui.spec       # PyInstaller spec
├── YT-DLP WebUI.spec       # PyInstaller spec (collected)
├── file_version_info.txt
└── dist/                   # Build output (runtime)
```

---

## 5. Core Modules (Detailed Design)

### 5.1 Configuration System

**Scope:** Everything the user can tune — global defaults + per-download overrides.

**`config.default.json` shape:**

```json
{
  "app": {
    "theme": "dark",
    "language": "en",
    "check_updates_on_start": true,
    "minimize_to_tray": true
  },
  "downloads": {
    "default_path": "{user_home}/Downloads/YTDLP-WebUI",
    "path_templates": {
      "video": "{download_root}/{uploader}/{title}.{ext}",
      "audio": "{download_root}/Music/{uploader}/{title}.{ext}",
      "playlist": "{download_root}/Playlists/{playlist_title}/{playlist_index} - {title}.{ext}"
    },
    "concurrent_downloads": 3,
    "max_retries": 5,
    "retry_sleep": 10,
    "fragment_retries": 10,
    "speed_limit": null,
    "throttled_rate": null
  },
  "format": {
    "preferred": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "resolution_cap": 1080,
    "container": "mp4",
    "audio_only": false,
    "audio_format": "mp3",
    "audio_quality": "0",
    "embed_subs": false,
    "subs_lang": ["en"],
    "embed_thumbnail": true,
    "embed_metadata": true,
    "write_thumbnail": false,
    "write_info_json": false,
    "write_description": false,
    "write_comments": false,
    "write_subs": false,
    "write_auto_subs": false,
    "merge_output_format": "mp4",
    "noplaylist": true,
    "ignore_errors": false,
    "no_warnings": false,
    "geo_bypass": true,
    "geo_bypass_country": null
  },
  "auth": {
    "cookies_from_browser": null,      // chrome|edge|firefox|brave|opera|safari|...
    "cookies_file": null,
    "username": null,
    "password": null,
    "netrc": null,
    "twofactor": null
  },
  "network": {
    "proxy": null,
    "socket_timeout": 30,
    "source_address": null,
    "force_ipv4": false,
    "force_ipv6": false,
    "user_agent": null,
    "referer": null
  },
  "postprocessing": {
    "ffmpeg_location": null,
    "prefer_ffmpeg": true,
    "keep_video": false,
    "fixup": "detect_or_warn",
    "postprocessor_args": {}
  },
  "extractor": {
    "age_limit": null,
    "default_search": "auto",
    "extractor_retries": 3,
    "force_generic_extractor": false
  }
}
```

**Behavior:**
- Global config saved to `data/config.json`.
- Per-download overrides merged on top of global (deep merge).
- Environment variables and CLI flags override everything: `YTDLP_WEBUI_DOWNLOAD_PATH`, `--resolution`, `--audio-only`, etc.
- Config schema validated on load; invalid values fall back to defaults with a warning toast in UI.

### 5.2 YouTube Browser / Extractor Layer

Uses `yt_dlp.YoutubeDL` with `extract_flat=True` for listing, and full extraction for detail.

**Supported browse surfaces:**
1. **Search** — query string → video/channel/playlist results (yt-dlp `ytsearch`, `ytsearchplaylist`)
2. **URL paste** — any YouTube URL (video, channel, playlist, shorts, live)
3. **Trending / popular** — optional (requires scraping or Invidious/Piped fallback)
4. **Channel / Playlist** — list videos with pagination info

**Extracted metadata per item:**
- `id`, `title`, `uploader`, `uploader_id`, `channel_id`, `channel_url`
- `duration`, `duration_string`, `view_count`, `like_count`, `upload_date`, `release_timestamp`
- `thumbnail`, `thumbnails` (all sizes)
- `description`, `categories`, `tags`
- `webpage_url`, `extractor`, `extractor_key`
- `available_formats` → grouped by: video-only, audio-only, video+audio, with height/fps/codec/vcodec/acodec/filesize/tbr
- `subtitles` (lang → list of formats), `automatic_captions`
- `is_live`, `was_live`, `play_in_browser`, `age_limit`

### 5.3 Download Engine (yt-dlp wrapper)

**Class `DownloadJob`:**
- Fields: `job_id`, `url`, `title`, `status` (queued/running/paused/completed/failed/cancelled), `progress_pct`, `speed`, `eta`, `downloaded_bytes`, `total_bytes`, `filepath`, `error`, `config` (merged), `created_at`, `completed_at`, `attempts`

**Progress hook integration:**
```python
def progress_hook(d):
    # d['status']: downloading/finished/error
    # emit progress via IPC to renderer
```

**Concurrency:** Fixed worker pool (default 3) pulling from a priority queue. Pause = stop accepting new jobs + cancel active yt-dlp process (send SIGTERM, fallback SIGKILL). Resume = re-queue paused/incomplete jobs (yt-dlp supports partial download resume via `--continue`).

**Post-processing pipeline (via yt-dlp postprocessors + ffmpeg):**
- FFmpegVideoConvertor (container)
- FFmpegExtractAudio (audio-only)
- FFmpegEmbedSubtitle / FFmpegMetadata / EmbedThumbnail
- FixupM3u8, FixupStretched, FixupDuration, FixupTimestamp, LimitDuration, SplitChapters, ModifyChapters, RecodeVideo, MoveFiles, FFmpegMerger

### 5.4 Job Queue & Persistence

- In-memory queue for active session
- SQLite table `download_jobs` persists job state across restarts (on boot, rehydrate `running`/`queued` jobs back into queue)
- Priority: user-set (high/normal/low), then FIFO
- `max_concurrent` enforced by semaphore

### 5.5 Media Library

SQLite table `library`:
- `id`, `job_id`, `source_url`, `title`, `uploader`, `duration`, `filepath`, `file_size`, `file_hash`, `resolution`, `container`, `downloaded_at`, `last_played`, `play_count`, `is_favorite`

Features:
- Rescan downloads folder (import existing files)
- Open file location, play in external player, delete file (+ DB entry), re-download
- Search/filter library

### 5.6 In-App Player (Optional, v2)

- Use `<video>` tag in Electron renderer pointing to local file path (file:// protocol)
- Basic controls: play/pause, volume, seek, fullscreen, speed
- Remember last position per file (stored in library DB)

---

## 6. Configuration Options — Reference Matrix

| Category | Setting | Type | Default | Notes |
|----------|---------|------|---------|-------|
| **Location** | `downloads.default_path` | string | `~/Downloads/YTDLP-WebUI` | Supports `{user_home}` placeholder |
| | Path templates | map | video/audio/playlist | `{title}`, `{uploader}`, `{ext}`, `{playlist_index}`, etc. |
| **Resolution** | `format.resolution_cap` | int | 1080 | 360/480/720/1080/1440/2143/4320 (best) |
| | `format.preferred` | format selector | `bestvideo[height<=1080]+bestaudio/best[height<=1080]` | yt-dlp format selector syntax |
| | `format.merge_output_format` | string | mp4 | mp4/mkv/webm/mov/avi |
| **Format** | `format.audio_only` | bool | false | Extract audio only |
| | `format.audio_format` | string | mp3 | mp3/m4a/opus/flac/wav |
| | `format.audio_quality` | string | "0" | VBR quality (0=best) |
| **Subs** | `format.embed_subs` | bool | false | Hard/soft embed subtitles |
| | `format.subs_lang` | list | `["en"]` | Language codes |
| | `format.write_subs` / `write_auto_subs` | bool | false | Write sidecar .vtt/.srt |
| **Metadata** | `format.embed_thumbnail` | bool | true | Embed cover art |
| | `format.embed_metadata` | bool | true | Embed title/artist/etc |
| | `format.write_info_json` / `write_description` | bool | false | Sidecar files |
| **Auth** | `auth.cookies_from_browser` | string|null | null | Import cookies from installed browser |
| | `auth.cookies_file` | string|null | null | Netscape cookies.txt |
| | `auth.username/password` | string|null | null | For sites requiring login |
| **Network** | `network.proxy` | string|null | null | `http://user:pass@host:port` |
| | `network.socket_timeout` | int | 30 | seconds |
| | `network.force_ipv4/ipv6` | bool | false | |
| **Queue** | `downloads.concurrent_downloads` | int | 3 | Max parallel yt-dlp processes |
| | `downloads.max_retries` | int | 5 | Per-job retry count |
| | `downloads.speed_limit` | int|null | null | Bytes/sec throttle |
| **Misc** | `format.noplaylist` | bool | true | Single video only unless playlist URL |
| | `format.geo_bypass` | bool | true | Bypass geo restrictions |
| | `format.keep_video` | bool | false | Keep intermediate video after audio extract |

---

## 7. Internal API (IPC Contract)

UI (`main.py`) → backend modules (`backend/`):

| Channel | Payload | Response |
|---------|---------|----------|
| `config:get` | — | full config object |
| `config:set` | `{key, value}` | `{ok}` |
| `config:reset` | — | `{ok}` |
| `search:query` | `{q, type}` | `{results: [...]} |
| `video:info` | `{url}` | `{metadata, formats, subtitles}` |
| `download:create` | `{url, config_overrides}` | `{job_id}` |
| `download:list` | — | `{jobs: [...]}` |
| `download:control` | `{job_id, action: pause|resume|cancel|retry}` | `{ok}` |
| `download:remove` | `{job_id, delete_file: bool}` | `{ok}` |
| `library:list` | `{query, filter}` | `{items: [...]}` |
| `library:action` | `{file_id, action: play|locate|delete|redownload|favorite}` | `{ok}` |
| `app:open_folder` | `{path}` | `{ok}` |

Backend → UI (events, emitted via `DownloadManager.on_event`):
- `download:progress` `{job_id, pct, speed, eta, downloaded, total}`
- `download:status` `{job_id, status}`
- `download:completed` `{job_id, filepath}`
- `download:failed` `{job_id, error}`
- `app:update_available` `{version}`

---

## 8. Database Schema (SQLite)

```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE download_jobs (
    job_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL DEFAULT 0,
    speed TEXT,
    eta TEXT,
    downloaded_bytes INTEGER DEFAULT 0,
    total_bytes INTEGER,
    filepath TEXT,
    error TEXT,
    config_json TEXT,
    attempts INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    source_url TEXT NOT NULL,
    title TEXT,
    uploader TEXT,
    duration INTEGER,
    filepath TEXT NOT NULL UNIQUE,
    file_size INTEGER,
    file_hash TEXT,
    resolution TEXT,
    container TEXT,
    downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_played TEXT,
    play_count INTEGER DEFAULT 0,
    is_favorite INTEGER DEFAULT 0,
    FOREIGN KEY (job_id) REFERENCES download_jobs(job_id)
);

CREATE INDEX idx_library_source ON library(source_url);
CREATE INDEX idx_jobs_status ON download_jobs(status);
```

---

## 9. UI / UX Design (Descriptive)

### 9.1 Layout (3-pane)
- **Left rail:** Nav (Home/Browse, Search, Queue, Library, Settings)
- **Center:** Content (search results, video detail, queue list, library grid)
- **Right drawer (slide-out):** Download configuration panel — opens when a video is selected; shows format picker, resolution slider, path picker, toggles, "Add to Queue" button

### 9.2 Views
1. **Home/Browse** — Trending, recommended, subscriptions (if auth), recent searches
2. **Search** — Debounced input, filters (video/channel/playlist, duration, upload date), results grid with thumbnail + metadata
3. **Video Detail** — Thumbnail, title, uploader, stats, description, format table (resolution/fps/codec/size), subtitles list, config drawer
4. **Queue** — Table of jobs with progress bars, speed, ETA, pause/resume/cancel buttons, clear completed
5. **Library** — Grid of downloaded media, search, filters (audio/video/favorite), context actions
6. **Settings** — Tabs: General, Downloads, Format/Resolution, Subtitles/Auth, Network, Advanced (ffmpeg path, cookies browser picker, reset config)

### 9.3 Theming
- Dark default, light toggle, system preference follow
- Accent color customizable

---

## 10. Version Roadmap (v1.1 → v2.0)

| Version | Theme | Target | Key Upgrades |
|---------|-------|--------|--------------|
| **v1.1** | Core stability | 4 weeks | Resume interrupted downloads, per-job bandwidth throttling, playback position memory, search history chips, empty states, accent color picker, config validation |
| **v1.2** | Player & library polish | 6 weeks | Variable playback speed (0.25x–4x), gapless playback, crossfade, library rescan/import, duplicate detection by hash, file integrity verification, inline tag editing, cover art gallery |
| **v1.3** | Discovery & curation | 6 weeks | Search filters (duration, date, type), trending by region, channel subscription/follow, related videos sidebar, watch-later/favorites filtering, playlist export (M3U/JSON/CSV) |
| **v1.4** | Power-user & ops | 6 weeks | Per-download format overrides, settings profiles, CLI flags, env var overrides, per-domain rate limits, queue priority drag-and-drop, download scheduling |
| **v2.0** | Platform & scale | 8 weeks | Multi-connection segmented downloads, smart playlists (auto-mixes), lyrics panel, gapless/crossfade audio normalization, chapter markers, mini player, Bluetooth auto-switch, cloud library backup, command palette |

> **v1.0.0** (shipped) — Pure Python PyQt6 release. Electron/Node/React fully removed. Single-file `main.py` with yt-dlp downloader, download queue, media player, SQLite library, multi-output audio, system tray, PyInstaller packaging.

---

### 10.1 v1.1 — Core Stability (4 weeks)

**Goal:** Harden the v1.0.0 foundation; close the most common friction points.

| # | Feature | Deliverable | Acceptance Criteria |
|---|---------|-------------|---------------------|
| 1.1 | Resume interrupted downloads | `_resume_download()` in `backend/downloader.py`; requeue `.part` files on restart | Interrupted download resumes instead of restarting from 0% |
| 1.2 | Per-job bandwidth throttling | KB/s input on each queue row; stored in job config | Individual job can be capped without affecting others |
| 1.3 | Playback position memory | Improve `playback_positions` table usage in `main.py` | Reopening a file resumes at saved ms position |
| 1.4 | Search history persistence | Save recent queries to `data/config.json`; render as chips | Search bar shows 5 most recent queries as clickable chips |
| 1.5 | Empty states | Illustration + primary CTA on Library, Search, Queue when empty | Every view has a non-blank first-time state |
| 1.6 | Accent color picker | Settings > Appearance > color picker; QSS regenerated at runtime | Picking a color updates accent instantly without restart |
| 1.7 | Config validation | Warn on invalid values in Settings; fall back to defaults | Invalid merge_output_format shows warning, app continues |

**Success criteria:** Zero data loss on interrupted downloads; settings apply instantly; no blank first-run views.

---

### 10.2 v1.2 — Player & Library Polish (6 weeks)

**Goal:** Make the media player and library feel like a dedicated music app.

| # | Feature | Deliverable | Acceptance Criteria |
|---|---------|-------------|---------------------|
| 2.1 | Variable playback speed | Speed dropdown 0.25x – 4.0x on player bar | `QMediaPlayer.setPlaybackRate()` reflects selection |
| 2.2 | Gapless playback | Pre-load next track while current plays | No audible gap between library tracks |
| 2.3 | Crossfade | Fade-out/fade-in between tracks (adjustable 0–10s) | Smooth transition between consecutive tracks |
| 2.4 | Library rescan / import | "Import Folder" dialog; scan disk for media files; add to SQLite | Existing downloads appear in Library without re-download |
| 2.5 | Duplicate detection | SHA-256 file hash on `library_add()`; skip if hash exists | Same file not added twice |
| 2.6 | File integrity verification | Post-download hash compare against recorded hash | Corrupt downloads flagged as failed |
| 2.7 | Inline tag editing | Edit title/artist/album/genre/year on Library row; write via FFmpegMetadata | Saved tags persist in SQLite and file metadata |
| 2.8 | Cover art gallery | Grid view of library items with cover art thumbnails | Visual browsing of downloaded media |

**Success criteria:** Player feels gapless; library imports existing files without duplicates; tags editable in-app.

---

### 10.3 v1.3 — Discovery & Curation (6 weeks)

**Goal:** Turn the app into a discovery tool, not just a downloader.

| # | Feature | Deliverable | Acceptance Criteria |
|---|---------|-------------|---------------------|
| 3.1 | Search filters | Duration, upload date, video type, license filters on Search view | Filter chips narrow `ytsearch` results |
| 3.2 | Trending by region | Region dropdown + "Refresh Trending" | Top Charts shows localized trending |
| 3.3 | Channel subscription | "Follow channel" on video detail; poll for new uploads | Subscribed channels appear in a Subscriptions view |
| 3.4 | Related videos | Sidebar on Video Detail with `related` extraction | Clicking related opens its detail view |
| 3.5 | Watch-later / favorites filtering | Toggle chips on Library view | Filter library to liked / watch-later only |
| 3.6 | Playlist export | Export library/playlist to M3U, JSON, CSV | Exported file opens in external players |

**Success criteria:** Users can find new content inside the app; curated lists are filterable and exportable.

---

### 10.4 v1.4 — Power-User & Ops (6 weeks)

**Goal:** Serve advanced users and headless/automated workflows.

| # | Feature | Deliverable | Acceptance Criteria |
|---|---------|-------------|---------------------|
| 4.1 | Per-download format overrides | Format drawer on Video Detail; overrides stored per job | One video downloads as MP3, another as 1080p MP4 |
| 4.2 | Settings profiles | Profile switcher (work/home/mobile); each with own config | Switching profiles swaps download path, resolution, theme |
| 4.3 | CLI flags | `python main.py --url ... --format mp3 --path ...` | Headless downloads without opening GUI |
| 4.4 | Env var overrides | `YTDLP_DOWNLOAD_PATH`, `YTDLP_RESOLUTION_CAP`, etc. | Environment variables override config defaults |
| 4.5 | Per-domain rate limits | Domain-specific KB/s caps in Settings > Network | youtube.com capped separately from other domains |
| 4.6 | Queue priority drag-and-drop | Reorder pending jobs in Queue view | Higher jobs download first |
| 4.7 | Download scheduling | Date/time picker on job creation; start at scheduled time | Job stays queued until start time |

**Success criteria:** Headless operation works; power users can fine-tune every download; queue is fully controllable.

---

### 10.5 v2.0 — Platform & Scale (8 weeks)

**Goal:** Premium media-app features and cross-device reliability.

| # | Feature | Deliverable | Acceptance Criteria |
|---|---------|-------------|---------------------|
| 5.1 | Multi-connection segmented downloads | Parallel fragment downloads per job | Large files download faster on high-bandwidth connections |
| 5.2 | Smart playlists | Auto-generated mixes by genre/year/play count | "Discovery Weekly"-style playlists update automatically |
| 5.3 | Lyrics panel | Fetch and display synced lyrics (floating window) | Lyrics scroll with playback position |
| 5.4 | Audio normalization | Volume leveling across tracks | No jarring volume jumps between videos |
| 5.5 | Chapter markers | Chapter list + seek UI on Video Detail | Long videos/podcasts navigable by chapter |
| 5.6 | Mini player | Floating, always-on-top, frameless window | Controls visible while working in other apps |
| 5.7 | Bluetooth auto-switch | Detect audio device connect; route output automatically | Playback moves to newly connected Bluetooth device |
| 5.8 | Cloud library backup | Encrypted backup of `library.db` + config to user-selected cloud | Library recoverable after machine loss |
| 5.9 | Command palette | Ctrl+K quick-search across views | Jump to any view, search, or action without menus |

**Success criteria:** App competes with dedicated media players; library is recoverable; power navigation via keyboard.

---

## 11. Release Cadence

| Version | Estimated | Merge Strategy |
|---------|-----------|----------------|
| v1.1 | 4 weeks | Weekly patch cuts; one minor release |
| v1.2 | 6 weeks | Bi-weekly cuts |
| v1.3 | 6 weeks | Bi-weekly cuts |
| v1.4 | 6 weeks | Bi-weekly cuts |
| v2.0 | 8 weeks | Release candidate cycle (2 RCs) |

Each version ships a GitHub release with PyInstaller-built artifacts (NSIS Windows, AppImage Linux, DMG macOS) plus `pip`-installable source.

---

## 12. Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| YouTube changes break extraction | Pin `yt-dlp` version; one-click "Update yt-dlp" in Settings; fallback error message |
| ffmpeg not installed | Ship `ffmpeg/bin/` per platform; validate `ffmpeg_location` on startup; setup wizard if missing |
| Large playlists freeze UI | `extract_flat` for listing; lazy-load pages; cap default playlist extract count with override |
| Copyright / ToS concerns | Disclaimer: personal use / content you own or have rights to; respect YouTube ToS |
| UI freezing during large downloads | `QThread` workers; keep UI thread responsive |
| Windows path length / Unicode | `restrictfilenames` option; careful `os.path` usage |
| Database corruption on crash | WAL journal mode (already set in `backend/library.py`); periodic backup |
| Cloud backup privacy | Client-side encryption before upload; user controls destination |

---

## 13. Testing Strategy

- **Unit tests (Python):** `config.py` validation/merge, `downloader.py` hook emission, `queue.py` concurrency/pause/resume, `library.py` CRUD, hash duplicate detection
- **Integration tests:** End-to-end download of a short public video; verify file exists, metadata embedded, DB row created; resume partial download
- **UI tests:** Search returns results; add-to-queue creates job; progress bar updates; pause then resume completes; settings apply instantly
- **Contract tests:** Verify backend RPC payload shapes match §7 API matrix
- **CI:** GitHub Actions — lint (ruff), unit tests, PyInstaller build on Windows/macOS/Linux

---

## 14. Build & Distribution

- PyInstaller (`*.spec`) with NSIS (Windows), DMG (macOS), AppImage/DEB (Linux)
- Single-file Python app packaged into a standalone executable per platform
- Auto-update via GitHub releases (v1.0.0+)
- Code signing (optional, for Windows SmartTrust / macOS Gatekeeper)

---

## 15. Immediate Next Steps

1. Verify `main.py`, `backend/`, and `ui/` import cleanly; run `python main.py`
2. Confirm `requirements.txt` and `pyproject.toml` dependency versions resolve
3. Test PyInstaller build with `yt-dlp-webui.spec` on target platform
4. Build the search + video detail UI and connect to `extractor.py`
5. Wire up the download queue and a test download
6. Begin v1.1: resume interrupted downloads + per-job bandwidth throttling

Would you like me to:
- **Generate starter code** for any v1.1 module (e.g., resume logic, bandwidth throttling, empty states)?
- **Create a GitHub Release v1.1 milestone** with issues for each planned upgrade?
- **Set up CI builds** for PyInstaller artifacts on Windows/macOS/Linux?