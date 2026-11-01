import os
import re
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple

import httpx
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.constants import ParseMode
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID_FREE,
    TELEGRAM_CHANNEL_ID_APPRENTICES,
    TELEGRAM_CHANNEL_ID_INVESTORS
)

logger = logging.getLogger(__name__)

TELEGRAPH_API = "https://api.telegra.ph"
CAPTION_LIMIT = 1000          # Telegram : 1024 caractères max pour la légende d'une image
MESSAGE_LIMIT = 4000          # Telegram : 4096 caractères max pour un message texte
DETAILS_SPLIT = re.compile(r"\n?\s*={2,}\s*DETAILS\s*={2,}\s*\n?", re.IGNORECASE)

# Repère les éléments Markdown (version Telegram) dans le texte rédigé par l'IA
INLINE_RE = re.compile(
    r"\[([^\]]+)\]\((https?://[^\s)]+)\)"      # [texte](lien)
    r"|`([^`\n]+)`"                             # `code`
    r"|\*([^*\n]+)\*"                           # *gras*
    r"|(?<![\w])_([^_\n]+)_(?![\w])"            # _italique_
)


# ----------------------------------------------------------------------
# Utilitaires de texte
# ----------------------------------------------------------------------
def split_summary_details(text: str) -> Tuple[str, str]:
    """Sépare le résumé (légende de l'image) du contenu détaillé (page Instant View)."""
    parts = DETAILS_SPLIT.split(text or "", maxsplit=1)
    summary = parts[0].strip()
    details = parts[1].strip() if len(parts) > 1 else ""
    return summary, details


def to_plain(text: str) -> str:
    """Retire le balisage Markdown (utilisé si Telegram refuse le formatage)."""
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"[*`]", "", text)
    text = re.sub(r"(?<![\w])_([^_\n]+)_(?![\w])", r"\1", text)
    return text


def cut(text: str, limit: int) -> str:
    """Coupe proprement un texte trop long."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0].rstrip() + "\n…"


def _inline_nodes(text: str) -> List[Any]:
    nodes: List[Any] = []
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            nodes.append(text[pos:m.start()])
        if m.group(1):
            nodes.append({"tag": "a", "attrs": {"href": m.group(2)}, "children": [m.group(1)]})
        elif m.group(3):
            nodes.append({"tag": "code", "children": [m.group(3)]})
        elif m.group(4):
            nodes.append({"tag": "b", "children": [m.group(4)]})
        elif m.group(5):
            nodes.append({"tag": "i", "children": [m.group(5)]})
        pos = m.end()
    if pos < len(text):
        nodes.append(text[pos:])
    return nodes or [text]


def markdown_to_telegraph_nodes(text: str) -> List[Dict[str, Any]]:
    """Convertit le texte de l'IA en contenu de page Telegraph (affichée en Instant View)."""
    nodes: List[Dict[str, Any]] = []
    list_items: List[Dict[str, Any]] = []
    list_tag: Optional[str] = None
    in_code = False
    code_lines: List[str] = []

    def flush_list():
        nonlocal list_items, list_tag
        if list_items:
            nodes.append({"tag": list_tag or "ul", "children": list_items})
        list_items, list_tag = [], None

    for raw in (text or "").splitlines():
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                nodes.append({"tag": "pre", "children": ["\n".join(code_lines)]})
                code_lines, in_code = [], False
            else:
                flush_list()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            flush_list()
            continue

        bullet = re.match(r"^[•\-–]\s+(.*)", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.*)", stripped)
        if bullet or numbered:
            tag = "ul" if bullet else "ol"
            if list_tag and list_tag != tag:
                flush_list()
            list_tag = tag
            content = (bullet or numbered).group(1)
            list_items.append({"tag": "li", "children": _inline_nodes(content)})
            continue

        flush_list()
        nodes.append({"tag": "p", "children": _inline_nodes(stripped)})

    if in_code and code_lines:
        nodes.append({"tag": "pre", "children": ["\n".join(code_lines)]})
    flush_list()
    return nodes


def page_title_from(summary: str) -> str:
    """Titre de la page : première ligne non vide du résumé, sans balisage."""
    for line in (summary or "").splitlines():
        clean = to_plain(line).strip()
        if clean:
            return clean[:200]
    return "AIBeacons"


# ----------------------------------------------------------------------
# Service de publication
# ----------------------------------------------------------------------
class TelegramPublisher:
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN):
        self.token = token
        self.channel_free = TELEGRAM_CHANNEL_ID_FREE
        self.channel_apprentices = TELEGRAM_CHANNEL_ID_APPRENTICES
        self.channel_investors = TELEGRAM_CHANNEL_ID_INVESTORS
        self.bot = Bot(token=self.token) if self.token else None
        self._telegraph_token: Optional[str] = os.getenv("TELEGRAPH_TOKEN", "").strip() or None

    # --- Telegraph (pages lues en Instant View) -----------------------
    async def _get_telegraph_token(self, client: httpx.AsyncClient) -> Optional[str]:
        if self._telegraph_token:
            return self._telegraph_token
        try:
            r = await client.post(
                f"{TELEGRAPH_API}/createAccount",
                json={"short_name": "AIBeacons", "author_name": "AIBeacons"}
            )
            data = r.json()
            if data.get("ok"):
                self._telegraph_token = data["result"]["access_token"]
                return self._telegraph_token
            logger.warning(f"Création du compte Telegraph refusée : {data}")
        except Exception as e:
            logger.warning(f"Création du compte Telegraph impossible : {e}")
        return None

    async def create_instant_view_page(
        self,
        summary: str,
        details: str,
        image_url: Optional[str],
        source_url: Optional[str]
    ) -> Optional[str]:
        """Crée une page Telegraph (ouverte en Instant View par Telegram) et renvoie son lien."""
        body = markdown_to_telegraph_nodes(details or summary)
        if source_url:
            body.append({
                "tag": "p",
                "children": [
                    "🔗 Source : ",
                    {"tag": "a", "attrs": {"href": source_url}, "children": ["lire l'article original"]}
                ]
            })
        title = page_title_from(summary)

        async with httpx.AsyncClient(timeout=20) as client:
            token = await self._get_telegraph_token(client)
            if not token:
                return None

            attempts = []
            if image_url:
                attempts.append([{"tag": "img", "attrs": {"src": image_url}}] + body)
            attempts.append(body)  # nouvel essai sans image si l'image est refusée

            for content in attempts:
                try:
                    r = await client.post(
                        f"{TELEGRAPH_API}/createPage",
                        json={
                            "access_token": token,
                            "title": title,
                            "author_name": "AIBeacons",
                            "content": content,
                            "return_content": False
                        }
                    )
                    data = r.json()
                    if data.get("ok"):
                        return data["result"]["url"]
                    logger.warning(f"Création de la page Telegraph refusée : {data.get('error')}")
                except Exception as e:
                    logger.warning(f"Création de la page Telegraph impossible : {e}")
        return None

    # --- Publication ---------------------------------------------------
    async def send_news_post(
        self,
        text: str,
        image_url: Optional[str] = None,
        source_url: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: str = "Canal"
    ) -> bool:
        """
        Publie une news sur le canal indiqué :
        - image de la news + résumé avec émojis en légende
        - bouton « Lire dans Telegram » (page Instant View avec le contenu détaillé)
        - bouton « Source officielle »
        Si l'image ou la page Instant View échouent, le bot se rabat sur un message plus simple.
        """
        target_channel = channel_id or self.channel_free
        if not self.bot or not target_channel:
            logger.warning(f"Publication annulée pour {channel_name} : identifiant ou token manquant.")
            return False

        summary, details = split_summary_details(text)
        if not summary:
            logger.warning(f"Publication annulée pour {channel_name} : texte vide.")
            return False

        # Page Instant View
        iv_url = await self.create_instant_view_page(summary, details, image_url, source_url)

        buttons = []
        if iv_url:
            buttons.append([InlineKeyboardButton(text="📖 Lire dans Telegram", url=iv_url)])
        if source_url:
            buttons.append([InlineKeyboardButton(text="🌐 Source officielle", url=source_url)])
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

        # 1) Image + résumé en légende
        if image_url:
            caption = cut(summary, CAPTION_LIMIT)
            for parse_mode, cap in ((ParseMode.MARKDOWN, caption), (None, to_plain(caption))):
                try:
                    await self.bot.send_photo(
                        chat_id=target_channel,
                        photo=image_url,
                        caption=cap,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )
                    logger.info(
                        f"Message publié avec succès sur {channel_name} ({'***'}) "
                        f"[image + {'Instant View' if iv_url else 'sans Instant View'}]."
                    )
                    return True
                except Exception as e:
                    logger.warning(f"Envoi avec image échoué sur {channel_name} ({parse_mode}) : {e}")

        # 2) Sans image : message texte avec aperçu du lien Instant View (ou de la source)
        preview_url = iv_url or source_url
        preview_options = None
        if preview_url:
            preview_options = LinkPreviewOptions(
                is_disabled=False,
                url=preview_url,
                prefer_large_media=True,
                show_above_text=True
            )
        body_text = cut(summary, MESSAGE_LIMIT)
        for parse_mode, content in ((ParseMode.MARKDOWN, body_text), (None, to_plain(body_text))):
            try:
                await self.bot.send_message(
                    chat_id=target_channel,
                    text=content,
                    parse_mode=parse_mode,
                    link_preview_options=preview_options,
                    reply_markup=reply_markup
                )
                logger.info(f"Message publié avec succès sur {channel_name} ({'***'}) [texte].")
                return True
            except Exception as e:
                logger.warning(f"Envoi texte échoué sur {channel_name} ({parse_mode}) : {e}")

        logger.error(f"Erreur fatale envoi Telegram vers {channel_name}.")
        return False

    async def check_connection(self) -> Dict[str, Any]:
        """Vérifie la validité du bot et les informations de compte."""
        if not self.bot:
            return {"ok": False, "error": "Token Telegram non configuré"}
        try:
            me = await self.bot.get_me()
            return {
                "ok": True,
                "bot_id": me.id,
                "bot_username": me.username,
                "first_name": me.first_name
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
