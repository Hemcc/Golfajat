"""
Golf Teeajat Scraper
====================
Hakee vapaat teeajat pääkaupunkiseudun golf-kentiltä ja tallentaa
tulokset docs/data.json -tiedostoon (GitHub Pages palvelee sen).

Käyttää Playwright-kirjastoa, joka osaa käsitellä JavaScript-renderöityjä
sivuja (NexGolf, Golf.fi jne.).

Asennus paikallisesti:
    pip install playwright beautifulsoup4
    playwright install chromium

Ajaminen:
    python scraper/scrape.py
"""

import asyncio
import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

# ─── KENTTIEN KONFIGURAATIO ──────────────────────────────────────────────────
# Lisää uusi kenttä tähän listaan. Jokainen kenttä on dict jossa:
#   id        – yksilöllinen tunnus (käytetään tiedostonimissä)
#   name      – näytettävä nimi
#   location  – kaupunki / alue
#   color     – korttiväri frontendissä (#rrggbb)
#   url       – varaussivun osoite
#   system    – käytettävä scraper-adapteri (nexgolf | golffi | custom)
#   booking_url – suora varauslinkki käyttäjälle

COURSES = [
    {
        "id": "tapiola",
        "name": "Tapiolan Golf",
        "location": "Espoo",
        "color": "#2D6A4F",
        "url": "https://tapiola.nexgolf.fi/",
        "booking_url": "https://tapiola.nexgolf.fi/",
        "system": "nexgolf",
    },
    {
        "id": "vantaa",
        "name": "Vantaan Golf",
        "location": "Vantaa, Sotunki",
        "color": "#1565C0",
        "url": "https://vantaangolf.nexgolf.fi/",
        "booking_url": "https://vantaangolf.nexgolf.fi/",
        "system": "nexgolf",
    },
    {
        "id": "nurmijarvi",
        "name": "Nurmijärven Golf",
        "location": "Nurmijärvi",
        "color": "#6A1B9A",
        "url": "https://nurmijarvi.nexgolf.fi/",
        "booking_url": "https://nurmijarvi.nexgolf.fi/",
        "system": "nexgolf",
    },
    {
        "id": "espoo",
        "name": "Espoon Golfseura",
        "location": "Espoo, Bodom",
        "color": "#558B2F",
        "url": "https://espoogolf.nexgolf.fi/",
        "booking_url": "https://espoogolf.nexgolf.fi/",
        "system": "nexgolf",
    },
    {
        "id": "masters",
        "name": "Helsinki Masters Golf",
        "location": "Helsinki, Vuosaari",
        "color": "#C8380A",
        "url": "https://mastersgolf.nexgolf.fi/",
        "booking_url": "https://mastersgolf.nexgolf.fi/",
        "system": "nexgolf",
    },
    # ── Lisää kenttä esimerkki ──────────────────────────────────────────────
    # {
    #     "id": "uusi_kentta",
    #     "name": "Uuden Kentän Golf",
    #     "location": "Helsinki",
    #     "color": "#FF6600",
    #     "url": "https://uusikentta.fi/varaus",
    #     "booking_url": "https://uusikentta.fi/varaus",
    #     "system": "custom",          # ks. scrape_custom() alla
    # },
]


# ─── NEXGOLF-ADAPTERI ────────────────────────────────────────────────────────
# NexGolf on yleisin varausjärjestelmä PKS:n kentillä.
# Sivusto renderöi teeajat JavaScriptillä, joten käytetään Playwrightia.

async def scrape_nexgolf(page: Page, course: dict) -> list[dict]:
    """Scrape NexGolf-pohjainen varaussivusto."""
    slots = []
    today = date.today().strftime("%Y-%m-%d")

    try:
        await page.goto(course["url"], timeout=30_000, wait_until="networkidle")

        # NexGolf lataa teeajat AJAX-kutsulla – odotetaan että data ilmestyy
        # Kokeillaan eri selektoreita (NexGolf-versiot vaihtelevat)
        selectors = [
            ".teetime-row",
            ".tee-time-item",
            "[data-teetime]",
            ".booking-slot",
            ".available-time",
        ]

        found_selector = None
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=8_000)
                found_selector = sel
                break
            except PWTimeout:
                continue

        if not found_selector:
            print(f"  ⚠️  {course['name']}: ei löydetty tunnettua selektoria – tallennetaan tyhjä")
            return []

        # Kerätään kaikki löydetyt aikaslotit
        rows = await page.query_selector_all(found_selector)
        for row in rows:
            text = (await row.inner_text()).strip()
            slot = parse_nexgolf_row(text, course)
            if slot:
                slots.append(slot)

    except Exception as e:
        print(f"  ✗ {course['name']} virhe: {e}")

    return slots


def parse_nexgolf_row(text: str, course: dict) -> Optional[dict]:
    """Parsii yhden teeaika-rivin tekstistä."""
    # Aika: HH:MM muodossa
    time_match = re.search(r'\b(\d{1,2}:\d{2})\b', text)
    if not time_match:
        return None

    time_str = time_match.group(1)
    # Normalisoi muotoon HH:MM
    h, m = time_str.split(":")
    time_str = f"{int(h):02d}:{m}"

    # Hinta: numero + € tai EUR
    price_match = re.search(r'(\d+)[,.]?(\d*)\s*[€e]', text, re.IGNORECASE)
    price = int(price_match.group(1)) if price_match else None

    # Reiät: 9 tai 18
    holes = 18
    if re.search(r'\b9\s*(reik|hole|väylä)', text, re.IGNORECASE):
        holes = 9
    elif re.search(r'\b9\b', text):
        holes = 9

    # Pelaajat
    players_match = re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(pelaa|player)', text, re.IGNORECASE)
    players = f"{players_match.group(1)}–{players_match.group(2)} pelaajaa" if players_match else "1–4 pelaajaa"

    # Tagit
    tags = []
    hour = int(time_str.split(":")[0])
    if hour < 10:
        tags.append("morning")
    if price and price < 40:
        tags.append("cheap")
    if re.search(r'last\s*min|lastmin|viim', text, re.IGNORECASE):
        tags.append("lastmin")
        if price and price not in tags:
            tags.append("cheap")

    return {
        "time": time_str,
        "holes": holes,
        "price": price,
        "originalPrice": None,
        "players": players,
        "tags": tags,
    }


# ─── CUSTOM ADAPTERI ─────────────────────────────────────────────────────────
# Käytä tätä kentille joilla on oma varausjärjestelmä.
# Muokkaa logiikkaa kentän sivuston rakenteen mukaan.

async def scrape_custom(page: Page, course: dict) -> list[dict]:
    """Esimerkki custom-adapterin rakenteesta."""
    slots = []
    try:
        await page.goto(course["url"], timeout=30_000, wait_until="networkidle")

        # TODO: muokkaa selektorit kentän sivun HTML-rakenteen mukaan
        # Käytä selaimen DevTools → Inspect element selvittääksesi rakenne
        #
        # Esimerkki:
        # rows = await page.query_selector_all(".your-slot-class")
        # for row in rows:
        #     time_el = await row.query_selector(".time")
        #     price_el = await row.query_selector(".price")
        #     ...

        print(f"  ⚙️  {course['name']}: custom-adapteri ei ole vielä konfiguroitu")

    except Exception as e:
        print(f"  ✗ {course['name']} virhe: {e}")

    return slots


# ─── PÄÄLOGIIKKA ─────────────────────────────────────────────────────────────

async def scrape_all_courses() -> list[dict]:
    """Scrape kaikki kentät ja palauta lista kenttä-diktejä."""
    results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],  # tarvitaan GitHub Actionsissa
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fi-FI",
        )

        for course in COURSES:
            print(f"🔍 Scrapataan: {course['name']} ({course['url']})")
            page = await context.new_page()

            system = course.get("system", "nexgolf")
            if system == "nexgolf":
                slots = await scrape_nexgolf(page, course)
            elif system == "custom":
                slots = await scrape_custom(page, course)
            else:
                print(f"  ⚠️  Tuntematon system: {system}")
                slots = []

            await page.close()

            # Järjestä aikojen mukaan
            slots.sort(key=lambda s: s["time"])

            results.append({
                "id": course["id"],
                "name": course["name"],
                "location": course["location"],
                "color": course["color"],
                "url": course["booking_url"],
                "slots": slots,
                "slot_count": len(slots),
                "scraped_at": datetime.now().isoformat(),
                "scrape_ok": True,
            })

            print(f"  ✓ {len(slots)} aikaslottia löydetty")

        await browser.close()

    return results


def save_results(courses: list[dict]):
    """Tallenna tulokset docs/data.json (GitHub Pages lukee tämän)."""
    output = {
        "updated_at": datetime.now().isoformat(),
        "updated_at_display": datetime.now().strftime("%-d.%-m.%Y klo %H:%M"),
        "date": date.today().isoformat(),
        "total_slots": sum(c["slot_count"] for c in courses),
        "courses": courses,
    }

    out_path = Path(__file__).parent.parent / "docs" / "data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Tallennettu → {out_path}  ({output['total_slots']} aikaa yhteensä)")


if __name__ == "__main__":
    print("=" * 60)
    print("Golf Teeajat Scraper")
    print(f"Päivä: {date.today().strftime('%-d.%-m.%Y')}")
    print("=" * 60)
    courses = asyncio.run(scrape_all_courses())
    save_results(courses)
