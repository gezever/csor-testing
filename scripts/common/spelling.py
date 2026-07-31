"""
spelling.py — gedeelde bouwstenen voor spellingscontrole op CSOR-tekst

PURPOSE
-------
Generieke, hergebruikbare bouwstenen voor spellingscontrole op vrije Nederlandstalige tekst uit
het register: near-duplicate-labelwoordclustering (oorspronkelijk inline in
check_eenheden_qudt.py::spelling_flags(), hier verplaatst zodat check_terminologie.py dezelfde
logica hergebruikt i.p.v. een tweede kopie te bouwen) en opzoeking tegen de externe
OpenTaal-correctielijst.

DATA PROVENANCE
----------------
Geen eigen data — `load_wordset()`/`load_corrections()` parsen de door
`scripts/fetch_opentaal_wordlist.py` opgehaalde bestanden
(`data/source/opentaal-wordlist.txt`, `data/source/opentaal-corrections.tsv`).

METHODOLOGY
-----------
- `near_duplicate_flags()`: frequentie + edit-distance-clustering (generiek, geen
  woordenboek nodig) — vindt tikfouten zoals "stifkstof"/"stifstof" i.p.v. "stikstof". Een
  zeldzaam woord (frequentie <= rare_threshold) dat sterk lijkt (SequenceMatcher-ratio >= cutoff)
  op een vaak voorkomend woord (frequentie >= frequent_threshold) binnen dezelfde tekstpool wordt
  gevlagd. Optioneel: met `wordset` meegegeven, wordt een zeldzaam woord dat zelf al een geldig
  Nederlands woord is (voorkomt in `wordset`) NIET gevlagd — een gelijkenis tussen twee bestaande
  woorden is geen tikfout-aanwijzing. `check_eenheden_qudt.py` roept dit zonder `wordset` aan
  (ongewijzigd gedrag t.o.v. vóór deze refactor); `check_terminologie.py` geeft wel de
  OpenTaal-woordenset mee.
- `known_typo_flags()`: per woord (eenvoudige witruimte-tokenisatie + leestekens strippen, niet
  de letter-only regex van `near_duplicate_flags()` — correctie-sleutels in `corrections.tsv`
  kunnen cijfers bevatten, bv. `0mdat`) een opzoeking in de curated OpenTaal-correctielijst.
  **Own addition, hoofdlettergevoelig i.p.v. case-insensitive**: een eerste, case-insensitieve
  versie gaf tijdens de verkenning valse positieven doordat korte CSOR-vakafkortingen (`Mn` =
  mangaan-symbool, `KI`, `sd`) toevallig samenvallen met los-Nederlandse chattaal-correcties in
  dezelfde lijst (`mn`->`m'n; mijn`) — zie `known_typo_flags()` zelf voor de exacte, twee-
  niveau hoofdletterlogica en de `_MIN_WORD_LENGTH`-ondergrens die dat afvangt. Hoge precisie
  (elke hit is een door OpenTaal bevestigde foutieve vorm), lage recall (vaktechnisch/chemisch
  CSOR-jargon staat niet in een algemene Nederlandse correctielijst) — bewust niet aangevuld met
  "woord ontbreekt in wordlist.txt" als signaal, dat gaf bij de Eenheid-check al valse
  positieven op legitiem jargon.

INTERPRETATION
--------------
Elke vlag is een kandidaat voor handmatige review, geen automatische correctie.

OUTPUTS
-------
Geen eigen output — geeft pandas DataFrames terug aan het aanroepende check-script.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import get_close_matches
from pathlib import Path

import pandas as pd

_WORD_RE = re.compile(r"[a-zA-Zàâäéèêëïîôöùûüç]+")
_STRIP_CHARS = ".,:;()[]{}'\"„”‚’!?«»"


def levenshtein(a: str, b: str) -> int:
    a, b = a or "", b or ""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def near_duplicate_flags(
    df: pd.DataFrame,
    id_col: str,
    label_col: str,
    extra_cols: list[str] | None = None,
    wordset: set[str] | None = None,
    frequent_threshold: int = 5,
    rare_threshold: int = 2,
    cutoff: float = 0.75,
) -> pd.DataFrame:
    """Near-duplicate-labelwoordclustering (zie METHODOLOGY). `wordset` is optioneel: geldige
    Nederlandse woorden (uit `load_wordset()`) worden dan niet als "zeldzaam/verdacht" behandeld.
    """
    extra_cols = extra_cols or []
    columns = [id_col, label_col, *extra_cols, "flag_type", "detail"]
    flags: list[dict] = []

    word_counts: Counter[str] = Counter()
    for label in df[label_col].dropna():
        for w in _WORD_RE.findall(label.lower()):
            word_counts[w] += 1

    frequent_words = [w for w, c in word_counts.items() if c >= frequent_threshold]
    rare_words = [
        w
        for w, c in word_counts.items()
        if c <= rare_threshold and not (wordset and w in wordset)
    ]

    for w in rare_words:
        close = get_close_matches(w, frequent_words, n=1, cutoff=cutoff)
        if not close:
            continue
        hits = df[df[label_col].str.contains(rf"\b{re.escape(w)}\b", case=False, na=False)]
        for _, r in hits.iterrows():
            row = {id_col: r[id_col], label_col: r[label_col]}
            for c in extra_cols:
                row[c] = r[c]
            row["flag_type"] = "near_duplicate_labelwoord"
            row["detail"] = f"'{w}' lijkt op vaker voorkomend '{close[0]}'"
            flags.append(row)

    return pd.DataFrame(flags, columns=columns)


_MIN_WORD_LENGTH = 3


def known_typo_flags(
    df: pd.DataFrame,
    id_col: str,
    label_col: str,
    corrections: dict[str, list[str]],
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Opzoeking per woord in de curated OpenTaal-correctielijst (zie METHODOLOGY).

    Twee niveaus, allebei enkel voor woorden van >= `_MIN_WORD_LENGTH` tekens — korte tokens
    zijn in CSOR-tekst doorgaans vak-/domeinafkortingen (bv. 'Mn', 'KI', 'sd'), die toevallig
    ook als informele-taal-correctie in `corrections.tsv` voorkomen ('mn'->'mijn', 'sd'->'SD');
    empirisch geverifieerd tijdens de verkenning (o.a. 'Mn' = mangaan-symbool, altijd zo
    geschreven in CSOR, viel anders samen met de chattaal-correctie 'mn'->'m'n; mijn'):
    - exacte match (hoofdlettergevoelig) tegen de correctielijst-sleutel — dekt zowel gewone
      kleine-letter-foutieve-vormen als expliciete hoofdletterconventieregels (bv.
      'Ijzer'->'IJzer', 'KI'->'ki') zonder een woord in een andere hoofdlettervorm dan de
      sleutel zelf mee te matchen;
    - anders, enkel wanneer het woord zelf zoals een gewoon 'Titelhoofdletter'-woord geschreven
      is (`word == word.capitalize()`, bv. woordbegin van een label zoals 'Caffeïne'): opzoeking
      van de kleine-letter-vorm tegen een uitsluitend-kleine-letter-sleutel in de correctielijst.
      Dit vangt de courante "label begint met hoofdletter"-situatie zonder de hoofdletter-
      conventieregels hierboven verkeerd te matchen (die sleutels zijn zelf geen kleine-letter-
      string, dus komen niet in aanmerking voor deze tweede opzoeking).
    """
    extra_cols = extra_cols or []
    columns = [id_col, label_col, *extra_cols, "flag_type", "detail", "suggestie"]
    flags: list[dict] = []

    for _, r in df.iterrows():
        text = r[label_col]
        if not isinstance(text, str):
            continue
        seen: set[str] = set()
        for token in text.split():
            word = token.strip(_STRIP_CHARS)
            if len(word) < _MIN_WORD_LENGTH or word in seen:
                continue

            if word in corrections:
                match_key = word
            elif word == word.capitalize() and word.lower() in corrections:
                match_key = word.lower()
            else:
                continue

            seen.add(word)
            row = {id_col: r[id_col], label_col: text}
            for c in extra_cols:
                row[c] = r[c]
            row["flag_type"] = "gekende_fout"
            row["detail"] = f"'{word}' komt voor als foutieve vorm in opentaal-corrections.tsv"
            row["suggestie"] = "; ".join(corrections[match_key])
            flags.append(row)

    return pd.DataFrame(flags, columns=columns)


def load_wordset(path: Path) -> set[str]:
    """Leest data/source/opentaal-wordlist.txt in tot een lowercase woordenset (meerwoordige
    regels worden op woordniveau gesplitst)."""
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        for w in line.strip().split():
            words.add(w.lower())
    return words


def load_corrections(path: Path) -> dict[str, list[str]]:
    """Leest data/source/opentaal-corrections.tsv in tot {foutief: [suggestie, ...]}.

    De sleutel behoudt de originele hoofdlettering uit het bronbestand (niet verlaagd) — zie
    `known_typo_flags()` METHODOLOGY: een deel van deze correcties is zelf een
    hoofdletterconventieregel (bv. 'Ijzer'->'IJzer', 'KI'->'ki'), die enkel correct te
    interpreteren is met de hoofdlettering intact.
    """
    corrections: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        foutief = parts[0].strip()
        if not foutief:
            continue
        suggesties_raw = parts[1].strip() if len(parts) > 1 else ""
        corrections[foutief] = [s.strip() for s in suggesties_raw.split(";") if s.strip()]
    return corrections
