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
#  MOTS-CLÉS APAC (hors Chine continentale)
# =============================================================================
KEYWORDS_GSE = [
    # ---------- GSE & ÉQUIPEMENTS ----------
    "ground support", "gse", "tug", "tractor", "loader", "de-icer", "gpu",
    "towbar", "baggage", "passenger boarding bridge", "air start unit",
    "belt loader", "conveyor belt", "staircase", "dolly", "catering truck",
    "lavatory truck", "water truck", "apron", "ramp", "electric ground support",
    "hybrid gse", "lithium battery gse", "autonomous gse", "maintenance gse",
    "mro ground",

    # ========== AÉROPORTS APAC (hors Chine continentale) ==========
    # Northeast Asia (incl. Mongolia, Japan, Korea, Taiwan, HK, Macau)
    "Tokyo Haneda", "Tokyo Narita", "Seoul Incheon", "Seoul Gimpo",
    "Hong Kong International", "Macau International",
    "Taipei Taoyuan", "Kaohsiung International",
    "Ulaanbaatar Chinggis Khaan", "Ulaanbaatar", "乌兰巴托", "成吉思汗国际机场",
    # Southeast Asia
    "Singapore Changi", "Kuala Lumpur International", "Bangkok Suvarnabhumi",
    "Bangkok Don Mueang", "Jakarta Soekarno-Hatta", "Denpasar Bali",
    "Manila Ninoy Aquino", "Cebu Mactan", "Ho Chi Minh Tan Son Nhat",
    "Hanoi Noi Bai", "Phuket International", "Chiang Mai International",
    "Penang International", "Langkawi International", "Kota Kinabalu",
    "Yangon International", "Mandalay International", "Naypyidaw",
    "Siem Reap Angkor", "Phnom Penh International", "Vientiane Wattay",
    "Luang Prabang", "Bandar Seri Begawan",
    # South Asia (Nepal, Bangladesh, Bhutan)
    "Kathmandu Tribhuvan", "Tribhuvan", "加德满都",
    "Dhaka Hazrat Shahjalal", "Hazrat Shahjalal", "达卡",
    "Paro International", "Paro", "帕罗",
    # Oceania
    "Sydney Kingsford Smith", "Melbourne Tullamarine", "Brisbane International",
    "Perth International", "Auckland International", "Christchurch International",
    "Wellington International", "Nadi International", "Port Moresby Jacksons",
    "Honiara International", "Port Vila Bauerfield", "Nauru International",
    # HK / Macau / Taiwan (en chinois traditionnel)
    "香港国际", "澳门国际", "台北桃园", "高雄国际",

    # ========== COMPAGNIES AÉRIENNES APAC (hors Chine continentale) ==========
    # Northeast Asia (Mongolia, Japan, Korea, Taiwan, HK, Macau)
    "Cathay Pacific", "Cathay Dragon", "HK Express", "Hong Kong Airlines",
    "Air Macau", "China Airlines", "EVA Air", "Starlux Airlines", "Tigerair Taiwan",
    "Korean Air", "Asiana Airlines", "Jeju Air", "Jin Air", "Air Busan", "T'way Air",
    "All Nippon Airways (ANA)", "Japan Airlines (JAL)", "Peach Aviation",
    "Skymark Airlines", "Solaseed Air", "Air Do", "Spring Airlines Japan",
    "MIAT Mongolian Airlines", "MIAT", "蒙古航空", "Hunnu Air",
    # Southeast Asia
    "Singapore Airlines", "Scoot", "Jetstar Asia", "Malaysia Airlines", "AirAsia",
    "AirAsia X", "Batik Air Malaysia", "Firefly", "Thai Airways", "Thai AirAsia",
    "Thai Lion Air", "Vietnam Airlines", "VietJet Air", "Bamboo Airways",
    "Philippine Airlines", "Cebu Pacific", "AirAsia Philippines", "PAL Express",
    "Garuda Indonesia", "Citilink", "Lion Air", "Batik Air Indonesia", "Indonesia AirAsia",
    "Myanmar Airways International", "Myanmar National Airlines", "Air KBZ",
    "Cambodia Angkor Air", "Lao Airlines", "Royal Brunei Airlines",
    # South Asia (Nepal, Bangladesh, Bhutan)
    "Biman Bangladesh Airlines", "US-Bangla Airlines", "Nova Air",
    "Buddha Air", "Yeti Airlines", "Himalaya Airlines", "Nepal Airlines",
    "Druk Air", "Drukair", "Bhutan Airlines", "不丹航空",
    # Oceania
    "Qantas", "QantasLink", "Virgin Australia", "Jetstar Airways", "Rex Airlines",
    "Air New Zealand", "Air Chathams", "Fiji Airways", "Nauru Airlines",
    "Air Niugini", "Solomon Airlines", "Air Vanuatu",
    # Termes génériques (en anglais principalement, car les sources sont en anglais)
    "order", "delivery", "fleet", "profit", "loss", "revenue", "net income",
    "resume flights", "grounding", "route", "new route", "bankruptcy", "restructuring",

    # ========== GROUND HANDLERS APAC ==========
    "SATs", "dnata", "Swissport", "Menzies", "Worldwide Flight Services", "WFS",
    "Celebi", "Havas Ground Handling", "Pan Asia Pacific Aviation Services",
    "Asia Airfreight Terminal", "Bangkok Flight Services", "Gapura Angkasa",
    "PT Gapura Angkasa", "Singapore新翔集团", "SATS",

    # ---------- RÉGLEMENTATIONS & SUPPLY CHAIN ----------
    "emission regulation", "electric ramp", "diesel ban",
    "steel price", "aluminium", "lithium", "battery cost",
    "semiconductor", "chip shortage", "supply chain disruption",
    "carbon peak",

    # ---------- GÉOPOLITIQUE ----------
    "Belt and Road", "BRI", "tariff", "trade war", "EU tariffs",
    "APAC", "Asia Pacific",

    # ---------- CONCURRENTS ----------
    "TLD Group", "TLD", "Alvest",
    "JBT Corporation", "JBT", "Oshkosh AeroTech", "Oshkosh",
    "Textron GSE", "Textron", "Tug Technologies", "Tronair", "ITW GSE",
    "Fast Global Solutions", "Fast Global", "WASP GSE",
    "Mallaghan", "Mallaghan Engineering", "Goldhofer", "MULAG",
    "HYDRO", "Guinault", "Cavotec", "AERO Specialties", "Aero Specialties",
    "Global Ground Support", "DOLL", "Nepean", "Gate GSE",
    "Clyde Machines", "Douglas Equipment", "Joloda Hydraroll", "CargoTec",
    "FgFlightline", "AMSS GSE", "Avia Equipment", "Teleflex Lionel-Dupont",
    "Bliss-Fox GSE", "Imai Aero-Equipment", "Toyota Industries",
    "JCB", "Jungheinrich", "Komatsu", "Cobus", "Rheinmetall",
    "Vestergaard", "Trepel", "AGSE", "Aviapartner", "Havas Ground Handling",
    "Alliance Ground International", "Watkins Aircraft Support",
    "Handiquip GSE", "MAK Controls", "Unitron", "Enersys", "RASAKTI",
    "ATEC Inc", "Wollard International", "BEUMER Group",
    "Powervamp", "Acsoon", "Velocity Airport Solutions",
    "Red Box International", "Power Systems International", "PSI",
    "GB Barberi", "Jetall GPU", "Aeromax GSE", "Current Power",
    "MRCCS", "Bertoli Power Units",
    # Chinese competitors (but they operate globally, keep them)
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
    "Alha GSE", "Shanghai Ifly", "Ifly GSE",
    # Location & Services
    "TCR Group", "TCR", "Mercury GSE", "Lufthansa Technik",
    "GE Aviation", "AFI KLM E&M", "ST Aerospace", "MTU Maintenance"
]

# =============================================================================
#  SOURCES (uniquement celles qui couvrent l'APAC hors Chine continentale)
# =============================================================================
SOURCES = [
    {
        "nom": "Ground Handling International",
        "url": "https://www.groundhandling.com/",
        "type": "scrape_generic",
        "selector": "article h3 a, .post-title a, a",
        "base_url": "https://www.groundhandling.com",
    },
    {
        "nom": "CGTN - Aviation",
        "url": "https://www.cgtn.com/",
        "type": "scrape_generic",
        "selector": "div.newsList a, a",
        "base_url": "https://www.cgtn.com",
        "encoding": "utf-8"
    },
    {
        "nom": "Orient Aviation",
        "url": "https://www.orientaviation.com/",
        "type": "scrape_generic",
        "selector": "h2.entry-title a, .post-title a",
        "base_url": "https://www.orientaviation.com",
    },
    {
        "nom": "Asian Aviation",
        "url": "https://asianaviation.com/",
        "type": "scrape_generic",
        "selector": "article h3 a, .entry-title a",
        "base_url": "https://asianaviation.com",
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
        "Accept-Language": "en-US,en;q=0.9,zh;q=0.8"
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
        for href, titre in list(unique_links.items())[:50]:
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
        articles = scrape_generic(source)  # toutes les sources sont de type générique maintenant
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
    log.info(f"Articles pertinents (GSE + APAC hors Chine) : {len(nouveaux)}")
    return nouveaux

# --- PROMPT DEEPSEEK (APAC) ------------------------------------------------
SYSTEM_PROMPT_GSE = """Tu es un expert du marché des équipements de support au sol (GSE) en Asie-Pacifique, 
spécialisé en stratégie industrielle et supply chain. Tu conseilles le CEO d'un fabricant / loueur de GSE (TLD Group).

**IMPORTANT** : Ne te limite pas aux articles parlant uniquement d'équipements. 
- Les ouvertures d'aéroports, les records de trafic, les commandes de flotte et les résultats financiers des compagnies sont des **INDICATEURS AVANCÉS** pour toute la région APAC (hors Chine continentale).
- Les annonces de tes concurrents (JBT, Textron, Guangtai, etc.) sont à analyser comme des menaces ou des opportunités.
- Traduis systématiquement ces informations en volumes d'équipements potentiels (ex: +5% de trafic à Singapour = +10 tracteurs).

Accorde une attention particulière à :
1. Les coûts des matières premières (acier, aluminium, lithium, semi-conducteurs)
2. Les fusions-acquisitions chez les handlers (Swissport, Menzies, dnata, SATs)
3. Les politiques commerciales (tarifs, Belt and Road)
4. Les réglementations environnementales en APAC

Pour chaque actualité importante, évalue l'impact concret sur :
1. Demande en équipements (tracteurs, chargeurs, passerelles, GPU)
2. Coûts des intrants (impact sur nos marges)
3. Appels d'offres et contrats de handling
4. Positionnement concurrentiel face aux challengers

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

    prompt = (f"Veille stratégique GSE - Asie-Pacifique (hors Chine) — {date_str}\n"
              f"Nombre d'articles sélectionnés : {len(articles)}\n\n{articles_txt}\n\n"
              "Pour chaque information importante :\n"
              "1. IMPACT : CRITIQUE / IMPORTANT / À SURVEILLER / INFO\n"
              "2. RÉSUMÉ (1-2 phrases) lié au marché GSE\n"
              "3. IMPACT BUSINESS (ex: hausse des coûts, opportunité de vente, menace concurrentielle)\n"
              "4. ACTION RECOMMANDÉE (contacter fournisseur, prospecter client, adapter catalogue)\n\n"
              "Termine par :\n"
              "- SYNTHÈSE EXÉCUTIVE (5 lignes max) pour le comité de direction\n"
              "- 3 INDICATEURS CLÉS À SURVEILLER cette semaine\n"
              "- RISQUE PRINCIPAL pour le marché GSE en Asie-Pacifique")

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
        return "Erreur API."

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
    except Exception as e:
        log.exception(f"Erreur fatale : {e}")

if __name__ == "__main__":
    executer_agent()
