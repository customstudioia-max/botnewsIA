import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from config import (
    GROQ_API_KEY, GROQ_MODEL,
    GEMINI_API_KEY, GEMINI_MODEL,
    MIN_RELEVANCE_SCORE, COMMUNITY_HASHTAG, LANDING_URL
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
            logger.info(f"AICurator initialisé avec Groq ({GROQ_MODEL} - AIBeacons).")
        elif GEMINI_API_KEY:
            from google import genai
            self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            self.provider = "gemini"
            logger.info(f"AICurator initialisé avec Google Gemini ({GEMINI_MODEL} - AIBeacons).")
        else:
            logger.warning("Aucune clé API IA configurée.")

    def _strip_think_tags(self, text: str) -> str:
        """Supprime les balises <think>...</think> générées par certains modèles."""
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
        et génère les 3 versions spécialisées pour AIBeacons :
        1. Canal Gratuit (Aimant & Teaser)
        2. Canal Apprentis (19,99 € - Pratique & Tuto/Prompt)
        3. Canal Investisseurs (39,99 € - Marchés & Stratégie)
        """
        if not self.provider:
            logger.error("Aucun fournisseur d'IA disponible.")
            return None

        recent_topics_str = ""
        if recent_topics:
            recent_topics_str = "\n".join(f"- {t}" for t in recent_topics[:15])

        prompt = f"""Tu es le moteur éditorial de « AIBeacons », un service d'intelligence artificielle diffusé sur 3 canaux Telegram distincts.
Pour chaque actualité IA reçue en entrée, tu dois évaluer sa pertinence et générer 3 versions adaptées aux objectifs et au prix de chaque canal.

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

3. RÉDACTION DES 3 CANAUX :

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CANAL 1 : GRATUIT (0 € / mois) — L'Aimant & Teaser
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Rôle : Informer simplement sans saturer, prouver la valeur et donner envie de passer à l'abonnement payant.
• Structure obligatoire :
  - Titre court et accrocheur avec 1 émoji.
  - Résumé en 2 ou 3 phrases simples (zéro jargon).
  - La source officielle avec lien hypertexte.
  - LE TEASER DE CONVERSION (Obligatoire) : Donne un début d'astuce ou annonce l'enjeu financier, puis bloque la suite avec un verrou 🔒 invitant à s'abonner :
    * Si la news concerne un outil ou un modèle : ajoute le teaser vers l'offre Apprentis. Exemple : "🔒 Le prompt testé prêt à copier-coller et le mini-tutoriel pas-à-pas sont disponibles dans le canal Apprentis."
    * Si la news concerne une levée de fonds ou un géant de la tech : ajoute le teaser vers l'offre Investisseurs. Exemple : "🔒 L'analyse d'impact financier et les opportunités de marché sont réservées aux membres Investisseurs."
    * Tu peux aussi mentionner les deux offres si pertinent.
  - Ajoute le bouton/lien d'abonnement : {LANDING_URL}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CANAL 2 : APPRENTIS (abonnement payant) — Pratique & Compétences
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Rôle : Former l'abonné, lui faire gagner du temps et lui donner des outils concrets à essayer immédiatement.
• Longueur : 1500 caractères maximum.
• Structure obligatoire :
  - 🎓 TITRE CLAIR + ÉTIQUETTE DE CATÉGORIE (Agents, No-Code, Prompting, Modèles).
  - 📰 En 3 points : Résumé simple de ce que fait la nouveauté (3 puces).
  - 🛠️ Comment l'essayer tout de suite : Mini-tutoriel pas-à-pas en 3 étapes numérotées.
  - 📋 Le Prompt prêt à copier-coller : Un prompt concret, optimisé et prêt à l'emploi lié à cette news (format code si pertinent).
  - 💡 Pourquoi c'est utile pour vous : Le gain de temps ou de productivité direct.
  - 🔗 Lien direct vers l'outil ou le GitHub / Source.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CANAL 3 : INVESTISSEURS (abonnement premium) — Marchés & Vision Stratégique
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Rôle : Offrir un avantage concurrentiel financier et stratégique aux décideurs et investisseurs.
• Longueur : 1500 caractères maximum.
• N'invente JAMAIS de chiffres : si l'article n'en donne pas, écris « Non communiqué ».
• Structure obligatoire :
  - 🚨 ALERTE MARCHÉ & STRATÉGIE IA : [Titre d'impact]
  - 📊 Données chiffrées : Montant de levée, valorisation, part de marché ou variation de coût d'API.
  - 🔍 Analyse d'impact :
    • Acteurs favorisés / Qui gagne
    • Acteurs disrompus ou fragilisés / Qui perd
  - 📈 Signal d'investissement & Opportunité : Ce que cela annonce pour le secteur dans les 6 à 12 mois.
  - 🛡️ Score d'impact stratégique : Note de 1 à 10 sur l'importance systémique de l'information.
  - 📑 Sources financières / dépêches officielles vérifiées.
Réponds UNIQUEMENT sous forme de JSON strict :
{{
  "is_duplicate": false,
  "relevance_score": 8,
  "is_selected": true,
  "channel_free": "texte formaté du canal gratuit",
  "channel_apprentices": "texte formaté du canal apprentis",
  "channel_investors": "texte formaté du canal investisseurs"
}}
"""

        try:
            if self.provider == "groq":
                response = self.groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "Tu es le moteur éditorial d'AIBeacons qui rédige des publications captivantes pour 3 canaux Telegram. Tu réponds UNIQUEMENT en JSON valide."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=4500,
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
                        temperature=0.3
                    )
                )
                raw_text = response.text or ""

            data = self._extract_json(raw_text)
            score = int(data.get("relevance_score", 0))
            is_dup = bool(data.get("is_duplicate", False))
            is_selected = bool(data.get("is_selected", False)) and not is_dup

            channel_free = data.get("channel_free", "").strip()
            channel_apprentices = data.get("channel_apprentices", "").strip()
            channel_investors = data.get("channel_investors", "").strip()

            # Message par défaut / fallback si l'un est vide
            telegram_message = channel_free

            return {
                "is_duplicate": is_dup,
                "relevance_score": score,
                "is_selected": is_selected,
                "telegram_message": telegram_message,
                "channel_free": channel_free,
                "channel_apprentices": channel_apprentices,
                "channel_investors": channel_investors
            }
        except Exception as e:
            logger.error(f"Erreur analyse IA ({self.provider}) pour '{article.get('title')}': {e}")
            return None
