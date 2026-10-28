import logging
import urllib.parse
import feedparser
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base import BaseCollector
from config import GOOGLE_NEWS_QUERIES

logger = logging.getLogger(__name__)

class GoogleNewsCollector(BaseCollector):
    def __init__(self, queries: List[Dict[str, str]] = None):
        self.queries = queries or GOOGLE_NEWS_QUERIES

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)[:1000]

    def fetch_news(self) -> List[Dict[str, Any]]:
        articles = []
        for q_info in self.queries:
            query = q_info.get("query", "")
            lang = q_info.get("lang", "fr")
            country = q_info.get("country", "FR")
            if not query:
                continue

            encoded_query = urllib.parse.quote_plus(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}&gl={country}&ceid={country}:{lang}"

            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:8]:
                    link = getattr(entry, "link", "")
                    title = getattr(entry, "title", "").strip()
                    if not link or not title:
                        continue

                    source_name = "Google News"
                    if hasattr(entry, "source") and hasattr(entry.source, "title"):
                        source_name = f"Google News ({entry.source.title})"

                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = self._clean_html(entry.summary)

                    published = getattr(entry, "published", "")

                    articles.append({
                        "url": link,
                        "title": title,
                        "source_type": "google_news",
                        "source_name": source_name,
                        "raw_summary": summary,
                        "published_at": published
                    })
            except Exception as e:
                logger.error(f"Erreur lors de la lecture de Google News ({query}): {e}")

        logger.info(f"GoogleNewsCollector: {len(articles)} articles trouvés.")
        return articles
