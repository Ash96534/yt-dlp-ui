"""Cross-posting framework for YT-DLP WebUI announcements.

This framework posts to social platforms using official APIs with
manually created accounts. It does NOT automate account creation,
which violates most platforms' Terms of Service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class PostResult:
    """Result of a post attempt."""
    platform: str
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None
    post_id: Optional[str] = None


class BasePoster(ABC):
    """Base class for platform posters."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def post(self, title: str, body: str, url: str) -> PostResult:
        """Post content to the platform."""
        ...

    def is_configured(self) -> bool:
        """Check if the poster has valid credentials."""
        return True


@dataclass
class PostConfig:
    """Configuration for a cross-post."""
    title: str
    body: str
    url: str
    platforms: list[str]
