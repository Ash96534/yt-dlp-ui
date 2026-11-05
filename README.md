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
| **Browser tab** | Native Chromium window — search, browse, and download any YouTube URL with one click |
| **Download queue** | Pause, resume, retry, cancel. Real-time progress, speed, ETA |
| **MP3 downloads** | Extract audio with embedded cover art and metadata |
| **Music library** | SQLite-backed index of everything you download |
| **Artist Radio** | Play every track by an artist, shuffled |
| **Album Radio** | Play full albums in track order |
| **Discovery Weekly** | Auto-shuffle your liked tracks |
| **Mood mixes** | Chill, Workout, Party, Focus, Sleep — keyword-matched from your library |
| **Top Charts** | Regional trending music discovery |
| **Built-in player** | Playback speed (0.5x–2x), skip ±10s, shuffle, repeat, crossfade, sleep timer, EQ bands |
| **Resume** | Playback position saved per file — close and come back where you left off |
| **Keyboard controls** | Space = play/pause, arrows = seek, M = mute, F = fullscreen |
| **System tray** | Minimize to tray, downloads keep running, now-playing tooltip |
| **Auto-update** | One-click yt-dlp updater so extraction never breaks |
| **Export/Import** | JSON playlist backup and restore |

---

## Tech Stack (Zero Bloat)

- **Python 3.10+** — single-file architecture
- **PyQt6** — Qt Widgets + WebEngine (Chromium) + Multimedia
- **yt-dlp** — in-process Python API (no CLI shelling out)
- **SQLite** — library index, watch history, playback positions
- **FFmpeg** — audio extraction, metadata embedding, cover art

No Electron. No React. No Node. No browser extensions. One `.py` file.

---

## Quick Start

```bash
# Clone
git clone https://github.com/Ash96534/yt-dlp-ui.git
cd yt-dlp-ui

# Install deps
pip install -r requirements.txt

# Run
python main.py
```

### FFmpeg

FFmpeg is required for audio extraction and metadata embedding.

- **Windows:** Binaries included in `ffmpeg/bin/`
- **macOS/Linux:** Install via your package manager (`brew install ffmpeg` or `sudo apt install ffmpeg`)

Then set the path in **Settings > Downloads > FFmpeg location** if it's not auto-detected.

---

## Navigation

```
Browser        — Open YouTube, download any video
Search         — Search YouTube with recent-search chips
Trending       — See what's popular right now
Music          — MP3 downloads, library, mood mixes
Top Charts     — Regional music charts
Video          — Format picker, per-video overrides
Queue          — Download management (pause/resume/retry)
Library        — Your media index, like/dislike, watch later
Settings       — Path, resolution, container, proxy, theme, EQ
```

---

## Configuration

Settings live in `data/config.json`. Your library index lives in `data/library.db` (SQLite).

Key settings:
- **Download path** — where files land
- **Resolution cap** — 360p to 4320p
- **Container** — MP4, MKV, WebM, MOV
- **Speed limit** — KB/s throttle
- **Theme** — Dark, Light, System, or Night Mode (auto 8pm–8am)
- **Proxy / Cookies** — for age-restricted or region-locked content

---

## Philosophy

Most YouTube downloaders are CLI tools, sketchy websites, or Electron apps that eat 400MB of RAM. This is none of those things.

It's a desktop app that respects your machine, stores everything locally, and treats your downloads like a personal media library — not a temp folder.

---

## License

MIT — use it, break it, remix it.

## Disclaimer

For personal use with content you own or have rights to. Respect YouTube's Terms of Service and applicable copyright law. The author is not responsible for misuse.

---

**Built with PyQt6 + yt-dlp. No API keys. No tracking. Just your videos, your way.**
