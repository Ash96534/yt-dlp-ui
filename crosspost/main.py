"""Main cross-poster for YT-DLP WebUI announcements.

Usage:
    python -m crosspost.main
    # or
    python crosspost/main.py

Environment variables:
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
    TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
    DEVTO_API_KEY
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List

from . import PostConfig, PostResult
from .reddit import RedditPoster
from .twitter import TwitterPoster
from .devto import DevToPoster

# Register posters here
POSTERS: Dict[str, type] = {
    "reddit": RedditPoster,
    "twitter": TwitterPoster,
    "devto": DevToPoster,
}

# Default configuration
DEFAULT_CONFIG = PostConfig(
    title="YT-DLP WebUI — YouTube Browser with Integrated Downloader",
    body=(
        "I built YT-DLP WebUI — a native desktop application for browsing YouTube "
        "and downloading videos with full yt-dlp integration. No API keys, no "
        "Electron bloat, no tracking.\n\n"
        "Features:\n"
        "• Integrated Chromium browser\n"
        "• Download queue with pause/resume/retry/cancel\n"
        "• Built-in media player with speed controls\n"
        "• Music library with artist radio, album radio, Discovery Weekly\n"
        "• Mood mixes (Chill, Workout, Party, Focus, Sleep)\n"
        "• Top Charts by region\n"
        "• Multi-output audio (play to multiple devices)\n"
        "• SQLite library with play count and watch history\n"
        "• System tray with now-playing tooltip\n"
        "• Auto-update yt-dlp\n"
        "• Export/import playlists\n\n"
        "Tech stack: Python 3.10+, PyQt6, yt-dlp, SQLite, FFmpeg\n"
        "No Electron, no React, no Node. Single .py file.\n\n"
        "Get it: {url}\n\n"
        "Open source, free, no tracking. Just your videos, your way.\n"
        "#opensource #youtube #python #pyqt #downloader"
    ),
    url="https://github.com/Ash96534/yt-dlp-ui",
    platforms=["reddit", "twitter", "devto"],
)


def post_to_all(config: PostConfig) -> List[PostResult]:
    """Post to all configured platforms.

    Args:
        config: PostConfig with title, body, url, and platforms list.

    Returns:
        List of PostResult objects.
    """
    results: List[PostResult] = []

    for platform_name in config.platforms:
        poster_class = POSTERS.get(platform_name.lower())
        if poster_class is None:
            results.append(
                PostResult(
                    platform=platform_name,
                    success=False,
                    error=f"Unknown platform: {platform_name}",
                )
            )
            continue

        poster = poster_class()
        if not poster.is_configured():
            results.append(
                PostResult(
                    platform=platform_name,
                    success=False,
                    error=f"{platform_name} credentials not configured",
                )
            )
            continue

        print(f"Posting to {platform_name}...")
        result = poster.post(config.title, config.body, config.url)
        results.append(result)

        status = "✅" if result.success else "❌"
        print(f"  {status} {platform_name}: {result.error or result.url or 'Posted'}")

    return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Cross-post YT-DLP WebUI announcement")
    parser.add_argument(
        "--title",
        default=DEFAULT_CONFIG.title,
        help="Post title",
    )
    parser.add_argument(
        "--body",
        default=DEFAULT_CONFIG.body,
        help="Post body",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_CONFIG.url,
        help="URL to share",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=DEFAULT_CONFIG.platforms,
        help="Platforms to post to",
    )
    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="List available platforms",
    )

    args = parser.parse_args()

    if args.list_platforms:
        print("Available platforms:")
        for name in POSTERS:
            print(f"  - {name}")
        return

    config = PostConfig(
        title=args.title,
        body=args.body,
        url=args.url,
        platforms=args.platforms,
    )

    results = post_to_all(config)

    # Summary
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    print(f"\n{'='*50}")
    print(f"Results: {success_count} succeeded, {fail_count} failed")
    print(f"{'='*50}")

    for result in results:
        status = "✅" if result.success else "❌"
        print(f"  {status} {result.platform}: {result.error or result.url or 'OK'}")


if __name__ == "__main__":
    main()
