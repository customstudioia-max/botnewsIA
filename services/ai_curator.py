import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from config import (
    GROQ_API_KEY, GROQ_MODEL,
    GEMINI_API_KEY, GEMINI_MODEL,
    MIN_RELEVANCE_SCORE, COMMUNITY_HASHTAG
)

logger = logging.getLogger(__name__)

class AICurator:
    def __init__(self):
        self.provider = None
        self.groq_client = None
        self.gemini_client = None

        if GROQ_API_KEY:
            from openai import OpenAI
            self.groq_client = OpenAI(
                api_key=GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1"
            )
            self.provider = "groq"
            logger.info(f"AICurator initialisé avec Groq ({GROQ_MODEL} - DeepSeek).")
        elif GEMINI_API_KEY:
            from google import genai
            self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            self.provider = "gemini"
            logger.info(f"AICurator initialisé avec Google Gemini ({GEMINI_MODEL}).")
        else:
            logger.warning("Aucune clé API IA configurée.")

    def _strip_think_tags(self, text: str) -> str:
        """Supprime les balises <think>...</think> générées par DeepSeek R1."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extrait et charge le JSON même s'il est entouré de blocs markdown."""
        cleaned = self._strip_think_tags(text)
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]

        return json.loads(cleaned)

    def evaluate_and_format(self, article: Dict[str, Any], recent_topics: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Évalue la pertinence de l'article, vérifie les doublons thématiques,
        et formate la news exactement selon le gabarit visuel Alpha News / MxM.
        """
        if not self.provider:
            logger.error("Aucun fournisseur d'IA disponible.")
            return None

        recent_topics_str = ""
        if recent_topics:
            recent_topics_str = "\n".join(f"- {t}" for t in recent_topics[:15])

        prompt = f"""Tu es un curateur et rédacteur d'actualités IA pour la communauté MxM Academy.

Voici l'article collecté :
- Titre : {article.get('title')}
- Source : {article.get('source_name')}
- Résumé / Contenu : {article.get('raw_summary', '')}
- Lien : {article.get('url')}

--- SUJETS DÉJÀ PUBLIÉS RÉCEMMENT (NE PAS RÉPÉTER) ---
{recent_topics_str or "Aucun sujet récent."}

Consignes STRICTES :
1. DÉDOUBLONNAGE : Si cet article traite du MÊME sujet ou événement qu'une des actualités déjà publiées ci-dessus, rejette-le immédiatement ("is_duplicate": true, "is_selected": false).
2. PERTINENCE : Note de 1 à 10. Ne retiens que les informations majeures, outils concrets ou annonces importantes (note >= {MIN_RELEVANCE_SCORE}).
3. EXTRACTION DU CONTENU (en français simple, direct et percutant) :
   - "title_fr": Titre accrocheur et fidèle traduit/adapté en français (1 ligne, pas de majuscules excessives).
   - "category": Domaine précis en 1 ou 2 mots (ex: "Modèles LLM", "Robotique", "Génération Vidéo", "Open Source", "Entreprises", "Recherche").
   - "impact": 1 phrase percutante qui résume le point clé ou l'impact concret pour les utilisateurs.

Réponds UNIQUEMENT sous forme de JSON valide :
{{
  "is_duplicate": <true si doublon, sinon false>,
  "relevance_score": <note de 1 à 10>,
  "is_selected": <true si relevance_score >= {MIN_RELEVANCE_SCORE} et non doublon, sinon false>,
  "title_fr": "<titre traduit/adapté en français>",
  "category": "<domaine>",
  "impact": "<impact clé en 1 phrase>"
}}
"""

        try:
            if self.provider == "groq":
                response = self.groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "Tu es un assistant qui répond exclusivement en JSON valide."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=300,
                    response_format={"type": "json_object"}
                )
                raw_text = response.choices[0].message.content or ""
            else:
                from google.genai import types
                response = self.gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                )
                raw_text = response.text or ""

            data = self._extract_json(raw_text)
            score = int(data.get("relevance_score", 0))
            is_dup = bool(data.get("is_duplicate", False))
            is_selected = bool(data.get("is_selected", False)) and not is_dup

            # Mise en page calquée sur le template demandé
            title_fr = data.get("title_fr", article.get("title", "")).strip()
            category = data.get("category", "Général").strip()
            impact = data.get("impact", "").strip()
            source_name = article.get("source_name", "Source")
            source_url = article.get("url", "")
            current_time = datetime.now().strftime("%H:%M")

            # Formatage exact du modèle :
            # 📰 NEWS IA 🟠🟠
            # 🌍 [Titre]
            # 🎯 Sujet: ...
            # 💡 Impact: ...
            # ⏰ Heure: 00:01
            # 📰 Source: ...
            # 🔗 Lire l'article complet
            # #MxMAcademy #Alertes
            # _Information et veille technologique._
            telegram_message = (
                f"📰 *NEWS IA* 🟠🟠\n\n"
                f"🌍 *{title_fr}*\n"
                f"🎯 *Sujet:* {category}\n"
                f"💡 *Impact:* {impact}\n"
                f"⏰ *Heure:* {current_time}\n"
                f"📰 *Source:* {source_name}\n\n"
                f"🔗 [Lire l'article complet]({source_url})\n\n"
                f"{COMMUNITY_HASHTAG} #Alertes #Tech\n\n"
                f"_Information et veille technologique._"
            )

            return {
                "is_duplicate": is_dup,
                "relevance_score": score,
                "is_selected": is_selected,
                "telegram_message": telegram_message
            }
        except Exception as e:
            logger.error(f"Erreur analyse IA ({self.provider}) pour '{article.get('title')}': {e}")
            return None
