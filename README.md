# Bot Telegram d'Actualités IA - MxM Academy 🤖📰

Bot automatisé de veille, curation et diffusion des actualités clés en Intelligence Artificielle pour la communauté **MxM Academy**.

---

## 🌟 Fonctionnalités

- **4 Sources de veille en temps réel** :
  - **Flux RSS Médias IA** : TechCrunch AI, The Verge, VentureBeat, Ars Technica, arXiv, blogs officiels (OpenAI, Google AI).
  - **Google News** : Alertes thématiques IA en temps réel (FR & EN).
  - **Reddit** : Posts majeurs de r/MachineLearning, r/LocalLLaMA, r/ArtificialInteligence, r/ChatGPT.
  - **Réseaux & Tendances** : HackerNews AI, GitHub Trending AI.
- **Dédoublonnage intelligent** : Stockage SQLite avec hachage d'URL et normalisation des titres (aucun article en double).
- **Curation & Synthèse avec Gemini 1.5 Flash** :
  - Évaluation de pertinence (note de 1 à 10 pour éliminer les rumeurs et le bruit).
  - Rédaction dynamique en français structuré : Titre accrocheur, 2-3 faits marquants, impact concret, lien source et hashtags (`#MxMAcademy`).
- **Publication automatique** : Diffusion directe sur un canal Telegram avec espacement anti-spam.
- **Mode autonome** : Planificateur automatique configurable (ex: toutes les 30 minutes).

---

## 🚀 Installation & Configuration

### 1. Cloner ou ouvrir le dossier du projet
Assure-toi d'être dans le dossier du projet :
```bash
cd "BOT NEWS IA"
```

### 2. Configurer les variables d'environnement
Copie le fichier d'exemple `.env.example` en `.env` :
```bash
copy .env.example .env
```

Puis ouvre le fichier `.env` pour renseigner :
1. **`TELEGRAM_BOT_TOKEN`** : Créé en 1 minute sur Telegram auprès de [@BotFather](https://t.me/BotFather) via la commande `/newbot`.
2. **`TELEGRAM_CHANNEL_ID`** : L'identifiant de ton canal (ex: `@nom_de_ton_canal` ou son ID numérique).
   > ⚠️ **Important** : Ajoute ton bot comme **Administrateur** de ton canal avec le droit de publier des messages.
3. **`GEMINI_API_KEY`** : Ta clé d'API gratuite Google AI Studio sur [aistudio.google.com](https://aistudio.google.com/).

---

## 🛠️ Commandes utiles

Toutes les commandes s'exécutent avec l'environnement virtuel Python activé :

### Vérifier l'état et les statistiques
```bash
.venv\Scripts\python main.py --status
```

### Tester la collecte des 4 sources (sans consommer de quota IA ni poster)
```bash
.venv\Scripts\python main.py --test-collect
```

### Lancer un cycle unique complet (Collecte + Analyse IA + Publication)
```bash
.venv\Scripts\python main.py --run-once
```

### Lancer le bot en continu (toutes les X minutes)
```bash
.venv\Scripts\python main.py
```

---

## 📁 Structure du projet

```
BOT NEWS IA/
├── config.py                 # Configuration centrale et URLs des sources
├── database.py               # SQLite (dédoublonnage, historique, stats)
├── main.py                   # Orchestrateur et planificateur
├── requirements.txt          # Dépendances Python
├── .env.example              # Gabarit des variables secrètes
├── collectors/               # Modules de collecte
│   ├── base.py               # Interface abstraite
│   ├── rss_collector.py      # RSS médias & labos IA
│   ├── google_news_collector.py # Alertes Google News
│   ├── reddit_collector.py   # Reddit hot topics
│   └── social_collector.py   # HackerNews / GitHub AI
└── services/                 # Traitement & Envoi
    ├── ai_curator.py         # Analyse & rédaction avec Google Gemini
    └── telegram_service.py   # Communication Telegram
```
