"""
dataset.py — lokale volledige-registersnapshot: ophalen, samenvoegen, hergebruiken

PURPOSE
-------
Regenereert bij elke pijplijnrun een lokale, volledige samenvoeging van alle 10 CSOR-graphs
(analyse/csor_merged.ttl). Alle scripts/check_*.py draaien hun CSOR-queries hierop lokaal via
rdflib i.p.v. elk apart en herhaaldelijk de live endpoint te bevragen — sneller (één fetch i.p.v.
tientallen HTTP-rondritten) en consistent (alle checks in één run zien exact dezelfde snapshot).

DATA PROVENANCE
----------------
Endpoint: https://data-ontwikkel.omgeving.vlaanderen.be/sparql, via
scripts/common/sparql_client.py::fetch_graph (per graph gepagineerd + geverifieerd tegen een
onafhankelijke COUNT-query — zie sparql_client.py METHODOLOGY en CLAUDE.md §4).
Graphs: de 10 CSOR-codelijstgraphs (GRAPH_NAMES hieronder) — dit is het volledige CSOR-register;
de ontologie-declaraties (owl:ObjectProperty, rdfs:domain/range, rdfs:label/comment op
properties) blijken empirisch mee te zitten in het `drager`-graph, dus geen apart vocabulaire-
graph nodig.

METHODOLOGY
-----------
fetch_and_save() haalt alle 10 graphs afzonderlijk geverifieerd op, merget ze in één
rdflib.Graph en serialiseert naar analyse/csor_merged.ttl (gitignored, regenereerbaar — net als
data/raw/). Own addition t.o.v. een eerdere iteratie van dit project, waar dit bestand een
eenmalig, niet-hergebruikt verkenningshulpmiddel was: het wordt nu bij elke
scripts/run_all.py-run vers opgehaald en is de enige databron van de checks (behalve de externe
PubChem/QUDT-crosschecks, die per definitie extern blijven).

INTERPRETATION
--------------
n.v.t. — bouwsteen, geen eigen bevindingen.

OUTPUTS
-------
analyse/csor_merged.ttl (gitignored, regenereerbaar)
"""

from __future__ import annotations

from pathlib import Path

import rdflib

from . import sparql_client as sc

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SNAPSHOT_PATH = REPO_ROOT / "analyse" / "csor_merged.ttl"

GRAPH_NAMES = [
    "drager",
    "eenheid",
    "kwalificeerbaar-aspect",
    "kwantificeerbaar-aspect",
    "natuurkundige-dimensie",
    "parameter",
    "parameteraspect",
    "resultaat-type",
    "soort-waardebepaling",
    "variabele",
]


def fetch_and_save(
    path: Path = DEFAULT_SNAPSHOT_PATH,
    endpoint: str = sc.DEFAULT_ENDPOINT,
    graph_names: list[str] | None = None,
) -> rdflib.Graph:
    """Haalt alle CSOR-graphs live+geverifieerd op, merget en bewaart als analyse/csor_merged.ttl.

    Wordt aangeroepen zonder argumenten door scripts/run_all.py (één keer per pijplijnrun) en
    door elk check_*.py::main() als er geen graph is meegegeven (standalone-run) — zie de
    METHODOLOGY-sectie van elk check-script.
    """
    graph_names = graph_names or GRAPH_NAMES
    merged = rdflib.Graph()
    print(f"Lokale snapshot regenereren uit {len(graph_names)} CSOR-graphs ({endpoint})...")
    for name in graph_names:
        fetch = sc.fetch_graph(name, endpoint=endpoint)
        merged += fetch.graph
        print(
            f"  {name}: {fetch.parsed_count} triples ({fetch.pages} pagina('s), "
            f"geverifieerd={fetch.verified})"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.serialize(destination=str(path), format="turtle")
    print(f"Lokale snapshot bijgewerkt: {path} ({len(merged)} triples).")
    return merged
