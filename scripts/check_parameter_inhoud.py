"""
check_parameter_inhoud.py — inhoudelijke consistentiechecks op Parameter en ParameterAspect

PURPOSE
-------
Test niet enkel of relaties/kardinaliteit kloppen (zie check_conceptschemas.py), maar of de
waarden van velden zelf onderling consistent en correct zijn — op basis van een diepgaande
steekproef per klasse-type (zie reports/rapport_parameter_inhoud.md). Beantwoordt: horen
`altLabel`/`verkorteNotatie` identiek te zijn, is een verlopen `geldigTot` nog actief, kan een
CAS-nummer van Parameter naar Variabele verrijkt worden, is de EEA-code correct opgemaakt, en
is het `ParameterAspect`-label nog steeds herleidbaar uit zijn samenstellende delen?

DATA PROVENANCE
----------------
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`
— zie dat bestand voor de onderliggende live-fetch/paginatie/verificatie-laag.
Queries: sparql/parameter_inhoud_checks.sparql (bron van waarheid; queryteksten hieronder
inline om ze programmatisch te kunnen uitvoeren — lokaal uitgevoerd via
`sparql_client.select_dataframe_local()`).

METHODOLOGY
-----------
- Alle checks hieronder zijn tijdens de verkenning eerst op de **volledige populatie**
  geverifieerd (niet enkel een steekproef) — dit script herhaalt diezelfde toetsen bij elke run
  tegen de vers opgehaalde lokale snapshot.
- **EEA-code-formatcheck**: own addition — `csor:eea` is de EEA-code (bevestigd via de
  property-definitie zelf), niet het EC/EINECS-nummer zoals eerder verondersteld. Het
  EC-nummerpatroon (XXX-XXX-X) gaf daardoor grotendeels valse afwijkingen; de correcte,
  generieke toets is `\\d+-\\d+-\\d+` (drie cijfergroepen van willekeurige lengte).
- **ParameterAspect-labelreconstructie**: het label volgt het patroon
  `"{Parameter.symbool} ({SoortWaardebepaling.prefLabel} in {Drager.prefLabel}):
  {KwantificeerbaarAspect.prefLabel}"` — empirisch afgeleid uit twee voorbeelden en op de
  volledige populatie van 8537 bevestigd (0 mismatches tijdens de verkenning).
- **Own addition, bewust NIET geïmplementeerd**: een vergelijkbare "symbool = kanonieke
  transformatie van het label"-hypothese voor `csor:SoortWaardebepaling` bleek bij toetsing op
  de volledige populatie van 80 fout (67/80 "afwijkingen" — `symbool` is een handmatige
  afkorting, geen deterministische afleiding). Zie reports/rapport_parameter_inhoud.md — geen
  check op een fout patroon bouwen.

INTERPRETATION
--------------
De CAS-verrijkingskansen en EEA-mismatches zijn suggesties/vlaggen voor handmatige review, geen
automatisch teruggeschreven correcties. De ParameterAspect-labelcheck is vooral
regressiebewaking: een mismatch wijst op een verouderd label na een latere hernoeming.

OUTPUTS
-------
output/tables/parameter_inhoud_vlaggen.csv
output/tables/parameter_cas_verrijking.csv
output/tables/parameter_eea_mismatch.csv
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
PREFIX csor: <https://data.omgeving.vlaanderen.be/ns/csor#>
"""

QUERY_ALTLABEL = (
    PREFIXES
    + """
SELECT ?p ?altLabel ?verkorteNotatie WHERE {
  ?p a csor:Parameter ; skos:altLabel ?altLabel ; csor:verkorteNotatie ?verkorteNotatie .
  FILTER(STR(?altLabel) != STR(?verkorteNotatie))
}
"""
)

QUERY_GELDIGTOT = (
    PREFIXES
    + """
SELECT ?p ?label ?geldigTot WHERE {
  ?p a csor:Parameter ; csor:geldigTot ?geldigTot ; skos:prefLabel ?label .
  FILTER NOT EXISTS { ?p owl:deprecated true }
  FILTER(?geldigTot < NOW())
}
"""
)

QUERY_CAS_VERRIJKING = (
    PREFIXES
    + """
SELECT ?p ?pLabel ?pCas ?v WHERE {
  ?p a csor:Parameter ; csor:cas ?pCas ; csor:heeftVariabele ?v ; skos:prefLabel ?pLabel .
  FILTER NOT EXISTS { ?v csor:cas ?vCas }
}
"""
)

QUERY_EEA_FORMAT = (
    PREFIXES
    + """
SELECT ?s ?eea WHERE {
  { ?s a csor:Parameter } UNION { ?s a csor:Variabele }
  ?s csor:eea ?eea .
  FILTER(!REGEX(STR(?eea), "^[0-9]+-[0-9]+-[0-9]+$"))
}
"""
)

QUERY_EEA_MISMATCH = (
    PREFIXES
    + """
SELECT ?p ?pLabel ?pEea ?vEea WHERE {
  ?p a csor:Parameter ; csor:eea ?pEea ; csor:heeftVariabele ?v ; skos:prefLabel ?pLabel .
  ?v csor:eea ?vEea .
  FILTER(STR(?pEea) != STR(?vEea))
}
"""
)

QUERY_PARAMETERASPECT_LABEL = (
    PREFIXES
    + """
SELECT ?pa ?label ?paramSymbool ?swbLabel ?dragerLabel ?kwaLabel WHERE {
  ?pa a csor:ParameterAspect ; skos:prefLabel ?label ;
      csor:heeftParameter ?param ; csor:heeftAspect ?kwa .
  FILTER NOT EXISTS { ?pa owl:deprecated true }
  ?param csor:symbool ?paramSymbool ;
         csor:heeftDrager ?drager ;
         csor:heeftSoortWaardebepaling ?swb .
  ?drager skos:prefLabel ?dragerLabel .
  ?swb skos:prefLabel ?swbLabel .
  ?kwa skos:prefLabel ?kwaLabel .
}
"""
)

# Self-test: bekend record PAS_5307, vastgesteld tijdens de verkenning.
SELF_TEST = {
    "notatie": "PAS_5307",
    "expected_label": "TCPP (standaard in water): vracht",
}


def build_flags(altlabel_df, geldigtot_df, eea_format_df) -> pd.DataFrame:
    flags = []
    for _, r in altlabel_df.iterrows():
        flags.append(
            {
                "notatie": r["p"].rsplit("/", 1)[-1],
                "klasse": "Parameter",
                "vlag_type": "altlabel_verkortenotatie_verschil",
                "detail": f"altLabel={r['altLabel']!r} verkorteNotatie={r['verkorteNotatie']!r}",
            }
        )
    for _, r in geldigtot_df.iterrows():
        flags.append(
            {
                "notatie": r["p"].rsplit("/", 1)[-1],
                "klasse": "Parameter",
                "vlag_type": "geldigtot_verlopen_maar_actief",
                "detail": f"geldigTot={r['geldigTot']} label={r['label']!r}",
            }
        )
    for _, r in eea_format_df.iterrows():
        flags.append(
            {
                "notatie": r["s"].rsplit("/", 1)[-1],
                "klasse": "Parameter/Variabele",
                "vlag_type": "eea_format_afwijkend",
                "detail": f"eea={r['eea']!r}",
            }
        )
    return pd.DataFrame(flags, columns=["notatie", "klasse", "vlag_type", "detail"])


def parameteraspect_label_check(df: pd.DataFrame) -> pd.DataFrame:
    def expected(r):
        return f"{r['paramSymbool']} ({r['swbLabel']} in {r['dragerLabel']}): {r['kwaLabel']}"

    df = df.copy()
    df["verwacht"] = df.apply(expected, axis=1)
    mismatches = df[df["label"] != df["verwacht"]]
    return mismatches[["pa", "label", "verwacht"]].rename(columns={"pa": "notatie"})


def self_test(df: pd.DataFrame) -> None:
    row = df[df["pa"].str.endswith(f"/{SELF_TEST['notatie']}")]
    if row.empty:
        raise RuntimeError(f"Self-test mislukt: {SELF_TEST['notatie']} niet gevonden.")
    row = row.iloc[0]
    actual = row["label"]
    if actual != SELF_TEST["expected_label"]:
        raise RuntimeError(
            f"Self-test mislukt voor {SELF_TEST['notatie']}: "
            f"verwacht {SELF_TEST['expected_label']!r}, gekregen {actual!r}."
        )
    print(f"Self-test OK: {SELF_TEST['notatie']} = {actual!r}")


def main(graph: rdflib.Graph | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    print("=== check_parameter_inhoud.py ===")

    if graph is None:
        graph = dataset.fetch_and_save()

    altlabel_df = sc.select_dataframe_local(QUERY_ALTLABEL, graph)
    geldigtot_df = sc.select_dataframe_local(QUERY_GELDIGTOT, graph)
    eea_format_df = sc.select_dataframe_local(QUERY_EEA_FORMAT, graph)
    cas_df = sc.select_dataframe_local(QUERY_CAS_VERRIJKING, graph)
    eea_mismatch_df = sc.select_dataframe_local(QUERY_EEA_MISMATCH, graph)
    pas_df = sc.select_dataframe_local(QUERY_PARAMETERASPECT_LABEL, graph)

    for name, df in (
        ("altlabel", altlabel_df),
        ("geldigtot", geldigtot_df),
        ("eea_format", eea_format_df),
        ("cas_verrijking", cas_df),
        ("eea_mismatch", eea_mismatch_df),
        ("parameteraspect_label", pas_df),
    ):
        df.to_parquet(INTERIM_DIR / f"parameter_inhoud_{name}.parquet")

    self_test(pas_df)

    flags_df = build_flags(altlabel_df, geldigtot_df, eea_format_df)
    pas_mismatches = parameteraspect_label_check(pas_df)
    for _, r in pas_mismatches.iterrows():
        flags_df.loc[len(flags_df)] = {
            "notatie": r["notatie"].rsplit("/", 1)[-1],
            "klasse": "ParameterAspect",
            "vlag_type": "label_niet_herleidbaar",
            "detail": f"actueel={r['label']!r} verwacht={r['verwacht']!r}",
        }
    flags_df.to_csv(OUTPUT_DIR / "parameter_inhoud_vlaggen.csv", index=False)

    cas_df.to_csv(OUTPUT_DIR / "parameter_cas_verrijking.csv", index=False)
    eea_mismatch_df.to_csv(OUTPUT_DIR / "parameter_eea_mismatch.csv", index=False)

    print(f"altLabel/verkorteNotatie-verschillen: {len(altlabel_df)}")
    print(f"geldigTot verlopen maar actief: {len(geldigtot_df)}")
    print(f"EEA-code-formaatafwijkingen: {len(eea_format_df)}")
    print(f"CAS-verrijkingskansen: {len(cas_df)}")
    print(f"Parameter-vs-Variabele EEA-mismatches: {len(eea_mismatch_df)}")
    print(f"ParameterAspect-labelmismatches: {len(pas_mismatches)} (van {len(pas_df)} getoetst)")
    print(f"\nTotaal vlaggen: {len(flags_df)}")


if __name__ == "__main__":
    main()
