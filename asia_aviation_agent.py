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
LOG_FILE = Path("logs/agent_gse.log")
SEEN_FILE = Path("seen_gse_articles.json")
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger(__name__)

# =============================================================================
#  MOTS-CLÉS APAC (périmètre final)
# =============================================================================
KEYWORDS_GSE = [
    # ---------- GSE & ÉQUIPEMENTS ----------
    "ground support", "gse", "tug", "tractor", "loader", "de-icer", "gpu",
    "towbar", "baggage", "passenger boarding bridge", "air start unit",
    "belt loader", "conveyor belt", "staircase", "dolly", "catering truck",
    "lavatory truck", "water truck", "apron", "ramp", "electric ground support",
    "hybrid gse", "lithium battery gse", "autonomous gse", "maintenance gse",
    "mro ground",
    "地勤设备", "地面支持设备", "行李拖车", "客梯车", "电源车", "气源车",
    "除冰车", "装载机", "传送带车", "飞机牵引车", "新能源地勤", "电动地勤",

    # ========== AÉROPORTS APAC ==========
    # Northeast Asia (incl. Mongolia)
    "Tokyo Haneda", "Tokyo Narita", "Seoul Incheon", "Seoul Gimpo", "Beijing Capital",
    "Beijing Daxing", "Shanghai Pudong", "Shanghai Hongqiao", "Guangzhou Baiyun",
    "Shenzhen Bao'an", "Hong Kong International", "Macau International",
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
    # Chinois (Chine)
    "北京首都", "北京大兴", "上海浦东", "上海虹桥", "广州白云", "深圳宝安",
    "成都天府", "重庆江北", "西安咸阳", "杭州萧山", "昆明长水", "厦门高崎",
    "南京禄口", "武汉天河", "长沙黄花", "郑州新郑", "青岛胶东", "海口美兰",
    "三亚凤凰", "大连周水子", "沈阳桃仙", "哈尔滨太平", "乌鲁木齐地窝堡",
    "香港国际", "澳门国际", "台北桃园", "高雄国际",

    # ========== COMPAGNIES AÉRIENNES APAC ==========
    # Northeast Asia (incl. Mongolia)
    "Air China", "China Eastern", "China Southern", "Hainan Airlines", "Beijing Capital Airlines",
    "Shanghai Airlines", "XiamenAir", "Shenzhen Airlines", "Sichuan Airlines", "Shandong Airlines",
    "Juneyao Air", "Spring Airlines", "China United Airlines", "Cathay Pacific", "Cathay Dragon",
    "HK Express", "Hong Kong Airlines", "Air Macau", "China Airlines", "EVA Air",
    "Starlux Airlines", "Tigerair Taiwan", "Korean Air", "Asiana Airlines", "Jeju Air",
    "Jin Air", "Air Busan", "T'way Air", "All Nippon Airways (ANA)", "Japan Airlines (JAL)",
    "Peach Aviation", "Skymark Airlines", "Solaseed Air", "Air Do", "Spring Airlines Japan",
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
    # Chinois (Chine)
    "中国国航", "国航", "中国东方航空", "东方航空", "东航",
    "中国南方航空", "南方航空", "南航", "海南航空", "海航",
    "厦门航空", "厦航", "深圳航空", "深航", "春秋航空", "春秋",
    "吉祥航空", "吉祥", "四川航空", "川航", "山东航空", "山航",
    "北京首都航空", "上海航空", "香港国泰航空", "国泰航空",
    "香港航空", "澳门航空", "中华航空", "长荣航空",
    "大韩航空", "韩亚航空", "济州航空", "真航空",
    "全日空", "日本航空", "新加坡航空", "马来西亚航空",
    "泰国航空", "越南航空", "菲律宾航空", "宿务太平洋航空",
    "印尼鹰航", "澳洲航空", "新西兰航空",
    # Termes génériques
    "订购", "交付", "机队", "盈利", "亏损", "营收", "净利润",
    "复航", "停飞", "航线", "新开航线", "恢复", "破产", "重组",

    # ========== GROUND HANDLERS APAC ==========
    "SATs", "dnata", "Swissport", "Menzies", "Worldwide Flight Services", "WFS",
    "Celebi", "Havas Ground Handling", "Pan Asia Pacific Aviation Services",
    "Asia Airfreight Terminal", "Beijing CAH SATS Aviation Services",
    "Bangkok Flight Services", "Gapura Angkasa", "PT Gapura Angkasa",
    "新加坡新翔集团", "SATS", "北京空港航空地面服务", "BGS",

    # ---------- RÉGLEMENTATIONS & SUPPLY CHAIN ----------
    "emission regulation", "electric ramp", "diesel ban",
    "steel price", "aluminium", "lithium", "battery cost",
    "semiconductor", "chip shortage", "supply chain disruption",
    "碳中和机场", "电动化", "柴油车禁行", "carbon peak",

    # ---------- GÉOPOLITIQUE ----------
    "Belt and Road", "BRI", "tariff", "trade war", "EU tariffs",
    "一带一路", "关税", "APAC", "Asia Pacific",

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
    # Chinese competitors
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
#  SOURCES (fonctionnelles + sources APAC)
# =============================================================================
SOURCES = [
    {
        "nom": "Bidcenter (Chine - Appels d'offres)",
        "url": "https://www.bidcenter.com.cn",
        "type": "scrape_bidcenter",
        "base_url": "https://www.bidcenter.com.cn",
        "encoding": "utf-8"
    },
    {
        "nom": "China Airport News",
        "url": "http://fuwu.caacnews.com.cn/1/5/index.html",
        "type": "scrape_generic",
        "selector": "div.newsList ul li a, .list li a, a",
        "base_url": "http://fuwu.caacnews.com.cn",
        "encoding": "utf-8"
    },
    {
        "nom": "CARNOC.com (China)",
        "url": "https://www.carnoc.com/",
        "type": "scrape_generic",
        "selector": "div.news_list a, .article_list a, a",
        "base_url": "https://www.carnoc.com",
        "encoding": "utf-8"
    },
    {
        "nom": "CAAC News (China)",
        "url": "http://www.caac.gov.cn/PHONE/ZTZL/",
        "type": "scrape_caac",
        "base_url": "http://www.caac.gov.cn"
    },
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
        "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3"
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

def scrape_caac(source):
    articles = []
    resp = requeter_avec_retry(source["url"])
    if not resp:
        return articles
    try:
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding='utf-8')
        links = soup.find_all('a', href=True)
        for link in links[:15]:
            titre = link.get_text(strip=True)
            if not titre or len(titre) < 10:
                continue
            href = link.get('href')
            if href:
                href = normaliser_url(href, source["base_url"])
            if titre and href:
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
        log.warning(f"Erreur parsing {source['nom']} : {e}")
    return articles

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

def scrape_bidcenter(source):
    articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bidcenter.com.cn/",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    resp = requeter_avec_retry(source["url"], headers=headers)
    if not resp:
        return articles
    try:
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding='utf-8')
        links = soup.select('div.tender_list a, ul.tender-list a, .gg_list a, table a, .list-item a')
        if not links:
            links = soup.find_all('a', href=True)
        unique_links = {}
        for link in links:
            href = link.get('href')
            titre = link.get_text(strip=True)
            if not href or not titre or len(titre) < 8:
                continue
            mots_exclus = ['首页', '上一页', '下一页', '末页', '登录', '注册', '发布', '搜索']
            if any(mot in titre for mot in mots_exclus):
                continue
            href = normaliser_url(href, source["base_url"])
            if href and 'bidcenter.com.cn' in href:
                unique_links[href] = titre
        for href, titre in list(unique_links.items())[:40]:
            articles.append({
                "source": source["nom"],
                "titre": titre[:150],
                "lien": href,
                "desc": "",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "id": hashlib.md5((titre + href).encode()).hexdigest(),
            })
        log.info(f"  Scraping {source['nom']}: {len(articles)} appels d'offres")
    except Exception as e:
        log.warning(f"Erreur scraping {source['nom']} : {e}")
    return articles

def collecter_tous_articles():
    tous_articles = []
    for source in SOURCES:
        log.info(f"Collecte depuis : {source['nom']}")
        if source["type"] == "scrape_caac":
            articles = scrape_caac(source)
        elif source["type"] == "scrape_bidcenter":
            articles = scrape_bidcenter(source)
        else:
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

# --- PROMPT DEEPSEEK (APAC) ------------------------------------------------
SYSTEM_PROMPT_GSE = """Tu es un expert du marché des équipements de support au sol (GSE) en Asie-Pacifique, 
spécialisé en stratégie industrielle et supply chain. Tu conseilles le CEO d'un fabricant / loueur de GSE (TLD Group).

**IMPORTANT** : Ne te limite pas aux articles parlant uniquement d'équipements. 
- Les ouvertures d'aéroports, les records de trafic, les commandes de flotte et les résultats financiers des compagnies sont des **INDICATEURS AVANCÉS** pour toute la région APAC.
- Les annonces de tes concurrents (JBT, Textron, Guangtai, etc.) sont à analyser comme des menaces ou des opportunités.
- Traduis systématiquement ces informations en volumes d'équipements potentiels (ex: +5% de trafic à Singapour = +10 tracteurs).

Accorde une attention particulière à :
1. Les coûts des matières premières (acier, aluminium, lithium, semi-conducteurs)
2. Les fusions-acquisitions chez les handlers (Swissport, Menzies, dnata, SATs)
3. Les politiques commerciales (tarifs, Belt and Road)
4. Les réglementations environnementales en Chine et en APAC

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

    prompt = (f"Veille stratégique GSE - Asie-Pacifique — {date_str}\n"
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
              f"  VEILLE STRATÉGIQUE GSE & CONCURRENCE (APAC) — {now}",
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
    dossier = Path("rapports")
    dossier.mkdir(exist_ok=True, parents=True)
    fichier = dossier / f"gse_veille_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(fichier, "w", encoding="utf-8") as f:
        f.write(rapport)
    log.info(f"Rapport créé : {fichier.absolute()}")

# --- EXÉCUTION ---------------------------------------------------------------
def executer_agent():
    log.info("Démarrage agent veille GSE + APAC (périmètre final)")
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
