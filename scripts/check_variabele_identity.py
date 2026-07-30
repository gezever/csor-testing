"""
check_variabele_identity.py — chemische-identiteitscheck op csor:Variabele

PURPOSE
-------
Test de datakwaliteit van de chemische-identiteitsvelden op csor:Variabele: kan een
CAS-nummer betrouwbaar naar een InChIKey herleid worden, en zijn de reeds opgeslagen
eigenschappen (cas, inchikey, iupacNaam) consistent met een externe referentiebron (PubChem)?
v1-scope: enkel PubChem als externe bron; ChEBI-crosscheck en EC/EEA-consistentie zijn bewust
buiten scope (zie reports/rapport_variabele_identiteit.md, paragraaf "buiten scope").

DATA PROVENANCE
----------------
Endpoint: https://data-ontwikkel.omgeving.vlaanderen.be/sparql
Graph:    https://data.omgeving.vlaanderen.be/id/graph/codelijst-csor-variabele (25.312 triples,
          gepagineerd opgehaald — zie common.sparql_client.fetch_graph en
          sparql/csor-variabele-fetch.sparql).
Externe bron: PubChem PUG-REST (common.pubchem), met bestandscache.

METHODOLOGY
-----------
- Interne checks (geen externe afhankelijkheid): CAS-checksum (mod-10 controlegetal, de
  standaard CAS Registry Number-validatie), InChIKey-vormvalidatie (regex), dubbele
  InChIKey/CAS over notaties heen (kruiscontrole met sparql/variabele_identity_checks.sparql
  queries A/B).
- PubChem CID-crosscheck (sterkste externe check, ondubbelzinnig): voor variabelen met zowel
  inchikey als een PubChem-CID-koppeling — vergelijk CSOR's inchikey/iupacNaam met wat PubChem
  voor die exacte CID teruggeeft.
- CAS-resolutie (own addition, gecombineerd met de "gap-set fallback" uit het plan in één
  stap/CSV): voor elke variabele met een CAS-nummer wordt een PubChem-lookup gedaan — eerst via
  het CAS-nummer zelf (PUG-REST "name"-endpoint accepteert CAS-nummers), en als dat niets
  oplevert én er nog geen inchikey gekend is, een fallback-lookup op prefLabel (substantienaam).
  Waar CSOR al een inchikey had, wordt die vergeleken met het resolutieresultaat (match/mismatch);
  waar niet, wordt het resolutieresultaat gerapporteerd als suggestie (niet teruggeschreven).

INTERPRETATION
--------------
Een "mismatch" in cid_crosscheck.csv is de sterkste rode vlag (CSOR en PubChem zijn het voor
exact dezelfde CID oneens) en verdient prioriteit boven CAS-resolutie-afwijkingen (die ook een
naam-matching-onzekerheid bij PubChem kunnen weerspiegelen, niet per se een CSOR-fout).
Een "unresolved" CAS-nummer is geen CSOR-fout, wel een aanwijzing dat het CAS-nummer zelf
mogelijk incorrect is (zie ook de CAS-checksumcheck) of dat PubChem die stof niet kent.

OUTPUTS
-------
output/tables/cas_resolution.csv
output/tables/cid_crosscheck.csv
output/tables/internal_flags.csv
data/interim/variabele_records.parquet (tussentijds)
data/raw/csor-variabele-<datum>.ttl (+.meta.json) (ruwe snapshot, provenance)
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import pubchem, sparql_client as sc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERIM_DIR = REPO_ROOT / "data" / "interim"
RAW_DIR = REPO_ROOT / "data" / "raw"
CACHE_ROOT = REPO_ROOT / "data" / "cache" / "pubchem"
OUTPUT_DIR = REPO_ROOT / "output" / "tables"

CSOR = "https://data.omgeving.vlaanderen.be/ns/csor#"
PUBCHEM_PRED = "https://pubchem.ncbi.nlm.nih.gov/rest/rdf/compound"
CID_RE = re.compile(r"CID(\d+)$")
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")

# Self-test: bekend record V_1 "alfa+beta Endosulfan", vastgesteld tijdens de verkenning.
SELF_TEST = {
    "notatie": "V_1",
    "cas": "115-29-7",
    "inchikey": "RDYMFSUJUZBWLH-UHFFFAOYSA-N",
    "cid": "3224",
}


def cas_checksum_valid(cas: str) -> bool:
    """Standaard CAS Registry Number-controlegetal (mod-10, gewogen vanaf de check-digit)."""
    digits = re.sub(r"[^0-9]", "", cas)
    if len(digits) < 3:
        return False
    check_digit = int(digits[-1])
    body = digits[:-1]
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    return total % 10 == check_digit


def build_records() -> tuple["pd.DataFrame", "sc.FetchResult"]:  # noqa: F821
    fetch = sc.fetch_graph("variabele")
    df = sc.to_dataframe(
        fetch.graph,
        class_uri=f"{CSOR}Variabele",
        predicates={
            "notatie": "http://www.w3.org/2004/02/skos/core#notation",
            "label": "http://www.w3.org/2004/02/skos/core#prefLabel",
            "cas": f"{CSOR}cas",
            "inchikey": f"{CSOR}inchikey",
            "iupacNaam": f"{CSOR}iupacNaam",
            "eea": f"{CSOR}eea",
            "pubchem_uri": PUBCHEM_PRED,
            "deprecated": "http://www.w3.org/2002/07/owl#deprecated",
        },
        id_column="uri",
    )
    df["deprecated"] = df["deprecated"] == "true"
    df["cid"] = df["pubchem_uri"].apply(
        lambda u: CID_RE.search(u).group(1) if isinstance(u, str) and CID_RE.search(u) else None
    )
    df = df[~df["deprecated"]].reset_index(drop=True)
    return df, fetch


def self_test(df: "pd.DataFrame") -> None:  # noqa: F821
    row = df[df["notatie"] == SELF_TEST["notatie"]]
    if row.empty:
        raise RuntimeError(f"Self-test mislukt: {SELF_TEST['notatie']} niet gevonden in de data.")
    row = row.iloc[0]
    for field in ("cas", "inchikey", "cid"):
        if row[field] != SELF_TEST[field]:
            raise RuntimeError(
                f"Self-test mislukt voor {SELF_TEST['notatie']}.{field}: "
                f"verwacht {SELF_TEST[field]!r}, gekregen {row[field]!r}."
            )
    print(
        f"Self-test OK: {SELF_TEST['notatie']} ({row['label']}) — "
        f"cas={row['cas']}, inchikey={row['inchikey']}, cid={row['cid']}"
    )


def internal_checks(df: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
    flags = []

    cas_notna = df[df["cas"].notna()]
    invalid_cas = cas_notna[~cas_notna["cas"].apply(cas_checksum_valid)]
    for _, r in invalid_cas.iterrows():
        flags.append(
            {
                "notatie": r["notatie"],
                "flag_type": "cas_checksum_invalid",
                "detail": f"cas={r['cas']}",
            }
        )

    invalid_inchikey = df[
        df["inchikey"].notna() & ~df["inchikey"].str.match(INCHIKEY_RE, na=False)
    ]
    for _, r in invalid_inchikey.iterrows():
        flags.append(
            {
                "notatie": r["notatie"],
                "flag_type": "inchikey_shape_invalid",
                "detail": f"inchikey={r['inchikey']}",
            }
        )

    for key, label in (("inchikey", "duplicate_inchikey"), ("cas", "duplicate_cas")):
        dup_groups = df[df[key].notna()].groupby(key)["notatie"].apply(list)
        dup_groups = dup_groups[dup_groups.apply(len) > 1]
        for value, notaties in dup_groups.items():
            flags.append(
                {
                    "notatie": ", ".join(notaties),
                    "flag_type": label,
                    "detail": f"{key}={value}",
                }
            )

    return pd.DataFrame(flags, columns=["notatie", "flag_type", "detail"])


def cid_crosscheck(df: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
    candidates = df[df["inchikey"].notna() & df["cid"].notna()]
    rows = []
    for _, r in candidates.iterrows():
        pc = pubchem.get_by_cid(r["cid"], CACHE_ROOT)
        pubchem_inchikey = pc.get("InChIKey")
        pubchem_iupac = pc.get("IUPACName")
        rows.append(
            {
                "notatie": r["notatie"],
                "cid": r["cid"],
                "csor_inchikey": r["inchikey"],
                "pubchem_inchikey": pubchem_inchikey,
                "inchikey_match": pubchem_inchikey == r["inchikey"] if pc.get("found") else None,
                "csor_iupac": r["iupacNaam"],
                "pubchem_iupac": pubchem_iupac,
                "found": pc.get("found", False),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "notatie",
            "cid",
            "csor_inchikey",
            "pubchem_inchikey",
            "inchikey_match",
            "csor_iupac",
            "pubchem_iupac",
            "found",
        ],
    )


def cas_resolution(df: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
    candidates = df[df["cas"].notna()]
    rows = []
    for _, r in candidates.iterrows():
        result = pubchem.get_by_cas(r["cas"], CACHE_ROOT, properties=["InChIKey"])
        method = "cas"
        if not result.get("found") and pd.isna(r["inchikey"]):
            result = pubchem.get_by_name(r["label"], CACHE_ROOT, properties=["InChIKey"])
            method = "name"

        resolved_inchikey = result.get("InChIKey")
        stored_inchikey = r["inchikey"] if pd.notna(r["inchikey"]) else None

        if not result.get("found"):
            status = "unresolved"
            method = None
        elif stored_inchikey is None:
            status = "resolved_new"
        elif resolved_inchikey == stored_inchikey:
            status = "match"
        else:
            status = "mismatch"

        rows.append(
            {
                "notatie": r["notatie"],
                "cas": r["cas"],
                "label": r["label"],
                "stored_inchikey": stored_inchikey,
                "resolved_inchikey": resolved_inchikey,
                "resolution_method": method,
                "status": status,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "notatie",
            "cas",
            "label",
            "stored_inchikey",
            "resolved_inchikey",
            "resolution_method",
            "status",
        ],
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    df, fetch = build_records()
    sc.save_snapshot(fetch, RAW_DIR, f"csor-variabele-{date.today().isoformat()}")
    df.to_parquet(INTERIM_DIR / "variabele_records.parquet")

    print(f"Fetch geverifieerd: {fetch.parsed_count} triples ({fetch.pages} pagina's).")
    print(
        f"Actieve variabelen: {len(df)} — cas={df['cas'].notna().sum()}, "
        f"inchikey={df['inchikey'].notna().sum()}, iupacNaam={df['iupacNaam'].notna().sum()}, "
        f"eea={df['eea'].notna().sum()}, cid={df['cid'].notna().sum()}"
    )

    self_test(df)

    flags_df = internal_checks(df)
    flags_df.to_csv(OUTPUT_DIR / "internal_flags.csv", index=False)
    print(f"\nInterne checks: {len(flags_df)} vlaggen ({flags_df['flag_type'].value_counts().to_dict() if len(flags_df) else {}})")

    print("\nPubChem CID-crosscheck loopt (gecached, ~0.2s/live-call)...")
    cid_df = cid_crosscheck(df)
    cid_df.to_csv(OUTPUT_DIR / "cid_crosscheck.csv", index=False)
    mismatches = cid_df[cid_df["inchikey_match"] == False]  # noqa: E712
    print(
        f"CID-crosscheck: {len(cid_df)} kandidaten, {int(cid_df['found'].sum())} gevonden bij "
        f"PubChem, {len(mismatches)} InChIKey-mismatch(es)."
    )

    print("\nCAS-resolutie loopt (gecached, ~0.2s/live-call)...")
    cas_df = cas_resolution(df)
    cas_df.to_csv(OUTPUT_DIR / "cas_resolution.csv", index=False)
    status_counts = cas_df["status"].value_counts().to_dict()
    print(f"CAS-resolutie: {len(cas_df)} kandidaten — {status_counts}")

    print(f"\nlive PubChem-calls deze run: {pubchem.live_call_count}")


if __name__ == "__main__":
    main()
