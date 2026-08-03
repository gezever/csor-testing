"""
check_terminologie.py — spellingscontrole en VMM-woordenboekdekking van CSOR-tekst

PURPOSE
-------
Beantwoordt twee vragen over de Nederlandstalige tekst in het register: bevat ze woorden die
door OpenTaal als foutief bevestigd zijn (spelling), en welk deel van die tekst dekt al een
officiële definitie in het VMM-woordenboek (terminologische dekking)? Scope is bewust élk
`@nl`-getagd literal in het register — niet beperkt tot `skos:prefLabel` van een vaste
klassenlijst — zodat ook `skos:altLabel`, `skos:definition`, `rdfs:comment`, `dct:title`, etc.
worden meegenomen.

DATA PROVENANCE
----------------
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`.
Externe bronnen (gecommitte snapshots, ververst door hun eigen `fetch_*.py`-script — dit script
haalt zelf niets live op):
- `data/source/opentaal-wordlist.txt` / `data/source/opentaal-corrections.tsv` — de officiële
  Nederlandse woordenlijst resp. curated foutief->correctie-lijst van Stichting OpenTaal, zie
  `scripts/fetch_opentaal_wordlist.py`.
- `data/source/vmm-woordenboek.ttl` — SKOS-thesaurus van VMM's publieke milieu-/waterglossarium,
  zie `scripts/fetch_vmm_woordenboek.py`.

METHODOLOGY
-----------
- **Brondata (gedeeld door secties A en B)**: elk `@nl`-getagd literal in de lokale graph,
  ongeacht predicaat — data-gedreven ontdekt (`isinstance(o, Literal) and o.language == "nl"`),
  geen hardgecodeerde predicaat- of klasselijst (zelfde "ontdekking i.p.v. hardgecodeerde
  lijst"-filosofie als `check_conceptschemas.py::class_coverage()`). **Own addition,
  performance**: rechtstreekse Python-graafiteratie i.p.v. een SPARQL
  `FILTER(lang(?tekst)="nl")`-SELECT — empirisch identiek resultaat (35.127 triples op de
  huidige snapshot, geverifieerd tegen een losse COUNT-query), maar ~100x sneller (0,4s vs. 38s)
  — zelfde geest als de `graph.subject_objects()`-aanpak in CLAUDE.md §4/`generate_diagram.py`
  voor kardinaliteitslogica, hier toegepast omdat het onderliggende patroon (`?s ?p ?tekst` met
  ?p onbepaald) een volledige triple-scan afdwingt die de SPARQL-engine merkbaar trager
  uitvoert dan een rechtstreekse Python-iteratie over dezelfde 274.931 triples.
- **Sectie A — spellingcontrole**:
  - `gekende_fout` (hoge precisie): elk woord uit elk `@nl`-literal wordt case-insensitief
    opgezocht in de OpenTaal-correctielijst. Bewust NIET aangevuld met "woord ontbreekt in
    wordlist.txt" als signaal — CSOR-tekst bevat legitiem vaktechnisch/chemisch jargon dat
    buiten een algemene Nederlandse woordenlijst valt (zie ook de substring-valkuil die de
    Eenheid-check al identificeerde bij stofcodes).
  - `near_duplicate_labelwoord`: dezelfde near-duplicate-clustering die
    `check_eenheden_qudt.py::spelling_flags()` al gebruikte voor `csor:Eenheid`, nu verplaatst
    naar `scripts/common/spelling.py` en hier per predicaat toegepast (`groupby("predicaat")`)
    i.p.v. over de volledige tekstpool ineens — labels/verkorteNotatie zijn korte termen,
    definitie-/commentaarvelden lopende tekst; één gezamenlijke woordfrequentiepool zou courante
    woorden uit lopende tekst laten fungeren als vals "frequent referentiewoord" voor
    onverwante technische termen. De OpenTaal-woordenset wordt meegegeven (`wordset=`) zodat een
    zeldzaam maar wél geldig Nederlands woord niet gevlagd wordt.
  - Overlap met de Eenheid-specifieke vlaggen in `eenheid_spelling_vlaggen.csv` is aanvaard, niet
    weggefilterd: andere techniek (ook corrections.tsv-lookup, per-predicaat-segmentatie),
    complementair aan die check.
- **Sectie B — VMM-woordenboekdekking**: `data/source/vmm-woordenboek.ttl` wordt met rdflib
  geparsed naar een lookup van genormaliseerde `skos:prefLabel`-termen (238 concepten). Elke
  distincte tekstwaarde (gememoized) wordt geklasseerd als `exact_tekst` (volledige, genormaliseerde
  tekst == VMM-term), `bevat_vmm_term` (VMM-term komt woordgrens-bewust voor in de tekst — geen
  losse substring-match, zelfde voorzichtigheid als de `\\b...\\b`-patronen in
  `check_eenheden_qudt.py`) of `geen`.

INTERPRETATION
--------------
Elke spellingvlag is een kandidaat voor handmatige review, geen automatische correctie. Weinig
tot geen `gekende_fout`-hits is een plausibel resultaat (hoge precisie, lage recall op
vaktechnisch jargon) — geen scriptfout. Voor sectie B is `geen` de verwachte meerderheid: het
VMM-woordenboek (238 algemene milieutermen) dekt maar een fractie van CSOR's veel grotere,
gespecialiseerde vocabularium; `exact_tekst`/`bevat_vmm_term`-hits zijn de interessante gevallen
waar een CSOR-begrip al een officiële VMM-definitie heeft.

OUTPUTS
-------
output/tables/terminologie_spelling_vlaggen.csv
output/tables/csor_vmm_termdekking.csv
output/reports/terminologie.html
data/interim/terminologie_*.parquet (tussentijds)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, report, spelling  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERIM_DIR = REPO_ROOT / "data" / "interim"
OUTPUT_DIR = REPO_ROOT / "output" / "tables"
SOURCE_DIR = REPO_ROOT / "data" / "source"

CSOR = "https://data.omgeving.vlaanderen.be/ns/csor#"
SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")


def local_name(uri: str) -> str:
    return uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def fetch_nl_literals(graph: rdflib.Graph) -> pd.DataFrame:
    """Alle @nl-getagde literals in de graph, ongeacht predicaat (data-gedreven, zie
    METHODOLOGY — geen hardgecodeerde predicaat-/klasselijst)."""
    type_index: dict = {}
    for s, o in graph.subject_objects(rdflib.RDF.type):
        if str(o).startswith(CSOR):
            type_index.setdefault(s, []).append(local_name(str(o)))

    rows = []
    for s, p, o in graph:
        if isinstance(o, rdflib.Literal) and o.language == "nl":
            klassen = type_index.get(s)
            rows.append(
                {
                    "subject": str(s),
                    "predicaat": local_name(str(p)),
                    "klasse": ",".join(klassen) if klassen else None,
                    "tekst": str(o),
                }
            )
    return pd.DataFrame(rows, columns=["subject", "predicaat", "klasse", "tekst"])


def self_test(corrections: dict[str, list[str]]) -> None:
    """Bekend corrections.tsv-paar door known_typo_flags() halen vóór de volledige populatie
    verwerkt wordt (CLAUDE.md §9)."""
    test_df = pd.DataFrame({"subject": ["__zelftest__"], "tekst": ["Dit is 0mdat een test."]})
    result = spelling.known_typo_flags(test_df, id_col="subject", label_col="tekst", corrections=corrections)
    if result.empty or result.iloc[0]["suggestie"] != "omdat":
        raise AssertionError("Zelftest gekende-fout-detectie mislukt ('0mdat' -> 'omdat' niet gevonden).")
    print("Zelftest gekende-fout-detectie geslaagd ('0mdat' -> 'omdat').")


def spelling_flags(
    literalen_df: pd.DataFrame, wordset: set[str], corrections: dict[str, list[str]]
) -> pd.DataFrame:
    typo_df = spelling.known_typo_flags(
        literalen_df,
        id_col="subject",
        label_col="tekst",
        corrections=corrections,
        extra_cols=["predicaat", "klasse"],
    )

    near_dup_frames = [
        spelling.near_duplicate_flags(
            group,
            id_col="subject",
            label_col="tekst",
            extra_cols=["predicaat", "klasse"],
            wordset=wordset,
        )
        for _, group in literalen_df.groupby("predicaat")
    ]
    near_dup_df = pd.concat(near_dup_frames, ignore_index=True)

    columns = ["subject", "predicaat", "klasse", "tekst", "flag_type", "detail", "suggestie"]
    combined = pd.concat([typo_df, near_dup_df], ignore_index=True, sort=False)
    combined["suggestie"] = combined.get("suggestie", "").fillna("")
    return combined[columns]


def load_vmm_terms(path: Path) -> dict[str, tuple[str, str]]:
    """{genormaliseerde skos:prefLabel: (concept-URI, skos:definition)} uit het VMM-woordenboek."""
    g = rdflib.Graph()
    g.parse(path, format="turtle")
    terms: dict[str, tuple[str, str]] = {}
    for concept in g.subjects(rdflib.RDF.type, SKOS.Concept):
        label = g.value(concept, SKOS.prefLabel)
        if label is None:
            continue
        definitie = g.value(concept, SKOS.definition)
        terms[str(label).strip().lower()] = (str(concept), str(definitie) if definitie else "")
    return terms


def vmm_matches(literalen_df: pd.DataFrame, vmm_terms: dict[str, tuple[str, str]]) -> pd.DataFrame:
    term_patterns = [
        (term, re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)) for term in vmm_terms
    ]
    cache: dict[str, tuple[str, str, str, str]] = {}

    def classify(tekst: str) -> tuple[str, str, str, str]:
        if tekst in cache:
            return cache[tekst]
        genorm = tekst.strip().lower()
        if genorm in vmm_terms:
            uri, definitie = vmm_terms[genorm]
            result = ("exact_tekst", genorm, uri, definitie)
        else:
            hit_term = next((term for term, pattern in term_patterns if pattern.search(tekst)), None)
            if hit_term:
                uri, definitie = vmm_terms[hit_term]
                result = ("bevat_vmm_term", hit_term, uri, definitie)
            else:
                result = ("geen", "", "", "")
        cache[tekst] = result
        return result

    matches = literalen_df["tekst"].map(classify)
    out = literalen_df.copy()
    out["match_type"] = [m[0] for m in matches]
    out["vmm_term"] = [m[1] for m in matches]
    out["vmm_uri"] = [m[2] for m in matches]
    out["vmm_definitie"] = [m[3] for m in matches]
    return out


def build_html_report(spelling_df: pd.DataFrame, dekking_df: pd.DataFrame) -> Path:
    disc_spelling = report.format_value_counts(spelling_df["flag_type"], "vlag", "vlaggen")
    fig_spelling = report.bar_counts(
        spelling_df["flag_type"].value_counts(),
        title="Spellingvlaggen per type",
        xaxis_title="flag_type",
    )

    disc_dekking = report.format_value_counts(dekking_df["match_type"], "literal", "literals")
    fig_dekking = report.bar_counts(
        dekking_df["match_type"].value_counts(),
        title="VMM-woordenboekdekking per match_type",
        xaxis_title="match_type",
    )
    gedekt_df = dekking_df[dekking_df["match_type"] != "geen"]

    sections = [
        report.Section(
            heading="Spellingcontrole (OpenTaal)",
            discussion=disc_spelling,
            figures=[fig_spelling],
            table_df=spelling_df if len(spelling_df) else None,
        ),
        report.Section(
            heading="VMM-woordenboekdekking",
            discussion=disc_dekking,
            figures=[fig_dekking],
            table_df=gedekt_df if len(gedekt_df) else None,
            table_columns=["subject", "predicaat", "klasse", "tekst", "match_type", "vmm_term"],
        ),
    ]
    return report.build_report(
        name="terminologie",
        title="CSOR — spellingscontrole en VMM-woordenboekdekking",
        intro=(
            "Bevat de Nederlandstalige tekst in het register (alle @nl-literals, elk predicaat) "
            "door OpenTaal bevestigde spelfouten, en welk deel dekt al een officiële VMM-definitie?"
        ),
        sections=sections,
    )


def main(graph: rdflib.Graph | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    if graph is None:
        graph = dataset.fetch_and_save()

    print("=== check_terminologie.py ===")

    wordset = spelling.load_wordset(SOURCE_DIR / "opentaal-wordlist.txt")
    corrections = spelling.load_corrections(SOURCE_DIR / "opentaal-corrections.tsv")
    print(f"OpenTaal: {len(wordset)} woorden, {len(corrections)} correctieparen ingelezen.")
    self_test(corrections)

    literalen_df = fetch_nl_literals(graph)
    literalen_df.to_parquet(INTERIM_DIR / "terminologie_nl_literals.parquet")
    print(
        f"\n{len(literalen_df)} @nl-literals gevonden over "
        f"{literalen_df['predicaat'].nunique()} predicaten: "
        f"{literalen_df['predicaat'].value_counts().to_dict()}"
    )

    # Columns: subject (instantie-URI), predicaat (lokale naam), klasse (csor:-klasse van
    # subject, kan leeg zijn), tekst (het @nl-literal), flag_type (gekende_fout of
    # near_duplicate_labelwoord), detail (toelichting), suggestie (enkel bij gekende_fout).
    spelling_df = spelling_flags(literalen_df, wordset, corrections)
    spelling_df.to_csv(OUTPUT_DIR / "terminologie_spelling_vlaggen.csv", index=False)
    print(f"\nSpellingvlaggen: {len(spelling_df)}")
    if len(spelling_df):
        print(spelling_df["flag_type"].value_counts().to_dict())

    vmm_terms = load_vmm_terms(SOURCE_DIR / "vmm-woordenboek.ttl")
    print(f"\nVMM-woordenboek: {len(vmm_terms)} termen ingelezen.")

    # Columns: subject, predicaat, klasse, tekst — zie hierboven. match_type (exact_tekst,
    # bevat_vmm_term of geen), vmm_term (de gematchte, genormaliseerde VMM-term, leeg bij geen),
    # vmm_uri (concept-URI in het VMM-woordenboek), vmm_definitie (skos:definition).
    dekking_df = vmm_matches(literalen_df, vmm_terms)
    dekking_df.to_csv(OUTPUT_DIR / "csor_vmm_termdekking.csv", index=False)
    print(f"\nVMM-dekking: {dekking_df['match_type'].value_counts().to_dict()}")

    report_path = build_html_report(spelling_df, dekking_df)
    print(f"\nRapport geschreven naar {report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
