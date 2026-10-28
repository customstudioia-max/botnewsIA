import logging
import asyncio
from typing import Dict, Any, Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logger = logging.getLogger(__name__)

class TelegramPublisher:
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN, channel_id: str = TELEGRAM_CHANNEL_ID):
        self.token = token
        self.channel_id = channel_id
        self.bot = Bot(token=self.token) if self.token else None

    async def send_news_post(self, text: str, image_url: Optional[str] = None, source_url: Optional[str] = None) -> bool:
        """
        Envoie l'annonce au format exact du modèle demandé :
        - En-tête 📰 NEWS IA 🟠🟠
        - Titre + Sujet + Impact + Heure + Source
        - Lien bleu [Lire l'article complet](url)
        - Carte d'aperçu d'image grand format EN BAS (show_above_text=False)
        - Bouton cliquable direct
        """
        if not self.bot or not self.channel_id:
            logger.error("Token Telegram ou Channel ID manquant. Impossible de publier.")
            return False

        # Bouton optionnel de redirection
        reply_markup = None
        if source_url:
            button = InlineKeyboardButton(text="🌐 Lire l'article complet", url=source_url)
            reply_markup = InlineKeyboardMarkup([[button]])

        # Configuration de l'aperçu de lien grand format en dessous du texte (comme sur la capture)
        preview_options = None
        if source_url:
            preview_options = LinkPreviewOptions(
                is_disabled=False,
                url=source_url,
                prefer_large_media=True,
                show_above_text=False
            )

        # 1. Envoi en Markdown avec aperçu d'image en bas
        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                link_preview_options=preview_options,
                reply_markup=reply_markup
            )
            logger.info("Message Telegram envoyé avec succès (Markdown + carte visuelle en bas).")
            return True
        except Exception as e_md:
            logger.warning(f"Échec envoi Markdown ({e_md}), tentative en texte brut...")
            try:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                    link_preview_options=preview_options,
                    reply_markup=reply_markup
                )
                logger.info("Message Telegram envoyé avec succès (texte brut + carte visuelle).")
                return True
            except Exception as e_plain:
                logger.error(f"Erreur fatale lors de l'envoi Telegram : {e_plain}")
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
