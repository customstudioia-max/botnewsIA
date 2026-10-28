import asyncio
import logging
import argparse
import sys
import io
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Forcer l'encodage UTF-8 sur Windows
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import config
import database
from collectors import RSSCollector, GoogleNewsCollector, RedditCollector, SocialCollector
from collectors.image_extractor import extract_og_image
from services import AICurator, TelegramPublisher

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BotNewsIA")

async def run_pipeline() -> None:
    """Cycle complet : Collecte -> Dédoublonnage -> Curation IA -> Publication Telegram."""
    logger.info("=== Début du cycle de veille IA ===")

    # 1. Collecte depuis les 4 sources
    collectors = [
        RSSCollector(),
        GoogleNewsCollector(),
        RedditCollector(),
        SocialCollector()
    ]

    total_discovered = 0
    new_articles_count = 0

    for collector in collectors:
        try:
            articles = collector.fetch_news()
            total_discovered += len(articles)
            for art in articles:
                article_id = database.save_article(
                    url=art["url"],
                    title=art["title"],
                    source_type=art["source_type"],
                    source_name=art["source_name"],
                    raw_summary=art.get("raw_summary", ""),
                    image_url=art.get("image_url", ""),
                    published_at=art.get("published_at", "")
                )
                if article_id:
                    new_articles_count += 1
        except Exception as e:
            logger.error(f"Erreur avec le collecteur {collector.__class__.__name__}: {e}")

    logger.info(f"Collecte terminée : {total_discovered} articles découverts, {new_articles_count} nouveaux enregistrés.")

    # 2. Curation & Synthèse avec l'IA (Groq / Gemini)
    unprocessed = database.get_unprocessed_articles(limit=10)
    if not unprocessed:
        logger.info("Aucun nouvel article à analyser.")
        return

    curator = AICurator()
    telegram = TelegramPublisher()
    recent_titles = database.get_recent_posted_titles(limit=25)

    posts_to_publish = []

    for art in unprocessed:
        if len(posts_to_publish) >= config.MAX_POSTS_PER_RUN:
            break

        safe_title = art['title'][:60].encode('ascii', errors='ignore').decode('ascii')
        logger.info(f"Analyse IA en cours : '{safe_title}...'")
        curation = curator.evaluate_and_format(art, recent_topics=recent_titles)
        if curation:
            database.update_article_curation(
                article_id=art["id"],
                relevance_score=curation["relevance_score"],
                telegram_message=curation["telegram_message"],
                is_selected=curation["is_selected"]
            )
            if curation.get("is_duplicate"):
                logger.info("Article rejeté : doublon d'un sujet déjà publié.")
            elif curation["is_selected"] and curation["telegram_message"]:
                logger.info(f"Article retenu (score: {curation['relevance_score']}/10)")

                # Récupération de l'image de la news (du flux ou extraction directe de la page)
                image_url = art.get("image_url")
                if not image_url:
                    logger.info("Extraction de l'image de la news depuis la source...")
                    image_url = extract_og_image(art.get("url"))

                posts_to_publish.append({
                    "id": art["id"],
                    "title": art["title"],
                    "message": curation["telegram_message"],
                    "image_url": image_url,
                    "source_url": art.get("url")
                })
        # Pause légère pour respecter les quotas de l'API
        await asyncio.sleep(2)

    # 3. Publication sur Telegram
    logger.info(f"Articles qualifiés pour publication : {len(posts_to_publish)}")
    published_count = 0

    for item in posts_to_publish[:config.MAX_POSTS_PER_RUN]:
        safe_title = item['title'][:50].encode('ascii', errors='ignore').decode('ascii')
        logger.info(f"Publication sur Telegram : '{safe_title}...'")
        success = await telegram.send_news_post(
            text=item["message"],
            image_url=item.get("image_url"),
            source_url=item.get("source_url")
        )
        if success:
            database.mark_as_posted(item["id"])
            published_count += 1
            # Délai entre deux publications pour éviter le spam
            await asyncio.sleep(4)
        else:
            logger.warning(f"Échec de publication pour l'article #{item['id']}")

    logger.info(f"=== Fin du cycle : {published_count} messages publiés sur Telegram ===")

def display_status():
    """Affiche l'état des configurations et les statistiques de la base."""
    stats = database.get_stats()
    print("\n--- STATISTIQUES BOT NEWS IA (MxM Academy) ---")
    print(f"Total articles indexés : {stats['total_articles']}")
    print(f"Total messages publiés  : {stats['posted_articles']}")
    print(f"Articles en attente     : {stats['pending_articles']}")
    print("\n--- ÉTAT DE LA CONFIGURATION ---")
    print(f"Clé Telegram configurée : {'Oui' if config.TELEGRAM_BOT_TOKEN else 'Non (manquante dans .env)'}")
    print(f"Canal Telegram          : {config.TELEGRAM_CHANNEL_ID or 'Non configuré'}")
    print(f"Clé Groq (DeepSeek)     : {'Oui' if config.GROQ_API_KEY else 'Non (manquante dans .env)'}")
    print(f"Modèle Groq             : {config.GROQ_MODEL}")
    print(f"Clé Gemini (secours)    : {'Oui' if config.GEMINI_API_KEY else 'Non (optionnelle)'}")
    print(f"Fréquence de passage    : Toutes les {config.FETCH_INTERVAL_MINUTES} minutes")
    print("------------------------------------------------\n")

def test_collect():
    """Teste la collecte de toutes les sources sans appel API payant ni Telegram."""
    print("\n--- TEST DE COLLECTE SUR LES 4 SOURCES ---")
    collectors = [
        RSSCollector(),
        GoogleNewsCollector(),
        RedditCollector(),
        SocialCollector()
    ]
    for c in collectors:
        name = c.__class__.__name__
        items = c.fetch_news()
        print(f"\n[+] {name} : {len(items)} éléments récupérés")
        for i, item in enumerate(items[:3], 1):
            safe_title = item['title'][:70].encode('ascii', errors='ignore').decode('ascii')
            print(f"    {i}. {safe_title} (Source: {item['source_name']})")
    print("\n--- TEST TERMINÉ AVEC SUCCÈS ---\n")

async def main():
    parser = argparse.ArgumentParser(description="Bot de veille et curation IA pour Telegram - MxM Academy")
    parser.add_argument("--run-once", action="store_true", help="Exécute un seul cycle complet puis quitte")
    parser.add_argument("--test-collect", action="store_true", help="Teste uniquement la collecte des 4 sources")
    parser.add_argument("--status", action="store_true", help="Affiche les statistiques et l'état des configurations")
    args = parser.parse_args()

    # Initialisation de la base SQLite
    database.init_db()

    if args.status:
        display_status()
        return

    if args.test_collect:
        test_collect()
        return

    if args.run_once:
        logger.info("Exécution en mode unique (--run-once)...")
        await run_pipeline()
        return

    # Mode automatique continu avec APScheduler
    logger.info(f"Démarrage du bot en mode automatique (toutes les {config.FETCH_INTERVAL_MINUTES} minutes)...")
    
    # Exécution immédiate au démarrage
    await run_pipeline()

    # Planification des prochains cycles
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_pipeline,
        "interval",
        minutes=config.FETCH_INTERVAL_MINUTES,
        id="news_pipeline"
    )
    scheduler.start()

    # Garder la boucle active
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Arrêt du bot demandé.")
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
