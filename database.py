import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initialise le schéma de base de données."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                raw_summary TEXT,
                image_url TEXT,
                published_at TEXT,
                discovered_at TEXT NOT NULL,
                relevance_score INTEGER DEFAULT 0,
                is_selected INTEGER DEFAULT 0,
                telegram_message TEXT,
                posted_at TEXT
            )
        """)
        # Migration si la colonne image_url n'existait pas encore
        try:
            conn.execute("ALTER TABLE articles ADD COLUMN image_url TEXT")
        except sqlite3.OperationalError:
            pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_normalized_title ON articles(normalized_title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_posted_at ON articles(posted_at)")
        conn.commit()

def compute_hash(text: str) -> str:
    """Calcule le hash SHA256 d'une chaîne normalisée."""
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

def normalize_title(title: str) -> str:
    """Normalise un titre pour détecter les doublons entre sources différentes."""
    cleaned = "".join(c for c in title.lower() if c.isalnum() or c.isspace())
    return " ".join(cleaned.split())

def is_already_known(url: str, title: str) -> bool:
    """Vérifie si l'article ou un article avec le même titre a déjà été traité."""
    u_hash = compute_hash(url)
    t_norm = normalize_title(title)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM articles WHERE url_hash = ? OR normalized_title = ?", (u_hash, t_norm))
        return cursor.fetchone() is not None

def save_article(
    url: str,
    title: str,
    source_type: str,
    source_name: str,
    raw_summary: str = "",
    image_url: str = "",
    published_at: str = ""
) -> Optional[int]:
    """Enregistre un article s'il n'existe pas déjà."""
    if is_already_known(url, title):
        return None

    u_hash = compute_hash(url)
    t_norm = normalize_title(title)
    discovered_at = datetime.utcnow().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO articles (
                    url_hash, title, normalized_title, url, source_type,
                    source_name, raw_summary, image_url, published_at, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                u_hash, title, t_norm, url, source_type,
                source_name, raw_summary, image_url, published_at, discovered_at
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

def get_unprocessed_articles(limit: int = 30) -> List[Dict[str, Any]]:
    """Récupère les articles qui n'ont pas encore été analysés ou publiés."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, url, source_type, source_name, raw_summary, image_url, published_at
            FROM articles
            WHERE posted_at IS NULL AND relevance_score = 0
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def update_article_curation(article_id: int, relevance_score: int, telegram_message: str, is_selected: bool) -> None:
    """Met à jour l'évaluation et le texte de synthèse rédigé par l'IA."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE articles
            SET relevance_score = ?, telegram_message = ?, is_selected = ?
            WHERE id = ?
        """, (relevance_score, telegram_message, 1 if is_selected else 0, article_id))
        conn.commit()

def mark_as_posted(article_id: int) -> None:
    """Marque l'article comme publié sur Telegram."""
    posted_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE articles SET posted_at = ? WHERE id = ?", (posted_at, article_id))
        conn.commit()

def get_recent_posted_titles(limit: int = 30) -> List[str]:
    """Retourne les titres des derniers articles publiés pour éviter les doublons thématiques."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title FROM articles
            WHERE posted_at IS NOT NULL
            ORDER BY posted_at DESC
            LIMIT ?
        """, (limit,))
        return [row[0] for row in cursor.fetchall()]

def get_stats() -> Dict[str, int]:
    """Retourne les statistiques de collecte et de publication."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM articles WHERE posted_at IS NOT NULL")
        posted = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM articles WHERE posted_at IS NULL AND is_selected = 1")
        pending = cursor.fetchone()[0]

        return {
            "total_articles": total,
            "posted_articles": posted,
            "pending_articles": pending
        }
