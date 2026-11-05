# Contributing to YT-DLP WebUI

Thanks for contributing! This project is a single-file Python desktop app, so contributions are focused and reviewable.

## Getting Started

```bash
git clone https://github.com/Ash96534/yt-dlp-ui.git
cd yt-dlp-ui
pip install -r requirements.txt
python main.py
```

## Architecture

The app is a single-file Python application (`main.py`) built with PyQt6:

- **Backend logic**: `yt-dlp` Python API (in-process, no CLI shelling out)
- **UI**: PyQt6 (Qt Widgets + WebEngine + Multimedia)
- **Database**: SQLite (`data/library.db`)
- **Configuration**: JSON (`data/config.json`)
- **Media**: FFmpeg for audio extraction and metadata embedding

## UI Component Package (`ui/`)

| File | Purpose |
|------|---------|
| `theme.py` | ThemeManager — dark/light/system/night themes with QSS generation |
| `nav_rail.py` | NavRail — collapsible sidebar navigation |
| `player_bar.py` | PlayerBar — always-visible media player bar |
| `audio_devices.py` | AudioOutputDevice + MultiOutputManager — multi-output audio |
| `widgets.py` | MediaCard, PrimaryButton, GhostButton, IconButton, SearchBar, ThemedSlider, ThemedCheckBox |

## Adding a New Feature

### 1. Add a new view

Create a method `_page_X(self)` that returns a `QWidget`, then:

1. Add a nav item in `_build_ui()`:
   ```python
   self.nav_rail.add_item("x", "Label", "Icon", lambda: self.set_view("x"))
   ```
2. Add the page to the stack:
   ```python
   self.page_x = self._page_x()
   self.stack.addWidget(self.page_x)
   ```
3. Add navigation entry in `set_view()`:
   ```python
   index = {"browser": 0, ..., "x": N}[key]
   ```

### 2. Add a download worker

Subclass `QThread`, implement `run()` with `yt-dlp.YoutubeDL`, emit progress/status signals:

```python
class MyWorker(QThread):
    progress = pyqtSignal(...)
    finished = pyqtSignal(...)
    
    def run(self):
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
```

## Code Style

- Follow PEP 8 where practical
- Use type hints on function signatures
- Docstrings on public classes and methods
- Keep methods small and focused
- All UI strings use light-gray `#a0a0a8` for secondary text, `#e8e8ea` for primary

## Testing

There is no formal test suite yet. Manual testing steps:

1. Run `python main.py`
2. Search for a video, add to queue
3. Download completes, appears in Library
4. Play the file from Library
5. Try multi-output audio (Settings > Audio)
6. Toggle theme (Settings > Appearance)

## Submitting Changes

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make changes
4. Test locally (`python main.py`)
5. Commit with a descriptive message
6. Push and open a Pull Request

## License

MIT — see LICENSE file (or the header comment in main.py).
