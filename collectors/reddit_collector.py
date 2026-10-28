import logging
import feedparser
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base import BaseCollector
from config import REDDIT_SUBREDDITS

logger = logging.getLogger(__name__)

class RedditCollector(BaseCollector):
    def __init__(self, subreddits: List[str] = None):
        self.subreddits = subreddits or REDDIT_SUBREDDITS
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)[:1000]

    def fetch_news(self) -> List[Dict[str, Any]]:
        articles = []
        for sub in self.subreddits:
            rss_url = f"https://www.reddit.com/r/{sub}/hot/.rss?limit=15"
            try:
                feed = feedparser.parse(rss_url, request_headers=self.headers)
                for entry in feed.entries[:8]:
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "")
                    if not link or not title:
                        continue

                    # Ignorer les megathreads hebdomadaires ou de promotion
                    lower_title = title.lower()
                    if "self-promotion thread" in lower_title or "weekly discussion" in lower_title:
                        continue

                    summary = ""
                    image_url = ""
                    raw_content = ""

                    if hasattr(entry, "content") and entry.content:
                        raw_content = entry.content[0].value
                        summary = self._clean_html(raw_content)
                    elif hasattr(entry, "summary"):
                        raw_content = entry.summary
                        summary = self._clean_html(raw_content)

                    # Chercher une image dans le flux Reddit
                    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                        image_url = entry.media_thumbnail[0].get("url", "")
                    elif raw_content:
                        soup = BeautifulSoup(raw_content, "html.parser")
                        img_tag = soup.find("img")
                        if img_tag and img_tag.get("src"):
                            image_url = img_tag["src"]

                    published = getattr(entry, "updated", "") or getattr(entry, "published", "")

                    articles.append({
                        "url": link,
                        "title": title,
                        "source_type": "reddit",
                        "source_name": f"Reddit r/{sub}",
                        "raw_summary": summary,
                        "image_url": image_url,
                        "published_at": published
                    })
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du flux RSS Reddit r/{sub}: {e}")

        logger.info(f"RedditCollector: {len(articles)} posts trouvés.")
        return articles
