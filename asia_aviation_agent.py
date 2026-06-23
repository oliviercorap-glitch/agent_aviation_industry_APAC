import os
import json
import logging
import hashlib
import requests
import time
import sys
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# --- Configuration -----------------------------------------------------------
load_dotenv()

# Dossier de logs
LOG_FILE = Path("logs/agent_apac.log")
SEEN_FILE = Path("seen_apac_articles.json")
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger(__name__)

# =============================================================================
#  MOTS-CLÉS APAC (hors Chine continentale)
# =============================================================================
KEYWORDS_GSE = [
    # GSE & ÉQUIPEMENTS
    "ground support", "gse", "tug", "tractor", "loader", "de-icer", "gpu",
    "towbar", "baggage", "passenger boarding bridge", "air start unit",
    "belt loader", "conveyor belt", "staircase", "dolly", "catering truck",
    "lavatory truck", "water truck", "apron", "ramp", "electric ground support",
    "hybrid gse", "lithium battery gse", "autonomous gse", "maintenance gse",
    "mro ground",

    # AÉROPORTS APAC
    "Tokyo Haneda", "Tokyo Narita", "Seoul Incheon", "Hong Kong International",
    "Taipei Taoyuan", "Singapore Changi", "Kuala Lumpur International",
    "Bangkok Suvarnabhumi", "Jakarta Soekarno-Hatta", "Manila Ninoy Aquino",
    "Sydney Kingsford Smith", "Melbourne Tullamarine", "Auckland International",
    "Ulaanbaatar Chinggis Khaan", "Kathmandu Tribhuvan", "Dhaka Hazrat Shahjalal",

    # COMPAGNIES AÉRIENNES CHINOISES (hors Chine)
    "Air China", "China Eastern", "China Southern", "Hainan Airlines", 
    "XiamenAir", "Shenzhen Airlines", "Sichuan Airlines", "Shandong Airlines",
    "中国国航", "国航", "中国东方航空", "东方航空", "东航",
    "中国南方航空", "南方航空", "南航", "海南航空", "海航",

    # AUTRES COMPAGNIES APAC
    "Cathay Pacific", "Hong Kong Airlines", "Korean Air", "Asiana Airlines",
    "Singapore Airlines", "Malaysia Airlines", "Thai Airways", "Vietnam Airlines",
    "Qantas", "Air New Zealand", "Fiji Airways",

    # GROUND HANDLERS
    "SATs", "dnata", "Swissport", "Menzies", "Worldwide Flight Services", "WFS",
    "Celebi", "Havas Ground Handling", "Gapura Angkasa",

    # CONCURRENTS CHINOIS (prioritaires)
    "Weihai Guangtai", "Guangtai", "威海广泰",
    "CIMC Tianda", "中集天达",
    "Jiangsu Tianyi", "Tianyi", "江苏天一",
    "Shenzhen TECHKING", "TECHKING", "深圳达航",
    "Hangfu", "航福",
    "Shanghai Jiajie", "上海嘉捷",
    "Guangzhou Jinhaoyang", "广州金浩阳",
    "Shenyang Tianhua", "沈阳天华",
    "Shandong Tianhe", "山东天河",
    "Zhejiang Goodsense", "浙江中力",

    # CONCURRENTS MONDAUX
    "TLD Group", "TLD", "Alvest", "JBT Corporation", "JBT", "Oshkosh AeroTech",
    "Textron GSE", "Textron", "Tronair", "ITW GSE", "Fast Global Solutions",
    "Mallaghan", "Goldhofer", "MULAG", "HYDRO", "Guinault", "Cavotec",

    # RÉGLEMENTATIONS & SUPPLY CHAIN
    "emission regulation", "electric ramp", "diesel ban",
    "steel price", "aluminium", "lithium", "battery cost",
    "semiconductor", "chip shortage", "supply chain disruption",
    "carbon peak",

    # GÉOPOLITIQUE
    "Belt and Road", "BRI", "tariff", "trade war", "EU tariffs",
    "APAC", "Asia Pacific",

    # TERMES GÉNÉRIQUES
    "order", "delivery", "fleet", "profit", "loss", "revenue",
    "resume flights", "grounding", "route", "new route",
    "contract", "tender", "procurement",
]

# =============================================================================
#  SOURCES (fonctionnelles)
# =============================================================================
SOURCES = [
    {
        "nom": "International Airport Review - News",
        "url": "https://www.internationalairportreview.com/news/",
        "type": "scrape_generic",
        "selector": "article h3 a, .post-title a, .entry-title a",
        "base_url": "https://www.internationalairportreview.com",
    },
    {
        "nom": "Airport Technology - News",
        "url": "https://www.airport-technology.com/news/",
        "type": "scrape_generic",
        "selector": "article h3 a, .card-title a, .post-title a",
        "base_url": "https://www.airport-technology.com",
    },
    {
        "nom": "Future Airport",
        "url": "https://www.futureairport.com/",
        "type": "scrape_generic",
        "selector": "article h2 a, .post-title a, .entry-title a",
        "base_url": "https://www.futureairport.com",
    },
    {
        "nom": "Airport World - Asia Pacific",
        "url": "https://www.airport-world.com/category/regions/asia-pacific/",
        "type": "scrape_generic",
        "selector": "article h3 a, .entry-title a",
        "base_url": "https://www.airport-world.com",
    },
    {
        "nom": "Ground Handling International",
        "url": "https://www.groundhandling.com/",
        "type": "scrape_generic",
        "selector": "article h3 a, .post-title a, a",
        "base_url": "https://www.groundhandling.com",
    },
    {
        "nom": "Aviation Pros - Ground Handling",
        "url": "https://www.aviationpros.com/ground-handling",
        "type": "scrape_generic",
        "selector": "div.article-listing a, h2.article-title a, .listing-title a",
        "base_url": "https://www.aviationpros.com",
    },
    {
        "nom": "Simple Flying - Asia",
        "url": "https://simpleflying.com/category/asia/",
        "type": "scrape_generic",
        "selector": "article h2 a, .post-title a",
        "base_url": "https://simpleflying.com",
    },
    {
        "nom": "Aviation Week - Asia",
        "url": "https://aviationweek.com/regions/asia",
        "type": "scrape_generic",
        "selector": "h3.article-title a, .node-title a",
        "base_url": "https://aviationweek.com",
    },
    {
        "nom": "Flight Global - Asia",
        "url": "https://www.flightglobal.com/asia/",
        "type": "scrape_generic",
        "selector": "article h3 a, .teaser-title a",
        "base_url": "https://www.flightglobal.com",
    },
    {
        "nom": "Reuters - Aerospace & Defense",
        "url": "https://www.reuters.com/business/aerospace-defense/",
        "type": "scrape_generic",
        "selector": "article h3 a, .story-title a",
        "base_url": "https://www.reuters.com",
    }
]

# --- FONCTIONS UTILITAIRES ---------------------------------------------------
def normaliser_url(url, base=None):
    if not url:
        return None
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url)
    url_propre = parsed._replace(query="", fragment="").geturl()
    if url_propre.endswith('/'):
        url_propre = url_propre[:-1]
    return url_propre

def charger_vus():
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def sauvegarder_vus(vus):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(vus), f, ensure_ascii=False, indent=2)

def requeter_avec_retry(url, retries=3, **kwargs):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    for i in range(retries):
        try:
            resp = requests.get(url, timeout=30, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            log.warning(f"Tentative {i+1}/{retries} échouée pour {url} : {e}")
            time.sleep(2 ** i)
    return None

def scrape_generic(source):
    articles = []
    resp = requeter_avec_retry(source["url"])
    if not resp:
        return articles
    try:
        encoding = source.get('encoding', 'utf-8')
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding=encoding)
        links = soup.select(source["selector"])
        unique_links = {}
        for link in links:
            href = link.get('href')
            titre = link.get_text(strip=True)
            if not href or not titre or len(titre) < 10:
                continue
            href = normaliser_url(href, source["base_url"])
            if href:
                unique_links[href] = titre
        for href, titre in list(unique_links.items())[:30]:
            articles.append({
                "source": source["nom"],
                "titre": titre[:150],
                "lien": href,
                "desc": "",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "id": hashlib.md5((titre + href).encode()).hexdigest(),
            })
        log.info(f"  Scraping {source['nom']}: {len(articles)} articles")
    except Exception as e:
        log.warning(f"Erreur scraping {source['nom']} : {e}")
    return articles

def collecter_tous_articles():
    tous_articles = []
    for source in SOURCES:
        log.info(f"Collecte depuis : {source['nom']}")
        articles = scrape_generic(source)
        tous_articles.extend(articles)
        time.sleep(1.5)
    log.info(f"Total articles bruts collectés: {len(tous_articles)}")
    return tous_articles

def filtrer_pertinents(articles, vus):
    nouveaux = []
    for a in articles:
        if a["id"] in vus:
            continue
        texte = (a["titre"] + " " + a.get("desc", "")).lower()
        if any(kw.lower() in texte for kw in KEYWORDS_GSE):
            nouveaux.append(a)
    log.info(f"Articles pertinents (GSE + APAC) : {len(nouveaux)}")
    return nouveaux

# --- PROMPT DEEPSEEK --------------------------------------------------------
SYSTEM_PROMPT_GSE = """Tu es un expert du marché des équipements de support au sol (GSE) en Asie-Pacifique, 
spécialisé en stratégie industrielle et supply chain. Tu conseilles le CEO d'un fabricant / loueur de GSE (TLD Group).

**PRIORITÉ ABSOLUE** :
- Accorde une attention particulière aux **activités internationales des concurrents chinois** (Weihai Guangtai, CIMC Tianda, Jiangsu Tianyi, etc.) en dehors de la Chine continentale.
- Accorde une attention particulière aux **compagnies aériennes chinoises** (Air China, China Southern, etc.) lorsqu'elles opèrent hors de Chine.

Pour chaque actualité importante, évalue l'impact concret sur :
1. Demande en équipements (tracteurs, chargeurs, passerelles, GPU)
2. Coûts des intrants (impact sur nos marges)
3. Appels d'offres et contrats de handling
4. Positionnement concurrentiel face aux challengers chinois

Ton analyse est en français, orientée décisions commerciales et industrielles.
Niveau d'impact : CRITIQUE / IMPORTANT / À SURVEILLER / INFO
"""

def analyser_avec_deepseek(articles):
    if not articles:
        return "Aucune information sectorielle significative pour la GSE aujourd'hui."

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY non définie")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    date_str = datetime.now().strftime("%d %B %Y")
    articles_txt = ""
    for i, a in enumerate(articles, 1):
        articles_txt += f"\n[{i}] Source : {a['source']}\n"
        articles_txt += f"    Titre : {a['titre']}\n"
        articles_txt += f"    Lien  : {a['lien']}\n"

    prompt = (f"Veille stratégique GSE - Asie-Pacifique (hors Chine continentale) — {date_str}\n"
              f"Nombre d'articles sélectionnés : {len(articles)}\n\n{articles_txt}\n\n"
              "Pour chaque information importante :\n"
              "1. IMPACT : CRITIQUE / IMPORTANT / À SURVEILLER / INFO\n"
              "2. RÉSUMÉ (1-2 phrases) lié au marché GSE\n"
              "3. IMPACT BUSINESS\n"
              "4. ACTION RECOMMANDÉE\n\n"
              "Termine par :\n"
              "- SYNTHÈSE EXÉCUTIVE (5 lignes max)\n"
              "- 3 INDICATEURS CLÉS À SURVEILLER\n"
              "- RISQUE PRINCIPAL")

    log.info(f"Envoi de {len(articles)} articles à DeepSeek...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": SYSTEM_PROMPT_GSE},
                      {"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        log.error(f"Erreur DeepSeek : {e}")
        return f"Erreur API: {e}"

# --- GÉNÉRATION RAPPORT ------------------------------------------------------
def generer_rapport(articles, analyse):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lignes = ["=" * 62,
              f"  VEILLE STRATÉGIQUE GSE & CONCURRENCE (APAC hors Chine) — {now}",
              "  Pour : Direction Industrielle & Commerciale", "=" * 62, "",
              f"  {len(articles)} information(s) pertinente(s)", "",
              "  SOURCES SURVEILLÉES :"]
    for s in SOURCES:
        lignes.append(f"    - {s['nom']}")
    if articles:
        lignes += ["", "-" * 62, "  ARTICLES DU JOUR", "-" * 62]
        for i, a in enumerate(articles, 1):
            lignes.append(f"\n  [{i}] {a['source']}")
            lignes.append(f"      {a['titre']}")
            if a["lien"]:
                lignes.append(f"      {a['lien']}")
    lignes += ["", "-" * 62, "  ANALYSE & RECOMMANDATIONS", "-" * 62, analyse, "", "=" * 62]
    return "\n".join(lignes)

def sauvegarder_rapport(rapport):
    dossier = Path("rapports_apac")
    dossier.mkdir(exist_ok=True, parents=True)
    fichier = dossier / f"apac_veille_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(fichier, "w", encoding="utf-8") as f:
        f.write(rapport)
    log.info(f"Rapport créé : {fichier.absolute()}")
    return fichier

# --- EXÉCUTION ---------------------------------------------------------------
def executer_agent():
    log.info("Démarrage agent veille GSE + APAC (hors Chine continentale)")
    try:
        vus = charger_vus()
        tous_articles = collecter_tous_articles()
        articles_pertinents = filtrer_pertinents(tous_articles, vus)
        analyse = analyser_avec_deepseek(articles_pertinents) if articles_pertinents else "Aucune information pertinente aujourd'hui."
        rapport = generer_rapport(articles_pertinents, analyse)
        print(rapport)
        sauvegarder_rapport(rapport)
        for a in articles_pertinents:
            vus.add(a["id"])
        sauvegarder_vus(vus)
        log.info("Terminé.")
        return True
    except Exception as e:
        log.exception(f"Erreur fatale : {e}")
        # Créer un rapport d'erreur
        dossier = Path("rapports_apac")
        dossier.mkdir(exist_ok=True, parents=True)
        fichier = dossier / f"error_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(fichier, "w", encoding="utf-8") as f:
            f.write(f"Erreur : {e}\n")
            f.write(traceback.format_exc())
        log.info(f"Rapport d'erreur créé : {fichier.absolute()}")
        return False

if __name__ == "__main__":
    # Lancer le script avec gestion d'erreur
    success = executer_agent()
    sys.exit(0 if success else 1)
