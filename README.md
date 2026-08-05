# Hlídač uvolnění vstupenek – Cinema City / IMAX Praha

Dokumentace k systému, který automaticky hlídá, kdy Cinema City uvolní
nové termíny prodeje vstupenek na konkrétní film, a pošle push
notifikaci na mobil. Postaveno kvůli filmu **Odyssea** v IMAX Praha
Flora, kde se termín zveřejnění nových dat pravidelně měnil.

## Jak to funguje (přehled)

```
cron-job.org (každých 5 min)
        │  POST /dispatches
        ▼
GitHub Actions workflow (watch.yml)
        │  spustí
        ▼
watch_tickets.py
        │  dotaz na interní JSON API Cinema City pro okno 60 dní dopředu
        │  hledá ID filmu v odpovědi
        ▼
Nový den nalezen? ──ano──► notifikace přes ntfy.sh ──► mobil (appka ntfy)
        │
        ne → jen se uloží stav (state.json) a čeká se dál
```

Používá se **interní JSON API**, které pohání web cinemacity.cz, ne
scraping HTML stránky (ta je React SPA a data v ní nejsou vidět bez
spuštění JavaScriptu).

## Komponenty

| Soubor / služba | K čemu slouží |
|---|---|
| `watch_tickets.py` | Hlavní skript. Dotazuje API, porovnává se stavem, posílá notifikaci. |
| `state.json` | Seznam dnů, které skript už nahlásil jako "v prodeji" – aby neposílal notifikaci pořád dokola. Skript si ho sám čte i zapisuje, commituje se zpět do repa. |
| `.github/workflows/watch.yml` | GitHub Actions workflow – spustí skript a commitne `state.json`. |
| GitHub repo secret `NTFY_TOPIC` | Tajný název "kanálu", na který appka ntfy poslouchá. |
| **ntfy.sh** | Zdarma push notifikační služba bez nutnosti účtu – appka na mobilu se přihlásí k odběru topicu. |
| **cron-job.org** | Externí spouštěč – volá GitHub API každých 5 min, aby spustil workflow. Nutné, protože nativní `schedule` trigger v GitHub Actions je nespolehlivý (velké zpoždění, občas úplně vynechá běh). |
| GitHub Fine-grained token | Použitý v cron-job.org, aby mohl přes API spouštět workflow. **Expiruje – nastaveno viz níže.** |

## Konfigurace pro tento konkrétní hlídač

- Film: Odyssea, `FILM_ID = "7268s2r"` (z URL parametru `for-movie=`)
- Kino: Praha Flora, `CINEMA_ID = "1052"`
- API endpoint:
  ```
  https://www.cinemacity.cz/cz/data-api-service/v1/quickbook/10101/film-events/in-cinema/1052/at-date/YYYY-MM-DD?attr=&lang=cs_CZ
  ```
- Okno kontroly: 60 dní dopředu od dnešního data

## Důležité: expirace GitHub tokenu

Fine-grained token vygenerovaný pro cron-job.org má nastavenou
platnost do **2. 11. 2026**. Po tomto datu přestane cronjob fungovat
(dostaneš chybu "Unauthorized" v logu na cron-job.org).

**Před tímto datem je potřeba:**
1. Vygenerovat nový token: GitHub → avatar vpravo nahoře → Settings →
   Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token (repo: `imax-ticket-watcher`, oprávnění Actions:
   Read and write).
2. V cron-job.org otevřít cronjob → Headers → aktualizovat hodnotu
   `Authorization` na `Bearer <novy-token>`.

## Jak ověřit, že vše funguje

1. **GitHub Actions → záložka Actions** – poslední běhy by měly mít
   zelenou fajfku. V logu kroku "Zkontrolovat vstupenky" hledej řádek
   `Zadne nove terminy.` (běžný stav) nebo `Nove terminy v prodeji: ...`
   (nalezeno).
2. **state.json v repu** (Code → state.json) – obsahuje seznam dnů,
   které skript už nahlásil.
3. **Vynucený test notifikace:** v `state.json` smaž jeden konkrétní
   datum (a odpovídající čárku, ať zůstane platný JSON), commitni.
   Skript ho při dalším běhu znovu najde a pošle notifikaci – tím je
   ověřený celý řetězec (detekce i doručení).

## Jak přizpůsobit pro jiný film / kino

Stačí v `watch_tickets.py` upravit tři konstanty na začátku souboru:

```python
SITE_ID = "10101"        # obvykle stejné pro cinemacity.cz/cz
CINEMA_ID = "1052"       # najdeš v URL webu jako in-cinema=...
FILM_ID = "7268s2r"      # najdeš v URL webu jako for-movie=...
```

ID kina i filmu se dá vyčíst přímo z URL stránky s výběrem vstupenek
na cinemacity.cz (`...&in-cinema=XXXX&for-movie=YYYYY&...`). Repo,
workflow ani ntfy topic není nutné měnit – stačí jen commitnout novou
verzi skriptu (ideálně nejdřív smazat/vyprázdnit `state.json`, ať se
neporovnává se starými daty jiného filmu).

## Poučení pro příště (co se osvědčilo / na co si dát pozor)

- **Nativní GitHub `schedule` cron nedůvěřovat** – pro cokoliv
  časově citlivého radši externí spouštěč (cron-job.org) volající
  `workflow_dispatch` přes API.
- **Substring match místo parsování JSON schématu** – API Cinema City
  není veřejně dokumentované, hledání ID filmu přímo v textu odpovědi
  je odolnější než spoléhat na konkrétní klíče.
- **Token do chatu/nesdíleného místa nikdy nevkládat** – při omylu
  rovnou revokovat a vygenerovat nový.
- **Stav (`state.json`) commitovat zpět do repa** – jinak by si
  GitHub Actions runner (který se pokaždé spouští "od nuly") nic
  nepamatoval mezi běhy a posílal by notifikaci pořád dokola.
