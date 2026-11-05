"""Reddit poster using PRAW (Python Reddit API Wrapper).

Requires:
    pip install praw

Environment variables:
    REDDIT_CLIENT_ID
    REDDIT_CLIENT_SECRET
    REDDIT_USERNAME
    REDDIT_PASSWORD

Setup:
    1. Create account at reddit.com/register (manually)
    2. Go to reddit.com/prefs/apps
    3. Click "Create App" or "Create another app"
    4. Select "script" type
    5. Copy client_id and client_secret
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    import praw
except ImportError:
    praw = None

from . import PostResult, BasePoster


class RedditPoster(BasePoster):
    """Reddit poster using PRAW."""

    def __init__(self):
        super().__init__("reddit")
        self._reddit = None
        self._subreddit = "python"  # default subreddit, change as needed

    def is_configured(self) -> bool:
        """Check if Reddit credentials are configured."""
        if praw is None:
            return False
        return all(
            os.environ.get(k)
            for k in [
                "REDDIT_CLIENT_ID",
                "REDDIT_CLIENT_SECRET",
                "REDDIT_USERNAME",
                "REDDIT_PASSWORD",
            ]
        )

    def _init_reddit(self):
        """Initialize PRAW Reddit instance."""
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=os.environ["REDDIT_CLIENT_ID"],
                client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                username=os.environ["REDDIT_USERNAME"],
                password=os.environ["REDDIT_PASSWORD"],
                user_agent="yt-dlp-webui-bot/1.0 by u/your_username",
            )

    def post(self, title: str, body: str, url: str) -> PostResult:
        """Post to Reddit."""
        if not self.is_configured():
            return PostResult(
                platform="reddit",
                success=False,
                error="Reddit credentials not configured",
            )

        try:
            self._init_reddit()

            # Build post body with link
            full_body = f"{body}\n\n[Link]({url})"

            # Submit to subreddit
            submission = self._reddit.subreddit(self._subreddit).submit(
                title=title[:299],  # Reddit title limit
                selftext=full_body[:40000],  # Reddit post limit
            )

            return PostResult(
                platform="reddit",
                success=True,
                url=f"https://reddit.com{submission.permalink}",
                post_id=submission.id,
            )

        except Exception as e:
            return PostResult(
                platform="reddit",
                success=False,
                error=str(e),
            )
