import logging
import feedparser
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base import BaseCollector
from config import SOCIAL_FEEDS

logger = logging.getLogger(__name__)

class SocialCollector(BaseCollector):
    def __init__(self, feeds: List[Dict[str, str]] = None):
        self.feeds = feeds or SOCIAL_FEEDS

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)[:1000]

    def fetch_news(self) -> List[Dict[str, Any]]:
        articles = []
        for feed_info in self.feeds:
            name = feed_info.get("name", "Social")
            url = feed_info.get("url")
            if not url:
                continue

            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:8]:
                    link = getattr(entry, "link", "")
                    title = getattr(entry, "title", "").strip()
                    if not link or not title:
                        continue

                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = self._clean_html(entry.summary)
                    elif hasattr(entry, "description"):
                        summary = self._clean_html(entry.description)

                    published = getattr(entry, "published", "")

                    articles.append({
                        "url": link,
                        "title": title,
                        "source_type": "social",
                        "source_name": name,
                        "raw_summary": summary,
                        "published_at": published
                    })
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du flux social {name} ({url}): {e}")

        logger.info(f"SocialCollector: {len(articles)} posts sociaux trouvés.")
        return articles
