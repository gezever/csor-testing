"""
pubchem.py — PubChem PUG-REST-client met bestandscache, voor csor-testing

PURPOSE
-------
Haalt substance-eigenschappen (InChIKey, IUPAC-naam, molecuulformule, SMILES) op bij PubChem,
by CID (ondubbelzinnig), by CAS-nummer, by naam (fuzzy, "name"-lookup — PubChem accepteert
CAS-nummers als naam) of by InChIKey (omgekeerde lookup, zie METHODOLOGY). Biedt daarnaast
`get_synonyms()` (PubChem-synoniemenlijst van een CID — bevat doorgaans ook CAS-nummers en
alternatieve namen) en `get_xrefs_rn()` (PubChem's eigen "Registry Number"-kruisverwijzingen,
een gemengde CAS-/EC-nummerlijst). Wordt gebruikt door scripts/check_variabele_identity.py.

DATA PROVENANCE
----------------
Bron: PubChem PUG-REST, https://pubchem.ncbi.nlm.nih.gov/rest/pug/
Aanpak overgenomen in geest (niet cross-repo geïmporteerd) van
`R/02_import.R::get_inchikey()` in het zusterproject A-Substance-Is-Not-Always-a-Substance.

METHODOLOGY
-----------
Elke lookup gaat eerst via een JSON-file-cache onder
data/cache/pubchem/{by_cid,by_cas,by_name,by_inchikey,by_cid_synonyms}/. Own addition: negatieve
resultaten (geen compound gevonden) worden ook gecachet (`{"found": false}`), zodat een
herhaalde run niet telkens dezelfde mislukte lookup herdoet. `time.sleep(0.2)` tussen live calls
(niet bij cache-hit) — etiquette t.o.v. de publieke API. `live_call_count` telt live HTTP-calls
sinds het laatste `reset_call_count()`, gebruikt om te verifiëren dat een tweede run met gevulde
cache nul live calls doet.

`get_synonyms()` gebruikt een ander PUG-REST-endpoint (`.../cid/{cid}/synonyms/JSON`) met een
andere JSON-vorm dan de property-lookups hierboven (`InformationList.Information[0].Synonym`,
een lijst strings, i.p.v. `PropertyTable.Properties[0]`) — vereist daarom een eigen
fetch-helper (`_fetch_synonyms()`) i.p.v. hergebruik van `_fetch_properties()`.

`get_xrefs_rn()` gebruikt `.../cid/{cid}/xrefs/RN/JSON` (zelfde `InformationList`-vorm als
synonyms, maar sleutel `RN` i.p.v. `Synonym`) — PubChem's "Registry Number"-kruisverwijzingen
bevatten CAS- én EC/EINECS-nummers door elkaar (bv. voor fluorantheen: `["205-912-4", "206-44-0",
"76774-50-0"]` — het eerste is het EC-nummer). De aanroeper filtert zelf op patroon
(EC: `\\d{3}-\\d{3}-\\d`, middelste groep exact 3 cijfers; CAS: middelste groep exact 2 cijfers)
— deze module doet zelf geen classificatie, enkel de ruwe lijst teruggeven.

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


def get_by_inchikey(
    inchikey: str, cache_root: Path, properties: list[str] = None
) -> dict:
    properties = properties or DEFAULT_PROPERTIES
    return _lookup(cache_root, "by_inchikey", inchikey, f"inchikey/{inchikey}", properties)


def _fetch_synonyms(cid: str) -> dict:
    """Live PUG-REST-call naar het synonyms-endpoint (andere JSON-vorm, zie METHODOLOGY)."""
    global live_call_count
    url = f"{PUG_BASE}/cid/{cid}/synonyms/JSON"
    live_call_count += 1
    try:
        resp = requests.get(url, timeout=30)
        time.sleep(RATE_LIMIT_SECONDS)
        if resp.status_code == 404:
            return {"found": False, "synonyms": []}
        resp.raise_for_status()
        data = resp.json()
        info = data.get("InformationList", {}).get("Information", [])
        synonyms = info[0].get("Synonym", []) if info else []
        return {"found": bool(synonyms), "synonyms": synonyms}
    except requests.RequestException as exc:
        time.sleep(RATE_LIMIT_SECONDS)
        return {"found": False, "synonyms": [], "error": str(exc)}


def get_synonyms(cid: str | int, cache_root: Path) -> dict:
    cid = str(cid)
    path = _cache_path(cache_root, "by_cid_synonyms", cid)
    cached = _read_cache(path)
    if cached is not None:
        return cached
    result = _fetch_synonyms(cid)
    _write_cache(path, result)
    return result


def _fetch_xrefs_rn(cid: str) -> dict:
    """Live PUG-REST-call naar het xrefs/RN-endpoint (zie METHODOLOGY)."""
    global live_call_count
    url = f"{PUG_BASE}/cid/{cid}/xrefs/RN/JSON"
    live_call_count += 1
    try:
        resp = requests.get(url, timeout=30)
        time.sleep(RATE_LIMIT_SECONDS)
        if resp.status_code == 404:
            return {"found": False, "rn": []}
        resp.raise_for_status()
        data = resp.json()
        info = data.get("InformationList", {}).get("Information", [])
        rn = info[0].get("RN", []) if info else []
        return {"found": bool(rn), "rn": rn}
    except requests.RequestException as exc:
        time.sleep(RATE_LIMIT_SECONDS)
        return {"found": False, "rn": [], "error": str(exc)}


def get_xrefs_rn(cid: str | int, cache_root: Path) -> dict:
    cid = str(cid)
    path = _cache_path(cache_root, "by_cid_xrefs_rn", cid)
    cached = _read_cache(path)
    if cached is not None:
        return cached
    result = _fetch_xrefs_rn(cid)
    _write_cache(path, result)
    return result
