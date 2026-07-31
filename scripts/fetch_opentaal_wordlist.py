"""
fetch_opentaal_wordlist.py — ververst de OpenTaal-woordenlijst en correctielijst in data/source/

PURPOSE
-------
Haalt de officiële Nederlandse woordenlijst (`wordlist.txt`, >400.000 woorden) en de curated
foutief->correctie-lijst (`elements/corrections.tsv`, ~17.000 paren) op van het publieke
OpenTaal/opentaal-wordlist-project, zodat `scripts/check_terminologie.py` CSOR-tekst
(alle `@nl`-literals) tegen een gezaghebbende Nederlandse woordenlijst kan toetsen. Dit is geen
CSOR-datakwaliteitscheck (vandaar geen check_-prefix, geen output/tables/-CSV en geen
HTML-rapport, zie CLAUDE.md §3/§10) maar een ververbare externe-bronfetch, analoog in geest aan
fetch_vmm_woordenboek.py.

DATA PROVENANCE
----------------
Bron: https://github.com/OpenTaal/opentaal-wordlist (Stichting OpenTaal), branch `master`,
opgehaald via de publieke raw-content-laag van GitHub (`raw.githubusercontent.com`) — geen
lokale checkout van dat project vereist, dus reproduceerbaar op elke machine. Dubbel
gelicenseerd onder Revised BSD / CC BY 3.0 Unported (attributie: Stichting OpenTaal); zie
LICENSE.txt in dat project.
Opgehaalde bestanden:
- `wordlist.txt` — volledige woordenlijst, één woord/frase per regel.
- `elements/corrections.tsv` — TSV, kolom 1 = foutieve vorm, kolom 2 = 0+ voorgestelde
  correcties (puntkomma-gescheiden, kan leeg zijn).

METHODOLOGY
-----------
Rechtstreekse HTTP GET van beide bestanden (geen paginatie nodig, platte tekstbestanden), met
een controle dat de respons niet leeg is (lege respons duidt op een verplaatst/hernoemd bestand,
geen stille afkap vertrouwen — zelfde geest als de items_total-verificatie in
fetch_vmm_woordenboek.py).

INTERPRETATION
--------------
n.v.t. — bouwsteen/brondata, geen eigen bevindingen. Een gewijzigd woordenaantal t.o.v. een
vorige run is geen scriptfout maar een indicatie dat OpenTaal de woordenlijst heeft bijgewerkt.

OUTPUTS
-------
data/source/opentaal-wordlist.txt (gecommit)
data/source/opentaal-corrections.tsv (gecommit)

USAGE
-----
python3 scripts/fetch_opentaal_wordlist.py
Geen parameters; herdraaien overschrijft beide bestanden volledig (idempotent). Bedoeld om af en
toe handmatig herdraaid te worden, niet als onderdeel van scripts/run_all.py (dat betreft
uitsluitend de CSOR-registerpijplijn zelf).
"""

from __future__ import annotations

from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_WORDLIST = REPO_ROOT / "data" / "source" / "opentaal-wordlist.txt"
OUT_CORRECTIONS = REPO_ROOT / "data" / "source" / "opentaal-corrections.tsv"

RAW_BASE = "https://raw.githubusercontent.com/OpenTaal/opentaal-wordlist/master"
URL_WORDLIST = f"{RAW_BASE}/wordlist.txt"
URL_CORRECTIONS = f"{RAW_BASE}/elements/corrections.tsv"
HEADERS = {"User-Agent": "csor-testing/opentaal-wordlist-fetch (+geert.vanhaute@vlaanderen.be)"}


def fetch_text(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    text = resp.text
    if not text.strip():
        raise RuntimeError(f"Lege respons van {url} — bestand mogelijk verplaatst/hernoemd.")
    return text


def main() -> None:
    OUT_WORDLIST.parent.mkdir(parents=True, exist_ok=True)

    print(f"Woordenlijst ophalen van {URL_WORDLIST} ...")
    wordlist_text = fetch_text(URL_WORDLIST)
    OUT_WORDLIST.write_text(wordlist_text, encoding="utf-8")
    n_words = len([line for line in wordlist_text.splitlines() if line.strip()])
    print(f"  {n_words} woorden -> {OUT_WORDLIST.relative_to(REPO_ROOT)}")

    print(f"Correctielijst ophalen van {URL_CORRECTIONS} ...")
    corrections_text = fetch_text(URL_CORRECTIONS)
    OUT_CORRECTIONS.write_text(corrections_text, encoding="utf-8")
    n_corrections = len([line for line in corrections_text.splitlines() if line.strip()])
    print(f"  {n_corrections} correctieparen -> {OUT_CORRECTIONS.relative_to(REPO_ROOT)}")

    print("\nKlaar.")


if __name__ == "__main__":
    main()
