"""
sparql_client.py — gedeelde SPARQL-fetch/paginatie-laag voor csor-testing

PURPOSE
-------
Haalt CSOR named graphs betrouwbaar en volledig op via SPARQL CONSTRUCT/SELECT tegen de
dev-endpoint, met de verplichte paginatie-aanpak. Wordt gedeeld door alle scripts/check_*.py.

DATA PROVENANCE
----------------
Endpoint: https://data-ontwikkel.omgeving.vlaanderen.be/sparql
Graphs:   https://data.omgeving.vlaanderen.be/id/graph/codelijst-csor-<naam>

METHODOLOGY
-----------
- fetch_graph(): per-graph gepagineerde CONSTRUCT (LIMIT/OFFSET, GEEN ORDER BY — dat gaf een
  HTTP 500 op deze endpoint tijdens verkenning), met verplichte verificatie tegen een losse
  COUNT-query. Reden: de endpoint knipt CONSTRUCT-resultaten stil af op 10.000 triples zonder
  foutmelding (zie CLAUDE.md §4) — zonder paginatie + verificatie zou dit onopgemerkt data
  laten wegvallen.
- select_dataframe(): SELECT-query rechtstreeks naar een pandas DataFrame.
- to_dataframe(): rdflib-graph -> tidy pandas DataFrame, één rij per subject van een gegeven
  rdf:type, één kolom per predicaat.

OUTPUTS
-------
Geen eigen output-bestanden — bouwsteen voor scripts/check_*.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import rdflib
import requests

DEFAULT_ENDPOINT = "https://data-ontwikkel.omgeving.vlaanderen.be/sparql"
GRAPH_NS = "https://data.omgeving.vlaanderen.be/id/graph/codelijst-csor-"
PAGE_SIZE = 10_000


def graph_uri(name: str) -> str:
    return f"{GRAPH_NS}{name}"


def _http_get(endpoint: str, query: str, accept: str) -> bytes:
    resp = requests.get(endpoint, params={"query": query}, headers={"Accept": accept}, timeout=120)
    resp.raise_for_status()
    return resp.content


def count_graph_triples(graph_name: str, endpoint: str = DEFAULT_ENDPOINT) -> int:
    """Onafhankelijke COUNT-query — de referentiewaarde waartegen fetch_graph() verifieert."""
    query = f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph_uri(graph_name)}> {{ ?s ?p ?o }} }}"
    data = _http_get(endpoint, query, "application/sparql-results+json")
    result = json.loads(data)
    return int(result["results"]["bindings"][0]["n"]["value"])


@dataclass
class FetchResult:
    graph: rdflib.Graph
    graph_name: str
    endpoint: str
    expected_count: int
    parsed_count: int
    pages: int
    fetched_at: str

    @property
    def verified(self) -> bool:
        return self.expected_count == self.parsed_count


def fetch_construct(
    query_body: str,
    endpoint: str = DEFAULT_ENDPOINT,
    page_size: int = PAGE_SIZE,
) -> tuple[rdflib.Graph, int]:
    """Pagineert een willekeurige `CONSTRUCT ... WHERE {...}`-queryromp (zonder LIMIT/OFFSET).

    Geen ORDER BY toevoegen aan query_body (HTTP 500 op deze endpoint); pagina's bleken
    empirisch stabiel en niet-overlappend zonder ORDER BY. Geeft (graph, aantal_pagina's) terug.
    Gebruikt door fetch_graph() (graph-scoped) en door check_samenstellende_variabelen.py voor
    query 3, die geen GRAPH-clausule gebruikt (het default/union-graph van de endpoint).
    """
    g = rdflib.Graph()
    offset = 0
    pages = 0
    while True:
        query = f"{query_body} LIMIT {page_size} OFFSET {offset}"
        data = _http_get(endpoint, query, "text/turtle")
        before = len(g)
        g.parse(data=data, format="turtle")
        page_triples = len(g) - before
        pages += 1
        if page_triples < page_size:
            break
        offset += page_size
    return g, pages


def fetch_graph(
    graph_name: str,
    endpoint: str = DEFAULT_ENDPOINT,
    page_size: int = PAGE_SIZE,
    verify: bool = True,
) -> FetchResult:
    """Haalt een volledige named graph op via gepagineerde CONSTRUCT-queries (zie fetch_construct)."""
    uri = graph_uri(graph_name)
    query_body = f"CONSTRUCT {{?s ?p ?o}} WHERE {{ GRAPH <{uri}> {{?s ?p ?o}} }}"
    g, pages = fetch_construct(query_body, endpoint, page_size)

    parsed_count = len(g)
    expected_count = count_graph_triples(graph_name, endpoint) if verify else parsed_count
    result = FetchResult(
        graph=g,
        graph_name=graph_name,
        endpoint=endpoint,
        expected_count=expected_count,
        parsed_count=parsed_count,
        pages=pages,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    if verify and not result.verified:
        raise RuntimeError(
            f"Fetch-verificatie mislukt voor graph '{graph_name}': "
            f"COUNT-query zegt {expected_count}, geparseerd {parsed_count} triples. "
            "Mogelijk is de 10.000-triple-cap toch geraakt, of is de paginatie niet stabiel "
            "gebleken tussen de losse requests — zie CLAUDE.md §4."
        )
    return result


def save_snapshot(result: FetchResult, raw_dir: Path, name: str) -> tuple[Path, Path]:
    """Bewaart een ruwe turtle-snapshot + provenance-metadata onder data/raw/ (gitignored)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    ttl_path = raw_dir / f"{name}.ttl"
    meta_path = raw_dir / f"{name}.meta.json"
    result.graph.serialize(destination=str(ttl_path), format="turtle")
    meta = {
        "endpoint": result.endpoint,
        "graph_uri": graph_uri(result.graph_name),
        "graph_name": result.graph_name,
        "fetched_at": result.fetched_at,
        "pages": result.pages,
        "expected_count": result.expected_count,
        "parsed_count": result.parsed_count,
        "verified": result.verified,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return ttl_path, meta_path


def select_dataframe(query: str, endpoint: str = DEFAULT_ENDPOINT) -> pd.DataFrame:
    """Voert een SPARQL SELECT-query uit en geeft de resultaten als pandas DataFrame terug."""
    data = _http_get(endpoint, query, "application/sparql-results+json")
    result = json.loads(data)
    variables = result["head"]["vars"]
    rows = []
    for binding in result["results"]["bindings"]:
        row = {var: (binding[var]["value"] if var in binding else None) for var in variables}
        rows.append(row)
    return pd.DataFrame(rows, columns=variables)


def to_dataframe(
    graph: rdflib.Graph,
    class_uri: str,
    predicates: dict[str, str],
    id_column: str = "uri",
) -> pd.DataFrame:
    """Zet subjects van een gegeven rdf:type om naar een tidy DataFrame.

    predicates: mapping van kolomnaam -> predicaat-URI. Een subject zonder waarde voor een
    predicaat krijgt None; bij meerdere waarden wordt enkel de eerste gebruikt (in de CSOR
    variabele-data komt dat voor de hier gebruikte predicaten niet voor — elders wel opletten).
    """
    columns = [id_column] + list(predicates.keys())
    rows = []
    for subject in graph.subjects(rdflib.RDF.type, rdflib.URIRef(class_uri)):
        row = {id_column: str(subject)}
        for col, pred in predicates.items():
            values = [str(o) for o in graph.objects(subject, rdflib.URIRef(pred))]
            row[col] = values[0] if values else None
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)
