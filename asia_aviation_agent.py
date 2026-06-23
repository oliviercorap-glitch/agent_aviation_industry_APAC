SOURCES = [
    # 1. International Airport Review - Top stories
    {
        "nom": "International Airport Review - News",
        "url": "https://www.internationalairportreview.com/news/",
        "type": "scrape_generic",
        "selector": "article h3 a, .post-title a, .entry-title a",
        "base_url": "https://www.internationalairportreview.com",
    },
    # 2. Airport Technology - News (autre URL qui fonctionne)
    {
        "nom": "Airport Technology - News",
        "url": "https://www.airport-technology.com/news/",
        "type": "scrape_generic",
        "selector": "article h3 a, .card-title a, .post-title a",
        "base_url": "https://www.airport-technology.com",
    },
    # 3. Future Airport (excellent pour les tendances APAC)
    {
        "nom": "Future Airport",
        "url": "https://www.futureairport.com/",
        "type": "scrape_generic",
        "selector": "article h2 a, .post-title a, .entry-title a",
        "base_url": "https://www.futureairport.com",
    },
    # 4. Airport World (ACI)
    {
        "nom": "Airport World - Asia Pacific",
        "url": "https://www.airport-world.com/category/regions/asia-pacific/",
        "type": "scrape_generic",
        "selector": "article h3 a, .entry-title a",
        "base_url": "https://www.airport-world.com",
    },
    # 5. Ground Handling International (OK)
    {
        "nom": "Ground Handling International",
        "url": "https://www.groundhandling.com/",
        "type": "scrape_generic",
        "selector": "article h3 a, .post-title a, a",
        "base_url": "https://www.groundhandling.com",
    },
    # 6. Aviation Pros (fonctionne)
    {
        "nom": "Aviation Pros - Ground Handling",
        "url": "https://www.aviationpros.com/ground-handling",
        "type": "scrape_generic",
        "selector": "div.article-listing a, h2.article-title a, .listing-title a",
        "base_url": "https://www.aviationpros.com",
    },
    # 7. Simple Flying (bonne couverture APAC)
    {
        "nom": "Simple Flying - Asia",
        "url": "https://simpleflying.com/category/asia/",
        "type": "scrape_generic",
        "selector": "article h2 a, .post-title a",
        "base_url": "https://simpleflying.com",
    },
    # 8. Aviation Week Network (très complet)
    {
        "nom": "Aviation Week - Asia",
        "url": "https://aviationweek.com/regions/asia",
        "type": "scrape_generic",
        "selector": "h3.article-title a, .node-title a",
        "base_url": "https://aviationweek.com",
    },
    # 9. Flight Global (news APAC)
    {
        "nom": "Flight Global - Asia",
        "url": "https://www.flightglobal.com/asia/",
        "type": "scrape_generic",
        "selector": "article h3 a, .teaser-title a",
        "base_url": "https://www.flightglobal.com",
    },
    # 10. Reuters - Aviation (pour les nouvelles générales)
    {
        "nom": "Reuters - Aerospace & Defense",
        "url": "https://www.reuters.com/business/aerospace-defense/",
        "type": "scrape_generic",
        "selector": "article h3 a, .story-title a",
        "base_url": "https://www.reuters.com",
    }
]
