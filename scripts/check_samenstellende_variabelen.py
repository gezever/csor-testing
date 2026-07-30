"""
check_samenstellende_variabelen.py — herhaalbare versie van de bestaande compositie-analyse

PURPOSE
-------
Voert de queries uit sparql/samenstellende_variabelen_check.sparql (1a, 1b, 1c, 2, 3, 4, 5)
herhaalbaar uit tegen de live CSOR-endpoint, in plaats van de eenmalige, statische analyse van
27 juli 2026 die vastligt in reports/rapport_samenstellende_variabelen.md. Vergelijkt de
herproduceerde kerncijfers met de cijfers uit dat rapport, zodat het rapport niet stilzwijgend
verouderd raakt als het register wijzigt.

DATA PROVENANCE
----------------
Endpoint: https://data-ontwikkel.omgeving.vlaanderen.be/sparql (default/union-graph — deze
queries gebruiken geen GRAPH-clausule, in tegenstelling tot check_variabele_identity.py).
Queries: sparql/samenstellende_variabelen_check.sparql (bron van waarheid; dit script bevat
dezelfde queryteksten inline om ze programmatisch te kunnen uitvoeren).

METHODOLOGY
-----------
- Queries 1a, 1b, 1c, 2, 4, 5 zijn SELECT-queries -> rechtstreeks naar een DataFrame
  (common.sparql_client.select_dataframe), geen paginatie nodig (kleine resultaatsets).
- Query 3 is een CONSTRUCT (genereert csor:heeftSamenstellendeVariabele-relaties) -> gepagineerd
  via common.sparql_client.fetch_construct (dezelfde 10k-cap-veiligheid als bij graph-fetches).
- Own addition: elke query wordt afzonderlijk als tussentijdse parquet bewaard onder
  data/interim/, zodat een volgende stap (of handmatige inspectie) niet opnieuw hoeft te
  bevragen.

INTERPRETATION
--------------
Een REGRESSIE-melding (afwijkend van het bestaande rapport) is geen fout op zich — het kan
betekenen dat het register intussen gewijzigd is (bv. het triazool-geval V_1533 is rechtgezet).
Het is een signaal om het bestaande rapport te herlezen en eventueel bij te werken, niet om het
script te "fixen".

OUTPUTS
-------
output/tables/samenstellende_1a_multivariabele_parameters.csv
output/tables/samenstellende_1b_gedeelde_variabelen.csv
output/tables/samenstellende_1c_inconsistente_composities.csv
output/tables/samenstellende_2_probleemgevallen.csv
output/tables/samenstellende_4_verschilafleidingen.csv
output/tables/samenstellende_5_eenterm_afleidingen.csv
data/raw/samenstellende_query3_construct-<datum>.ttl (query 3's CONSTRUCT-output, apart als .ttl)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import sparql_client as sc  # noqa: E402

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

# Kerncijfers uit reports/rapport_samenstellende_variabelen.md (27 juli 2026), gebruikt als
# regressiereferentie — geen harde assert, enkel een gerapporteerde afwijking.
EXPECTED = {
    "1a_rows": 0,
    "1b_rows": 1046,
    "2_rows": 2,
    "4_rows": 7,
    "5_rows": 7,
}


def run_and_save(name: str, query: str) -> "pd.DataFrame":  # noqa: F821
    df = sc.select_dataframe(query)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM_DIR / f"samenstellende_{name}.parquet")
    return df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df_1a = run_and_save("1a", QUERY_1A)
    df_1a.to_csv(OUTPUT_DIR / "samenstellende_1a_multivariabele_parameters.csv", index=False)

    df_1b = run_and_save("1b", QUERY_1B)
    df_1b.to_csv(OUTPUT_DIR / "samenstellende_1b_gedeelde_variabelen.csv", index=False)

    df_1c = run_and_save("1c", QUERY_1C)
    df_1c.to_csv(OUTPUT_DIR / "samenstellende_1c_inconsistente_composities.csv", index=False)

    df_2 = run_and_save("2", QUERY_2)
    df_2.to_csv(OUTPUT_DIR / "samenstellende_2_probleemgevallen.csv", index=False)

    df_4 = run_and_save("4", QUERY_4)
    df_4.to_csv(OUTPUT_DIR / "samenstellende_4_verschilafleidingen.csv", index=False)

    df_5 = run_and_save("5", QUERY_5)
    df_5.to_csv(OUTPUT_DIR / "samenstellende_5_eenterm_afleidingen.csv", index=False)

    g3, pages3 = sc.fetch_construct(QUERY_3_BODY)
    snapshot_name = f"samenstellende_query3_construct-{date.today().isoformat()}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    g3.serialize(destination=str(RAW_DIR / f"{snapshot_name}.ttl"), format="turtle")

    actual = {
        "1a_rows": len(df_1a),
        "1b_rows": len(df_1b),
        "2_rows": len(df_2),
        # Own addition: het rapport telt "7 verschil-afleidingen" als DISTINCTE afleidingen
        # (AFL_62 + 6 PFAS-afleidingen); de rauwe SELECT geeft 8 RIJEN terug omdat AFL_62 twee
        # termen met een negatieve factor heeft (nitriet én nitraat) en dus twee keer voorkomt.
        # nunique() reproduceert exact wat het rapport bedoelt met "7"; len(df_4) zou hier
        # 8 geven en een vals-positieve regressiemelding opleveren.
        "4_rows": df_4["afleiding"].nunique(),
        "5_rows": len(df_5),
    }

    print("=== check_samenstellende_variabelen.py ===")
    print(f"Query 1a (multi-variabele parameters): {actual['1a_rows']} rijen")
    print(f"Query 1b (gedeelde variabelen):         {actual['1b_rows']} rijen")
    print(f"Query 1c (inconsistente composities):   {len(df_1c)} rijen")
    print(f"Query 2  (probleemgevallen):             {actual['2_rows']} rijen")
    print(f"Query 3  (gegenereerde relaties):        {len(g3)} triples, {pages3} pagina('s)")
    print(
        f"Query 4  (verschilafleidingen):          {len(df_4)} rijen, "
        f"{actual['4_rows']} distincte afleidingen"
    )
    print(f"Query 5  (eenterm-afleidingen):           {actual['5_rows']} rijen")

    print("\nRegressie t.o.v. reports/rapport_samenstellende_variabelen.md (27 juli 2026):")
    regressions = 0
    for key, expected_value in EXPECTED.items():
        got = actual[key]
        if got != expected_value:
            regressions += 1
            print(f"  AFWIJKEND — {key}: verwacht {expected_value}, nu {got}")
    if regressions == 0:
        print("  Geen afwijkingen — herproduceerde cijfers komen overeen met het rapport.")
    else:
        print(
            f"  {regressions} afwijking(en) gevonden — controleer of het register gewijzigd is "
            "en werk reports/rapport_samenstellende_variabelen.md bij indien nodig."
        )


if __name__ == "__main__":
    main()
