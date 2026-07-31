"""
fetch_vmm_woordenboek.py — ververst de SKOS-vertaling van het VMM-woordenboek in data/source/

PURPOSE
-------
Haalt alle termen van het openbare VMM-woordenboek (https://vmm.vlaanderen.be/woordenboek) op en
zet ze om naar SKOS, zodat CSOR-begrippen (bv. Parameter- of ParameterAspect-labels) later tegen
een externe, VMM-eigen begrippenlijst gemapt kunnen worden. Dit is geen CSOR-datakwaliteitscheck
(vandaar geen check_-prefix, geen output/tables/-CSV en geen HTML-rapport, zie CLAUDE.md §3/§10)
maar een ververbare externe-bronfetch, analoog in geest aan scripts/common/dataset.py::
fetch_and_save() voor de CSOR-graphs zelf.

DATA PROVENANCE
----------------
Bron: geen officiële API — de publieke Plone/Volto REST-laag onder de website zelf
(https://vmm.vlaanderen.be/++api++/woordenboek), dezelfde JSON die de website-frontend gebruikt.
Elke term (Plone content-type "Term") levert een titel en een HTML-definitie; dat laatste wordt
tot platte tekst herleid (tags gestript, whitespace genormaliseerd).

METHODOLOGY
-----------
1. Paginated listing ophalen (b_start/b_size) tot alle items binnen zijn; geverifieerd tegen het
   listing-veld items_total (zelfde geest als de CONSTRUCT-paginatie in CLAUDE.md §4 — geen
   stille afkap vertrouwen).
2. Voor elke term het volledige detailobject ophalen (title, definition.data) — de listing zelf
   bevat geen definitie.
3. Opbouw als rdflib.Graph: één skos:ConceptScheme (het woordenboek zelf) met per term een
   skos:Concept (skos:prefLabel, skos:definition, optioneel skos:scopeNote, skos:inScheme/
   skos:topConceptOf, dct:source naar de brompagina).
4. Serialisatie naar zowel Turtle (.ttl) als RDF/XML (.rdf) — bestaande downstream-consumenten
   kunnen zo het voor hen makkelijkste formaat kiezen.

INTERPRETATION
--------------
n.v.t. — bouwsteen/brondata, geen eigen bevindingen. Bij een hertoop lezing: het aantal termen
(items_total) schommelt licht naarmate VMM het woordenboek onderhoudt; een gedaald aantal t.o.v.
een vorige run is geen scriptfout maar een indicatie dat VMM termen heeft verwijderd/samengevoegd.

OUTPUTS
-------
data/source/vmm-woordenboek.ttl (Turtle, gecommit)
data/source/vmm-woordenboek.rdf (RDF/XML, gecommit)

USAGE
-----
python3 scripts/fetch_vmm_woordenboek.py
Geen parameters; herdraaien overschrijft beide bestanden volledig (idempotent — geen partiële
merge met een vorige run). Bedoeld om af en toe handmatig herdraaid te worden, niet als onderdeel
van scripts/run_all.py (dat betreft uitsluitend de CSOR-registerpijplijn zelf).
"""

from __future__ import annotations

import html
import re
import time
from pathlib import Path

import requests
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, SKOS

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_TTL = REPO_ROOT / "data" / "source" / "vmm-woordenboek.ttl"
OUT_RDF = REPO_ROOT / "data" / "source" / "vmm-woordenboek.rdf"

SITE = "https://vmm.vlaanderen.be"
API_LIST = f"{SITE}/++api++/woordenboek"
HEADERS = {"Accept": "application/json", "User-Agent": "csor-testing/vmm-woordenboek-fetch (+geert.vanhaute@vlaanderen.be)"}
WB = Namespace(f"{SITE}/woordenboek/")

REQUEST_SLEEP_SECONDS = 0.15


def fetch_json(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def strip_html(fragment: str | None) -> str:
    if not fragment:
        return ""
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def collect_listing(b_size: int = 50) -> list[dict]:
    items: list[dict] = []
    b_start = 0
    items_total: int | None = None
    while True:
        data = fetch_json(f"{API_LIST}?b_start={b_start}&b_size={b_size}")
        items_total = data.get("items_total", items_total)
        batch = data.get("items", [])
        if not batch:
            break
        items.extend(batch)
        if items_total is not None and len(items) >= items_total:
            break
        b_start += b_size
        time.sleep(REQUEST_SLEEP_SECONDS)

    if items_total is not None and len(items) != items_total:
        raise RuntimeError(
            f"Paginatie onvolledig: {len(items)} termen opgehaald, maar items_total={items_total}."
        )
    return items


def build_graph(items: list[dict]) -> Graph:
    g = Graph()
    g.bind("wb", WB)
    g.bind("dct", DCTERMS)
    g.bind("skos", SKOS)

    scheme_uri = URIRef(f"{SITE}/woordenboek")
    g.add((scheme_uri, RDF.type, SKOS.ConceptScheme))
    g.add((scheme_uri, RDFS.label, Literal("VMM Woordenboek", lang="nl")))
    g.add((scheme_uri, DCTERMS.title, Literal("VMM Woordenboek", lang="nl")))
    g.add((scheme_uri, DCTERMS.source, URIRef(f"{SITE}/woordenboek")))
    g.add((scheme_uri, DCTERMS.publisher, Literal("Vlaamse Milieumaatschappij (VMM)", lang="nl")))

    skipped: list[str] = []
    for i, item in enumerate(items, 1):
        term_url = item["@id"]
        title = item.get("title", "").strip()
        print(f"  [{i}/{len(items)}] {title}")
        try:
            detail = fetch_json(term_url.replace(SITE, f"{SITE}/++api++"))
        except requests.RequestException as e:
            print(f"    WAARSCHUWING: kon detail niet ophalen ({e}), term overgeslagen.")
            skipped.append(term_url)
            continue

        concept_uri = URIRef(term_url)
        g.add((concept_uri, RDF.type, SKOS.Concept))
        g.add((concept_uri, SKOS.inScheme, scheme_uri))
        g.add((concept_uri, SKOS.prefLabel, Literal(detail.get("title", title), lang="nl")))

        definition_text = strip_html((detail.get("definition") or {}).get("data", ""))
        if definition_text:
            g.add((concept_uri, SKOS.definition, Literal(definition_text, lang="nl")))

        description = (detail.get("description") or "").strip()
        if description and description != definition_text:
            g.add((concept_uri, SKOS.scopeNote, Literal(description, lang="nl")))

        g.add((concept_uri, DCTERMS.source, URIRef(term_url)))
        g.add((scheme_uri, SKOS.hasTopConcept, concept_uri))
        g.add((concept_uri, SKOS.topConceptOf, scheme_uri))

        time.sleep(REQUEST_SLEEP_SECONDS)

    if skipped:
        raise RuntimeError(
            f"{len(skipped)} term(en) overgeslagen door fetchfouten, verwerking gestaakt: {skipped}"
        )
    return g


def main() -> None:
    print(f"Termenlijst ophalen van {API_LIST} ...")
    items = collect_listing()
    print(f"  {len(items)} termen gevonden (geverifieerd tegen items_total).")

    print("Details per term ophalen en SKOS-graph opbouwen...")
    g = build_graph(items)

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(OUT_TTL), format="turtle")
    g.serialize(destination=str(OUT_RDF), format="xml")

    n_concepts = sum(1 for _ in g.subjects(RDF.type, SKOS.Concept))
    print(f"\nKlaar: {n_concepts} skos:Concept, {len(g)} triples.")
    print(f"  {OUT_TTL.relative_to(REPO_ROOT)}")
    print(f"  {OUT_RDF.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
