"""Twitter/X poster using tweepy (Twitter API v2).

Requires:
    pip install tweepy

Environment variables:
    TWITTER_API_KEY
    TWITTER_API_SECRET
    TWITTER_ACCESS_TOKEN
    TWITTER_ACCESS_TOKEN_SECRET

Setup:
    1. Create account at twitter.com/i/flow/signup (manually)
    2. Go to developer.twitter.com
    3. Create a Project and App
    4. Generate Access Token and Secret
    5. Copy API Key, API Secret, Access Token, Access Token Secret
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    import tweepy
except ImportError:
    tweepy = None

from . import PostResult, BasePoster


class TwitterPoster(BasePoster):
    """Twitter/X poster using API v2."""

    def __init__(self):
        super().__init__("twitter")
        self._client = None

    def is_configured(self) -> bool:
        """Check if Twitter credentials are configured."""
        if tweepy is None:
            return False
        return all(
            os.environ.get(k)
            for k in [
                "TWITTER_API_KEY",
                "TWITTER_API_SECRET",
                "TWITTER_ACCESS_TOKEN",
                "TWITTER_ACCESS_TOKEN_SECRET",
            ]
        )

    def _init_client(self):
        """Initialize tweepy Client."""
        if self._client is None:
            self._client = tweepy.Client(
                consumer_key=os.environ["TWITTER_API_KEY"],
                consumer_secret=os.environ["TWITTER_API_SECRET"],
                access_token=os.environ["TWITTER_ACCESS_TOKEN"],
                access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
            )

    def post(self, title: str, body: str, url: str) -> PostResult:
        """Post to Twitter/X."""
        if not self.is_configured():
            return PostResult(
                platform="twitter",
                success=False,
                error="Twitter credentials not configured",
            )

        try:
            self._init_client()

            # Twitter/X has 280 character limit
            # Construct tweet: title + URL (URLs count as 23 chars regardless of length)
            text = f"{title}\n\n{body}\n\n{url}"

            # Truncate if too long
            if len(text) > 275:
                # Cut body to fit
                available = 275 - len(title) - len(url) - 4  # 4 for newlines
                body = body[: max(0, available)] + "..."
                text = f"{title}\n\n{body}\n\n{url}"

            response = self._client.create_tweet(text=text)

            tweet_id = response.data["id"]
            tweet_url = f"https://twitter.com/i/status/{tweet_id}"

            return PostResult(
                platform="twitter",
                success=True,
                url=tweet_url,
                post_id=tweet_id,
            )

        except Exception as e:
            return PostResult(
                platform="twitter",
                success=False,
                error=str(e),
            )
