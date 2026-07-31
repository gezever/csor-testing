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
- Relatie-ontdekking i.p.v. een namespace-stringfilter: een predicaat geldt als "relatie"
  zodra minstens één triple een resource (URI of blanke knoop, geen literal) verbindt aan een
  `csor:`-klasse-instantie, langs subject- of objectzijde — ongeacht namespace. Own addition:
  de oorspronkelijke aanpak (`?prop a owl:ObjectProperty . FILTER(STRSTARTS(STR(?prop),
  STR(csor:)))`) mistte zo systematisch relaties die wél CSOR-instanties verbinden maar in een
  andere namespace zitten (`skos:inScheme`, `skos:broader`/`narrower` — de eenheid-hiërarchie,
  al gekend in `generate_diagram.py::RELATION_PROPERTIES` maar hier over het hoofd gezien —
  `skos:member`, `skos:broadMatch`/`exactMatch`, `dcterms:references`/`creator`, de
  PubChem-link). `rdf:type` zelf is expliciet uitgesloten (typering, geen domeinrelatie).
  Zelfde geest als de klasse-ontdekking hierboven: geen hardgecodeerde lijst/namespace-aanname,
  wel data-gedreven.
- Kardinaliteit: voor elke ontdekte relatie wordt automatisch de forward- (subject -> aantal
  objecten) en backward-kardinaliteit (object -> aantal subjecten) berekend.
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
output/reports/conceptschemas.html
data/interim/conceptschema_*.parquet (tussentijds)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, report, sparql_client as sc  # noqa: E402

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


CSOR_NS = "https://data.omgeving.vlaanderen.be/ns/csor#"

# Bekende namespaces voor de compacte qname()-weergave (enkel leesbaarheid, geen semantiek).
PREFIX_MAP = {
    CSOR_NS: "csor",
    "http://www.w3.org/2004/02/skos/core#": "skos",
    "http://purl.org/dc/terms/": "dcterms",
}
PUBCHEM_PRED = "https://pubchem.ncbi.nlm.nih.gov/rest/rdf/compound"


def qname(uri: str) -> str:
    if uri == PUBCHEM_PRED:
        return "pubchem:compound"
    for ns, prefix in PREFIX_MAP.items():
        if uri.startswith(ns) and uri != ns:
            return f"{prefix}:{uri[len(ns):]}"
    return uri


def discover_relations(graph: rdflib.Graph) -> pd.DataFrame:
    """Own addition, data-gedreven i.p.v. een namespace-stringfilter: zie METHODOLOGY.

    Vindt elk predicaat dat minstens één csor:-klasse-instantie verbindt aan een resource
    (URI of blanke knoop), langs subject- of objectzijde, ongeacht namespace. `rdf:type` is
    expliciet uitgesloten (typering, geen domeinrelatie). label/domain/range worden per
    gevonden predicaat rechtstreeks opgezocht (geen SPARQL nodig, triviale kost voor enkele
    tientallen predicaten) — blijven leeg voor predicaten uit externe vocabularia (skos:,
    dcterms:, ...) die in deze lokale snapshot geen eigen rdfs:label/domain/range-declaratie
    hebben, wat correct en verwacht is.
    """
    csor_instances = {
        s for s, o in graph.subject_objects(rdflib.RDF.type) if str(o).startswith(CSOR_NS)
    }
    relations: set[rdflib.URIRef] = set()
    for s, p, o in graph:
        if p == rdflib.RDF.type:
            continue
        if not isinstance(o, (rdflib.URIRef, rdflib.BNode)):
            continue
        if s in csor_instances or o in csor_instances:
            relations.add(p)

    rows = []
    for prop in sorted(relations, key=str):
        labels = list(graph.objects(prop, rdflib.RDFS.label))
        domains = list(graph.objects(prop, rdflib.RDFS.domain))
        ranges = list(graph.objects(prop, rdflib.RDFS.range))
        rows.append(
            {
                "prop": str(prop),
                "label": str(labels[0]) if labels else None,
                "domain": str(domains[0]) if domains else None,
                "range": str(ranges[0]) if ranges else None,
            }
        )
    df = pd.DataFrame(rows, columns=["prop", "label", "domain", "range"])
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM_DIR / "conceptschema_object_properties.parquet")
    return df


def cardinalities(prop_uris: list[str], graph: rdflib.Graph) -> pd.DataFrame:
    """Own addition, performance: dit was oorspronkelijk een geneste-subquery SPARQL-query per
    property/richting (SELECT MIN/MAX/AVG/COUNT WHERE { SELECT ?s (COUNT(DISTINCT ?o)...)
    GROUP BY ?s }) — functioneel identiek aan wat hier gebeurt, maar rdflib's pure-Python
    SPARQL-engine bleek voor geneste aggregaten catastrofaal traag (één zo'n query op de
    274.931-triple lokale graph mat 88 seconden; bij 24 properties x 2 richtingen zou dat de
    hele pijplijnrun tot ver over een uur oprekken). graph.subject_objects() + Python
    dict/set-telling reproduceert exact dezelfde semantiek in milliseconden.

    `prop_uris` zijn volledige URI's (niet langer lokale namen binnen csor: verondersteld) —
    sinds discover_relations() ook niet-csor:-relaties vindt, zou een CSOR_NS-prefix-aanname
    hier een onzinnige URI opleveren.
    """
    rows = []
    for uri in prop_uris:
        forward: dict = {}
        backward: dict = {}
        for s, o in graph.subject_objects(rdflib.URIRef(uri)):
            forward.setdefault(s, set()).add(o)
            backward.setdefault(o, set()).add(s)
        for direction, mapping in (("forward", forward), ("backward", backward)):
            counts = [len(v) for v in mapping.values()]
            rows.append(
                {
                    "property": qname(uri),
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


def _display(value) -> str:
    """Leesbare weergave voor een domain/range-waarde in de relatie-tabel: URI -> lokale naam,
    blanke-knoop-ID -> vaste tekst, leeg -> streepje."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if "://" in value:
        return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return "(blanke knoop)"


def build_html_report(
    coverage_df: pd.DataFrame,
    orphans_df: pd.DataFrame,
    inv_df: pd.DataFrame,
    props_df: pd.DataFrame,
    card_df: pd.DataFrame,
) -> Path:
    pct_dekking = 100 * coverage_df["metScheme"].sum() / coverage_df["totaal"].sum()
    afwijkend = coverage_df[coverage_df["categorie"] == "codelijst-met-afwijking"]
    class_labels = [c.rsplit("#", 1)[-1] for c in coverage_df["class"]]
    fig_coverage = go.Figure()
    fig_coverage.add_bar(name="totaal", x=class_labels, y=coverage_df["totaal"], marker_color=report.PALETTE[0])
    fig_coverage.add_bar(name="metScheme", x=class_labels, y=coverage_df["metScheme"], marker_color=report.PALETTE[1])
    fig_coverage.update_layout(
        title="Instanties per klasse: totaal vs. met skos:inScheme",
        xaxis_title="klasse",
        yaxis_title="aantal",
        barmode="group",
    )
    disc_coverage = (
        f"{pct_dekking:.1f}% van alle csor:-instanties heeft een skos:inScheme-koppeling. "
        + (
            f"{len(afwijkend)} klasse(s) tonen een afwijkende (onvolledige) dekking: "
            f"{', '.join(c.rsplit('#', 1)[-1] for c in afwijkend['class'])}. Dit is een "
            "concrete aanwijzing voor onvolledigheid en verdient navolging."
            if len(afwijkend)
            else "Geen enkele klasse toont een afwijkende dekking — dit is het verwachte "
            "patroon (een klasse zonder scheme-lidmaatschap is op zich geen fout, maar een "
            "gedeeltelijke dekking binnen een codelijstklasse wel)."
        )
    )

    fig_orphans = report.bar_counts(
        orphans_df["orphan_type"].value_counts(),
        title="Orphans per type",
        xaxis_title="orphan_type",
    )
    disc_orphans = (
        f"{len(orphans_df)} orphan-record(en) gevonden — instanties die volgens het model een "
        "gerelateerd object zouden moeten hebben, maar dat niet hebben."
        if len(orphans_df)
        else "Geen orphans gevonden — het verwachte patroon."
    )

    if len(inv_df):
        disc_inverse = (
            f"{len(inv_df)} inverse-paar-asymmetrie(ën) gevonden, verdeeld over: "
            f"{', '.join(f'{k} ({v})' for k, v in inv_df['paar'].value_counts().items())}. "
            "Elke rij betekent dat één richting van een verondersteld inverse-paar ontbreekt — "
            "een concrete aanwijzing voor onvolledigheid."
        )
    else:
        disc_inverse = (
            "Geen inverse-paar-asymmetrieën gevonden voor de twee getoetste paren "
            "(heeftParameterAspect<->heeftParameter, heeftKwantificeerbaarAspect<->"
            "toepasbareEenheid) — het verwachte patroon."
        )

    sections = [
        report.Section(
            heading="Conceptschema-dekking per klasse",
            discussion=disc_coverage,
            figures=[fig_coverage],
            table_df=coverage_df,
        ),
        report.Section(
            heading="Orphan-detectie",
            discussion=disc_orphans,
            figures=[fig_orphans] if len(orphans_df) else [],
            table_df=orphans_df if len(orphans_df) else None,
        ),
        report.Section(
            heading="Inverse-paar-asymmetrieën",
            discussion=disc_inverse,
            table_df=inv_df if len(inv_df) else None,
        ),
    ]

    pivot = card_df.pivot(index="property", columns="richting", values="max").fillna(0)
    for direction in ("forward", "backward"):
        if direction not in pivot.columns:
            pivot[direction] = 0
    pivot["totaal"] = pivot["forward"] + pivot["backward"]
    pivot = pivot.sort_values("totaal", ascending=False).head(15)
    fig_card = go.Figure()
    fig_card.add_bar(name="forward max", x=pivot.index.tolist(), y=pivot["forward"], marker_color=report.PALETTE[0])
    fig_card.add_bar(name="backward max", x=pivot.index.tolist(), y=pivot["backward"], marker_color=report.PALETTE[1])
    fig_card.update_layout(
        title="Top-15 relaties naar max-kardinaliteit (forward vs. backward)",
        xaxis_title="relatie",
        yaxis_title="max kardinaliteit",
        barmode="group",
    )

    card_nonzero = card_df.dropna(subset=["max"])
    top3 = card_nonzero.sort_values("max", ascending=False).head(3)
    disc_card = (
        f"{len(props_df)} relaties ontdekt — data-gedreven (elk predicaat dat minstens één "
        "csor:-klasse-instantie verbindt aan een resource, ongeacht namespace), niet beperkt "
        "tot csor:-eigen owl:ObjectProperty-declaraties. Hoogste max-kardinaliteiten: "
        + ", ".join(
            f"{r['property']} ({r['richting']}, max {int(r['max'])})" for _, r in top3.iterrows()
        )
        + "."
    )
    props_display = pd.DataFrame(
        {
            "relatie": [qname(p) for p in props_df["prop"]],
            "label": props_df["label"].fillna("—"),
            "domain": props_df["domain"].apply(_display),
            "range": props_df["range"].apply(_display),
        }
    )

    sections.append(
        report.Section(
            heading="Object-properties en kardinaliteiten",
            discussion=disc_card,
            figures=[fig_card],
            table_df=props_display,
            table_n=len(props_display),
        )
    )

    return report.build_report(
        name="conceptschemas",
        title="CSOR — conceptschema's: structuur, volledigheid en kardinaliteit",
        intro=(
            "Welke conceptschema's zijn er en hoe verhouden hun klassen zich tot elkaar, "
            "behoort ieder element tot een conceptschema, en wat zijn de kardinaliteiten van "
            "de onderlinge relaties?"
        ),
        sections=sections,
    )


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

    props_df = discover_relations(graph)
    props_df.to_csv(OUTPUT_DIR / "csor_relaties.csv", index=False)
    print(f"\nRelaties gevonden: {len(props_df)}")

    card_df = cardinalities(props_df["prop"].tolist(), graph)
    card_df.to_csv(OUTPUT_DIR / "csor_relatie_kardinaliteiten.csv", index=False)
    print(f"Kardinaliteiten berekend voor {len(props_df)} relaties.")

    inv_df = inverse_pair_flags(graph)
    print(f"\nInverse-paar-asymmetrieën: {len(inv_df)}")
    if len(inv_df):
        inv_df.to_csv(OUTPUT_DIR / "csor_inverse_paar_asymmetrieen.csv", index=False)
        print(inv_df.to_string())

    orphans_df = orphans(graph)
    orphans_df.to_csv(OUTPUT_DIR / "csor_orphans.csv", index=False)
    print(f"\nOrphans: {len(orphans_df)}")
    print(orphans_df["orphan_type"].value_counts().to_dict())

    report_path = build_html_report(coverage_df, orphans_df, inv_df, props_df, card_df)
    print(f"\nRapport geschreven naar {report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
