from typing import Dict, Any, List
from abc import ABC, abstractmethod

class BaseCollector(ABC):
    """Classe de base pour tous les collecteurs de news."""

    @abstractmethod
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        Récupère une liste d'articles.
        Chaque article doit être un dictionnaire avec :
        - url: str
        - title: str
        - source_type: str ("rss", "google_news", "reddit", "social")
        - source_name: str (ex: "TechCrunch AI")
        - raw_summary: str (résumé brut ou extrait)
        - published_at: str (date ISO ou format texte)
        """
        pass
