"""
check_eenheden_qudt.py — QUDT-koppelingskwaliteit en interne spellingscontrole voor csor:Eenheid

PURPOSE
-------
Test in welke mate csor:Eenheid aan QUDT gekoppeld is en hoe goed die koppeling is (resolutie
+ semantische kwaliteit), of er voor de nog niet-gekoppelde eenheden een QUDT-kandidaat met een
(bijna) identiek symbool bestaat (een vergeten-koppeling-suggestie), en toetst daarnaast —
onafhankelijk van QUDT — of `skos:prefLabel` en `csor:symbool` intern consistent en vrij van
tikfouten zijn. Zie reports/rapport_conceptschemas_en_qudt.md voor de volledige interpretatie.

DATA PROVENANCE
----------------
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`
— de `eenheid`-instanties (357 actief) zitten daarin (voorheen: rechtstreeks het
`codelijst-csor-eenheid`-graph).
Externe bron: QUDT Linked Data (common.qudt), met bestandscache — blijft per definitie live/extern.
Voor de koppelingssuggesties (zie METHODOLOGY): common.qudt.fetch_unit_vocabulary(), de
volledige QUDT-eenhedenvocabulaire (https://qudt.org/3.5.0/vocab/unit), eveneens gecached.
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
- Koppelingssuggesties voor ongekoppelde eenheden: `common.qudt.fetch_unit_vocabulary()` haalt
  de volledige QUDT-eenhedenvocabulaire op (zie DATA PROVENANCE); voor elke van de 195
  ongekoppelde eenheden wordt eerst hoofdlettergevoelig exact op `qudt:symbol` gezocht, pas
  daarna — als fallback — genormaliseerd via dezelfde `normalize_symbol()` als de crosscheck
  hierboven. Own addition: hoofdlettergevoelig eerst lost de meeste schijnbare dubbelzinnigheid
  vanzelf op (bv. csor:symbool `Pa` matcht dan enkel de QUDT-eenheid met symbol `Pa` (Pascal),
  niet ook `PA`/`pA` (PetaAmpère/PicoAmpère) — die zouden anders via de case-insensitieve
  normalisatiestap onterecht meematchen). Blijft er per eenheid toch meer dan één kandidaat
  over, dan komt elke kandidaat als aparte rij in de output — een kandidaat, geen automatische
  koppeling.

INTERPRETATION
--------------
Elke vlag hier is een kandidaat voor handmatige review, geen automatische correctie — met
uitzondering van de expliciet in het rapport benoemde, individueel geverifieerde fouten
(E_105, E_113, E_323), die als directe aanbeveling gelden. Idem voor de koppelingssuggesties:
een (bijna) identiek symbool is een sterke aanwijzing, geen bevestiging — de daadwerkelijke
QUantityKind/dimensie is niet getoetst.

OUTPUTS
-------
output/tables/eenheid_qudt_koppeling.csv
output/tables/eenheid_qudt_ontbrekend.csv
output/tables/eenheid_qudt_suggesties.csv
output/tables/eenheid_spelling_vlaggen.csv
output/reports/eenheden_qudt.html
data/interim/eenheid_*.parquet (tussentijds)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, qudt, report, spelling, sparql_client as sc  # noqa: E402
from common.spelling import levenshtein  # noqa: E402

# Individueel geverifieerde fouten die als directe aanbeveling gelden (zie INTERPRETATION).
KNOWN_VERIFIED_ERRORS = {"E_105", "E_113", "E_323"}

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
    # Near-duplicate labelwoorden (generiek, geen stof-woordenboek) — gedeelde implementatie,
    # zie scripts/common/spelling.py::near_duplicate_flags().
    near_dup_df = spelling.near_duplicate_flags(
        all_df, id_col="eenheid", label_col="label", extra_cols=["symbool"]
    )
    flags = near_dup_df.to_dict("records")

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


def suggest_missing_links(missing_df: pd.DataFrame, units: list[dict]) -> pd.DataFrame:
    """Zoekt voor elke ongekoppelde eenheid een QUDT-kandidaat met (bijna) identiek symbool.

    Zie METHODOLOGY: hoofdlettergevoelig exact eerst, genormaliseerd (normalize_symbol()) als
    fallback. Eén rij per (eenheid, kandidaat)-paar; eenheden zonder kandidaat komen niet voor.
    """
    by_exact: dict[str, list[dict]] = {}
    by_norm: dict[str, list[dict]] = {}
    for u in units:
        by_exact.setdefault(u["symbol"], []).append(u)
        by_norm.setdefault(normalize_symbol(u["symbol"]), []).append(u)

    rows = []
    for _, r in missing_df.iterrows():
        symbool = r["symbool"]
        if not isinstance(symbool, str) or not symbool:
            continue
        if symbool in by_exact:
            match_tier, kandidaten = "exact", by_exact[symbool]
        elif normalize_symbol(symbool) in by_norm:
            match_tier, kandidaten = "genormaliseerd", by_norm[normalize_symbol(symbool)]
        else:
            continue
        for k in kandidaten:
            rows.append(
                {
                    "eenheid": r["eenheid"],
                    "label": r["label"],
                    "symbool": symbool,
                    "match_tier": match_tier,
                    "aantal_kandidaten": len(kandidaten),
                    "qudt_uri": k["uri"],
                    "qudt_symbool": k["symbol"],
                }
            )

    columns = [
        "eenheid",
        "label",
        "symbool",
        "match_tier",
        "aantal_kandidaten",
        "qudt_uri",
        "qudt_symbool",
    ]
    return pd.DataFrame(rows, columns=columns)


def build_html_report(
    cross_df: pd.DataFrame,
    missing_df: pd.DataFrame,
    flags_df: pd.DataFrame,
    suggesties_df: pd.DataFrame,
) -> Path:
    linkage_counts = cross_df["matchType"].value_counts()
    linkage_counts["geen koppeling"] = len(missing_df)
    fig_linkage = report.bar_counts(
        linkage_counts,
        title="Koppelingsstatus per eenheid",
        xaxis_title="matchType",
    )
    notaties = set(cross_df["eenheid"].str.rsplit("/", n=1).str[-1]) | set(
        missing_df["eenheid"].str.rsplit("/", n=1).str[-1]
    )
    open_known_errors = KNOWN_VERIFIED_ERRORS & notaties
    disc_linkage = (
        f"{len(cross_df)} van {len(cross_df) + len(missing_df)} actieve eenheden hebben een "
        f"QUDT-koppeling ({len(missing_df)} zonder koppeling). "
        + (
            f"De individueel geverifieerde fouten {', '.join(sorted(open_known_errors))} komen "
            "nog voor als open vlag — directe aanbeveling."
            if open_known_errors
            else "Geen van de individueel geverifieerde fouten (E_105, E_113, E_323) komt nog "
            "voor als open vlag."
        )
    )

    fig_edit = go.Figure(
        go.Histogram(x=cross_df["edit_distance_genormaliseerd"], marker_color=report.FLAT_COLOR)
    )
    fig_edit.update_layout(
        title="Genormaliseerde edit-distance (csor:symbool vs. qudt:symbol)",
        xaxis_title="edit-distance",
        yaxis_title="aantal",
    )
    n_afwijkend = int((cross_df["edit_distance_genormaliseerd"] > 0).sum())
    disc_edit = (
        f"{n_afwijkend} van {len(cross_df)} koppelingen tonen een genormaliseerde afwijking "
        "tussen csor:symbool en qudt:symbol (edit-distance > 0) — een kandidaat voor "
        "handmatige review, geen automatische correctie."
        if n_afwijkend
        else f"Alle {len(cross_df)} koppelingen komen genormaliseerd exact overeen — het "
        "verwachte patroon."
    )

    fig_spelling = report.bar_counts(
        flags_df["flag_type"].value_counts(),
        title="Spelling-/consistentievlaggen per type",
        xaxis_title="flag_type",
    )
    disc_spelling = (
        f"{len(flags_df)} interne spelling-/consistentievlag(gen) gevonden, onafhankelijk van "
        "QUDT-beschikbaarheid."
        if len(flags_df)
        else "Geen interne spelling-/consistentievlaggen gevonden."
    )

    sections = [
        report.Section(
            heading="QUDT-koppelingsstatus",
            discussion=disc_linkage,
            figures=[fig_linkage],
        ),
        report.Section(
            heading="Semantische kwaliteit van gekoppelde eenheden",
            discussion=disc_edit,
            figures=[fig_edit],
            table_df=cross_df[cross_df["categorie"] == "afwijkend"] if n_afwijkend else None,
            table_columns=["eenheid", "label", "csor_symbool", "qudt_symbool", "categorie"],
        ),
        report.Section(
            heading="Interne spelling-/consistentiecontrole",
            discussion=disc_spelling,
            figures=[fig_spelling] if len(flags_df) else [],
            table_df=flags_df if len(flags_df) else None,
        ),
    ]

    n_kandidaat_eenheden = suggesties_df["eenheid"].nunique()
    fig_suggesties = report.bar_counts(
        suggesties_df.drop_duplicates("eenheid")["match_tier"].value_counts(),
        title="Koppelingssuggesties per match_tier (unieke eenheden)",
        xaxis_title="match_tier",
    )
    disc_suggesties = (
        f"{n_kandidaat_eenheden} van {len(missing_df)} ongekoppelde eenheden hebben een "
        "QUDT-kandidaat met een (bijna) identiek symbool (hoofdlettergevoelig exact of na "
        "normalisatie) — een kandidaat voor een vergeten koppeling, geen automatische "
        "koppeling."
        if n_kandidaat_eenheden
        else f"Geen van de {len(missing_df)} ongekoppelde eenheden heeft een QUDT-kandidaat "
        "met een (bijna) identiek symbool."
    )
    sections.append(
        report.Section(
            heading="Koppelingssuggesties voor ongekoppelde eenheden",
            discussion=disc_suggesties,
            figures=[fig_suggesties] if n_kandidaat_eenheden else [],
            table_df=suggesties_df if n_kandidaat_eenheden else None,
            # Own addition t.o.v. de Section-default (table_n=10): deze tabel is klein en
            # volledig actionable (kandidaat-koppelingen voor handmatige review) — de standaard
            # top-10-afkap zou hier net de meerderheid van de bevindingen verbergen.
            table_n=len(suggesties_df),
        )
    )

    return report.build_report(
        name="eenheden_qudt",
        title="CSOR — QUDT-koppelingskwaliteit en spellingscontrole voor csor:Eenheid",
        intro=(
            "In welke mate is csor:Eenheid aan QUDT gekoppeld en hoe goed is die koppeling, "
            "zijn er kandidaat-koppelingen voor de nog ongekoppelde eenheden, en zijn "
            "skos:prefLabel en csor:symbool intern consistent en vrij van tikfouten?"
        ),
        sections=sections,
    )


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

    # Columns: eenheid/label/symbool zoals hierboven; match_tier (exact = hoofdlettergevoelig
    # identiek csor:symbool/qudt:symbol, genormaliseerd = enkel gelijk na normalize_symbol());
    # aantal_kandidaten (>1 = dubbelzinnig, meerdere QUDT-eenheden met dat symbool); qudt_uri/
    # qudt_symbool van de kandidaat. Eén rij per (eenheid, kandidaat)-paar.
    units = qudt.fetch_unit_vocabulary(CACHE_ROOT)
    suggesties_df = suggest_missing_links(missing_df, units)
    suggesties_df.to_csv(OUTPUT_DIR / "eenheid_qudt_suggesties.csv", index=False)
    n_kandidaat_eenheden = suggesties_df["eenheid"].nunique()
    print(
        f"\nKoppelingssuggesties: {n_kandidaat_eenheden} van {len(missing_df)} ongekoppelde "
        f"eenheden hebben een QUDT-kandidaat ({len(suggesties_df)} kandidaat-rijen totaal)."
    )

    print(f"\nlive QUDT-calls deze run: {qudt.live_call_count}")

    report_path = build_html_report(cross_df, missing_df, flags_df, suggesties_df)
    print(f"\nRapport geschreven naar {report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
