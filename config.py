import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Charger les variables d'environnement (.env si présent, sinon environnement système)
load_dotenv(BASE_DIR / ".env")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "").strip()

# Groq (DeepSeek R1 gratuit)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()

# Gemini AI (alternative)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

# Paramètres de publication
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", "30"))
MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "3"))
MIN_RELEVANCE_SCORE = int(os.getenv("MIN_RELEVANCE_SCORE", "7"))
COMMUNITY_HASHTAG = os.getenv("COMMUNITY_HASHTAG", "#MxMAcademy").strip()

# Base de données SQLite
DB_PATH = DATA_DIR / "news_bot.db"

# Sources RSS majeurs pour l'IA
RSS_FEEDS = [
    # Médias spécialisés Tech & IA
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "Ars Technica AI", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
    # Blogs officiels labos IA
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml"},
    {"name": "Google AI Blog", "url": "http://googleaiblog.blogspot.com/atom.xml"},
    # arXiv cs.AI
    {"name": "arXiv cs.AI", "url": "https://rss.arxiv.org/rss/cs.AI"},
]

# Requêtes Google News ciblées IA (FR et EN)
GOOGLE_NEWS_QUERIES = [
    {"query": "intelligence artificielle OR generative AI when:1d", "lang": "fr", "country": "FR"},
    {"query": "OpenAI OR Anthropic OR DeepSeek OR Gemini AI when:1d", "lang": "en", "country": "US"}
]

# Subreddits IA (via endpoint JSON public)
REDDIT_SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "ArtificialInteligence",
    "ChatGPT"
]

# Sources Réseaux Sociaux / Curation X
# Flux syndiqués d'actualités technologiques et IA majeurs
SOCIAL_FEEDS = [
    {"name": "HackerNews Top AI", "url": "https://hnrss.org/frontpage?q=AI+OR+LLM+OR+GPT+OR+Claude"},
    {"name": "GitHub Trending AI", "url": "https://github-trends.net/topic/artificial-intelligence/rss"}
]
