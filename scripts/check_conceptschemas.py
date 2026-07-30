"""
check_conceptschemas.py — structuur, volledigheid en kardinaliteit van CSOR-conceptschema's

PURPOSE
-------
Beantwoordt drie vragen over het CSOR-datamodel: welke conceptschema's zijn er en hoe
verhouden hun klassen zich tot elkaar (relatie-kaart), behoort ieder element tot een
conceptschema, en wat zijn de kardinaliteiten van de onderlinge relaties? Zie
reports/rapport_conceptschemas_en_qudt.md voor de volledige interpretatie.

DATA PROVENANCE
----------------
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`.
Alle queries filteren expliciet op de csor:-namespace (`STRSTARTS(STR(?class), STR(csor:))`);
die instanties/declaraties bestaan uitsluitend binnen de 10 CSOR-graphs (ook de
`owl:ObjectProperty`-declaraties zelf blijken binnen het `drager`-graph te zitten — geverifieerd
tijdens de migratie naar deze lokale laag), dus de restrictie tot die graphs (i.p.v. het
volledige 47-schema's-brede default-graph van de live endpoint) verandert de resultaten niet.
Queries: sparql/conceptschema_checks.sparql (bron van waarheid; queryteksten hieronder inline
om ze programmatisch te kunnen uitvoeren — lokaal uitgevoerd via
sparql_client.select_dataframe_local()).

METHODOLOGY
-----------
- Klasse-ontdekking i.p.v. een hardgecodeerde lijst van 10: elke `csor:`-getypeerde klasse
  wordt gevonden via `?inst a ?class`, met per klasse het aantal instanties en het aantal
  daarvan met `skos:inScheme`. Own addition: dit voorkomt de twee valkuilen uit de
  verkenning — generieke `skos:Concept`-telling wordt vervuild door externe DCAT-thema-URI's
  in dezelfde named graph, en `skos:Collection`-instanties tellen wél mee als schema-lid maar
  niet als klasse-instantie; door per specifieke csor:-klasse te tellen i.p.v. generiek op
  `skos:Concept`, vervallen beide valkuilen vanzelf.
- Kardinaliteit: voor elke gevonden `owl:ObjectProperty` binnen de csor:-namespace wordt
  automatisch de forward- (subject -> aantal objecten) en backward-kardinaliteit (object ->
  aantal subjecten) berekend.
- Inverse-paar-consistentie: voor de twee bekende inverse-paren
  (`heeftParameterAspect`<->`heeftParameter`, `heeftKwantificeerbaarAspect`<->
  `toepasbareEenheid`) wordt in beide richtingen getoetst op asymmetrieën.
- Orphan-detectie: parameters zonder `ParameterAspect`, eenheden zonder
  `KwantificeerbaarAspect`, en dragers die door geen enkele parameter gebruikt worden.

INTERPRETATION
--------------
Een klasse zonder scheme-lidmaatschap is niet per definitie een fout — zie de 7 structurele/
rekenkundige klassen (afleidingen, termen, referenties) die bij ontwerp buiten het
conceptschema-model vallen. Een asymmetrie in een inverse-paar, of een orphan-record, is wel
een concrete aanwijzing voor onvolledigheid en verdient navolging.

OUTPUTS
-------
output/tables/conceptschema_dekking.csv
output/tables/csor_relaties.csv
output/tables/csor_relatie_kardinaliteiten.csv
output/tables/csor_orphans.csv
data/interim/conceptschema_*.parquet (tussentijds)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, sparql_client as sc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERIM_DIR = REPO_ROOT / "data" / "interim"
OUTPUT_DIR = REPO_ROOT / "output" / "tables"

PREFIXES = """
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX csor: <https://data.omgeving.vlaanderen.be/ns/csor#>
"""

# Bekende inverse-paren om op asymmetrie te toetsen (property_a, property_b): elke
# ?s property_a ?o moet ook ?o property_b ?s hebben, en omgekeerd.
INVERSE_PAIRS = [
    ("heeftParameterAspect", "heeftParameter"),
    ("heeftKwantificeerbaarAspect", "toepasbareEenheid"),
]


def run(name: str, query: str, graph: rdflib.Graph) -> pd.DataFrame:
    df = sc.select_dataframe_local(query, graph)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM_DIR / f"conceptschema_{name}.parquet")
    return df


def class_coverage(graph: rdflib.Graph) -> pd.DataFrame:
    q = (
        PREFIXES
        + """
    SELECT ?class (COUNT(DISTINCT ?inst) AS ?totaal)
           (COUNT(DISTINCT ?withScheme) AS ?metScheme)
           (COUNT(DISTINCT ?withConceptType) AS ?isConcept)
    WHERE {
      ?inst a ?class .
      FILTER(STRSTARTS(STR(?class), STR(csor:)))
      OPTIONAL { ?inst skos:inScheme ?s . BIND(?inst AS ?withScheme) }
      OPTIONAL { ?inst a skos:Concept . BIND(?inst AS ?withConceptType) }
    }
    GROUP BY ?class
    ORDER BY DESC(?totaal)
    """
    )
    df = run("klasse_dekking", q, graph)
    for col in ("totaal", "metScheme", "isConcept"):
        df[col] = df[col].astype(int)

    def categorize(r):
        if r["metScheme"] == 0:
            return "structureel-geen-scheme"
        if r["totaal"] == r["metScheme"]:
            return "codelijst-100pct"
        return "codelijst-met-afwijking"

    df["categorie"] = df.apply(categorize, axis=1)
    return df


def object_properties(graph: rdflib.Graph) -> pd.DataFrame:
    q = (
        PREFIXES
        + """
    SELECT ?prop ?label ?domain ?range
    WHERE {
      ?prop a owl:ObjectProperty .
      FILTER(STRSTARTS(STR(?prop), STR(csor:)))
      OPTIONAL { ?prop rdfs:label ?label }
      OPTIONAL { ?prop rdfs:domain ?domain }
      OPTIONAL { ?prop rdfs:range ?range }
    }
    ORDER BY ?prop
    """
    )
    return run("object_properties", q, graph)


CSOR_NS = "https://data.omgeving.vlaanderen.be/ns/csor#"


def cardinalities(prop_local_names: list[str], graph: rdflib.Graph) -> pd.DataFrame:
    """Own addition, performance: dit was oorspronkelijk een geneste-subquery SPARQL-query per
    property/richting (SELECT MIN/MAX/AVG/COUNT WHERE { SELECT ?s (COUNT(DISTINCT ?o)...)
    GROUP BY ?s }) — functioneel identiek aan wat hier gebeurt, maar rdflib's pure-Python
    SPARQL-engine bleek voor geneste aggregaten catastrofaal traag (één zo'n query op de
    274.931-triple lokale graph mat 88 seconden; bij 24 properties x 2 richtingen zou dat de
    hele pijplijnrun tot ver over een uur oprekken). graph.subject_objects() + Python
    dict/set-telling reproduceert exact dezelfde semantiek in milliseconden.
    """
    rows = []
    for p in prop_local_names:
        forward: dict = {}
        backward: dict = {}
        for s, o in graph.subject_objects(rdflib.URIRef(f"{CSOR_NS}{p}")):
            forward.setdefault(s, set()).add(o)
            backward.setdefault(o, set()).add(s)
        for direction, mapping in (("forward", forward), ("backward", backward)):
            counts = [len(v) for v in mapping.values()]
            rows.append(
                {
                    "property": p,
                    "richting": direction,
                    "min": min(counts) if counts else None,
                    "max": max(counts) if counts else None,
                    "gemiddeld": round(sum(counts) / len(counts), 2) if counts else None,
                    "aantal": len(counts),
                }
            )
    df = pd.DataFrame(rows)
    df.to_parquet(INTERIM_DIR / "conceptschema_kardinaliteiten.parquet")
    return df


def inverse_pair_flags(graph: rdflib.Graph) -> pd.DataFrame:
    flags = []
    for prop_a, prop_b in INVERSE_PAIRS:
        for a, b, richting in ((prop_a, prop_b, "forward"), (prop_b, prop_a, "backward")):
            q = (
                PREFIXES
                + f"""
            SELECT ?s ?o WHERE {{
              ?s csor:{a} ?o .
              FILTER NOT EXISTS {{ ?o csor:{b} ?s }}
            }}
            """
            )
            df = sc.select_dataframe_local(q, graph)
            for _, r in df.iterrows():
                flags.append(
                    {
                        "paar": f"{prop_a}<->{prop_b}",
                        "richting": richting,
                        "subject": r["s"],
                        "object": r["o"],
                    }
                )
    return pd.DataFrame(flags, columns=["paar", "richting", "subject", "object"])


def orphans(graph: rdflib.Graph) -> pd.DataFrame:
    q_param = (
        PREFIXES
        + """
    SELECT ?notatie ?label WHERE {
      ?param a csor:Parameter ; skos:prefLabel ?label .
      OPTIONAL { ?param skos:notation ?notatie }
      FILTER NOT EXISTS { ?param csor:heeftParameterAspect ?a }
    }
    """
    )
    q_eenheid = (
        PREFIXES
        + """
    SELECT ?notatie ?label WHERE {
      ?eenheid a csor:Eenheid ; skos:prefLabel ?label .
      OPTIONAL { ?eenheid skos:notation ?notatie }
      FILTER NOT EXISTS { ?eenheid csor:heeftKwantificeerbaarAspect ?k }
    }
    """
    )
    q_drager = (
        PREFIXES
        + """
    SELECT ?notatie ?label WHERE {
      ?drager a csor:Drager ; skos:prefLabel ?label .
      OPTIONAL { ?drager skos:notation ?notatie }
      FILTER NOT EXISTS { ?p csor:heeftDrager ?drager }
    }
    """
    )
    dfp = sc.select_dataframe_local(q_param, graph)
    dfp["orphan_type"] = "parameter_zonder_parameteraspect"
    dfe = sc.select_dataframe_local(q_eenheid, graph)
    dfe["orphan_type"] = "eenheid_zonder_kwantificeerbaaraspect"
    dfd = sc.select_dataframe_local(q_drager, graph)
    dfd["orphan_type"] = "drager_nooit_gebruikt"
    return pd.concat([dfp, dfe, dfd], ignore_index=True)[["notatie", "label", "orphan_type"]]


def main(graph: rdflib.Graph | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if graph is None:
        graph = dataset.fetch_and_save()

    coverage_df = class_coverage(graph)
    coverage_df.to_csv(OUTPUT_DIR / "conceptschema_dekking.csv", index=False)
    print("=== check_conceptschemas.py ===")
    print(f"Klassen gevonden: {len(coverage_df)}")
    print(
        coverage_df.groupby("categorie")["class"].apply(list).to_dict()
    )

    props_df = object_properties(graph)
    props_df.to_csv(OUTPUT_DIR / "csor_relaties.csv", index=False)
    print(f"\nObject-properties gevonden: {len(props_df)}")

    prop_local_names = [uri.rsplit("#", 1)[-1] for uri in props_df["prop"]]
    card_df = cardinalities(prop_local_names, graph)
    card_df.to_csv(OUTPUT_DIR / "csor_relatie_kardinaliteiten.csv", index=False)
    print(f"Kardinaliteiten berekend voor {len(prop_local_names)} properties.")

    inv_df = inverse_pair_flags(graph)
    print(f"\nInverse-paar-asymmetrieën: {len(inv_df)}")
    if len(inv_df):
        inv_df.to_csv(OUTPUT_DIR / "csor_inverse_paar_asymmetrieen.csv", index=False)
        print(inv_df.to_string())

    orphans_df = orphans(graph)
    orphans_df.to_csv(OUTPUT_DIR / "csor_orphans.csv", index=False)
    print(f"\nOrphans: {len(orphans_df)}")
    print(orphans_df["orphan_type"].value_counts().to_dict())


if __name__ == "__main__":
    main()
