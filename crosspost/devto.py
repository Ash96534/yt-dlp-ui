"""Dev.to poster using Dev.to API.

Requires:
    pip install requests

Environment variables:
    DEVTO_API_KEY

Setup:
    1. Create account at dev.to/signup (manually)
    2. Go to dev.to/settings/api_keys
    3. Create an API key
    4. Copy the API key
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from . import PostResult, BasePoster


class DevToPoster(BasePoster):
    """Dev.to poster using Dev.to API."""

    def __init__(self):
        super().__init__("devto")
        self.base_url = "https://dev.to/api"

    def is_configured(self) -> bool:
        """Check if Dev.to API key is configured."""
        return bool(os.environ.get("DEVTO_API_KEY"))

    def post(self, title: str, body: str, url: str) -> PostResult:
        """Post to Dev.to."""
        if not self.is_configured():
            return PostResult(
                platform="devto",
                success=False,
                error="Dev.to API key not configured",
            )

        try:
            # Dev.to article payload
            payload = {
                "title": title[:255],  # Dev.to title limit
                "body": f"{body}\n\n[Read more]({url})",
                "published": True,
                "tags": ["youtube", "yt-dlp", "python", "desktop-app", "opensource"],
            }

            headers = {
                "Content-Type": "application/json",
                "api-key": os.environ["DEVTO_API_KEY"],
            }

            response = requests.post(
                f"{self.base_url}/articles",
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 201:
                data = response.json()
                return PostResult(
                    platform="devto",
                    success=True,
                    url=data.get("url", ""),
                    post_id=str(data.get("id", "")),
                )
            else:
                return PostResult(
                    platform="devto",
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                )

        except Exception as e:
            return PostResult(
                platform="devto",
                success=False,
                error=str(e),
            )
