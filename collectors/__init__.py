from .base import BaseCollector
from .rss_collector import RSSCollector
from .google_news_collector import GoogleNewsCollector
from .reddit_collector import RedditCollector
from .social_collector import SocialCollector

__all__ = [
    "BaseCollector",
    "RSSCollector",
    "GoogleNewsCollector",
    "RedditCollector",
    "SocialCollector"
]
