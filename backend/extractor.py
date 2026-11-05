"""YouTube metadata extraction via yt-dlp (no API key required)."""
from __future__ import annotations

import yt_dlp
from typing import Any, Dict, List, Optional


def _ydl_opts(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
    }
    if extra:
        opts.update(extra)
    return opts


def extract_info(url: str, extra_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full metadata extraction for a single URL (video / playlist / channel)."""
    opts = _ydl_opts(extra_opts)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return _sanitize_info(info)


def search(query: str, max_results: int = 20) -> List[Dict[str, Any]]:
    """YouTube search via ytsearch. Returns a list of flattened video entries."""
    opts = _ydl_opts({
        'extract_flat': 'in_playlist',
        'playlistend': max_results,
    })
    search_url = f'ytsearch{max_results}:{query}'
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(search_url, download=False)
    entries = info.get('entries') or []
    return [_sanitize_info(e, flat=True) for e in entries if e]


def _fmt_duration(seconds: Optional[int]) -> Optional[str]:
    if not seconds:
        return None
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m:02d}:{s:02d}'


def _sanitize_info(info: Dict[str, Any], flat: bool = False) -> Dict[str, Any]:
    """Strip internals into a JSON-friendly dict for the frontend."""
    if not info:
        return {}

    formats = info.get('formats') or []
    video_formats: List[Dict[str, Any]] = []
    audio_formats: List[Dict[str, Any]] = []
    combined_formats: List[Dict[str, Any]] = []

    for f in formats:
        vcodec = f.get('vcodec') or 'none'
        acodec = f.get('acodec') or 'none'
        entry = {
            'format_id': f.get('format_id'),
            'ext': f.get('ext'),
            'height': f.get('height'),
            'width': f.get('width'),
            'fps': f.get('fps'),
            'vcodec': vcodec,
            'acodec': acodec,
            'tbr': f.get('tbr'),
            'filesize': f.get('filesize') or f.get('filesize_approx'),
            'has_video': vcodec != 'none',
            'has_audio': acodec != 'none',
        }
        if vcodec != 'none' and acodec != 'none':
            combined_formats.append(entry)
        elif vcodec != 'none':
            video_formats.append(entry)
        elif acodec != 'none':
            audio_formats.append(entry)

    # Deduplicate video formats by height, keep best tbr
    seen_h: Dict[int, Dict[str, Any]] = {}
    for f in video_formats:
        h = f['height']
        if h and (h not in seen_h or (f['tbr'] or 0) > (seen_h[h]['tbr'] or 0)):
            seen_h[h] = f
    video_formats = sorted(seen_h.values(), key=lambda x: (x['height'] or 0))

    subtitles = info.get('subtitles') or {}
    auto_subs = info.get('automatic_captions') or {}
    sub_langs = sorted(set(list(subtitles.keys()) + list(auto_subs.keys())))

    thumbnails = info.get('thumbnails') or []
    thumb = None
    if thumbnails:
        thumb = thumbnails[-1].get('url')
    elif info.get('thumbnail'):
        thumb = info.get('thumbnail')

    return {
        'id': info.get('id'),
        'title': info.get('title'),
        'uploader': info.get('uploader'),
        'uploader_id': info.get('uploader_id'),
        'channel_id': info.get('channel_id'),
        'channel_url': info.get('channel_url'),
        'duration': info.get('duration'),
        'duration_string': _fmt_duration(info.get('duration')),
        'view_count': info.get('view_count'),
        'like_count': info.get('like_count'),
        'upload_date': info.get('upload_date'),
        'release_timestamp': info.get('release_timestamp'),
        'description': info.get('description'),
        'categories': info.get('categories') or [],
        'tags': info.get('tags') or [],
        'webpage_url': info.get('webpage_url'),
        'extractor': info.get('extractor'),
        'thumbnail': thumb,
        'thumbnails': thumbnails,
        'is_live': bool(info.get('is_live')),
        'was_live': bool(info.get('was_live')),
        'age_limit': info.get('age_limit'),
        'noplaylist': bool(info.get('noplaylist')),
        'playlist': info.get('playlist'),
        'playlist_index': info.get('playlist_index'),
        'playlist_title': info.get('playlist_title'),
        'video_formats': video_formats,
        'audio_formats': audio_formats,
        'combined_formats': combined_formats,
        'subtitles': subtitles,
        'automatic_captions': auto_subs,
        'sub_langs': sub_langs,
        'flat': flat,
    }
