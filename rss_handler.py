import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

__all__ = ["fetch_article_text", "safe_filename"]

logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (compatible; RSSPodcastMaker/1.0)"


def fetch_article_text(url: str) -> Optional[str]:
    """
    Fetches the full text of an article from a URL, stripping HTML tags and boilerplate.

    Args:
        url: The URL of the article.

    Returns:
        The cleaned, whitespace-collapsed text content, or None if the fetch fails.
    """
    try:
        response = httpx.get(url, timeout=15, headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.extract()

        text = soup.get_text(separator=" ")
        # Collapse whitespace
        text = " ".join(text.split())
        return text
    except Exception as e:
        logger.error(f"Failed to fetch article text from {url}: {e}")
        return None


def safe_filename(name: str) -> str:
    """
    Sanitizes a string for use as a filename by removing illegal characters.

    Args:
        name: The original string (e.g., an article title).

    Returns:
        A sanitized string safe for most filesystems.
    """
    keepcharacters = (" ", ".", "_", "-")
    return "".join(c for c in name if c.isalnum() or c in keepcharacters).rstrip()
