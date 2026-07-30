"""
pubchem.py — PubChem PUG-REST-client met bestandscache, voor csor-testing

PURPOSE
-------
Haalt substance-eigenschappen (InChIKey, IUPAC-naam, molecuulformule, SMILES) op bij PubChem,
by CID (ondubbelzinnig), by CAS-nummer of by naam (fuzzy, "name"-lookup — PubChem accepteert
CAS-nummers als naam). Wordt gebruikt door scripts/check_variabele_identity.py.

DATA PROVENANCE
----------------
Bron: PubChem PUG-REST, https://pubchem.ncbi.nlm.nih.gov/rest/pug/
Aanpak overgenomen in geest (niet cross-repo geïmporteerd) van
`R/02_import.R::get_inchikey()` in het zusterproject A-Substance-Is-Not-Always-a-Substance.

METHODOLOGY
-----------
Elke lookup gaat eerst via een JSON-file-cache onder data/cache/pubchem/{by_cid,by_cas,by_name}/.
Own addition: negatieve resultaten (geen compound gevonden) worden ook gecachet
(`{"found": false}`), zodat een herhaalde run niet telkens dezelfde mislukte lookup herdoet.
`time.sleep(0.2)` tussen live calls (niet bij cache-hit) — etiquette t.o.v. de publieke API.
`live_call_count` telt live HTTP-calls sinds het laatste `reset_call_count()`, gebruikt om te
verifiëren dat een tweede run met gevulde cache nul live calls doet.

OUTPUTS
-------
Geen eigen output-bestanden — bouwsteen voor scripts/check_variabele_identity.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path

import requests

PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
# Own addition: "ConnectivitySMILES" i.p.v. het oudere "CanonicalSMILES" — PubChem accepteert de
# oude naam nog als alias in de request, maar retourneert altijd de sleutel "ConnectivitySMILES";
# door meteen de huidige naam te gebruiken blijft de output voorspelbaar.
DEFAULT_PROPERTIES = ["InChIKey", "IUPACName", "MolecularFormula", "ConnectivitySMILES"]
RATE_LIMIT_SECONDS = 0.2

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


def _cache_path(cache_root: Path, kind: str, key: str) -> Path:
    return cache_root / kind / f"{_safe_key(key)}.json"


def _read_cache(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text())
    return None


def _write_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _fetch_properties(url_segment: str, properties: list[str]) -> dict:
    """Live PUG-REST-call. Geeft {"found": True, **properties} of {"found": False} terug."""
    global live_call_count
    prop_list = ",".join(properties)
    url = f"{PUG_BASE}/{url_segment}/property/{prop_list}/JSON"
    live_call_count += 1
    try:
        resp = requests.get(url, timeout=30)
        time.sleep(RATE_LIMIT_SECONDS)
        if resp.status_code == 404:
            return {"found": False}
        resp.raise_for_status()
        data = resp.json()
        props = data.get("PropertyTable", {}).get("Properties", [])
        if not props:
            return {"found": False}
        return {"found": True, **props[0]}
    except requests.RequestException as exc:
        time.sleep(RATE_LIMIT_SECONDS)
        return {"found": False, "error": str(exc)}


def _lookup(
    cache_root: Path,
    kind: str,
    key: str,
    url_segment: str,
    properties: list[str],
) -> dict:
    path = _cache_path(cache_root, kind, key)
    cached = _read_cache(path)
    if cached is not None:
        return cached
    result = _fetch_properties(url_segment, properties)
    _write_cache(path, result)
    return result


def get_by_cid(
    cid: str | int, cache_root: Path, properties: list[str] = None
) -> dict:
    properties = properties or DEFAULT_PROPERTIES
    cid = str(cid)
    return _lookup(cache_root, "by_cid", cid, f"cid/{cid}", properties)


def get_by_cas(
    cas: str, cache_root: Path, properties: list[str] = None
) -> dict:
    properties = properties or ["InChIKey"]
    encoded = urllib.parse.quote(cas, safe="")
    return _lookup(cache_root, "by_cas", cas, f"name/{encoded}", properties)


def get_by_name(
    name: str, cache_root: Path, properties: list[str] = None
) -> dict:
    properties = properties or ["InChIKey"]
    encoded = urllib.parse.quote(name, safe="")
    return _lookup(cache_root, "by_name", name, f"name/{encoded}", properties)
