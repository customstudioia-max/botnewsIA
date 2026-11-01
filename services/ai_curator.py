import os
import re
import json
import time
import logging
from typing import Dict, Any, Optional, List
from config import (
    GROQ_API_KEY, GROQ_MODEL,
    GEMINI_API_KEY, GEMINI_MODEL,
    MIN_RELEVANCE_SCORE, LANDING_URL
)

logger = logging.getLogger(__name__)

# Seuils de sélection par canal (modifiables via variables d'environnement)
# - Gratuit  : MIN_RELEVANCE_SCORE (déjà dans config.py, 7 par défaut)
# - Pro      : MIN_PRO_SCORE  (valeur pédagogique de la news, 6 par défaut)
# - VIP      : MIN_VIP_SCORE  (valeur marché / stratégie de la news, 6 par défaut)
MIN_PRO_SCORE = int(os.getenv("MIN_PRO_SCORE", "").strip() or "6")
MIN_VIP_SCORE = int(os.getenv("MIN_VIP_SCORE", "").strip() or "6")

# Limites de longueur (Telegram accepte 4096 caractères max par message)
MAX_FREE_CHARS = 900
MAX_PRO_CHARS = 2200
MAX_VIP_CHARS = 2000


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

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------
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
            cleaned = cleaned[start:end + 1]

        return json.loads(cleaned)

    def _clean_text(self, text: str, max_chars: int) -> str:
        """Nettoie une réponse texte et la coupe proprement si elle est trop longue."""
        text = self._strip_think_tags(text or "")
        # Retire un éventuel bloc ``` qui entourerait toute la réponse
        text = re.sub(r"^```[a-zA-Z]*\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rsplit("\n", 1)[0].rstrip() + "\n…"
        return text

    def _complete(self, system: str, user: str, max_tokens: int, json_mode: bool = False) -> str:
        """Appel au modèle, avec une nouvelle tentative en cas d'erreur (quota, réseau)."""
        last_error = None
        for attempt in range(2):
            try:
                if self.provider == "groq":
                    kwargs = dict(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user}
                        ],
                        temperature=0.3,
                        max_tokens=max_tokens,
                    )
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}
                    response = self.groq_client.chat.completions.create(**kwargs)
                    return response.choices[0].message.content or ""
                else:
                    from google.genai import types
                    cfg = dict(temperature=0.3, system_instruction=system)
                    if json_mode:
                        cfg["response_mime_type"] = "application/json"
                    response = self.gemini_client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=user,
                        config=types.GenerateContentConfig(**cfg)
                    )
                    return response.text or ""
            except Exception as e:
                last_error = e
                logger.warning(f"Appel IA échoué (tentative {attempt + 1}/2) : {e}")
                time.sleep(5)
        raise last_error

    @staticmethod
    def _article_block(article: Dict[str, Any]) -> str:
        return (
            f"- Titre : {article.get('title')}\n"
            f"- Source : {article.get('source_name')}\n"
            f"- Résumé / Contenu : {article.get('raw_summary', '')}\n"
            f"- Lien : {article.get('url')}"
        )

    # ------------------------------------------------------------------
    # Étape 1 : classer la news (un seul petit appel)
    # ------------------------------------------------------------------
    def _classify(self, article: Dict[str, Any], recent_topics: List[str]) -> Optional[Dict[str, Any]]:
        recent_topics_str = "\n".join(f"- {t}" for t in (recent_topics or [])[:15]) or "Aucun sujet récent."

        system = (
            "Tu es le rédacteur en chef d'AIBeacons, un service de veille sur l'intelligence artificielle. "
            "Tu réponds UNIQUEMENT avec un JSON valide."
        )
        user = f"""Voici une actualité collectée :
{self._article_block(article)}

--- SUJETS DÉJÀ PUBLIÉS RÉCEMMENT (NE PAS RÉPÉTER) ---
{recent_topics_str}

Évalue cette actualité :
1. "is_duplicate" : true si elle traite du MÊME sujet ou événement qu'un sujet déjà publié ci-dessus.
2. "relevance_score" (1 à 10) : importance générale pour le grand public intéressé par l'IA.
3. "learning_score" (1 à 10) : utilité pour quelqu'un qui APPREND à utiliser l'IA (nouvel outil utilisable maintenant, technique de prompting, tutoriel, modèle ou projet open-source à essayer, fonctionnalité concrète). Une annonce purement financière ou un article de recherche très théorique vaut peu.
4. "market_score" (1 à 10) : importance pour un INVESTISSEUR ou un décideur (levée de fonds, valorisation, acquisition, stratégie d'une grande entreprise, prix des API, régulation, puces, impact sur un secteur). Un simple tutoriel vaut peu.

Sois exigeant : réserve les notes >= 7 aux informations vraiment importantes.

Réponds UNIQUEMENT avec ce JSON :
{{"is_duplicate": false, "relevance_score": 5, "learning_score": 5, "market_score": 5}}"""

        try:
            raw = self._complete(system, user, max_tokens=1500, json_mode=True)
            data = self._extract_json(raw)
            return {
                "is_duplicate": bool(data.get("is_duplicate", False)),
                "relevance_score": int(data.get("relevance_score", 0)),
                "learning_score": int(data.get("learning_score", 0)),
                "market_score": int(data.get("market_score", 0)),
            }
        except Exception as e:
            logger.error(f"Erreur classification IA ({self.provider}) pour '{article.get('title')}': {e}")
            return None

    # ------------------------------------------------------------------
    # Étape 2 : rédiger un texte DIFFÉRENT par canal (appels séparés)
    # ------------------------------------------------------------------
    def _write_free(self, article: Dict[str, Any], teaser: str) -> str:
        if teaser == "pro":
            teaser_rule = (
                "Termine par un teaser verrouillé vers le canal AIBeacons Pro, par exemple : "
                "« 🔒 Le prompt prêt à copier-coller et le mini-tutoriel pas-à-pas sont dans AIBeacons Pro. »"
            )
        elif teaser == "vip":
            teaser_rule = (
                "Termine par un teaser verrouillé vers le canal VIP Investisseurs, par exemple : "
                "« 🔒 L'analyse d'impact et les opportunités de marché sont réservées aux membres VIP. »"
            )
        else:
            teaser_rule = (
                "Termine par une phrase qui invite à rejoindre les canaux payants "
                "(AIBeacons Pro pour apprendre, VIP pour les analyses de marché)."
            )

        system = "Tu rédiges des publications Telegram courtes et claires en français."
        user = f"""Rédige la publication du CANAL GRATUIT d'AIBeacons à partir de cette actualité :
{self._article_block(article)}

Rôle : informer simplement, prouver la valeur du service et donner envie de s'abonner.
Structure obligatoire :
- Un titre court et accrocheur avec 1 émoji, en gras (*Titre*).
- Un résumé en 2 ou 3 phrases simples, sans jargon.
- La source avec un lien : [Nom de la source](lien).
- {teaser_rule}
- Une dernière ligne : 👉 S'abonner : {LANDING_URL}

Règles : {MAX_FREE_CHARS} caractères maximum. N'invente aucun fait ni chiffre absent de l'actualité.
Format Telegram : *gras* avec un seul astérisque, _italique_, [texte](lien). Pas de titres avec #.
Réponds uniquement avec le texte de la publication, sans introduction ni commentaire."""
        try:
            return self._clean_text(self._complete(system, user, max_tokens=2500), MAX_FREE_CHARS)
        except Exception as e:
            logger.error(f"Erreur rédaction canal Gratuit : {e}")
            return ""

    def _write_pro(self, article: Dict[str, Any]) -> str:
        system = "Tu es un formateur en IA qui rédige des publications Telegram pratiques en français."
        user = f"""Rédige la publication du CANAL AIBEACONS PRO (abonnés qui veulent APPRENDRE et utiliser l'IA) à partir de cette actualité :
{self._article_block(article)}

Structure obligatoire :
🎓 *TITRE CLAIR* — [Catégorie : Agents, No-Code, Prompting, Modèles ou Outils]

📰 *En 3 points*
• point 1
• point 2
• point 3

🛠️ *Comment l'essayer tout de suite*
1. étape 1
2. étape 2
3. étape 3

📋 *Prompt prêt à copier-coller*
Un prompt concret lié à cette actualité, entre accents graves (`...`).

💡 *Pourquoi c'est utile* : le gain de temps ou de productivité direct, en une phrase.

🔗 Source : [Nom](lien)

Règles : {MAX_PRO_CHARS} caractères maximum. Reste fidèle à l'actualité : n'invente aucune fonctionnalité, aucun prix, aucune étape qui n'existe pas. Si l'actualité ne permet pas un vrai tutoriel, propose une manière concrète d'exploiter l'information sans prétendre qu'un outil fait ce qu'il ne fait pas.
Format Telegram : *gras* avec un seul astérisque, _italique_, `code`, [texte](lien). Pas de titres avec #.
Réponds uniquement avec le texte de la publication, sans introduction ni commentaire."""
        try:
            return self._clean_text(self._complete(system, user, max_tokens=3000), MAX_PRO_CHARS)
        except Exception as e:
            logger.error(f"Erreur rédaction canal Pro : {e}")
            return ""

    def _write_vip(self, article: Dict[str, Any]) -> str:
        system = "Tu es un analyste qui rédige des notes de marché Telegram concises en français."
        user = f"""Rédige la publication du CANAL VIP INVESTISSEURS (décideurs et investisseurs) à partir de cette actualité :
{self._article_block(article)}

Structure obligatoire :
🚨 *ALERTE MARCHÉ IA* : titre d'impact

📊 *Données clés* : montants, valorisation, part de marché ou variation de prix, uniquement s'ils figurent dans l'actualité. Sinon écris « Non communiqué ».

🔍 *Analyse d'impact*
• Qui gagne : ...
• Qui est fragilisé : ...

📈 *Signal & opportunité* : ce que cela annonce pour le secteur dans les 6 à 12 mois, présenté comme une analyse et non comme une certitude.

🛡️ *Importance stratégique* : X/10

📑 Source : [Nom](lien)

Règles : {MAX_VIP_CHARS} caractères maximum. N'invente JAMAIS de chiffres ni de faits absents de l'actualité. Ceci est une analyse d'information, pas un conseil d'investissement personnalisé.
Format Telegram : *gras* avec un seul astérisque, _italique_, [texte](lien). Pas de titres avec #.
Réponds uniquement avec le texte de la publication, sans introduction ni commentaire."""
        try:
            return self._clean_text(self._complete(system, user, max_tokens=3000), MAX_VIP_CHARS)
        except Exception as e:
            logger.error(f"Erreur rédaction canal VIP : {e}")
            return ""

    # ------------------------------------------------------------------
    # Point d'entrée utilisé par main.py
    # ------------------------------------------------------------------
    def evaluate_and_format(self, article: Dict[str, Any], recent_topics: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Classe la news puis rédige, pour chaque canal concerné, un texte qui lui est propre :
        - Gratuit : news importantes (score général >= MIN_RELEVANCE_SCORE) + teaser vers les canaux payants
        - Pro     : news utiles pour apprendre (learning_score >= MIN_PRO_SCORE)
        - VIP     : news marché / stratégie (market_score >= MIN_VIP_SCORE)
        Un canal dont la news ne correspond pas reçoit une chaîne vide et est ignoré par main.py.
        """
        if not self.provider:
            logger.error("Aucun fournisseur d'IA disponible.")
            return None

        info = self._classify(article, recent_topics)
        if info is None:
            return None

        is_dup = info["is_duplicate"]
        general = info["relevance_score"]
        learning = info["learning_score"]
        market = info["market_score"]

        free_ok = (not is_dup) and general >= MIN_RELEVANCE_SCORE
        pro_ok = (not is_dup) and learning >= MIN_PRO_SCORE
        vip_ok = (not is_dup) and market >= MIN_VIP_SCORE

        channel_free = channel_pro = channel_vip = ""

        if pro_ok:
            time.sleep(1)
            channel_pro = self._write_pro(article)
        if vip_ok:
            time.sleep(1)
            channel_vip = self._write_vip(article)
        if free_ok:
            if pro_ok and (not vip_ok or learning >= market):
                teaser = "pro"
            elif vip_ok:
                teaser = "vip"
            else:
                teaser = "both"
            time.sleep(1)
            channel_free = self._write_free(article, teaser)

        is_selected = bool(channel_free or channel_pro or channel_vip)
        telegram_message = channel_free or channel_pro or channel_vip

        logger.info(
            f"Notes : général={general}, apprentissage={learning}, marché={market} -> "
            f"gratuit={'oui' if channel_free else 'non'}, "
            f"pro={'oui' if channel_pro else 'non'}, "
            f"vip={'oui' if channel_vip else 'non'}"
        )

        return {
            "is_duplicate": is_dup,
            "relevance_score": max(general, learning, market),
            "is_selected": is_selected,
            "telegram_message": telegram_message,
            "channel_free": channel_free,
            "channel_apprentices": channel_pro,
            "channel_investors": channel_vip
        }
