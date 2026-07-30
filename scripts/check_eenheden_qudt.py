"""
check_eenheden_qudt.py — QUDT-koppelingskwaliteit en interne spellingscontrole voor csor:Eenheid

PURPOSE
-------
Test in welke mate csor:Eenheid aan QUDT gekoppeld is en hoe goed die koppeling is (resolutie
+ semantische kwaliteit), en toetst daarnaast — onafhankelijk van QUDT — of `skos:prefLabel`
en `csor:symbool` intern consistent en vrij van tikfouten zijn. Zie
reports/rapport_conceptschemas_en_qudt.md voor de volledige interpretatie.

DATA PROVENANCE
----------------
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`
— de `eenheid`-instanties (357 actief) zitten daarin (voorheen: rechtstreeks het
`codelijst-csor-eenheid`-graph).
Externe bron: QUDT Linked Data (common.qudt), met bestandscache — blijft per definitie live/extern.
Queries: sparql/eenheid_qudt_checks.sparql (bron van waarheid; queryteksten hieronder inline,
lokaal uitgevoerd via sparql_client.select_dataframe_local()).

METHODOLOGY
-----------
- QUDT-crosscheck: voor elke unieke gekoppelde QUDT-URI wordt live gedereferentieerd
  (HTTP-statuscontrole) en wordt `qudt:symbol` vergeleken met `csor:symbool` via
  Levenshtein edit-distance, zowel ruw als na normalisatie van de gekende
  notatieconventies (µ->μ, jr->a, /u->/h). Own addition: edit-distance i.p.v. exacte match,
  omdat een binaire match/no-match geen onderscheid maakt tussen een pure notatiekwestie en
  een echte inhoudelijke afwijking.
- Interne spellingscontrole (los van QUDT-beschikbaarheid, op alle 357 eenheden):
  - Near-duplicate labelwoorden: frequentie + edit-distance-clustering (generiek, geen
    stof-woordenboek) — vindt tikfouten zoals "stifkstof"/"stifstof" i.p.v. "stikstof".
  - Label/symbool-stofconsistentie: woordgrens-bewuste extractie van de stofkwalificatie uit
    het symbool (enkel voor "g"-gebaseerde eenheden, waar dit patroon zich voordoet), tegen
    een curated afkortingen-woordenboek. Own addition: bewust NIET op substring-niveau
    matchen (bv. "C" zoeken binnen "Cl") — dat gaf tijdens verkenning zowel valse positieven
    (Nm³, Pa, FTU) als valse negatieven (de E_323-fout werd erdoor gemaskeerd). Enkel het
    volledige, geëxtraheerde kwalificatie-token wordt vergeleken.
- URI-schema-verificatie (http vs. https, common.qudt.fetch): CSOR slaat QUDT-koppelingen op
  als `http://`. Voor elke koppeling wordt het HTTP-redirect-verloop geregistreerd (302 =
  normale TLS-afdwinging, 301 = mogelijk verhuisde identifier) én wordt gecontroleerd of de
  opgehaalde RDF-payload de exact door CSOR opgeslagen URI (inclusief schema) zelf als
  subject gebruikt — dat is de eigenlijke toets of `http://` de canonieke QUDT-identifier is,
  los van of de verbinding via een redirect loopt.

INTERPRETATION
--------------
Elke vlag hier is een kandidaat voor handmatige review, geen automatische correctie — met
uitzondering van de expliciet in het rapport benoemde, individueel geverifieerde fouten
(E_105, E_113, E_323), die als directe aanbeveling gelden.

OUTPUTS
-------
output/tables/eenheid_qudt_koppeling.csv
output/tables/eenheid_qudt_ontbrekend.csv
output/tables/eenheid_spelling_vlaggen.csv
data/interim/eenheid_*.parquet (tussentijds)
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from difflib import get_close_matches
from pathlib import Path

import pandas as pd
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, qudt, sparql_client as sc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERIM_DIR = REPO_ROOT / "data" / "interim"
CACHE_ROOT = REPO_ROOT / "data" / "cache" / "qudt"
OUTPUT_DIR = REPO_ROOT / "output" / "tables"

PREFIXES = """
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX csor: <https://data.omgeving.vlaanderen.be/ns/csor#>
"""

# Curated stof-afkortingen; enkel gebruikt op het volledige, geëxtraheerde kwalificatie-token
# (nooit als substring-zoekpatroon) — zie METHODOLOGY.
SUBSTANCE_CODES = {
    "stikstof": "N",
    "koolstof": "C",
    "zuurstof": "O2",
    "fosfor": "P",
    "zwavel": "S",
    "chloor": "Cl",
    "fluor": "F",
    "tin": "Sn",
}
KNOWN_CODES = set(SUBSTANCE_CODES.values())

QUALIFIER_RE = re.compile(r"^[mµkn]?g\s*([A-Za-z][A-Za-z0-9]{0,4})?(?:/|$)")


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


def normalize_symbol(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return s.replace("µ", "μ").replace("jr", "a").replace("/u", "/h").lower()


def fetch_linked_units(graph: rdflib.Graph) -> pd.DataFrame:
    # Own addition t.o.v. de live versie: geen GRAPH <...>-clausule meer nodig — de lokale
    # merge bewaart geen graph-context, maar csor:Eenheid-instanties bestaan sowieso enkel in
    # het eenheid-graph (zie DATA PROVENANCE), dus een rechtstreekse ?eenheid a csor:Eenheid
    # geeft hetzelfde resultaat.
    q = (
        PREFIXES
        + """
    SELECT ?eenheid ?label ?symbool ?matchType ?qudt
    WHERE {
      ?eenheid a csor:Eenheid ; skos:prefLabel ?label .
      OPTIONAL { ?eenheid csor:symbool ?symbool }
      FILTER NOT EXISTS { ?eenheid owl:deprecated true }
      { ?eenheid skos:exactMatch ?qudt . BIND("exactMatch" AS ?matchType) }
      UNION { ?eenheid skos:broadMatch ?qudt . BIND("broadMatch" AS ?matchType) }
      UNION { ?eenheid skos:closeMatch ?qudt . BIND("closeMatch" AS ?matchType) }
      UNION { ?eenheid skos:narrowMatch ?qudt . BIND("narrowMatch" AS ?matchType) }
      UNION { ?eenheid skos:relatedMatch ?qudt . BIND("relatedMatch" AS ?matchType) }
      FILTER(STRSTARTS(STR(?qudt), "http://qudt.org/"))
    }
    """
    )
    return sc.select_dataframe_local(q, graph)


def fetch_all_units(graph: rdflib.Graph) -> pd.DataFrame:
    q = (
        PREFIXES
        + """
    SELECT ?eenheid ?label ?symbool
    WHERE {
      ?eenheid a csor:Eenheid ; skos:prefLabel ?label .
      OPTIONAL { ?eenheid csor:symbool ?symbool }
      FILTER NOT EXISTS { ?eenheid owl:deprecated true }
    }
    """
    )
    return sc.select_dataframe_local(q, graph)


def qudt_crosscheck(linked_df: pd.DataFrame) -> pd.DataFrame:
    unique_uris = sorted(linked_df["qudt"].unique())
    info = {uri: qudt.fetch(uri, CACHE_ROOT) for uri in unique_uris}

    rows = []
    for _, r in linked_df.iterrows():
        meta = info[r["qudt"]]
        qudt_symbol = meta.get("symbol")
        edit_raw = levenshtein(r["symbool"], qudt_symbol)
        edit_norm = levenshtein(normalize_symbol(r["symbool"]), normalize_symbol(qudt_symbol))
        if not meta.get("found"):
            categorie = "http_fout"
        elif edit_norm == 0:
            categorie = "exact" if edit_raw == 0 else "notatie_only"
        else:
            categorie = "afwijkend"

        redirect_statuses = meta.get("redirect_statuses") or []
        rows.append(
            {
                "eenheid": r["eenheid"],
                "label": r["label"],
                "csor_symbool": r["symbool"],
                "matchType": r["matchType"],
                "qudt_uri": r["qudt"],
                "qudt_symbool": qudt_symbol,
                "http_status": meta.get("status_code"),
                "edit_distance_raw": edit_raw,
                "edit_distance_genormaliseerd": edit_norm,
                "categorie": categorie,
                # URI-schema-verificatie (http vs. https) — zie common/qudt.py METHODOLOGY.
                "redirect_statuses": ",".join(str(s) for s in redirect_statuses),
                "final_url": meta.get("final_url"),
                "permanent_redirect": meta.get("permanent_redirect", False),
                "payload_subject_matches": meta.get("payload_subject_matches", False),
            }
        )
    return pd.DataFrame(rows)


def spelling_flags(all_df: pd.DataFrame) -> pd.DataFrame:
    flags = []

    # Near-duplicate labelwoorden (generiek, geen stof-woordenboek).
    word_counts = Counter()
    for label in all_df["label"].dropna():
        for w in re.findall(r"[a-zA-Zàâäéèêëïîôöùûüç]+", label.lower()):
            word_counts[w] += 1
    frequent_words = [w for w, c in word_counts.items() if c >= 5]
    rare_words = [w for w, c in word_counts.items() if c <= 2]
    for w in rare_words:
        close = get_close_matches(w, frequent_words, n=1, cutoff=0.75)
        if close:
            hits = all_df[all_df["label"].str.contains(rf"\b{re.escape(w)}\b", case=False, na=False)]
            for _, r in hits.iterrows():
                flags.append(
                    {
                        "eenheid": r["eenheid"],
                        "label": r["label"],
                        "symbool": r["symbool"],
                        "flag_type": "near_duplicate_labelwoord",
                        "detail": f"'{w}' lijkt op vaker voorkomend '{close[0]}'",
                    }
                )

    # Label/symbool-stofconsistentie (woordgrens-bewust, enkel g-gebaseerde symbolen).
    for _, r in all_df.iterrows():
        label = (r["label"] or "").lower()
        symbool = r["symbool"]
        expected = next((code for word, code in SUBSTANCE_CODES.items() if word in label), None)
        if expected is None or not isinstance(symbool, str):
            continue
        m = QUALIFIER_RE.match(symbool)
        qualifier = m.group(1) if m else None
        if qualifier and qualifier in KNOWN_CODES and qualifier != expected:
            flags.append(
                {
                    "eenheid": r["eenheid"],
                    "label": r["label"],
                    "symbool": symbool,
                    "flag_type": "label_symbool_stofmismatch",
                    "detail": f"label wijst op '{expected}', symbool bevat '{qualifier}'",
                }
            )

    return pd.DataFrame(flags, columns=["eenheid", "label", "symbool", "flag_type", "detail"])


def main(graph: rdflib.Graph | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    if graph is None:
        graph = dataset.fetch_and_save()

    linked_df = fetch_linked_units(graph)
    linked_df.to_parquet(INTERIM_DIR / "eenheid_qudt_linked.parquet")
    all_df = fetch_all_units(graph)
    all_df.to_parquet(INTERIM_DIR / "eenheid_alle.parquet")

    print("=== check_eenheden_qudt.py ===")
    print(f"Actieve eenheden: {len(all_df)}, met QUDT-koppeling: {len(linked_df)}")
    print(linked_df["matchType"].value_counts().to_dict())

    cross_df = qudt_crosscheck(linked_df)
    cross_df.to_csv(OUTPUT_DIR / "eenheid_qudt_koppeling.csv", index=False)
    print("\nCategorieën:")
    print(cross_df["categorie"].value_counts().to_dict())
    print(f"HTTP-fouten: {int((cross_df['http_status'] != 200).sum())}")

    n_redirected = int((cross_df["redirect_statuses"] != "").sum())
    n_permanent = int(cross_df["permanent_redirect"].sum())
    n_subject_mismatch = int((~cross_df["payload_subject_matches"]).sum())
    print(
        f"\nURI-schema-verificatie (http vs. https): {n_redirected} van {len(cross_df)} "
        f"koppelingen doorlopen een HTTP-redirect, waarvan {n_permanent} permanent (301) — "
        "een 301 zou wijzen op een verhuisde identifier, een 302 is normale TLS-afdwinging."
    )
    if n_subject_mismatch:
        print(
            f"LET OP: {n_subject_mismatch} koppeling(en) waarvan de RDF-payload de door CSOR "
            "opgeslagen URI niet als subject gebruikt — CSOR's schema-keuze (http/https) komt "
            "dan niet overeen met QUDT's canonieke identifier. Zie eenheid_qudt_koppeling.csv."
        )
    else:
        print(
            "Alle gekoppelde URI's: de RDF-payload gebruikt telkens exact de door CSOR "
            "opgeslagen URI (incl. schema) als subject — CSOR's http/https-schrijfwijze is "
            "dus overal de canonieke QUDT-identifier."
        )

    missing_df = all_df[~all_df["eenheid"].isin(linked_df["eenheid"])]
    missing_df.to_csv(OUTPUT_DIR / "eenheid_qudt_ontbrekend.csv", index=False)
    print(f"\nZonder QUDT-koppeling: {len(missing_df)}")

    flags_df = spelling_flags(all_df)
    flags_df.to_csv(OUTPUT_DIR / "eenheid_spelling_vlaggen.csv", index=False)
    print(f"\nSpelling-/consistentievlaggen: {len(flags_df)}")
    if len(flags_df):
        print(flags_df[["label", "symbool", "flag_type", "detail"]].to_string())

    print(f"\nlive QUDT-calls deze run: {qudt.live_call_count}")


if __name__ == "__main__":
    main()
