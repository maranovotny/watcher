#!/usr/bin/env python3
"""
Hlidac uvolneni vstupenek - Cinema City / IMAX Praha.

Pri kazdem spusteni projde okno budoucich dat (DAYS_AHEAD dni od dneska)
a zepta se interniho JSON API Cinema City, jestli uz jsou pro dany den
v prodeji vstupenky na FILM_ID v CINEMA_ID. Jakmile se objevi datum,
ktere tam pri predchozim behu nebylo, posle push notifikaci pres ntfy.sh
a zapamatuje si ho, aby se notifikace neopakovala.

Pouziti (lokalne):
    NTFY_TOPIC=muj-tajny-topic python3 watch_tickets.py

V GitHub Actions se NTFY_TOPIC nastavuje jako repository secret
(viz workflow watch.yml).
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

# ---------------------------------------------------------------- CONFIG --
SITE_ID = "10101"        # quickbook site id pro cinemacity.cz/cz
CINEMA_ID = "1052"       # Praha Flora (IMAX)
FILM_ID = "7268s2r"      # id filmu z URL (parametr for-movie=...)
LANG = "cs_CZ"
DAYS_AHEAD = 60          # jak daleko do budoucnosti kontrolovat
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")
# ---------------------------------------------------------------------------

URL_TEMPLATE = (
    "https://www.cinemacity.cz/cz/data-api-service/v1/quickbook/"
    f"{SITE_ID}/film-events/in-cinema/{CINEMA_ID}/at-date/{{d}}?attr=&lang={LANG}"
)


def film_on_sale(target_date: date) -> bool:
    """Vrati True, pokud odpoved API pro dany den obsahuje FILM_ID."""
    url = URL_TEMPLATE.format(d=target_date.isoformat())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        # 400/404 = pro tento den jeste neni rozvrh publikovany
        if exc.code in (400, 404):
            return False
        raise
    except urllib.error.URLError:
        return False
    # Presna struktura API neni verejne dokumentovana - hledani FILM_ID
    # primo v textu odpovedi je odolnejsi vuci zmenam schematu nez
    # parsovani konkretnich klicu v JSONu.
    return FILM_ID in body


def load_known() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_known(known: set) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(known), f, indent=2)


def notify(message: str) -> None:
       print(message)
       if not NTFY_TOPIC:
           print("NTFY_TOPIC neni nastaveny - notifikace se neposila.", file=sys.stderr)
           return
       headers = {"Title": "Nove vstupenky - Odyssea IMAX"}
       if NOTIFY_EMAIL:
           headers["Email"] = NOTIFY_EMAIL
       try:
           urllib.request.urlopen(
               urllib.request.Request(
                   f"https://ntfy.sh/{NTFY_TOPIC}",
                   data=message.encode("utf-8"),
                   headers=headers,
                   method="POST",
               ),
               timeout=10,
           )
       except Exception as exc:
           print(f"Nepodarilo se poslat notifikaci: {exc}", file=sys.stderr)


def main() -> None:
    known = load_known()
    today = date.today()
    new_dates = []

    for offset in range(DAYS_AHEAD):
        d = today + timedelta(days=offset)
        key = d.isoformat()
        if key in known:
            continue
        if film_on_sale(d):
            new_dates.append(key)
            known.add(key)

    if new_dates:
        notify(
            "Nove terminy v prodeji: "
            + ", ".join(new_dates)
            + " -> https://www.cinemacity.cz/cinemas/flora/1052"
        )
    else:
        print("Zadne nove terminy.")

    save_known(known)


if __name__ == "__main__":
    main()
