import logging
import feedparser
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base import BaseCollector
from config import RSS_FEEDS

logger = logging.getLogger(__name__)

class RSSCollector(BaseCollector):
    def __init__(self, feeds: List[Dict[str, str]] = None):
        self.feeds = feeds or RSS_FEEDS

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)[:1000]

    def fetch_news(self) -> List[Dict[str, Any]]:
        articles = []
        for feed_info in self.feeds:
            name = feed_info.get("name", "RSS")
            url = feed_info.get("url")
            if not url:
                continue

            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:
                    link = getattr(entry, "link", "")
                    title = getattr(entry, "title", "").strip()
                    if not link or not title:
                        continue

                    # Récupération du résumé ou description
                    summary = ""
                    image_url = ""
                    raw_content = ""

                    if hasattr(entry, "content") and entry.content:
                        raw_content = entry.content[0].value
                        summary = self._clean_html(raw_content)
                    elif hasattr(entry, "summary"):
                        raw_content = entry.summary
                        summary = self._clean_html(raw_content)
                    elif hasattr(entry, "description"):
                        raw_content = entry.description
                        summary = self._clean_html(raw_content)

                    # Extraction de l'image (media_content, media_thumbnail, enclosures, ou balise img)
                    if hasattr(entry, "media_content") and entry.media_content:
                        image_url = entry.media_content[0].get("url", "")
                    elif hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                        image_url = entry.media_thumbnail[0].get("url", "")
                    elif hasattr(entry, "enclosures") and entry.enclosures:
                        for enc in entry.enclosures:
                            if enc.get("type", "").startswith("image/"):
                                image_url = enc.get("href", "")
                                break

                    # Si pas trouvé, chercher la première balise <img> dans le contenu HTML brut
                    if not image_url and raw_content:
                        soup = BeautifulSoup(raw_content, "html.parser")
                        img_tag = soup.find("img")
                        if img_tag and img_tag.get("src"):
                            image_url = img_tag["src"]

                    published = getattr(entry, "published", "") or getattr(entry, "updated", "")

                    articles.append({
                        "url": link,
                        "title": title,
                        "source_type": "rss",
                        "source_name": name,
                        "raw_summary": summary,
                        "image_url": image_url,
                        "published_at": published
                    })
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du flux RSS {name} ({url}): {e}")

        logger.info(f"RSSCollector: {len(articles)} articles trouvés.")
        return articles
