"""
rates.py — preluare curs valutar (cumpărare/vânzare) pentru bănci din Moldova.

Sursă: valutar.md — agregă cursurile de la MAIB, MICB (Moldindconbank),
Victoriabank, FinComBank ș.a. Fiecare bancă are o pagină proprie cu un
tabel simplu (monedă / buy / sell), ceea ce e mult mai stabil de "citit"
decât să faci scraping direct pe siteurile băncilor (care sunt SPA-uri
grele, cu structură ce se schimbă des).

Dacă la un moment dat structura paginii valutar.md se schimbă și parserul
nu mai găsește nimic, funcțiile de mai jos vor arunca RuntimeError cu un
mesaj clar — nu vor întoarce date greșite în tăcere.
"""

import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Bănci suportate: cheie internă -> (nume afișat, slug pe valutar.md)
# ---------------------------------------------------------------------------
BANKS = {
    "maib": ("MAIB", "moldova-agroindbank"),
    "micb": ("MICB", "moldindconbank"),
    "victoriabank": ("Victoriabank", "victoriabank"),
    "fincombank": ("FinComBank", "fincombank"),
}

BASE_URL = "https://valutar.md/en/banks/{slug}"

# nume complet (cum apare pe pagină) -> cod valutar ISO
NAME_TO_CODE = {
    "euro": "EUR",
    "us dollar": "USD",
    "russian ruble": "RUB",
    "romanian leu": "RON",
    "ukraine hryvnia": "UAH",
    "pound sterling": "GBP",
    "swiss franc": "CHF",
    "turkish lira": "TRY",
    "albanian lek": "ALL",
    "armenian dram": "AMD",
    "australian dollar": "AUD",
    "azerbaijanian manat": "AZN",
    "belarussian ruble": "BYN",
    "canadian dollar": "CAD",
    "chinese yuan renminbi": "CNY",
    "czech koruna": "CZK",
    "danish krone": "DKK",
    "georgian lar": "GEL",
    "hong kong dollar": "HKD",
    "hungarian forint": "HUF",
    "iceland krona": "ISK",
    "indian rupee": "INR",
    "japanese yen": "JPY",
    "kazakhstan tenge": "KZT",
    "kuwaiti dinar": "KWD",
    "kyrgyzstan som": "KGS",
    "macedonian denar": "MKD",
    "malaysian ringgit": "MYR",
    "new zealand dollar": "NZD",
    "norwegian krone": "NOK",
    "polish zloty": "PLN",
    "serbian dinar": "RSD",
    "shekel israelit": "ILS",
    "south korean won": "KRW",
    "swedish krona": "SEK",
    "tajikistan somoni": "TJS",
    "turkmenistan manat": "TMT",
    "u.a.e. dirham": "AED",
    "uzbekistan sum": "UZS",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CursValutarBot/1.0; +https://t.me/)"
}

_CACHE_TTL = 300  # secunde — nu bate site-ul la fiecare click, cache 5 min
_cache = {}  # slug -> (timestamp, {cod_valuta: (buy, sell)})


def _fetch_bank_table(slug: str) -> dict:
    """Descarcă și parsează tabelul de curs pentru o bancă. Rezultat cache-uit."""
    now = time.time()
    if slug in _cache and now - _cache[slug][0] < _CACHE_TTL:
        return _cache[slug][1]

    url = BASE_URL.format(slug=slug)
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError(f"Nu am găsit tabelul de curs pe pagina {url} — s-a schimbat structura site-ului.")

    result = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue  # rândul de header sau altceva

        link = cells[0].find("a")
        name = (link.text if link else cells[0].text).strip().lower()
        code = NAME_TO_CODE.get(name)
        if not code:
            continue

        buy_txt = cells[1].text.strip().replace(",", ".")
        sell_txt = cells[2].text.strip().replace(",", ".")
        try:
            buy = float(buy_txt)
            sell = float(sell_txt)
        except ValueError:
            continue  # ex. rânduri cu "-" pentru monede fără curs azi

        result[code] = (buy, sell)

    if not result:
        raise RuntimeError(f"Tabelul de pe {url} nu a putut fi interpretat (0 valute găsite).")

    _cache[slug] = (now, result)
    return result


def get_rate_for_currency(currency_code: str) -> dict:
    """
    Întoarce cursul unei valute la toate băncile suportate.

    Returnează: {cheie_banca: (nume_afisat, buy, sell) sau None dacă banca
    nu are curs pentru acea valută / a picat cererea}
    """
    currency_code = currency_code.upper()
    out = {}
    for key, (display_name, slug) in BANKS.items():
        try:
            table = _fetch_bank_table(slug)
            pair = table.get(currency_code)
            out[key] = (display_name, pair[0], pair[1]) if pair else (display_name, None, None)
        except Exception as exc:  # noqa: BLE001 — vrem să continuăm cu celelalte bănci
            out[key] = (display_name, "eroare", str(exc))
    return out


def format_rate_message(currency_code: str) -> str:
    """Construiește mesajul text trimis în Telegram pentru o valută."""
    currency_code = currency_code.upper()

    # USDT (Tether) nu e valută fiat — băncile din Moldova nu-l cotează.
    # Folosim cursul USD ca aproximare și marcăm clar asta.
    note = ""
    lookup_code = currency_code
    if currency_code == "USDT":
        lookup_code = "USD"
        note = "\n⚠️ USDT nu e cotat de bănci — se arată cursul USD (referință, 1 USDT ≈ 1 USD)."

    data = get_rate_for_currency(lookup_code)
    
    # Dacă obții ora curentă, folosește datetime:
    current_time = datetime.now() + timedelta(hours=3)
    lines = [f"💱 Curs {currency_code}/MDL – {current_time.strftime('%d.%m.%Y %H:%M')}\n"]
    any_found = False
    for key in ("maib", "micb", "victoriabank", "fincombank"):
        name, buy, sell = data[key]
        if isinstance(buy, float):
            any_found = True
            lines.append(f"🏦 {name}:  {buy:.2f}  /  {sell:.2f}")
        elif buy == "eroare":
            lines.append(f"🏦 {name}: indisponibil momentan")
        else:
            lines.append(f"🏦 {name}: nu cotează {lookup_code}")

    if not any_found:
        lines.append("\nNu am găsit curs pentru această valută la băncile monitorizate.")

    lines.append(note) if note else None
    return "\n".join(lines)
