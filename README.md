# YT-DLP WebUI

A pure Python desktop application for browsing YouTube and downloading videos/audio with full yt-dlp integration. Built with PyQt6 — no Electron, no React, no web bridge. Single-file architecture with a native Chromium browser tab, built-in media player, music library, and 60+ features.

## Features

### YouTube Browser
- Integrated Chromium (QWebEngineView) browser tab — default gateway
- Search YouTube, browse trending, view top charts
- "Download this video" button on any YouTube page
- Video format picker (resolution, codec, container, audio-only)
- Per-video download overrides (resolution cap, embed thumbnail/metadata/subs)

### Download Engine
- Powered by yt-dlp (no API key required)
- Download queue with pause, resume, retry, cancel
- Real-time progress, speed, ETA
- Concurrent download control
- Download speed limit
- Auto-retry on failure
- Drag & drop URLs onto the window

### Media Player (Built-in)
- Native Qt Multimedia player — no VLC required
- Play downloaded videos and MP3s directly in the app
- Playback speed (0.5x–2x), skip ±10s, shuffle, repeat (All/One/None)
- Autoplay next, crossfade, gapless, sleep timer
- True random Fisher-Yates shuffle
- Playback position resume
- Keyboard shortcuts: Space (play/pause), arrows (seek), Up/Down (volume), M (mute), F (fullscreen)
- Mini player (always-on-top)
- Lyrics panel, album art viewer, recently played history

### Music Section (YouTube Music / Spotify-style)
- Download MP3s from YouTube (best audio, VBR quality 0, embedded metadata & cover art)
- Local music library with cover thumbnails
- Artist Radio — play all tracks by an artist
- Album Radio — play all tracks in an album
- Discovery Weekly — shuffle your liked songs
- Mood Playlists (Chill, Workout, Party, Focus, Sleep)
- Top Charts by region
- Like/Dislike/Watch Later per track
- Playlists: export/import JSON, collaborative playlist import from YouTube URL

### Library & Library Management
- SQLite library index of all downloaded media
- Search/filter library, favorites, watch later
- Open file location, re-download, share (copy URL)
- Play count tracking

### Settings
- Download path, concurrent downloads, max retries, speed limit
- Resolution cap, container format, audio-only, embed thumbnail/metadata/subs
- Proxy, cookies-from-browser, cookies file
- Theme: Dark / Light / System / Night Mode (auto 8pm–8am)
- Equalizer bands, volume normalize
- Auto-update yt-dlp

## Tech Stack

- **Language**: Python 3.10+
- **UI Framework**: PyQt6 (Qt Widgets + WebEngine + Multimedia)
- **Downloader**: yt-dlp (Python API, in-process)
- **Media**: Qt Multimedia (QMediaPlayer, QVideoWidget, QAudioOutput)
- **Database**: SQLite
- **Packaging**: PyInstaller / manual run

## Installation & Usage

### Prerequisites
- Python 3.10 or higher
- FFmpeg (for audio extraction, metadata embedding, thumbnail embed) — bundled for Windows in `ffmpeg/bin/`

### Run from Source
```bash
git clone https://github.com/yourusername/yt-dlp-webui.git
cd yt-dlp-webui
pip install -r requirements.txt
python main.py
```

### FFmpeg
On Windows, FFmpeg binaries are included in `ffmpeg/bin/`. On other platforms, install FFmpeg system-wide or set `postprocessing.ffmpeg_location` in Settings.

## Architecture

```
main.py                          # Single-file application (UI + backend + downloader)
├── YTDLPApp(QMainWindow)        # Main window, navigation, all views
├── DownloadWorker(QThread)      # yt-dlp download engine with progress hooks
├── MusicDownloadWorker(QThread) # MP3 extraction worker
├── PlaylistFetchWorker(QThread) # Playlist/channel URL extraction
├── SearchWorker(QThread)        # YouTube search
├── InfoWorker(QThread)          # Video metadata extraction
├── YtDlpUpdateWorker(QThread)   # yt-dlp auto-updater
├── MiniPlayer(QWidget)          # Always-on-top mini player
├── LyricsPanel(QWidget)         # Lyrics display
├── AlbumArtViewer(QDialog)      # Full-size album art
├── RecentlyPlayedDialog(QDialog)# Playback history
├── EQBandsDialog(QDialog)       # Equalizer bands
├── BatchDownloadDialog(QDialog) # Batch playlist downloader
├── PlaylistImportDialog(QDialog)# Import playlist from URL
├── QFlowLayout(QLayout)         # Flow layout for recent searches
└── SQLite database (data/library.db)  # Library index, watch history, playback positions
```

## Navigation

| View | Purpose |
|------|---------|
| 🌐 Browser | Chromium YouTube browser with download button |
| 🔍 Search | YouTube search with recent searches |
| 🔥 Trending | Trending videos |
| 🎵 Music | MP3 downloads, music library, mood playlists |
| 📊 Top Charts | Regional music charts |
| ▶️ Video | Video detail, format picker, per-video overrides |
| ⬇️ Queue | Download queue (pause/resume/retry/cancel) |
| 📚 Library | Downloaded media index, play, share, like/dislike |
| ⚙️ Settings | Download, format, network, appearance config |

## Configuration

Settings are saved to `data/config.json`. The library index is stored in `data/library.db` (SQLite).

Key config sections:
- `downloads` — path, concurrent downloads, retries, speed limit
- `format` — resolution cap, container, audio-only, embed options
- `network` — proxy, cookies
- `auth` — cookies-from-browser, cookies-file
- `app` — theme, recent searches

## License

MIT

## Disclaimer

This tool is for personal use and content you own or have rights to. Respect YouTube's Terms of Service and copyright laws. The author is not responsible for misuse.
