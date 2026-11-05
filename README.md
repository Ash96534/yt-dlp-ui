# YT-DLP WebUI

**A single-file, Electron-free desktop app that turns YouTube into your personal media library.** Built with PyQt6 and powered by yt-dlp — no API keys, no browser extensions, no Electron bloat.

---

## The Pitch

Open YouTube in a native Chromium window. Find a video. Click **Download**. It lands in your local library with cover art, metadata, and full playback controls. Build playlists, spin artist radios, set sleep timers, adjust playback speed — all inside one window.

It's yt-dlp with a face.

---

## What It Does

| Feature | What it means |
|---------|---------------|
| **Integrated YouTube Browser** | Native Chromium window — search, browse, and download any YouTube URL with one click |
| **Download Queue** | Pause, resume, retry, cancel. Real-time progress, speed, ETA |
| **MP3 Downloads** | Extract audio with embedded cover art and metadata |
| **Music Library** | SQLite-backed index of everything you download |
| **Artist Radio** | Play every track by an artist, shuffled |
| **Album Radio** | Play full albums in track order |
| **Discovery Weekly** | Auto-shuffle your liked tracks |
| **Mood Mixes** | Chill, Workout, Party, Focus, Sleep — keyword-matched from your library |
| **Top Charts** | Regional trending music discovery |
| **Built-in Media Player** | Playback speed (0.5x–2x), skip ±10s, shuffle, repeat, crossfade, sleep timer, EQ bands |
| **Playback Resume** | Position saved per file — close and come back where you left off |
| **Keyboard Controls** | Space = play/pause, arrows = seek, M = mute, F = fullscreen, N/P = next/prev |
| **System Tray** | Minimize to tray, downloads keep running, now-playing tooltip |
| **Auto-Update** | One-click yt-dlp updater so extraction never breaks |
| **Export/Import** | JSON playlist backup and restore |
| **Multi-Output Audio** | Play to multiple devices simultaneously (Bluetooth speaker + laptop + headphones) |

---

## Tech Stack (Zero Bloat)

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.10+ |
| **UI Framework** | PyQt6 (Qt Widgets + WebEngine Chromium + Multimedia) |
| **Downloader** | yt-dlp (in-process Python API) |
| **Database** | SQLite (library index, watch history, playback positions) |
| **Media** | FFmpeg (audio extraction, metadata embedding, cover art) |

No Electron. No React. No Node. No browser extensions. One `.py` file (~3,600 lines).

---

## Quick Start

```bash
# Clone
git clone https://github.com/Ash96534/yt-dlp-ui.git
cd yt-dlp-ui

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### FFmpeg

FFmpeg is required for audio extraction (MP3), metadata embedding, and cover art.

- **Windows:** Binaries included in `ffmpeg/bin/`
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` (or your distro's equivalent)

Then set the path in **Settings > Downloads > FFmpeg location** if it's not auto-detected.

---

## Navigation

| View | Purpose |
|------|---------|
| **Browser** | Open YouTube in a native Chromium window. Download any video with one click |
| **Search** | Search YouTube with recent-search chips and card-based results |
| **Trending** | See what's popular right now |
| **Music** | MP3 downloads, local library, mood mixes, artist/album radio |
| **Top Charts** | Regional trending music discovery |
| **Video** | Format picker, per-video overrides (resolution, container, embed options) |
| **Queue** | Download management — pause/resume/retry/cancel with real-time progress |
| **Library** | Your media index — like/dislike/watch-later, play, open folder, share |
| **Settings** | Download path, resolution, container, proxy, theme, EQ, audio devices |

---

## Configuration

Settings live in `data/config.json`. Your library index lives in `data/library.db` (SQLite).

### Key Settings Sections

| Section | Options |
|---------|---------|
| **Downloads** | Path, concurrent downloads (1–10), max retries, speed limit (KB/s) |
| **Format** | Resolution cap (360p–4320p), container (MP4/MKV/WebM/MOV), audio-only, embed thumbnail/metadata/subs |
| **Network** | Proxy, cookies-from-browser, cookies file |
| **Auth** | Cookies from browser, cookies file path |
| **App** | Theme (dark/light/system/night), recent searches |
| **Audio** | Output device selection (multi-output supported) |

---

## Multi-Output Audio

Play to multiple audio devices simultaneously — for example, your Bluetooth speaker **and** laptop speakers at the same time.

1. Go to **Settings > Audio**
2. Check all output devices you want to use
3. Play any media — it will route to all selected devices

Each output gets its own `QMediaPlayer` + `QAudioOutput` pair, keeping playback perfectly synced across devices.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Skip back / forward 10 seconds |
| `↑` / `↓` | Volume up / down |
| `M` | Mute / Unmute |
| `F` | Toggle fullscreen |
| `N` | Next track |
| `P` | Previous track |

---

## File Structure

```
yt-dlp-webui/
├── main.py                 # Main application (~3,600 lines, single file)
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── PROJECT_PLAN.md         # Original project plan
├── UI_OVERHAUL_PLAN.md     # UI redesign documentation
├── config/
│   └── config.default.json # Default application settings
├── ffmpeg/
│   └── bin/                # FFmpeg binaries (Windows)
│       ├── ffmpeg.exe
│       └── ffprobe.exe
├── data/                   # Created at runtime
│   ├── config.json         # User settings
│   └── library.db          # SQLite library index
└── ui/                     # UI component package
    ├── __init__.py
    ├── theme.py            # Dark/light/system/night theme engine
    ├── nav_rail.py         # Collapsible navigation sidebar
    ├── player_bar.py       # Always-visible media player bar
    ├── audio_devices.py    # Multi-output audio manager
    └── widgets.py          # Reusable widgets (MediaCard, buttons, etc.)
```

---

## Architecture

The app is built around a single `QMainWindow` (`YTDLPApp`) with:

- **Navigation Rail** (`ui/nav_rail.py`) — Collapsible sidebar with all views
- **Content Stack** (`QStackedWidget`) — One page per view (Browser, Search, Music, etc.)
- **Player Bar** (`ui/player_bar.py`) — Always-visible bottom player with collapsed/expanded states
- **Theme Manager** (`ui/theme.py`) — Instant dark/light/system/night theme switching
- **MultiOutputManager** (`ui/audio_devices.py`) — Simultaneous playback to multiple audio devices

Download workers run in `QThread` subclasses so the UI never blocks:

- `DownloadWorker` — General yt-dlp downloads with progress hooks
- `MusicDownloadWorker` — MP3-optimized downloads
- `PlaylistFetchWorker` — Extract playlist entries without downloading
- `InfoWorker` / `SearchWorker` — Metadata extraction and search
- `YtDlpUpdateWorker` — Background yt-dlp updates

---

## License

MIT — use it, break it, remix it.

## Disclaimer

For personal use with content you own or have rights to. Respect YouTube's Terms of Service and applicable copyright law. The author is not responsible for misuse.

---

**Built with PyQt6 + yt-dlp. No API keys. No tracking. Just your videos, your way.**
