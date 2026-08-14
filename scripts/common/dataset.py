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
Bron (alle 10 graphs): de publieke GitHub-broncoderepo's van elke CSOR-codelijst
(github.com/milieuinfo/codelijst-csor-<naam>, raw.githubusercontent.com, branch `main`) — de
.ttl-broncodebestanden waaruit de live registerendpoint gedeployed wordt.
Own addition, vervangt de live-SPARQL-fetch na een concreet gereproduceerde databug:
sparql_client.py::fetch_graph()'s gepagineerde CONSTRUCT (`LIMIT/OFFSET` over een ongefilterde
`?s ?p ?o` binnen één GRAPH) kan op grote graphs triples VERZINNEN — bevestigd op parameter
(156k triples/32 pagina's à page_size=5000): de structurele/relationele triples van
`parameteraspect/PAS_7411` en `parameter/P_3870` kwamen correct terug, maar literal-waarde-
triples (prefLabel/altLabel/symbool/verkorteNotatie/heeftVariabele) van een ANDER, elders in de
paginavolgorde gelegen subject raakten foutief aan `P_3870` toegeschreven ("Fe"/Ijzer werd
"DFLBZ"/Diflubenzuron) — met een ongewijzigd totaal, dus de bestaande COUNT-verificatie merkte
het niet op. Vier onafhankelijke bronnen (live `/doc`-resource-endpoint, een ongepagineerde
gefilterde `/sparql`-query, de publieke GitHub-broncode, een lokale git-checkout van diezelfde
broncode) bevestigden alle vier de correcte waarde — enkel de gepagineerde CONSTRUCT-scan gaf
het verzonnen resultaat. GitHub-broncode (één ongepagineerde download per graph) is dus
betrouwbaarder dan de gepagineerde live-fetch.
**Live COUNT ligt structureel hoger dan GitHub, en dat is geen publicatie-achterstand — GitHub
loopt qua broncode-commits altijd vóór op wat live gedeployed is.** Per-predicaat vergeleken op
zowel `drager` (911 live vs. 90 GitHub) als `parameter` (156.318 live vs. 148.633 GitHub): elk
csor:-domeinpredicaat (heeftDrager, symbool, heeftBronParameter, factor, ...) heeft op beide
graphs een **exact identiek** aantal triples live en op GitHub — de volledige kloof zit in
niet-domein-predicaten (dcat:/dcterms:-catalogusmetadata, sh:-SHACL-shapes,
sparql-service-description:*, spdx:*) die de deploypijplijn van elke `codelijst-csor-<naam>`-
repo bij het builden aan de named graph toevoegt (zie `codelijst-csor-drager/src/
99_deploy_latest.js`: mergt élk lokaal `.ttl`-bestand, incl. build-time gegenereerde DCAT-
catalogus-/dataset-metadata onder `temp/` — gitignored, dus geen statische GitHub-bron — via
een propriëtaire reasoner (`RoxiReasoner`/`roxi-js`) vóór de `PUT` naar de live named graph).
**Empirisch bevestigd irrelevant voor csor-testing**: `check_conceptschemas.py` en
`generate_diagram.py` gebruiken geen enkele niet-domeintriple — de eerste doet
relatie-ontdekking data-gedreven (ontbrekende rdfs:label/domain/range is expliciet "correct en
verwacht", zie discover_relations()); de tweede vermijdt rdfs:domain/range bewust omdat die in
CSOR "niet betrouwbaar ingevuld" zijn. Getest op `drager`: met enkel de 90 GitHub-triples geven
beide scripts byte-voor-byte dezelfde tellingen (17 klassen/33 relaties/77 orphans; 10
klassen/16 relaties) als met de volledige 911-triple live-fetch.

METHODOLOGY
-----------
fetch_and_save() haalt alle 10 graphs op via fetch_graph_from_github() (één ongepagineerde
download per graph, dus paginatie-fabricatiebug architecturaal uitgesloten). Elke fetch wordt
ter info afgetoetst tegen sparql_client.count_graph_triples() (live) — geen harde
faalvoorwaarde, enkel een zichtbare stdout-waarschuwing bij een afwijking: die is normaal
(catalogusmetadata-ruis, zie DATA PROVENANCE) zolang ze bestaat uit niet-domeintriples. `drager`
krijgt een aparte, geruststellende boodschap (zie DRAGER_KNOWN_GAP_GRAPH) omdat die kloof al
predicaat-per-predicaat bevestigd is; voor andere graphs blijft de waarschuwing generiek
geformuleerd (nog niet individueel bevestigd, al is `parameter`s kloof hierboven ook al
volledig verklaard).

INTERPRETATION
--------------
n.v.t. — bouwsteen, geen eigen bevindingen. Een "N triple(s) verschil met live"-waarschuwing in
de stdout-samenvatting is verwacht (catalogusmetadata die de deploypijplijn toevoegt, niet
GitHub die achterloopt) en geen actiepunt op zich — enkel wanneer een per-predicaat-vergelijking
(zoals hierboven voor drager/parameter) een csor:-domeinpredicaat zelf zou laten afwijken, is
dat een echt actiepunt.

OUTPUTS
-------
analyse/csor_merged.ttl (gitignored, regenereerbaar)
"""

from __future__ import annotations

from pathlib import Path

import rdflib
import requests

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

GITHUB_ORG = "milieuinfo"
GITHUB_BRANCH = "main"

# Graph met een gekende, onschadelijke live/GitHub-kloof (zie DATA PROVENANCE) — enkel gebruikt
# om de stdout-waarschuwing in fetch_and_save() te verfijnen, geen functioneel onderscheid.
DRAGER_KNOWN_GAP_GRAPH = "drager"


def _github_raw_url(graph_name: str) -> str:
    """Bouwt de raw.githubusercontent.com-URL voor een CSOR-codelijst-broncodebestand.

    Elke codelijst-csor-<naam>-repo bewaart zijn .ttl onder een conceptscheme-submap zonder
    koppeltekens in de mapnaam (bv. graph 'kwalificeerbaar-aspect' -> map/bestand
    'kwalificeerbaaraspect') — de repo-naam zelf behoudt de koppeltekens wel.
    """
    subpath = graph_name.replace("-", "")
    return (
        f"https://raw.githubusercontent.com/{GITHUB_ORG}/codelijst-csor-{graph_name}/"
        f"{GITHUB_BRANCH}/src/main/resources/be/vlaanderen/omgeving/data/id/conceptscheme/"
        f"csor/{subpath}/{subpath}.ttl"
    )


def fetch_graph_from_github(graph_name: str) -> rdflib.Graph:
    """Haalt een CSOR-codelijst-graph op als .ttl-broncodebestand uit de publieke GitHub-repo.

    Eén ongepagineerde GET van het volledige bestand — architecturaal immuun voor de
    paginatie-fabricatiebug van sparql_client.py::fetch_graph() (zie DATA PROVENANCE), omdat er
    geen LIMIT/OFFSET-scan aan te pas komt.
    """
    url = _github_raw_url(graph_name)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    g = rdflib.Graph()
    g.parse(data=resp.content, format="turtle")
    return g


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
    print(f"Lokale snapshot regenereren uit {len(graph_names)} CSOR-graphs (GitHub-broncode)...")
    for name in graph_names:
        g = fetch_graph_from_github(name)
        parsed_count = len(g)
        merged += g
        live_count = sc.count_graph_triples(name, endpoint)
        delta = live_count - parsed_count
        if delta == 0:
            status = "up-to-date met live"
        elif name == DRAGER_KNOWN_GAP_GRAPH:
            status = (
                f"LET OP: {delta} triple(s) verschil met live — gekend en onschadelijk "
                "(build-time gegenereerde DCAT-catalogusmetadata + ontologie-declaraties die "
                "geen enkele check gebruikt, zie DATA PROVENANCE)"
            )
        else:
            status = f"LET OP: {delta} triple(s) verschil met live — GitHub kan achterlopen"
        print(f"  {name}: {parsed_count} triples (GitHub-bron, live COUNT={live_count} — {status})")
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.serialize(destination=str(path), format="turtle")
    print(f"Lokale snapshot bijgewerkt: {path} ({len(merged)} triples).")
    return merged
