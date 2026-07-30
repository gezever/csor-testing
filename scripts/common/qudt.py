"""
qudt.py — QUDT-dereferentie-client met bestandscache, voor csor-testing

PURPOSE
-------
Dereferentieert QUDT-eenheid-URI's (http://qudt.org/vocab/unit/...) en extraheert
qudt:symbol, rdfs:label (en), qudt:ucumCode en qudt:hasQuantityKind. Wordt gebruikt door
scripts/check_eenheden_qudt.py om csor:Eenheid tegen QUDT te valideren.

DATA PROVENANCE
----------------
Bron: QUDT Linked Data, https://qudt.org/vocab/unit/ (dereferentieerbaar, Accept: text/turtle).

METHODOLOGY
-----------
Elke lookup gaat eerst via een JSON-file-cache onder data/cache/qudt/. Own addition:
zowel succesvolle als mislukte (non-200) resultaten worden gecachet, zodat een herhaalde run
niet telkens dezelfde dode/trage link herbevraagt. Geen rate-limit-sleep nodig (QUDT is een
statische Linked-Data-publicatie, geen rate-limited API zoals PubChem).

URI-schema-verificatie (http vs. https): CSOR slaat QUDT-koppelingen op als `http://`, niet
`https://`. Elke fetch registreert het volledige redirect-verloop (statuscodes + finale URL)
en of de opgehaalde RDF-payload de OORSPRONKELIJK opgevraagde URI (dus de exacte string zoals
CSOR die opslaat) zelf als subject gebruikt — dat is de eigenlijke toets of CSOR's schema-
keuze de canonieke QUDT-identifier is, los van of de HTTP-verbinding toevallig via een
tussenliggende redirect loopt.

OUTPUTS
-------
Geen eigen output-bestanden — bouwsteen voor scripts/check_eenheden_qudt.py.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import rdflib
import requests

QUDT = rdflib.Namespace("http://qudt.org/schema/qudt/")
RDFS = rdflib.RDFS

_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9_.-]")

live_call_count = 0


def reset_call_count() -> None:
    global live_call_count
    live_call_count = 0


def _safe_key(value: str) -> str:
    key = _SAFE_KEY_RE.sub("_", value)
    if len(key) > 100:
        key = hashlib.md5(value.encode("utf-8")).hexdigest()
    return key


def _cache_path(cache_root: Path, uri: str) -> Path:
    return cache_root / f"{_safe_key(uri)}.json"


def fetch(uri: str, cache_root: Path) -> dict:
    """Haalt (gecached) metadata op voor een QUDT-eenheid-URI.

    Geeft bij succes terug: {"found": True, "status_code": 200, "symbol": ...,
    "label_en": ..., "ucum": ..., "quantitykind": [...], "redirect_statuses": [302, ...],
    "final_url": ..., "permanent_redirect": bool, "payload_subject_triples": int,
    "payload_subject_matches": bool}. Bij mislukking: {"found": False, "status_code": ...}.

    `payload_subject_matches` is True wanneer de RDF-payload de exact opgevraagde `uri`
    (dus de string zoals CSOR die opslaat) als subject gebruikt — de toets of CSOR's
    http/https-schema de canonieke QUDT-identifier is, los van eventuele HTTP-redirects.
    """
    global live_call_count
    path = _cache_path(cache_root, uri)
    if path.exists():
        return json.loads(path.read_text())

    live_call_count += 1
    result: dict
    try:
        resp = requests.get(uri, headers={"Accept": "text/turtle"}, timeout=30, allow_redirects=True)
        redirect_statuses = [h.status_code for h in resp.history]
        permanent_redirect = 301 in redirect_statuses
        if resp.status_code != 200:
            result = {
                "found": False,
                "status_code": resp.status_code,
                "redirect_statuses": redirect_statuses,
                "final_url": resp.url,
            }
        else:
            g = rdflib.Graph()
            g.parse(data=resp.content, format="turtle")
            subj = rdflib.URIRef(uri)
            payload_subject_triples = len(list(g.triples((subj, None, None))))
            symbol = next((str(o) for o in g.objects(subj, QUDT.symbol)), None)
            label_en = next(
                (str(o) for o in g.objects(subj, RDFS.label) if getattr(o, "language", None) == "en"),
                None,
            )
            ucum = next((str(o) for o in g.objects(subj, QUDT.ucumCode)), None)
            quantitykind = [str(o).rsplit("/", 1)[-1] for o in g.objects(subj, QUDT.hasQuantityKind)]
            result = {
                "found": True,
                "status_code": 200,
                "symbol": symbol,
                "label_en": label_en,
                "ucum": ucum,
                "quantitykind": quantitykind,
                "redirect_statuses": redirect_statuses,
                "final_url": resp.url,
                "permanent_redirect": permanent_redirect,
                "payload_subject_triples": payload_subject_triples,
                "payload_subject_matches": payload_subject_triples > 0,
            }
    except requests.RequestException as exc:
        result = {"found": False, "status_code": None, "error": str(exc)}

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    return result
