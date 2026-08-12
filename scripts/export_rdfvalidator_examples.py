"""
export_rdfvalidator_examples.py — verse per-graph CSOR-snapshots voor RdfValidator

PURPOSE
-------
Ververst de CSOR-voorbeeldinstantiedata en de ontologiebestanden die
`/home/gehau/git/RdfValidator`'s JUnit-testharness (`CosrValidationTest.java`) gebruikt om
`csor.ttl` tegen de werkelijke registerdata te valideren. Geen `check_*.py`-script (geen
output/tables/output/reports) — een eenmalig te herdraaien utility-script, analoog aan de
fetch_*.py-scripts in §1 van CLAUDE.md, maar dan met een ander repo als bestemming.

DATA PROVENANCE
----------------
Bron: https://data-ontwikkel.omgeving.vlaanderen.be/sparql, elk van de 10 CSOR-codelijstgraphs
(`scripts/common/dataset.py::GRAPH_NAMES`), individueel en vers opgehaald — NIET geslicet uit
`analyse/csor_merged.ttl`. Reden: dat bestand is zelf al het resultaat van apart-geparste
CONSTRUCT-pagina's; blanke-knoop-identiteit (csor:ParameterTerm/csor:VeeltermParameterTerm) gaat
daarbij al verloren (CLAUDE.md §4). Een nieuwe live fetch per graph via
`scripts/common/sparql_client.py::fetch_graph()` (dezelfde aanpak als
`dataset.py::fetch_and_save()`) is niet slechter dan de bestaande RdfValidator-voorbeelddata
(die volgens dezelfde methode tot stand kwam) en garandeert een actuele stand.

METHODOLOGY
-----------
Voor elke graph in GRAPH_NAMES: fetch_graph(naam) -> serialiseer naar
RdfValidator/src/test/resources/examples/cosr/<bestandsnaam>.ttl. Bestandsnaam volgt de
conventie die de bestaande testharness al gebruikt; `kwantificeerbaar-aspect` en
`kwantificeerbare-aspect`-verwarring (twee bestanden voor dezelfde graph, zie
plan/rapportnotities) wordt opgelost tot één correct benoemd bestand
(`kwantificeerbaaraspect.ttl`) — het oude, verkeerd benoemde bestand wordt verwijderd. Kopieert
ook `ontology/csor.ttl` en `ontology/pubchem.ttl` naar
`RdfValidator/src/test/resources/ontologies/` (overschrijft de eerdere, niet-gecommitte
conceptversie van `csor.ttl` daar).

INTERPRETATION
--------------
n.v.t. — bouwsteen voor een validatiestap in een extern repo, geen eigen bevindingen.

OUTPUTS
-------
RdfValidator/src/test/resources/examples/cosr/*.ttl (extern repo, niet gecommit door dit script)
RdfValidator/src/test/resources/ontologies/{csor,pubchem}.ttl (extern repo, niet gecommit)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import sparql_client as sc  # noqa: E402
from common.dataset import GRAPH_NAMES  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RDFVALIDATOR_ROOT = Path("/home/gehau/git/RdfValidator")
EXAMPLES_DIR = RDFVALIDATOR_ROOT / "src/test/resources/examples/cosr"
ONTOLOGIES_DIR = RDFVALIDATOR_ROOT / "src/test/resources/ontologies"

GRAPH_TO_FILENAME = {
    "drager": "drager.ttl",
    "eenheid": "eenheid.ttl",
    "kwalificeerbaar-aspect": "kwalificeerbaaraspect.ttl",
    "kwantificeerbaar-aspect": "kwantificeerbaaraspect.ttl",
    "natuurkundige-dimensie": "natuurkundigedimensie.ttl",
    "parameter": "parameter.ttl",
    "parameteraspect": "parameteraspect.ttl",
    "resultaat-type": "resultaattype.ttl",
    "soort-waardebepaling": "soortwaardebepaling.ttl",
    "variabele": "variabele.ttl",
}

# Verkeerd benoemd bestand uit de vorige (24 juni) export — bevatte in werkelijkheid de
# csor:KwantificeerbaarAspect-instanties (met het ondertussen hernoemde `csor:eenheden`-
# predicaat), terwijl het correct benoemde `kwantificeerbaaraspect.ttl` toen net de omgekeerde
# csor:Eenheid-kant bevatte. Wordt hier opgeruimd na de verse export.
STALE_FILE_TO_REMOVE = "kwantificeerbareaspect.ttl"


def main() -> None:
    if not RDFVALIDATOR_ROOT.exists():
        raise SystemExit(f"RdfValidator-repo niet gevonden op {RDFVALIDATOR_ROOT}")

    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    ONTOLOGIES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== export_rdfvalidator_examples.py ({len(GRAPH_NAMES)} graphs) ===")
    for name in GRAPH_NAMES:
        filename = GRAPH_TO_FILENAME[name]
        fetch = sc.fetch_graph(name)
        dest = EXAMPLES_DIR / filename
        fetch.graph.serialize(destination=str(dest), format="turtle")
        print(
            f"  {name}: {fetch.parsed_count} triples ({fetch.pages} pagina('s), "
            f"geverifieerd={fetch.verified}) -> {dest.relative_to(RDFVALIDATOR_ROOT)}"
        )

    stale = EXAMPLES_DIR / STALE_FILE_TO_REMOVE
    if stale.exists():
        stale.unlink()
        print(f"  verwijderd (verkeerd benoemd, achterhaald): {stale.relative_to(RDFVALIDATOR_ROOT)}")

    for name in ("csor.ttl", "pubchem.ttl"):
        src = REPO_ROOT / "ontology" / name
        dest = ONTOLOGIES_DIR / name
        shutil.copyfile(src, dest)
        print(f"  ontologie gekopieerd: ontology/{name} -> {dest.relative_to(RDFVALIDATOR_ROOT)}")

    print("Klaar.")


if __name__ == "__main__":
    main()
