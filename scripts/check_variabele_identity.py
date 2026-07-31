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
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`
— bevat o.a. de `variabele`-instanties (25.312 triples, voorheen rechtstreeks als apart graph
opgehaald via sparql/csor-variabele-fetch.sparql; die paginatie/verificatie gebeurt nu bij de
snapshot-regeneratie zelf, zie common/dataset.py).
Externe bron: PubChem PUG-REST (common.pubchem), met bestandscache — blijft per definitie
live/extern.

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
- Omgekeerde CAS-resolutie via InChIKey (own addition): de CAS-resolutie hierboven probeert een
  naam-fallback enkel wanneer er nog géén inchikey gekend is — een variabele met zowel `cas` als
  `inchikey`, waarvoor de CAS-lookup toch niets oplevert, blijft dus zonder verdere poging
  `unresolved` (8 van de 34 huidige `unresolved`-gevallen hebben wél al een inchikey). Voor die
  8 wordt de al gekende inchikey omgekeerd bij PubChem opgezocht (`pubchem.get_by_inchikey()`)
  en, bij een gevonden CID, de volledige synoniemenlijst opgevraagd (`pubchem.get_synonyms()`).
  Daaruit worden CAS-vormige synoniemen gefilterd (dezelfde `CAS_RE` als de interne checks) om te
  zien of PubChem een ander CAS-nummer voor die stof gebruikt, en wordt getoetst of
  `skos:prefLabel` letterlijk (case-insensitief) als synoniem voorkomt. Bewust geen fuzzy/
  edit-distance-matching op de naam — een kleine edit-distance tussen twee lange chemische namen
  is geen betrouwbaar signaal (zie ook de near-duplicate-voorzichtigheid elders in dit project);
  de volledige synoniemenlijst wordt wel meegeschreven zodat een reviewer een niet-letterlijke
  gelijkenis (bv. taalverschil NL/EN) zelf kan beoordelen.

INTERPRETATION
--------------
Een "mismatch" in cid_crosscheck.csv is de sterkste rode vlag (CSOR en PubChem zijn het voor
exact dezelfde CID oneens) en verdient prioriteit boven CAS-resolutie-afwijkingen (die ook een
naam-matching-onzekerheid bij PubChem kunnen weerspiegelen, niet per se een CSOR-fout).
Een "unresolved" CAS-nummer is geen CSOR-fout, wel een aanwijzing dat het CAS-nummer zelf
mogelijk incorrect is (zie ook de CAS-checksumcheck) of dat PubChem die stof niet kent. Een
`cas_afwijkend`-resultaat in cas_resolution_omgekeerd.csv is een sterke aanwijzing dat CSOR's
CAS-nummer verouderd/fout is (de inchikey — een structuurgebaseerde sleutel — wijst naar een
andere PubChem-CAS-notatie); `geen_cas_synoniem` is geen aanwijzing van een fout, enkel dat
PubChem voor die stof geen CAS-synoniem publiceert.

OUTPUTS
-------
output/tables/cas_resolution.csv
output/tables/cas_resolution_omgekeerd.csv
output/tables/cid_crosscheck.csv
output/tables/internal_flags.csv
output/reports/variabele_identity.html
data/interim/variabele_records.parquet (tussentijds)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, pubchem, report, sparql_client as sc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERIM_DIR = REPO_ROOT / "data" / "interim"
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


def build_records(graph: rdflib.Graph) -> "pd.DataFrame":  # noqa: F821
    df = sc.to_dataframe(
        graph,
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
    return df


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


def reverse_resolve_unresolved(cas_df: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
    """Omgekeerde CAS-resolutie via de al gekende inchikey (zie METHODOLOGY) voor de subset van
    'unresolved' CAS-resolutiegevallen die toch al een inchikey hebben."""
    candidates = cas_df[(cas_df["status"] == "unresolved") & cas_df["stored_inchikey"].notna()]
    rows = []
    for _, r in candidates.iterrows():
        pc = pubchem.get_by_inchikey(r["stored_inchikey"], CACHE_ROOT)

        cid = pc.get("CID") if pc.get("found") else None
        iupac = pc.get("IUPACName") if pc.get("found") else None
        cas_kandidaten: list[str] = []
        synoniemen: list[str] = []
        label_in_synoniemen = False

        if cid is not None:
            syn = pubchem.get_synonyms(cid, CACHE_ROOT)
            synoniemen = syn.get("synonyms", [])
            cas_kandidaten = sorted({s for s in synoniemen if CAS_RE.match(s)})
            label_lower = str(r["label"]).strip().lower()
            label_in_synoniemen = any(s.strip().lower() == label_lower for s in synoniemen)

        if cid is None:
            resultaat = "niet_gevonden"
        elif not cas_kandidaten:
            resultaat = "geen_cas_synoniem"
        elif r["cas"] in cas_kandidaten:
            resultaat = "cas_bevestigd"
        else:
            resultaat = "cas_afwijkend"

        rows.append(
            {
                "notatie": r["notatie"],
                "cas": r["cas"],
                "label": r["label"],
                "stored_inchikey": r["stored_inchikey"],
                "pubchem_cid": cid,
                "pubchem_iupac": iupac,
                "pubchem_cas_kandidaten": "; ".join(cas_kandidaten),
                "resultaat": resultaat,
                "label_in_synoniemen": label_in_synoniemen,
                "pubchem_synoniemen": "; ".join(synoniemen),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "notatie",
            "cas",
            "label",
            "stored_inchikey",
            "pubchem_cid",
            "pubchem_iupac",
            "pubchem_cas_kandidaten",
            "resultaat",
            "label_in_synoniemen",
            "pubchem_synoniemen",
        ],
    )


def build_html_report(
    flags_df: "pd.DataFrame",  # noqa: F821
    cid_df: "pd.DataFrame",  # noqa: F821
    cas_df: "pd.DataFrame",  # noqa: F821
    reverse_df: "pd.DataFrame",  # noqa: F821
) -> Path:
    fig_flags = report.bar_counts(
        flags_df["flag_type"].value_counts(),
        title="Interne vlaggen per type",
        xaxis_title="flag_type",
    )
    disc_flags = (
        f"{len(flags_df)} interne vlag(gen) — CAS-checksum, InChIKey-vorm, of duplicaten, "
        "zonder externe afhankelijkheid."
        if len(flags_df)
        else "Geen interne vlaggen gevonden — het verwachte patroon."
    )

    fig_status = report.bar_counts(
        cas_df["status"].value_counts(),
        title="CAS-resolutie per status",
        xaxis_title="status",
    )
    n_unresolved = int((cas_df["status"] == "unresolved").sum())
    n_mismatch = int((cas_df["status"] == "mismatch").sum())
    geen_match_df = cas_df[cas_df["status"] != "match"]
    disc_status = (
        f"{len(cas_df)} CAS-kandidaten getoetst — {n_mismatch} mismatch(es), {n_unresolved} "
        "unresolved. Een 'unresolved' CAS-nummer is geen CSOR-fout, wel een aanwijzing dat het "
        "CAS-nummer zelf mogelijk incorrect is of dat PubChem die stof niet kent. Onderstaande "
        f"tabel toont alle {len(geen_match_df)} stoffen-variabelen zonder 'match'-status "
        "(mismatch, unresolved of resolved_new)."
    )

    mismatches = cid_df[cid_df["inchikey_match"] == False]  # noqa: E712
    disc_cid = (
        f"{int(cid_df['found'].sum())} van {len(cid_df)} CID-kandidaten teruggevonden bij "
        "PubChem. "
        + (
            f"{len(mismatches)} InChIKey-mismatch(en) — dit is de sterkste rode vlag in dit "
            "script: CSOR en PubChem zijn het voor exact dezelfde CID oneens, en dit verdient "
            f"prioriteit boven CAS-resolutie-afwijkingen. Voorbeelden: "
            f"{', '.join(mismatches['notatie'].head(5))}."
            if len(mismatches)
            else "Geen InChIKey-mismatches — het verwachte patroon."
        )
    )

    sections = [
        report.Section(
            heading="Interne checks",
            discussion=disc_flags,
            figures=[fig_flags] if len(flags_df) else [],
            table_df=flags_df if len(flags_df) else None,
        ),
        report.Section(
            heading="CAS-resolutie",
            discussion=disc_status,
            figures=[fig_status],
            table_df=geen_match_df if len(geen_match_df) else None,
            # Own addition t.o.v. de Section-default (table_n=10): compacte, volledig
            # actionable lijst — de standaard top-10-afkap zou hier de meerderheid verbergen.
            table_n=len(geen_match_df),
        ),
        report.Section(
            heading="PubChem CID-crosscheck",
            discussion=disc_cid,
            table_df=mismatches if len(mismatches) else None,
        ),
    ]

    if len(reverse_df):
        n_afwijkend = int((reverse_df["resultaat"] == "cas_afwijkend").sum())
        n_bevestigd = int((reverse_df["resultaat"] == "cas_bevestigd").sum())
        disc_reverse = (
            f"{len(reverse_df)} 'unresolved' CAS-gevallen hadden toch al een inchikey — "
            "omgekeerd opgezocht bij PubChem via die inchikey. "
            f"{n_afwijkend} tonen een ander CAS-nummer bij PubChem dan CSOR's opgeslagen "
            "waarde (sterke aanwijzing van een verouderd/fout CAS-nummer), "
            f"{n_bevestigd} bevestigen CSOR's CAS-nummer alsnog (PubChem kende het CAS-nummer "
            "enkel niet als zoekterm)."
            if n_afwijkend or n_bevestigd
            else f"{len(reverse_df)} 'unresolved' CAS-gevallen hadden toch al een inchikey — "
            "omgekeerd opgezocht bij PubChem, maar geen enkele levert een CAS-vormig synoniem "
            "op om tegen CSOR's waarde af te toetsen."
        )
        sections.append(
            report.Section(
                heading="Omgekeerde CAS-resolutie via InChIKey",
                discussion=disc_reverse,
                table_df=reverse_df,
                table_n=len(reverse_df),
            )
        )

    return report.build_report(
        name="variabele_identity",
        title="CSOR — chemische-identiteitscheck op csor:Variabele",
        intro=(
            "Kan een CAS-nummer betrouwbaar naar een InChIKey herleid worden, en zijn de "
            "reeds opgeslagen eigenschappen (cas, inchikey, iupacNaam) consistent met PubChem "
            "als externe referentiebron?"
        ),
        sections=sections,
    )


def main(graph: rdflib.Graph | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    if graph is None:
        graph = dataset.fetch_and_save()

    df = build_records(graph)
    df.to_parquet(INTERIM_DIR / "variabele_records.parquet")

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

    # Columns: notatie/cas/label/stored_inchikey zoals cas_resolution.csv (subset met
    # status=unresolved en stored_inchikey niet leeg); pubchem_cid/pubchem_iupac van de
    # omgekeerde inchikey-lookup; pubchem_cas_kandidaten (";"-gescheiden CAS-vormige synoniemen);
    # resultaat (niet_gevonden/geen_cas_synoniem/cas_bevestigd/cas_afwijkend);
    # label_in_synoniemen (True als skos:prefLabel letterlijk als PubChem-synoniem voorkomt);
    # pubchem_synoniemen (volledige synoniemenlijst, ";"-gescheiden, voor handmatige review).
    print("\nOmgekeerde CAS-resolutie via InChIKey loopt (gecached, ~0.2s/live-call)...")
    reverse_df = reverse_resolve_unresolved(cas_df)
    reverse_df.to_csv(OUTPUT_DIR / "cas_resolution_omgekeerd.csv", index=False)
    print(
        f"Omgekeerde CAS-resolutie: {len(reverse_df)} kandidaten — "
        f"{reverse_df['resultaat'].value_counts().to_dict() if len(reverse_df) else {}}"
    )

    print(f"\nlive PubChem-calls deze run: {pubchem.live_call_count}")

    report_path = build_html_report(flags_df, cid_df, cas_df, reverse_df)
    print(f"\nRapport geschreven naar {report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
