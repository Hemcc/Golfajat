# ⛳ Golfajat.fi – PKS Golf Teeajat

Kerää pääkaupunkiseudun vapaat golf-teeajat automaattisesti yhdelle sivulle.  
**Täysin ilmainen** – GitHub Actions + GitHub Pages.

## Rakenne

```
golfajat/
├── .github/
│   └── workflows/
│       └── scrape.yml        ← GitHub Actions ajastus (joka 2h)
├── scraper/
│   └── scrape.py             ← Python-scraper (Playwright)
├── docs/
│   ├── index.html            ← Frontend (GitHub Pages tarjoilee)
│   └── data.json             ← Scraper kirjoittaa tähän (auto-päivittyy)
└── requirements.txt
```

## Käyttöönotto (15 min)

### 1. Luo GitHub-repo

```bash
git init golfajat
cd golfajat
# Kopioi kaikki tiedostot tähän kansioon
git add .
git commit -m "init: golf teeajat aggregaattori"
```

Luo uusi repo GitHubissa ja push:
```bash
git remote add origin https://github.com/KÄYTTÄJÄNIMI/golfajat.git
git push -u origin main
```

### 2. Kytke GitHub Pages päälle

1. Mene repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main`, kansio: `/docs`
4. Tallenna → saat osoitteen `https://KÄYTTÄJÄNIMI.github.io/golfajat`

### 3. Käynnistä scraper ensimmäisen kerran

1. Mene repo → **Actions**-välilehti
2. Valitse **Scrape Golf Teeajat**
3. Klikkaa **Run workflow** → **Run workflow**
4. Odota ~2 min → `data.json` päivittyy
5. Avaa sivustosi – data näkyy!

Tämän jälkeen scraper ajaa automaattisesti joka 2. tunti klo 06–20.

### 4. Lisää kenttä

Avaa `scraper/scrape.py` ja lisää `COURSES`-listaan:

```python
{
    "id": "uusi_kentta",
    "name": "Uuden Kentän Golf",
    "location": "Helsinki",
    "color": "#FF6600",
    "url": "https://uusikentta.nexgolf.fi/",
    "booking_url": "https://uusikentta.nexgolf.fi/",
    "system": "nexgolf",   # tai "custom"
},
```

## Paikallinen kehitys

```bash
# Asenna riippuvuudet
pip install -r requirements.txt
playwright install chromium

# Aja scraper
python scraper/scrape.py

# Testaa frontend paikallisesti
cd docs
python -m http.server 8080
# → http://localhost:8080
```

## Kuinka scraper toimii

```
GitHub Actions (cron joka 2h)
        │
        ▼
scrape.py käynnistyy
        │
        ▼
Playwright avaa headless Chromiumn
        │
        ├─→ Tapiola NexGolf  ─┐
        ├─→ Vantaan Golf     ─┤
        ├─→ Nurmijärvi       ─┤─→ Parsii teeajat + hinnat
        ├─→ Espoo Golf       ─┤
        └─→ Helsinki Masters ─┘
                │
                ▼
        docs/data.json päivittyy
                │
                ▼
        git commit + push (automaattinen)
                │
                ▼
        GitHub Pages tarjoilee uuden datan
                │
                ▼
        Käyttäjä näkee tuoreet teeajat
```

## NexGolf-huomio

NexGolf-sivustot vaativat kirjautumisen varauksen tekemiseen,
mutta **vapaiden aikojen selaaminen** on julkista. Scraper lukee
vain julkisen teeaikalistauksen.

Jos kenttä vaatii kirjautumisen jo listaukseenkin, käytä
`system: "custom"` -adapteria ja lisää kirjautumislogiikka
`scrape_custom()`-funktioon (käyttäjätunnus Secretseihin).

## Kustannukset

| Palvelu | Hinta |
|---------|-------|
| GitHub Repo | Ilmainen |
| GitHub Actions | Ilmainen (julkinen repo: rajoittamaton, yksityinen: 2000 min/kk) |
| GitHub Pages | Ilmainen |
| **Yhteensä** | **0 €/kk** |
