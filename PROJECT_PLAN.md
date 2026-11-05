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

## 10. Implementation Roadmap (Phases)

| Phase | Goal | Key Deliverables |
|-------|------|------------------|
| **P1 — Foundation** | Repo setup, PyQt6 shell, Python backend modules, config system | `main.py`, `backend/`, `ui/`, `config/`, `config.default.json`, requirements.txt, first build |
| **P2 — Extraction** | YouTube search + video info | `extractor.py`, search view, video detail view, format table |
| **P3 — Download Engine** | yt-dlp integration, queue, progress | `downloader.py`, `queue.py`, queue view, pause/resume/cancel |
| **P4 — Configuration UI** | Global + per-download settings | Settings view, config drawer on video detail, defaults merge logic |
| **P5 — Library** | SQLite index, file management | `library.py`, library view, open-locate-delete-redownload |
| **P6 — Polish** | Theming, notifications, tray, updater, packaging | PyInstaller spec, ffmpeg bundling, auto-update, NSIS/AppImage/DMG installer |

---

## 11. Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| YouTube changes break extraction | Pin `yt-dlp` version, add one-click "Update yt-dlp" in settings, fallback error message telling user to update |
| ffmpeg not installed | Ship ffmpeg binaries per platform in `ffmpeg/`; validate `ffmpeg_location` on startup; show setup wizard if missing |
| Large playlists freeze UI | `extract_flat` for listing, lazy-load pages, cap default playlist extract count with user override |
| Copyright / ToS concerns | Include disclaimer: tool for personal use / content you own or have rights to; respect YouTube ToS |
| UI freezing during large downloads | Offload downloads to `QThread` workers; keep UI thread responsive |
| Windows path length / Unicode | Normalize filenames via `yt-dlp` `restrictfilenames` option; use `os.path` carefully |

---

## 12. Testing Strategy

- **Unit tests (Python):** `config.py` validation/merge, `downloader.py` hook emission, `queue.py` concurrency/pause/resume, `library.py` CRUD
- **Integration tests:** End-to-end download of a short public video; verify file exists, metadata embedded, DB row created
- **UI tests (Playwright):** Search returns results, add-to-queue creates job, progress bar updates, pause then resume completes
- **Contract tests:** Verify IPC payload shapes match the API matrix in §7
- **CI:** GitHub Actions — lint (ruff/prettier), unit tests, build on Windows/macOS/Linux

---

## 13. Build & Distribution

- PyInstaller (`*.spec`) with NSIS (Windows), DMG (macOS), AppImage/DEB (Linux)
- Single-file Python app packaged into a standalone executable per platform
- Auto-update via GitHub releases
- Code signing (optional, for Windows SmartTrust / macOS Gatekeeper)

---

## 14. Immediate Next Steps

1. Verify `main.py`, `backend/`, and `ui/` import cleanly; run `python main.py`
2. Confirm `requirements.txt` and `pyproject.toml` dependency versions resolve
3. Test PyInstaller build with `yt-dlp-webui.spec` on target platform
4. Build the search + video detail UI and connect to `extractor.py`
5. Wire up the download queue and a test download

Would you like me to:
- **Generate starter code** for any of these modules (e.g., the Python backend `config.py` + `downloader.py`, or PyQt6 UI widgets)?
- **Choose between PyQt6 and another Python GUI toolkit** for the UI?
- **Add OAuth/login** for age-restricted or private content (requires cookies from browser / YouTube Data API)?