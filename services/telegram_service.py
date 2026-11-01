import logging
import asyncio
from typing import Dict, Any, Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.constants import ParseMode
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID_FREE,
    TELEGRAM_CHANNEL_ID_APPRENTICES,
    TELEGRAM_CHANNEL_ID_INVESTORS
)

logger = logging.getLogger(__name__)

class TelegramPublisher:
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN):
        self.token = token
        self.channel_free = TELEGRAM_CHANNEL_ID_FREE
        self.channel_apprentices = TELEGRAM_CHANNEL_ID_APPRENTICES
        self.channel_investors = TELEGRAM_CHANNEL_ID_INVESTORS
        self.bot = Bot(token=self.token) if self.token else None

    async def send_news_post(
        self,
        text: str,
        image_url: Optional[str] = None,
        source_url: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: str = "Canal"
    ) -> bool:
        """
        Envoie l'annonce au format demandé sur le canal spécifié :
        - Lien bleu [Lire l'article complet](url)
        - Carte d'aperçu d'image grand format en bas
        - Bouton de redirection si disponible
        """
        target_channel = channel_id or self.channel_free
        if not self.bot or not target_channel:
            logger.warning(f"Publication annulée pour {channel_name} : identifiant ou token manquant.")
            return False

        reply_markup = None
        if source_url:
            button = InlineKeyboardButton(text="🌐 Source officielle", url=source_url)
            reply_markup = InlineKeyboardMarkup([[button]])

        preview_options = None
        if source_url:
            preview_options = LinkPreviewOptions(
                is_disabled=False,
                url=source_url,
                prefer_large_media=True,
                show_above_text=False
            )

        try:
            await self.bot.send_message(
                chat_id=target_channel,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                link_preview_options=preview_options,
                reply_markup=reply_markup
            )
            logger.info(f"Message publié avec succès sur {channel_name} ({target_channel}).")
            return True
        except Exception as e_md:
            logger.warning(f"Échec Markdown pour {channel_name} ({e_md}), essai en texte brut...")
            try:
                await self.bot.send_message(
                    chat_id=target_channel,
                    text=text,
                    link_preview_options=preview_options,
                    reply_markup=reply_markup
                )
                logger.info(f"Message publié en texte brut sur {channel_name}.")
                return True
            except Exception as e_plain:
                logger.error(f"Erreur fatale envoi Telegram vers {channel_name} : {e_plain}")
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
