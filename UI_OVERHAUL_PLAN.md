# YT-DLP WebUI — UI Overhaul Plan

**Goal:** Transform the current functional-but-basic PyQt6 widget layout into a modern, cohesive, music/streaming-service-inspired desktop application with clear visual hierarchy, consistent controls, and polished micro-interactions.

---

## 1. Design Principles

| Principle | Meaning |
|-----------|---------|
| **Media-first** | The player is always present and always visible; content views slide behind it |
| **Dark by default** | Deep charcoal background with accent color for active states; light theme as an opt-in |
| **One glance** | Any view should show title, artwork, controls, and progress without scrolling |
| **Direct manipulation** | Drag-to-seek, hover-to-preview, single-click actions — no hidden menus |
| **Native feel** | Use Qt's native styling but push it beyond default widget look with custom QSS and QPainter overrides where needed |

---

## 2. Visual Design System

### Color Palette

**Dark Theme (default)**

| Role | Hex | Usage |
|------|-----|-------|
| Background | `#0f0f12` | Main window, panels |
| Surface | `#1a1a1e` | Cards, popovers, mini player |
| Elevated | `#24242e` | Hovered items, active tabs |
| Border | `#2a2a33` | Subtle dividers |
| Text Primary | `#e8e8ea` | Titles, labels |
| Text Secondary | `#a0a0a8` | Metadata, captions |
| Accent | `#3b82f6` | Primary buttons, active state, progress |
| Accent Hover | `#60a5fa` | Hovered primary buttons |
| Success | `#22c55e` | Completed downloads |
| Warning | `#f59e0b` | Paused, retrying |
| Error | `#ef4444` | Failed downloads |
| Muted | `#4b4b55` | Disabled controls, placeholders |

**Light Theme (opt-in)**

Swap background/surface to `#fafafa` / `#ffffff` and text to `#111827`, keep accent colors identical.

### Typography

| Element | Family | Size | Weight |
|---------|--------|------|--------|
| Display (app title) | Segoe UI / Inter | 20px | Bold |
| H1 (view titles) | Segoe UI / Inter | 16px | Bold |
| H2 (section titles) | Segoe UI / Inter | 13px | Semibold |
| Body (descriptions) | Segoe UI / Inter | 12px | Regular |
| Caption (metadata) | Segoe UI / Inter | 11px | Regular |
| Mono (timestamps, speeds) | Consolas / JetBrains Mono | 11px | Regular |

### Iconography

Replace emoji text labels with SVG icons (PyQt6 `QSvgWidget` or `QIcon` from SVG files):

| Action | Icon |
|--------|------|
| Play / Pause | Triangle / Two vertical bars |
| Next / Previous | Skip forward / backward |
| Download | Down arrow into tray |
| Library | Stack of rectangles |
| Search | Magnifying glass |
| Settings | Gear |
| Like | Heart (filled / outline) |
| Artist Radio | Broadcast tower |
| Album Art | Square with mountain/sun |
| Shuffle | Crossing arrows |
| Repeat | Loop arrow |
| Sleep | Moon / Clock |
| Mini Player | Expand / Collapse |

---

## 3. Layout Architecture

### Shell (single window)

```
+---------------------------------------------------------------+
| [App Icon]  YT-DLP WebUI     [Search]   [Settings] [Tray]   |
+---------------------------------------------------------------+
|  NAVIGATION RAIL                    CONTENT AREA             |
|                                                                 |
|  ● Browser                          [Current View]           |
|  ○ Search                                                       |
|  ○ Music                                                        |
|  ○ Charts                                                       |
|  ○ Video                                                        |
|  ○ Queue                                                        |
|  ○ Library                                                      |
|  ○ Settings                                                     |
|                                                                 |
|  [Collapse Rail button]                                         |
+---------------------------------------------------------------+
|  PLAYER BAR (always visible, collapsed by default)             |
|  [Art]  [Title]  [Prev] [Play] [Next]  [Progress]  [Vol] [X] |
+---------------------------------------------------------------+
```

### Navigation Rail (left, collapsible)

- Icon-only when collapsed; label appears on hover or expanded
- Active view highlighted with accent color left border + subtle background
- "Browser" is the default landing view

### Content Area (right, fills remaining space)

- Each view is a `QStackedWidget` page
- Views use `QScrollArea` internally for overflow
- Cards use rounded corners (`#24242e` surface) with subtle borders

### Player Bar (bottom, docked)

- Always visible when media is loaded or queue is non-empty
- Collapsed height: ~64px; expanded height: ~110px
- Collapse/expand toggle on the right edge
- Shows: artwork thumbnail (48x48), title (ellipsized), artist, prev/play/next, progress bar, volume, close

---

## 4. View-by-View Redesign

### 4.1 Browser (Default)

**Concept:** A YouTube window inside the app, with an overlay download bar.

- Top: Native QWebEngineView (unchanged)
- Overlay bar (slides down on YouTube URL detection):
  - "YouTube video detected"
  - Resolution preset chips (360p, 720p, 1080p, 4K)
  - Format: Video / Audio (MP3)
  - [Download] primary button
- Below overlay: Download queue mini-list (last 3 jobs)

### 4.2 Search

**Concept:** Spotify-style search results with album-art grid.

- Search bar at top (debounced 300ms)
- "Recent Searches" pill chips below search bar
- Results in 3-column card grid:
  - Cover art (16:9)
  - Title (2 lines max)
  - Uploader
  - Duration badge (bottom-right corner of art)
  - Hover overlay: [Download MP3] [Add to Queue]
- Empty state: illustration + "Search for videos, playlists, or channels"

### 4.3 Music (Redesigned)

**Concept:** YouTube Music / Spotify library view.

**Left column (narrow, ~280px):**
- "Your Music" header
- Quick filters: All / Liked / Watch Later / Downloaded
- "Create Playlist" button
- Existing playlists list (click to view tracks)

**Right column (wide):**
- Track grid (4 columns)
- Each card:
  - Square cover art
  - Title
  - Artist
  - Like heart (toggle)
  - Hover: [Play] [Add to Playlist] [Artist Radio]
- Bottom of grid: "Import Playlist URL" / "Export Library" buttons

### 4.4 Top Charts

**Concept:** Billboard-style ranked list.

- Region selector dropdown
- Ranked list #1–#50
- Each row: Rank badge | Cover art | Title | Artist | Duration | [MP3] button
- Pull-to-refresh equivalent: [Refresh Charts] button

### 4.5 Video Detail

**Concept:** YouTube video page reimagined.

- Hero: Video thumbnail (wide, 16:9)
- Below hero: Title, uploader, stats row (views, date, duration)
- Tabs: Formats | Chapters | Subtitles
- Formats: Selectable chips grouped by quality (1080p, 720p, 480p, 360p) + Audio-only toggle
- Per-video overrides panel (collapsible): Resolution cap, container, embed thumbnail/metadata/subs
- [Add to Queue] primary button (full width)

### 4.6 Queue

**Concept:** Download manager with status colors.

- List view (not grid)
- Each row: Job icon (status color) | Title | Progress bar | Speed | ETA | Actions (Pause / Retry / Delete)
- Header stats: Active downloads, completed today, failed
- Empty state: "Your downloads will appear here"

### 4.7 Library

**Concept:** Media file explorer with playback focus.

- Grid of downloaded files
- Each card: Cover art | Title | File size | Format badge | [Play] [Open Folder] [Share] [Delete]
- Top bar: Search + [Play All] button
- Context menu on right-click: Play, Add to Playlist, Delete, Show in Folder

### 4.8 Settings

**Concept:** System settings-style grouped cards.

Tabs:
- **Downloads:** Path picker, concurrent slider (1–10), retry count, speed limit slider
- **Format:** Resolution cap dropdown, container dropdown, checkboxes (audio-only, embed thumbnail, embed metadata, embed subs)
- **Network:** Proxy field, cookies-from-browser dropdown, cookies-file picker
- **Appearance:** Theme selector (Dark/Light/System/Night), accent color picker
- **Updates:** [Check for yt-dlp updates] button + status label

---

## 5. Component Library (Custom Widgets)

Build reusable custom widgets in `ui/` package:

| Component | Qt Base | Purpose |
|-----------|---------|---------|
| `MediaCard` | QFrame | Cover art + title + actions hover overlay |
| `DownloadRow` | QWidget | Status icon, title, progress, speed, ETA, actions |
| `FormatChip` | QPushButton | Selectable resolution/format pill |
| `PrimaryButton` | QPushButton | Accent-colored, rounded, hover lift |
| `GhostButton` | QPushButton | Transparent, border, text-only |
| `IconButton` | QToolButton | Square, icon-only, hover background |
| `Slider` | QSlider | Custom-styled track/thumb for volume/progress |
| `SearchBar` | QLineEdit | Rounded, icon-left, clear-on-esc |
| `CollapseRail` | QPushButton | Toggle navigation rail width |

All custom widgets get a `setTheme(dark: bool)` method to swap QSS at runtime without restart.

---

## 6. Interaction Details

| Interaction | Behavior |
|-------------|----------|
| Hover over MediaCard | Actions buttons fade in; card lifts 2px |
| Click cover art in library | Plays immediately |
| Drag a URL onto window | Adds to queue immediately |
| Click download in Browser overlay | Adds to queue, switches to Queue view |
| Click Play in Queue | Switches to player-expanded mode |
| Resize window | Content grid reflows (2 → 3 → 4 columns) |
| Press Esc in fullscreen player | Exits fullscreen |
| Press Space anywhere | Toggles play/pause (global shortcut) |

---

## 7. Implementation Phases

### Phase 1: Design System & Shell (Week 1)
- Create `ui/` package with custom widgets
- Implement QSS theme engine (dark/light toggle at runtime)
- Build collapsible navigation rail
- Build always-visible player bar (collapsed/expanded)
- Migrate existing views into new shell (no feature changes yet)

### Phase 2: View Overhauls (Week 2)
- Redesign Search (grid cards + recent chips)
- Redesign Music (left/right split, like heart, artist radio)
- Redesign Queue (status-colored rows, header stats)
- Redesign Library (card grid, play-all)
- Redesign Video Detail (hero + format chips)

### Phase 3: Player & Polish (Week 3)
- Expandable player bar with artwork
- Lyrics panel (floating window)
- Album art viewer (modal)
- Recently played modal
- Mini player (frameless, always-on-top)
- Keyboard shortcuts registry

### Phase 4: Settings & Final (Week 4)
- Redesigned settings with cards
- Theme accent color picker
- Night mode auto-toggle
- Final QA on all 8 views

---

## 8. Files to Create/Modify

```
main.py              # Rewrite shell + views using new components
ui/__init__.py
ui/theme.py          # QSS theme engine
ui/widgets.py        # MediaCard, DownloadRow, FormatChip, etc.
ui/player_bar.py     # Always-visible player
ui/nav_rail.py       # Collapsible navigation
resources/icons/     # SVG icon files
resources/styles.qss # Base stylesheet
```

---

## 9. Success Criteria

- [ ] Single window, no floating dialogs except settings/import
- [ ] Player bar always accessible (one click to play/pause)
- [ ] Theme switch applies instantly without restart
- [ ] All 8 views usable at 900x600 minimum window size
- [ ] Download to playback in under 3 clicks from Browser view
