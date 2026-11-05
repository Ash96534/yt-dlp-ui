# Release Notes

## v1.1 (In Development) — Core Stability

### Added
- Resume interrupted downloads on restart — download jobs are persisted to `data/jobs.json`; queued/running jobs are automatically requeued on launch
- Per-job bandwidth throttling via `downloads.speed_limit_kbps` (0 = unlimited; MB/s conversion not needed)
- Empty states with helpful prompts for Library, Music Library, Queue, and Search
- Accent color picker in Settings → Appearance (pick/reset, applies instantly, persisted in config)
- Config validation with warnings and safe fallbacks for invalid merge_output_format, audio_format, resolution_cap, proxy, theme, and download/network limits

### Fixed
- Downloads no longer crash on start (missing `pyqtSignal` declarations on `DownloadWorker`)
- `InfoWorker`/`SearchWorker` moved before the entry point (previously never defined at runtime)
- Player Bar now works with `MultiOutputManager` (seek, speed, play/pause)
- Overlay buttons wired at runtime selection (Mini Player, Lyrics, Album Art, Crossfade, Gapless, Recent)
- Playback position saved on quit/minimize-to-tray
- "System" theme mode works (ThemeManager bound to QApplication)
- Search view no longer references undefined widgets; recent-search chips render correctly

---

## YT-DLP WebUI v1.0.0

## Features

- **Integrated Chromium YouTube browser** - Search, browse, and download any YouTube URL with one click
- **Download queue** - Pause, resume, retry, cancel with real-time progress, speed, ETA
- **Built-in media player** - Playback speed (0.5x-2x), skip ±10s, shuffle, repeat, crossfade, sleep timer
- **Music Library** - SQLite-backed index with like/dislike/watch-later, play count
- **Artist Radio** - Play every track by an artist, shuffled
- **Album Radio** - Play full albums in track order
- **Discovery Weekly** - Auto-shuffle your liked tracks
- **Mood mixes** - Chill, Workout, Party, Focus, Sleep
- **Top Charts** - Regional trending music discovery
- **Multi-output audio** - Play to multiple devices simultaneously
- **System tray** - Minimize to tray, downloads keep running, now-playing tooltip
- **Auto-update yt-dlp** - One-click updater
- **Export/Import** - JSON playlist backup and restore

## Installation

### Windows
Download `YT-DLP-WebUI-Setup-1.0.0.exe` or the portable ZIP.

### Linux
Download `YT-DLP-WebUI-1.0.0-x86_64.AppImage`

### macOS
Download `YT-DLP-WebUI-1.0.0-macOS.dmg`

## Quick Start

1. Install and launch the app
2. Search for a YouTube video or paste a URL
3. Click "Add to queue" to download
4. Play downloaded media from the Library tab

## Requirements

- Windows 10/11, macOS 10.15+, or Linux
- FFmpeg (bundled on Windows, install separately on other platforms)

## License

MIT
