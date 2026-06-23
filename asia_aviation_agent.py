import os
import json
import logging
import hashlib
import requests
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# --- Configuration -----------------------------------------------------------
load_dotenv()
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
#  MOTS-CLÉS APAC (GSE + AÉROPORTS + COMPAGNIES + CONCURRENTS)
# =============================================================================
KEYWORDS_APAC = [
    # ---------- GSE & ÉQUIPEMENTS ----------
    "ground support", "gse", "tug", "tractor", "loader", "de-icer", "gpu",
    "towbar", "baggage", "passenger boarding bridge", "air start unit",
    "belt loader", "conveyor belt", "staircase", "dolly", "catering truck",
    "lavatory truck", "water truck", "apron", "ramp", "electric ground support",
    "hybrid gse", "lithium battery gse", "autonomous gse", "maintenance gse",
    "mro ground",

    # ---------- AÉROPORTS (APAC) ----------
    "Changi Airport", "Hong Kong International", "Suvarnabhumi",
    "Narita Airport", "Kansai Airport", "Incheon Airport",
    "Sydney Airport", "Melbourne Airport", "Brisbane Airport",
    "Auckland Airport", "Kuala Lumpur International", "Jakarta Soekarno-Hatta",
    "Manila Ninoy Aquino", "Delhi Indira Gandhi", "Mumbai Chhatrapati Shivaji",
    "airport expansion", "new runway", "terminal upgrade", "infrastructure investment",

    # ---------- COMPAGNIES AÉRIENNES (APAC) ----------
    "Singapore Airlines", "Qantas", "Japan Airlines", "All Nippon Airways",
    "AirAsia", "Scoot", "Vietnam Airlines", "Korean Air", "Cathay Pacific",
    "China Airlines", "EVA Air", "Philippine Airlines", "Garuda Indonesia",
    "Malaysia Airlines", "Thai Airways", "Air New Zealand", "IndiGo",
    "SpiceJet", "Air India", "Jetstar", "Virgin Australia",
    "fleet order", "aircraft delivery", "new routes", "passenger traffic record",

    # ---------- HANDLERS & SERVICES ----------
    "SATS", "dnata", "Swissport", "Menzies", "ground handling contract",
    "catering", "fueling", "cargo handling",

    # ---------- RÉGLEMENTATIONS (APAC) ----------
    "emission regulation", "electric ramp", "carbon neutral airport",
    "noise regulation", "curfew", "slot allocation",

    # ---------- CONCURRENTS (APAC) ----------
    # Top mondiaux déjà présents dans la version Chine, on les garde
    "TLD", "JBT", "Oshkosh", "Textron", "Tronair", "ITW GSE",
    "Fast Global", "Mallaghan", "Goldhofer", "MULAG", "HYDRO",
    "Guinault", "Cavotec", "AERO Specialties",
    # Concurrents locaux APAC
    "Weihai Guangtai", "威海广泰",
    "Shenzhen CIMC Tianda", "中集天达",
    "Guinault", "TCR",
    # Autres concurrents (à adapter)
    "GSE APAC", "APAC GSE", "Avia Equipment Pte",
]

# =============================================================================
#  SOURCES APAC (FONCTIONNELLES)
# =============================================================================
SOURCES_APAC = [
    # 1. ORIENT AVIATION (source majeure pour APAC)
    {
        "nom": "Orient Aviation",
        "url": "https://www.orientaviation.com/",
        "type": "scrape_generic",
        "selector": "h2.entry-title a, .post-title a, article h3 a",
        "base_url": "https://www.orientaviation.com",
    },
    # 2. ASIAN AVIATION
    {
        "nom": "Asian Aviation",
        "url": "https://asianaviation.com/",
        "type": "scrape_generic",
        "selector": "article h3 a, .entry-title a, .post-title a",
        "base_url": "https://asianaviation.com",
    },
    # 3. GROUND HANDLING INTERNATIONAL (section APAC)
    {
        "nom": "Ground Handling International",
        "url": "https://www.groundhandling.com/asia-pacific",
        "type": "scrape_generic",
        "selector": "article h3 a, .post-title a, a",
        "base_url": "https://www.groundhandling.com",
    },
    # 4. AIRSIDE INTERNATIONAL (couverture GSE)
    {
        "nom": "Airside International",
        "url": "https://www.airsideint.com/",
        "type": "scrape_generic",
        "selector": "div.article a, h2.article-title a, .post-title a",
        "base_url": "https://www.airsideint.com",
    },
    # 5. AEROTIME (magazine aéronautique Asie)
    {
        "nom": "Aerotime",
        "url": "https://www.aerotime.aero/",
        "type": "scrape_generic",
        "selector": "div.article a, h3 a, .post-title a",
        "base_url": "https://www.aerotime.aero",
    },
    # 6. AIRLINE ROUTES (nouvelles routes et infras)
    {
        "nom": "AirlineRoutes",
        "url": "https://www.airlineroutes.net/",
        "type": "scrape_generic",
        "selector": "div.entry a, h2 a",
        "base_url": "https://www.airlineroutes.net",
    },
    # 7. AAPA (Association of Asia Pacific Airlines) - pour les données
    {
        "nom": "AAPA",
        "url": "https://www.aapa.or.jp/",
        "type": "scrape_generic",
        "selector": "div.news a, a",
        "base_url": "https://www.aapa.or.jp",
    }
    # Vous pouvez ajouter d'autres sources comme "Airport World" ou "Changi Airport Group"
]

# --- Fonctions utilitaires (reprises de votre script Chine) ---
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
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7"
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

# --- Fonctions de scraping (générique) ---
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
            # Nettoyage des liens
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
    for source in SOURCES_APAC:
        log.info(f"Collecte APAC depuis : {source['nom']}")
        articles = scrape_generic(source)
        tous_articles.extend(articles)
        time.sleep(1.5)
    log.info(f"Total articles APAC bruts collectés: {len(tous_articles)}")
    return tous_articles

def filtrer_pertinents(articles, vus):
    nouveaux = []
    for a in articles:
        if a["id"] in vus:
            continue
        texte = (a["titre"] + " " + a.get("desc", "")).lower()
        if any(kw.lower() in texte for kw in KEYWORDS_APAC):
            nouveaux.append(a)
    log.info(f"Articles pertinents (APAC) : {len(nouveaux)}")
    return nouveaux

# --- PROMPT DEEPSEEK POUR APAC ---
SYSTEM_PROMPT_APAC = """Tu es un expert du marché des équipements de support au sol (GSE) en Asie-Pacifique (APAC), 
spécialisé en stratégie industrielle et supply chain. Tu conseilles le CEO d'un fabricant / loueur de GSE (TLD Group) pour ses activités en APAC.

**IMPORTANT** : Analyse les actualités sous l'angle de l'APAC (Singapour, Australie, Japon, Corée, Inde, ASEAN, etc.).
- Les ouvertures d'aéroports, les records de trafic, les commandes de flotte des compagnies APAC sont des indicateurs avancés.
- Les mouvements des concurrents (Weihai Guangtai, Guinault, les acteurs locaux) sont à surveiller.
- Traduis ces signaux en opportunités commerciales pour TLD dans la région.

Accorde une attention particulière à :
1. Les appels d'offres GSE dans les aéroports clés (Changi, Sydney, etc.)
2. Les réglementations environnementales (électrification, réduction de bruit)
3. Les contrats de handling remportés par SATS, dnata, Swissport, Menzies
4. Les investissements dans les infrastructures aéroportuaires

Pour chaque actualité importante, évalue l'impact sur la demande en GSE et la position concurrentielle de TLD.

Ton analyse est en français, orientée décisions commerciales et industrielles.
Niveau d'impact : CRITIQUE / IMPORTANT / À SURVEILLER / INFO
"""

def analyser_avec_deepseek(articles):
    if not articles:
        return "Aucune information significative pour l'APAC aujourd'hui."

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

    prompt = (f"Veille stratégique GSE - Asie-Pacifique — {date_str}\n"
              f"Nombre d'articles sélectionnés : {len(articles)}\n\n{articles_txt}\n\n"
              "Pour chaque information importante :\n"
              "1. IMPACT : CRITIQUE / IMPORTANT / À SURVEILLER / INFO\n"
              "2. RÉSUMÉ (1-2 phrases) lié au marché GSE APAC\n"
              "3. IMPACT BUSINESS (opportunité, menace concurrentielle, risque)\n"
              "4. ACTION RECOMMANDÉE (contacter, prospecter, ajuster)\n\n"
              "Termine par :\n"
              "- SYNTHÈSE EXÉCUTIVE (5 lignes max) pour la direction APAC\n"
              "- 3 INDICATEURS CLÉS À SURVEILLER cette semaine\n"
              "- RISQUE PRINCIPAL pour le marché GSE en APAC")

    log.info(f"Envoi de {len(articles)} articles à DeepSeek...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": SYSTEM_PROMPT_APAC},
                      {"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        log.error(f"Erreur DeepSeek : {e}")
        return "Erreur API."

# --- GÉNÉRATION RAPPORT APAC ---
def generer_rapport(articles, analyse):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lignes = ["=" * 62,
              f"  VEILLE STRATÉGIQUE GSE - ASIE-PACIFIQUE — {now}",
              "  Pour : Direction Commerciale APAC", "=" * 62, "",
              f"  {len(articles)} information(s) pertinente(s)", "",
              "  SOURCES SURVEILLÉES :"]
    for s in SOURCES_APAC:
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
    log.info(f"Rapport APAC créé : {fichier.absolute()}")

# --- EXÉCUTION ---
def executer_agent():
    log.info("Démarrage agent veille GSE APAC (version dédiée)")
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
    except Exception as e:
        log.exception(f"Erreur fatale : {e}")

if __name__ == "__main__":
    executer_agent()
