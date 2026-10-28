import requests
from bs4 import BeautifulSoup
from typing import Optional
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def extract_og_image(url: str) -> Optional[str]:
    """Récupère l'image OpenGraph ou Twitter d'une page d'article."""
    if not url or not url.startswith("http"):
        return None
    try:
        response = requests.get(url, headers=HEADERS, timeout=4)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. og:image
        tag = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        if tag and tag.get("content"):
            img = tag["content"].strip()
            if img.startswith("http"):
                return img

        # 2. twitter:image
        tag = soup.find("meta", attrs={"name": "twitter:image"}) or soup.find("meta", property="twitter:image")
        if tag and tag.get("content"):
            img = tag["content"].strip()
            if img.startswith("http"):
                return img

        # 3. Première grande image dans l'article
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src.startswith("http") and not any(skip in src.lower() for skip in ["icon", "logo", "avatar", "badge"]):
                return src

    except Exception as e:
        logger.debug(f"Impossible de récupérer l'image pour {url}: {e}")

    return None
