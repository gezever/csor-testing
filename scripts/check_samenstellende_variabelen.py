"""
check_samenstellende_variabelen.py — herhaalbare versie van de bestaande compositie-analyse

PURPOSE
-------
Voert de queries uit sparql/samenstellende_variabelen_check.sparql (1a, 1b, 1c, 2, 3, 4, 5)
herhaalbaar uit: welke parameters delen variabelen (samenstellende-variabele-composities), en
welke van die composities tonen een structureel datakwaliteitsprobleem (inconsistente
composities, probleemgevallen, verschil-/eenterm-afleidingen)?

DATA PROVENANCE
----------------
Gemengd, met opzet — zie de gedocumenteerde valkuil in METHODOLOGY:
- Queries 1a/1b: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`, bij elke
  `scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`),
  via `sparql_client.select_dataframe_local()`.
- Queries 1c/2/3/4/5: BLIJVEN live tegen https://data-ontwikkel.omgeving.vlaanderen.be/sparql
  (default/union-graph) — zie METHODOLOGY voor de reden (blanke-knoop-identiteit).
Queries: sparql/samenstellende_variabelen_check.sparql (bron van waarheid; dit script bevat
dezelfde queryteksten inline om ze programmatisch te kunnen uitvoeren).

METHODOLOGY
-----------
- **Gedocumenteerde valkuil — blanke-knoop-identiteit gaat verloren over gepagineerde CONSTRUCT-
  pagina's heen.** Queries 1c, 2, 3, 4 en 5 navigeren via `csor:heeftTerm`/`csor:heeftBronParameter`
  naar `csor:ParameterTerm`-tussenobjecten — dit zijn RDF-**blanke knopen** (geen URI's). RDF/
  Turtle-blanke-knoopscoping is per document: elke gepagineerde CONSTRUCT-pagina wordt apart
  geparset (`common/sparql_client.py::fetch_construct`), dus een blanke knoop wiens
  samenhorende triples (bv. `?afleiding heeftTerm ?term` op pagina k, `?term heeftBronParameter
  ?p` op pagina k+1) over twee pagina's verspreid raken, wordt na het samenvoegen tot TWEE
  losse, niet-gerelateerde blanke knopen — de join breekt stil (0 resultaten in plaats van een
  foutmelding). Empirisch geverifieerd: het `parameter`-graph (155.530 triples, 16 pagina's)
  bevat de ~1279 `heeftTerm`-triples die dit raken; lokaal joinen gaf stelselmatig 0/1279 in
  plaats van 1279/1279 live. Dit treft **geen** van de andere vier check-scripts of
  generate_diagram.py — die navigeren uitsluitend URI-getypeerde entiteiten (Parameter,
  Variabele, Eenheid, ...), nooit de anonieme Term/Afleiding-machinerie. Zie ook CLAUDE.md §4.
- Queries 1a, 1b (geen blanke knopen, enkel `csor:heeftVariabele` tussen URI-entiteiten) zijn
  daarom wél naar de lokale snapshot gemigreerd -> `sparql_client.select_dataframe_local()`.
- Queries 1c, 2, 4, 5 blijven SELECT-queries rechtstreeks naar een DataFrame
  (common.sparql_client.select_dataframe, live).
- Query 3 is een CONSTRUCT (genereert csor:heeftSamenstellendeVariabele-relaties) -> gepagineerd
  via common.sparql_client.fetch_construct (dezelfde 10k-cap-veiligheid als bij graph-fetches;
  het eindresultaat van déze CONSTRUCT bevat zelf geen blanke knopen, enkel de WHERE-clausule
  navigeert ze — dus geen paginatie-identiteitsprobleem in de output, wel in de evaluatie als
  het lokaal zou draaien, vandaar ook hier live).
- Own addition: elke query wordt afzonderlijk als tussentijdse parquet bewaard onder
  data/interim/, zodat een volgende stap (of handmatige inspectie) niet opnieuw hoeft te
  bevragen.

INTERPRETATION
--------------
Een niet-nul telling bij 1c (inconsistente composities), 2 (probleemgevallen), 4
(verschilafleidingen) of 5 (eenterm-afleidingen) is op zich geen fout — elke query toetst een
specifiek structureel patroon in de compositie-logica en vergt inhoudelijke beoordeling per
geval (zie de queryomschrijvingen in sparql/samenstellende_variabelen_check.sparql). Query 1b
(gedeelde variabelen) is puur informatief: een hoge telling wijst op een veelgebruikte
variabele, geen probleem.

OUTPUTS
-------
output/tables/samenstellende_1a_multivariabele_parameters.csv
output/tables/samenstellende_1b_gedeelde_variabelen.csv
output/tables/samenstellende_1c_inconsistente_composities.csv
output/tables/samenstellende_2_probleemgevallen.csv
output/tables/samenstellende_4_verschilafleidingen.csv
output/tables/samenstellende_5_eenterm_afleidingen.csv
data/raw/samenstellende_query3_construct-<datum>.ttl (query 3's CONSTRUCT-output, apart als .ttl)
output/reports/samenstellende_variabelen.html
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, report, sparql_client as sc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERIM_DIR = REPO_ROOT / "data" / "interim"
RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_DIR = REPO_ROOT / "output" / "tables"

PREFIXES = """
PREFIX csor: <https://data.omgeving.vlaanderen.be/ns/csor#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
"""

QUERY_1A = (
    PREFIXES
    + """
SELECT ?parameter ?parameterLabel (COUNT(?variabele) AS ?aantalVariabelen)
WHERE {
  ?parameter csor:heeftVariabele ?variabele ;
             skos:prefLabel ?parameterLabel .
  FILTER NOT EXISTS { ?variabele owl:deprecated true }
}
GROUP BY ?parameter ?parameterLabel
HAVING (COUNT(?variabele) > 1)
ORDER BY DESC(?aantalVariabelen)
"""
)

QUERY_1B = (
    PREFIXES
    + """
SELECT ?variabele ?variabeleLabel (COUNT(?parameter) AS ?aantalParameters)
WHERE {
  ?parameter csor:heeftVariabele ?variabele .
  ?variabele skos:prefLabel ?variabeleLabel .
  FILTER NOT EXISTS { ?variabele owl:deprecated true }
}
GROUP BY ?variabele ?variabeleLabel
HAVING (COUNT(?parameter) > 1)
ORDER BY DESC(?aantalParameters)
"""
)

QUERY_1C = (
    PREFIXES
    + """
SELECT DISTINCT ?somVariabele ?somLabel ?doelParameter1 ?doelParameter2
WHERE {
  ?doelParameter1 csor:heeftVariabele ?somVariabele ;
                  csor:heeftAfleiding ?afl1 .
  ?doelParameter2 csor:heeftVariabele ?somVariabele ;
                  csor:heeftAfleiding ?afl2 .
  ?afl1 a csor:ParameterAfleidingVeelterm .
  ?afl2 a csor:ParameterAfleidingVeelterm .
  FILTER (STR(?doelParameter1) < STR(?doelParameter2))

  OPTIONAL { ?somVariabele skos:prefLabel ?somLabel }

  {
    ?afl1 csor:heeftTerm/csor:heeftBronParameter/csor:heeftVariabele ?bronVar .
    FILTER NOT EXISTS {
      ?afl2 csor:heeftTerm/csor:heeftBronParameter/csor:heeftVariabele ?bronVar .
    }
  } UNION {
    ?afl2 csor:heeftTerm/csor:heeftBronParameter/csor:heeftVariabele ?bronVar .
    FILTER NOT EXISTS {
      ?afl1 csor:heeftTerm/csor:heeftBronParameter/csor:heeftVariabele ?bronVar .
    }
  }
}
ORDER BY ?somLabel
"""
)

QUERY_2 = (
    PREFIXES
    + """
SELECT ?somVariabele ?somLabel ?bronParameter ?bronLabel
       (COUNT(DISTINCT ?kandidaat) AS ?aantalKandidaten)
WHERE {
  ?doelParameter csor:heeftVariabele ?somVariabele ;
                 csor:heeftAfleiding ?afleiding .
  ?afleiding a csor:ParameterAfleidingVeelterm ;
             csor:heeftTerm/csor:heeftBronParameter ?bronParameter .

  FILTER NOT EXISTS { ?somVariabele owl:deprecated true }

  OPTIONAL { ?somVariabele skos:prefLabel ?somLabel }
  OPTIONAL { ?bronParameter skos:prefLabel ?bronLabel }

  OPTIONAL {
    ?bronParameter csor:heeftVariabele ?kandidaat .
    FILTER NOT EXISTS { ?kandidaat owl:deprecated true }
  }
}
GROUP BY ?somVariabele ?somLabel ?bronParameter ?bronLabel
HAVING (COUNT(DISTINCT ?kandidaat) != 1)
ORDER BY ?somLabel ?bronLabel
"""
)

QUERY_3_BODY = (
    PREFIXES
    + """
CONSTRUCT {
  ?somVariabele csor:heeftSamenstellendeVariabele ?kandidaat .
  ?kandidaat csor:isSamenstellendeVariabeleVan ?somVariabele .
}
WHERE {
  ?doelParameter csor:heeftVariabele ?somVariabele ;
                 csor:heeftAfleiding ?afleiding .
  ?afleiding a csor:ParameterAfleidingVeelterm ;
             csor:heeftTerm ?term .
  ?term csor:heeftBronParameter ?bronParameter .
  ?bronParameter csor:heeftVariabele ?kandidaat .

  FILTER (?somVariabele != ?kandidaat)

  FILTER NOT EXISTS {
    ?afleiding csor:heeftTerm/csor:factor ?f .
    FILTER (?f <= 0)
  }

  ?afleiding csor:heeftTerm ?t1 , ?t2 .
  FILTER (?t1 != ?t2)

  FILTER NOT EXISTS { ?somVariabele owl:deprecated true }
  FILTER NOT EXISTS { ?kandidaat owl:deprecated true }
}
"""
)

QUERY_4 = (
    PREFIXES
    + """
SELECT ?afleiding ?afleidingLabel ?doelParameter ?doelLabel ?factor ?bronLabel
WHERE {
  ?afleiding a csor:ParameterAfleidingVeelterm ;
             csor:heeftDoelParameter ?doelParameter ;
             csor:heeftTerm ?term .
  ?term csor:factor ?factor ;
        csor:heeftBronParameter ?bronParameter .
  FILTER (?factor <= 0)
  OPTIONAL { ?afleiding skos:prefLabel ?afleidingLabel }
  OPTIONAL { ?doelParameter skos:prefLabel ?doelLabel }
  OPTIONAL { ?bronParameter skos:prefLabel ?bronLabel }
}
ORDER BY ?doelLabel
"""
)

QUERY_5 = (
    PREFIXES
    + """
SELECT ?afleiding ?afleidingLabel ?doelLabel ?factor ?bronLabel
WHERE {
  ?afleiding a csor:ParameterAfleidingVeelterm ;
             csor:heeftDoelParameter ?doelParameter ;
             csor:heeftTerm ?enigeTerm .
  ?enigeTerm csor:factor ?factor ;
             csor:heeftBronParameter ?bronParameter .
  FILTER NOT EXISTS {
    ?afleiding csor:heeftTerm ?andereTerm .
    FILTER (?andereTerm != ?enigeTerm)
  }
  OPTIONAL { ?afleiding skos:prefLabel ?afleidingLabel }
  OPTIONAL { ?doelParameter skos:prefLabel ?doelLabel }
  OPTIONAL { ?bronParameter skos:prefLabel ?bronLabel }
}
ORDER BY ?doelLabel
"""
)


def run_and_save_local(name: str, query: str, graph: rdflib.Graph) -> "pd.DataFrame":  # noqa: F821
    df = sc.select_dataframe_local(query, graph)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM_DIR / f"samenstellende_{name}.parquet")
    return df


def run_and_save_live(name: str, query: str) -> "pd.DataFrame":  # noqa: F821
    # Blijft live — zie METHODOLOGY (blanke-knoop-identiteit gaat verloren over gepagineerde
    # CONSTRUCT-pagina's van de lokale snapshot heen).
    df = sc.select_dataframe(query)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM_DIR / f"samenstellende_{name}.parquet")
    return df


def build_html_report(
    df_1b: pd.DataFrame,
    actual: dict,
) -> Path:
    df_1b_sorted = df_1b.copy()
    df_1b_sorted["aantalParameters"] = df_1b_sorted["aantalParameters"].astype(int)
    df_1b_sorted = df_1b_sorted.sort_values("aantalParameters", ascending=False).head(15)
    fig_top = go.Figure(
        go.Bar(
            x=df_1b_sorted["aantalParameters"][::-1],
            y=df_1b_sorted["variabeleLabel"][::-1],
            orientation="h",
            marker_color=report.FLAT_COLOR,
        )
    )
    fig_top.update_layout(
        title="Top-15 variabelen gedeeld door de meeste parameters",
        xaxis_title="aantal parameters",
        yaxis_title="",
    )
    disc_top = (
        f"{len(df_1b)} variabelen worden door meerdere parameters gedeeld, met als uitschieter "
        f"{df_1b_sorted['variabeleLabel'].iloc[0]} ({int(df_1b_sorted['aantalParameters'].iloc[0])} "
        "parameters)."
    )

    row_counts = pd.Series(
        {
            "1a": actual["1a_rows"],
            "1c": actual["1c_rows"],
            "2": actual["2_rows"],
            "4": actual["4_rows"],
            "5": actual["5_rows"],
        }
    )
    fig_rows = report.bar_counts(
        row_counts, title="Rijen per deelquery", xaxis_title="query"
    )
    nonzero = {k: v for k, v in row_counts.items() if v > 0}
    disc_rows = (
        "Geen van de deelquery's (1a, 1c, 2, 4, 5) toont momenteel een flag."
        if not nonzero
        else (
            "Deelquery('s) met een niet-nul telling: "
            + ", ".join(f"{k} ({v})" for k, v in nonzero.items())
            + ". Elke query toetst een specifiek structureel patroon in de compositie-logica "
            "(zie sparql/samenstellende_variabelen_check.sparql) en vergt inhoudelijke "
            "beoordeling per geval, geen automatische correctie."
        )
    )

    sections = [
        report.Section(
            heading="Query 1b — gedeelde variabelen",
            discussion=disc_top,
            figures=[fig_top],
        ),
        report.Section(
            heading="Rijen per deelquery",
            discussion=disc_rows,
            figures=[fig_rows],
        ),
    ]
    return report.build_report(
        name="samenstellende_variabelen",
        title="CSOR — samenstellende variabelen: reproductie van de compositie-analyse",
        intro=(
            "Welke parameters delen variabelen (samenstellende-variabele-composities), en "
            "welke van die composities tonen een structureel datakwaliteitsprobleem "
            "(inconsistente composities, probleemgevallen, verschil-/eenterm-afleidingen)?"
        ),
        sections=sections,
    )


def main(graph: rdflib.Graph | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if graph is None:
        graph = dataset.fetch_and_save()

    df_1a = run_and_save_local("1a", QUERY_1A, graph)
    df_1a.to_csv(OUTPUT_DIR / "samenstellende_1a_multivariabele_parameters.csv", index=False)

    df_1b = run_and_save_local("1b", QUERY_1B, graph)
    df_1b.to_csv(OUTPUT_DIR / "samenstellende_1b_gedeelde_variabelen.csv", index=False)

    df_1c = run_and_save_live("1c", QUERY_1C)
    df_1c.to_csv(OUTPUT_DIR / "samenstellende_1c_inconsistente_composities.csv", index=False)

    df_2 = run_and_save_live("2", QUERY_2)
    df_2.to_csv(OUTPUT_DIR / "samenstellende_2_probleemgevallen.csv", index=False)

    df_4 = run_and_save_live("4", QUERY_4)
    df_4.to_csv(OUTPUT_DIR / "samenstellende_4_verschilafleidingen.csv", index=False)

    df_5 = run_and_save_live("5", QUERY_5)
    df_5.to_csv(OUTPUT_DIR / "samenstellende_5_eenterm_afleidingen.csv", index=False)

    g3, pages3 = sc.fetch_construct(QUERY_3_BODY)
    snapshot_name = f"samenstellende_query3_construct-{date.today().isoformat()}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    g3.serialize(destination=str(RAW_DIR / f"{snapshot_name}.ttl"), format="turtle")

    actual = {
        "1a_rows": len(df_1a),
        "1b_rows": len(df_1b),
        "1c_rows": len(df_1c),
        "2_rows": len(df_2),
        # Own addition: als één afleiding meerdere termen met een negatieve factor heeft (bv.
        # AFL_62, nitriet én nitraat), levert de rauwe SELECT die afleiding twee keer op.
        # nunique() telt het aantal DISTINCTE afleidingen i.p.v. rijen — dat is de eigenlijke
        # vraag ("hoeveel afleidingen tonen dit patroon", niet "hoeveel term-rijen").
        "4_rows": df_4["afleiding"].nunique(),
        "5_rows": len(df_5),
    }

    print("=== check_samenstellende_variabelen.py ===")
    print(f"Query 1a (multi-variabele parameters): {actual['1a_rows']} rijen")
    print(f"Query 1b (gedeelde variabelen):         {actual['1b_rows']} rijen")
    print(f"Query 1c (inconsistente composities):   {len(df_1c)} rijen")
    print(f"Query 2  (probleemgevallen):             {actual['2_rows']} rijen")
    print(f"Query 3  (gegenereerde relaties):        {len(g3)} triples")
    print(
        f"Query 4  (verschilafleidingen):          {len(df_4)} rijen, "
        f"{actual['4_rows']} distincte afleidingen"
    )
    print(f"Query 5  (eenterm-afleidingen):           {actual['5_rows']} rijen")

    report_path = build_html_report(df_1b, actual)
    print(f"\nRapport geschreven naar {report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
