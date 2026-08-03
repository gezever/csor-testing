"""
check_variabele_identity.py — chemische-identiteitscheck op csor:Variabele

PURPOSE
-------
Test de datakwaliteit van de chemische-identiteitsvelden op csor:Variabele: kan een
CAS-nummer betrouwbaar naar een InChIKey herleid worden, zijn de reeds opgeslagen
eigenschappen (cas, inchikey, iupacNaam) consistent met een externe referentiebron (PubChem),
en klopt `csor:eea` (voor individuele stoffen empirisch vaak het EC/EINECS-nummer, zie
METHODOLOGY) tegen ECHA en PubChem? v1-scope: PubChem + ECHA-regelgevingslijsten als externe
bronnen; ChEBI-crosscheck blijft bewust buiten scope (zie reports/rapport_variabele_identiteit.md,
paragraaf "buiten scope" — de EC/EEA-consistentie die daar destijds ook als buiten scope
vermeld stond, is inmiddels wél gedekt, zie hieronder).

DATA PROVENANCE
----------------
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`
— bevat o.a. de `variabele`-instanties (25.312 triples, voorheen rechtstreeks als apart graph
opgehaald via sparql/csor-variabele-fetch.sparql; die paginatie/verificatie gebeurt nu bij de
snapshot-regeneratie zelf, zie common/dataset.py).
Externe bronnen: PubChem PUG-REST (common.pubchem), met bestandscache — blijft per definitie
live/extern. Voor de EC-nummercrosscheck (zie METHODOLOGY): `data/source/echa_lijsten_ec_cas.csv`
— een gecommitte, door `scripts/fetch_echa_lists.py` ververste combinatie van 14 publieke
ECHA-regelgevingslijsten (CAS↔EC-paren) — dit script leest enkel dat bestand, haalt zelf niets
live op bij ECHA.

METHODOLOGY
-----------
- Interne checks (geen externe afhankelijkheid): CAS-checksum (mod-10 controlegetal, de
  standaard CAS Registry Number-validatie), EC-checksum (mod-11, ISBN-achtig — own addition,
  ondanks een eerdere, foutieve aanname in dit project dat zo'n controlegetal voor EC-nummers
  niet publiek gedocumenteerd zou zijn; geverifieerd tegen bekende echte EC-nummers, zie
  `ec_checksum_valid()`), InChIKey-vormvalidatie (regex), dubbele InChIKey/CAS over notaties
  heen (kruiscontrole met sparql/variabele_identity_checks.sparql queries A/B).
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
  gelijkenis (bv. taalverschil NL/EN) zelf kan beoordelen. Own addition: naast CAS-kandidaten
  wordt op basis van diezelfde CID ook een EC-nummerkandidaat gezocht (`echa_lijsten_ec_cas.csv`
  + PubChem `xrefs/RN`, zie hieronder) — zonder aparte InChIKey-verificatiestap, want de CID zelf
  is al aan CSOR's eigen, gekende inchikey verankerd.
- EC-nummercrosscheck voor `csor:eea` (own addition): een steekproef tijdens de verkenning
  (live tegen `chem.echa.europa.eu`'s volledige substance-database) gaf 14/15 exacte matches
  tussen `csor:eea` en het echte EC-nummer voor individuele stoffen — dit weerspreekt deels de
  eerdere, in dit script nog steeds correcte aanname dat `csor:eea` géén EC-nummer zou zijn voor
  stofgroepen/somparameters (die hebben geen EC-vormige `eea`, zie `parameter_eea_mismatch.csv`
  in check_parameter_inhoud.py). Voor elke `csor:Variabele` met een EC-vormige `eea`
  (`\\d{3}-\\d{3}-\\d`, middelste groep exact 3 cijfers — onderscheidbaar van CAS' exact 2) én
  een `cas`: (a) exacte match van `cas` tegen `data/source/echa_lijsten_ec_cas.csv` (14
  ECHA-regelgevingslijsten, zie fetch_echa_lists.py — regelgevende deelverzamelingen, geen
  volledige stoffendatabank, dus lagere dekking dan de 14/15-steekproef is verwacht), en (b) een
  PubChem-crosscheck via het tot nu toe ongebruikte `xrefs/RN`-endpoint
  (`common.pubchem.get_xrefs_rn()`) — PubChem's eigen "Registry Number"-lijst bevat CAS- én
  EC-nummers door elkaar, gefilterd op hetzelfde EC-patroon. Beide bronnen zijn onafhankelijk;
  een match in minstens één ervan telt als bevestiging.
- CAS→EC-suggesties, InChIKey-geverifieerd (own addition, omgekeerde/bredere variant van de
  crosscheck hierboven): `eea_ec_crosscheck()` gaat uit van een al aanwezige, EC-vormige
  `csor:eea` (120 kandidaten). Deze check gaat in de andere richting — voor **alle** variabelen
  met een `cas` (1257, ongeacht of/hoe `eea` al ingevuld is) worden dezelfde twee bronnen
  (ECHA-lijsten + PubChem `xrefs/RN`) geraadpleegd om kandidaat-EC-nummers te vínden, niet enkel
  te verifiëren. Elke gevonden kandidaat wordt vervolgens **onafhankelijk geverifieerd**: het
  EC-nummer zelf wordt als zoekterm bij PubChem opgezocht (`pubchem.get_by_name()` — PubChem's
  "name"-endpoint accepteert EC-nummers net zoals CAS-nummers, empirisch bevestigd tijdens de
  verkenning) en de resulterende InChIKey wordt vergeleken met de InChIKey die de CAS-lookup al
  opleverde. Enkel bij een InChIKey-match (dezelfde structuur, dus zeker dezelfde stof) telt een
  kandidaat als geverifieerd — dit vangt het geval op waarbij een CAS/EC-paar toevallig in
  dezelfde bronrij staat zonder werkelijk dezelfde stof te zijn. Steekproef tijdens de
  verkenning: CAS `79-57-2` (Oxytetracycline) → InChIKey `OWFJMIVZYSDULZ-...`; PubChem's
  xrefs-kandidaat `103-115-5` → zelfde CID (54675779) én InChIKey — geverifieerd; CSOR's eigen
  `eea` (`218-161-2`) blijkt bij PubChem zelfs helemaal onbekend als zoekterm.

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
PubChem voor die stof geen CAS-synoniem publiceert. Voor `eea_ec_crosscheck.csv`: `afwijkend`
(minstens één bron vond EC-kandidaten voor dat CAS-nummer, maar `csor:eea` zit er niet tussen)
is een concrete aanwijzing voor een fout `eea`-veld; `onbekend` (geen van beide bronnen vond
EC-data) is — gezien de beperkte dekking van de 14 regelgevingslijsten — geen aanwijzing van
een fout, enkel dat die stof op geen van de geraadpleegde lijsten voorkomt. Voor
`cas_ec_suggesties.csv`: `suggestie` (een geverifieerde EC-kandidaat gevonden, maar `csor:eea`
zelf is leeg) is een concrete aanvulling, geen fout; `afwijkend` is dezelfde sterke aanwijzing
als hierboven; `kandidaten_niet_bevestigd` (een kandidaat gevonden in de bronlijsten, maar de
InChIKey-verificatie kon geen enkele bevestigen) wijst op een mogelijk foute CAS/EC-koppeling
in de **bronlijst zelf** (ECHA of PubChem), niet per se in CSOR.

OUTPUTS
-------
output/tables/cas_resolution.csv
output/tables/cas_resolution_omgekeerd.csv
output/tables/cid_crosscheck.csv
output/tables/cas_ec_suggesties.csv
output/tables/internal_flags.csv
output/tables/eea_ec_crosscheck.csv
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
SOURCE_DIR = REPO_ROOT / "data" / "source"

CSOR = "https://data.omgeving.vlaanderen.be/ns/csor#"
PUBCHEM_PRED = "https://pubchem.ncbi.nlm.nih.gov/rest/rdf/compound"
CID_RE = re.compile(r"CID(\d+)$")
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
EC_RE = re.compile(r"^\d{3}-\d{3}-\d$")
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


def ec_checksum_valid(ec: str) -> bool:
    """EC/EINECS-controlegetal (mod-11, ISBN-achtig): som van de eerste 6 cijfers, elk
    vermenigvuldigd met zijn positie (1 t/m 6), mod 11 == het 7e cijfer. Own addition,
    geverifieerd tegen bekende echte EC-nummers tijdens de verkenning (bv. Fluorantheen
    205-912-4: 1*2+2*0+3*5+4*9+5*1+6*2=70, 70 mod 11=4). Enkel van toepassing op
    EC-vormige strings (EC_RE); geeft False terug voor alles wat niet dat formaat heeft.
    """
    m = EC_RE.match(ec)
    if not m:
        return False
    digits = [int(c) for c in ec if c.isdigit()]
    check_digit = digits[6]
    total = sum((i + 1) * digits[i] for i in range(6))
    return total % 11 == check_digit


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

    eea_ec_shaped = df[df["eea"].notna() & df["eea"].str.match(EC_RE, na=False)]
    invalid_eea = eea_ec_shaped[~eea_ec_shaped["eea"].apply(ec_checksum_valid)]
    for _, r in invalid_eea.iterrows():
        flags.append(
            {
                "notatie": r["notatie"],
                "flag_type": "eea_ec_checksum_invalid",
                "detail": f"eea={r['eea']}",
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


def reverse_resolve_unresolved(
    cas_df: "pd.DataFrame", echa_df: "pd.DataFrame"  # noqa: F821
) -> "pd.DataFrame":  # noqa: F821
    """Omgekeerde CAS-resolutie via de al gekende inchikey (zie METHODOLOGY) voor de subset van
    'unresolved' CAS-resolutiegevallen die toch al een inchikey hebben. Own addition: suggereert
    ook een EC-nummer (zelfde twee bronnen als eea_ec_crosscheck()/cas_ec_suggestions(), maar
    hier zonder aparte InChIKey-verificatiestap — de CID is al aan CSOR's eigen, gekende
    inchikey verankerd, dus elke kandidaat die eruit voortvloeit is het per constructie ook)."""
    echa_by_cas = _echa_by_cas(echa_df)
    candidates = cas_df[(cas_df["status"] == "unresolved") & cas_df["stored_inchikey"].notna()]
    rows = []
    for _, r in candidates.iterrows():
        pc = pubchem.get_by_inchikey(r["stored_inchikey"], CACHE_ROOT)

        cid = pc.get("CID") if pc.get("found") else None
        iupac = pc.get("IUPACName") if pc.get("found") else None
        cas_kandidaten: list[str] = []
        synoniemen: list[str] = []
        label_in_synoniemen = False
        ec_kandidaten: set[str] = set()

        if cid is not None:
            syn = pubchem.get_synonyms(cid, CACHE_ROOT)
            synoniemen = syn.get("synonyms", [])
            cas_kandidaten = sorted({s for s in synoniemen if CAS_RE.match(s)})
            label_lower = str(r["label"]).strip().lower()
            label_in_synoniemen = any(s.strip().lower() == label_lower for s in synoniemen)

            for c in {r["cas"], *cas_kandidaten}:
                ec_kandidaten |= echa_by_cas.get(c, set())
            xrefs = pubchem.get_xrefs_rn(cid, CACHE_ROOT)
            ec_kandidaten |= {rn for rn in xrefs.get("rn", []) if EC_RE.match(rn)}

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
                "pubchem_ec_kandidaten": "; ".join(sorted(ec_kandidaten)),
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
            "pubchem_ec_kandidaten",
            "resultaat",
            "label_in_synoniemen",
            "pubchem_synoniemen",
        ],
    )


def _echa_by_cas(echa_df: "pd.DataFrame") -> dict[str, set[str]]:  # noqa: F821
    """{cas_number: {ec_number, ...}} uit echa_lijsten_ec_cas.csv — gedeeld door de drie
    EC-nummerchecks hieronder (eea_ec_crosscheck, cas_ec_suggestions, reverse_resolve_unresolved)."""
    echa_by_cas: dict[str, set[str]] = {}
    for cas, ec in zip(echa_df["cas_number"], echa_df["ec_number"]):
        if pd.notna(cas) and pd.notna(ec):
            echa_by_cas.setdefault(cas, set()).add(ec)
    return echa_by_cas


def eea_ec_crosscheck(
    df: "pd.DataFrame", echa_df: "pd.DataFrame"  # noqa: F821
) -> "pd.DataFrame":  # noqa: F821
    """Toetst csor:eea (voor individuele stoffen empirisch vaak het EC/EINECS-nummer) tegen
    ECHA's regelgevingslijsten en PubChem's Registry-Number-kruisverwijzingen (zie METHODOLOGY)."""
    candidates = df[df["eea"].notna() & df["cas"].notna()]
    candidates = candidates[candidates["eea"].str.match(EC_RE)]

    echa_by_cas = _echa_by_cas(echa_df)

    rows = []
    for _, r in candidates.iterrows():
        cas = r["cas"]
        eea = r["eea"]

        echa_kandidaten = sorted(echa_by_cas.get(cas, set()))

        pc = pubchem.get_by_cas(cas, CACHE_ROOT, properties=["InChIKey"])
        pubchem_kandidaten: list[str] = []
        if pc.get("found") and pc.get("CID"):
            xrefs = pubchem.get_xrefs_rn(pc["CID"], CACHE_ROOT)
            pubchem_kandidaten = sorted({rn for rn in xrefs.get("rn", []) if EC_RE.match(rn)})

        echa_match = eea in echa_kandidaten
        pubchem_match = eea in pubchem_kandidaten

        if echa_match or pubchem_match:
            resultaat = "bevestigd"
        elif echa_kandidaten or pubchem_kandidaten:
            resultaat = "afwijkend"
        else:
            resultaat = "onbekend"

        rows.append(
            {
                "notatie": r["notatie"],
                "label": r["label"],
                "cas": cas,
                "csor_eea": eea,
                "echa_ec_kandidaten": "; ".join(echa_kandidaten),
                "echa_match": echa_match,
                "pubchem_ec_kandidaten": "; ".join(pubchem_kandidaten),
                "pubchem_match": pubchem_match,
                "resultaat": resultaat,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "notatie",
            "label",
            "cas",
            "csor_eea",
            "echa_ec_kandidaten",
            "echa_match",
            "pubchem_ec_kandidaten",
            "pubchem_match",
            "resultaat",
        ],
    )


def cas_ec_suggestions(
    df: "pd.DataFrame", echa_df: "pd.DataFrame"  # noqa: F821
) -> "pd.DataFrame":  # noqa: F821
    """Omgekeerde, bredere variant van eea_ec_crosscheck(): voor élke variabele met een cas
    (ongeacht of/hoe eea al ingevuld is) EC-kandidaten zoeken bij ECHA en PubChem, en elke
    kandidaat onafhankelijk verifiëren via InChIKey (zie METHODOLOGY)."""
    candidates = df[df["cas"].notna()]
    echa_by_cas = _echa_by_cas(echa_df)

    rows = []
    for _, r in candidates.iterrows():
        cas = r["cas"]
        eea = r["eea"] if pd.notna(r["eea"]) else None

        pc_cas = pubchem.get_by_cas(cas, CACHE_ROOT, properties=["InChIKey"])
        inchikey_cas = pc_cas.get("InChIKey") if pc_cas.get("found") else None

        echa_kandidaten = sorted(echa_by_cas.get(cas, set()))
        pubchem_kandidaten: list[str] = []
        if pc_cas.get("found") and pc_cas.get("CID"):
            xrefs = pubchem.get_xrefs_rn(pc_cas["CID"], CACHE_ROOT)
            pubchem_kandidaten = sorted({rn for rn in xrefs.get("rn", []) if EC_RE.match(rn)})

        alle_kandidaten = sorted(set(echa_kandidaten) | set(pubchem_kandidaten))

        geverifieerd: list[str] = []
        if inchikey_cas is not None:
            for ec in alle_kandidaten:
                pc_ec = pubchem.get_by_name(ec, CACHE_ROOT, properties=["InChIKey"])
                if pc_ec.get("found") and pc_ec.get("InChIKey") == inchikey_cas:
                    geverifieerd.append(ec)

        if not alle_kandidaten:
            resultaat = "onbekend"
        elif not geverifieerd:
            resultaat = "kandidaten_niet_bevestigd"
        elif eea is None:
            resultaat = "suggestie"
        elif eea in geverifieerd:
            resultaat = "bevestigd"
        else:
            resultaat = "afwijkend"

        rows.append(
            {
                "notatie": r["notatie"],
                "label": r["label"],
                "cas": cas,
                "csor_eea": eea,
                "echa_ec_kandidaten": "; ".join(echa_kandidaten),
                "pubchem_ec_kandidaten": "; ".join(pubchem_kandidaten),
                "geverifieerde_ec_kandidaten": "; ".join(geverifieerd),
                "resultaat": resultaat,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "notatie",
            "label",
            "cas",
            "csor_eea",
            "echa_ec_kandidaten",
            "pubchem_ec_kandidaten",
            "geverifieerde_ec_kandidaten",
            "resultaat",
        ],
    )


def build_html_report(
    flags_df: "pd.DataFrame",  # noqa: F821
    cid_df: "pd.DataFrame",  # noqa: F821
    cas_df: "pd.DataFrame",  # noqa: F821
    reverse_df: "pd.DataFrame",  # noqa: F821
    eea_df: "pd.DataFrame",  # noqa: F821
    cas_ec_df: "pd.DataFrame",  # noqa: F821
) -> Path:
    fig_flags = report.bar_counts(
        flags_df["flag_type"].value_counts(),
        title="Interne vlaggen per type",
        xaxis_title="flag_type",
    )
    disc_flags = (
        f"{len(flags_df)} interne vlag(gen) — CAS-checksum, EC-checksum, InChIKey-vorm, of "
        "duplicaten, zonder externe afhankelijkheid."
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
        n_ec_kandidaat = int((reverse_df["pubchem_ec_kandidaten"] != "").sum())
        disc_reverse = (
            (
                f"{len(reverse_df)} 'unresolved' CAS-gevallen hadden toch al een inchikey — "
                "omgekeerd opgezocht bij PubChem via die inchikey. "
                f"{n_afwijkend} tonen een ander CAS-nummer bij PubChem dan CSOR's opgeslagen "
                "waarde (sterke aanwijzing van een verouderd/fout CAS-nummer), "
                f"{n_bevestigd} bevestigen CSOR's CAS-nummer alsnog (PubChem kende het "
                "CAS-nummer enkel niet als zoekterm)."
                if n_afwijkend or n_bevestigd
                else f"{len(reverse_df)} 'unresolved' CAS-gevallen hadden toch al een inchikey — "
                "omgekeerd opgezocht bij PubChem, maar geen enkele levert een CAS-vormig "
                "synoniem op om tegen CSOR's waarde af te toetsen."
            )
            + f" {n_ec_kandidaat} van de {len(reverse_df)} hebben op basis van diezelfde "
            "inchikey ook een EC-nummerkandidaat (ECHA-lijsten en/of PubChem xrefs/RN, zie "
            "kolom pubchem_ec_kandidaten)."
        )
        sections.append(
            report.Section(
                heading="Omgekeerde CAS-resolutie via InChIKey",
                discussion=disc_reverse,
                table_df=reverse_df,
                table_n=len(reverse_df),
            )
        )

    if len(eea_df):
        fig_eea = report.bar_counts(
            eea_df["resultaat"].value_counts(),
            title="EC-nummercrosscheck per resultaat",
            xaxis_title="resultaat",
        )
        n_bevestigd_eea = int((eea_df["resultaat"] == "bevestigd").sum())
        n_afwijkend_eea = int((eea_df["resultaat"] == "afwijkend").sum())
        n_onbekend_eea = int((eea_df["resultaat"] == "onbekend").sum())
        disc_eea = (
            f"{len(eea_df)} csor:Variabele met een EC-vormige csor:eea getoetst tegen 14 "
            "ECHA-regelgevingslijsten (data/source/echa_lijsten_ec_cas.csv) en PubChem's "
            f"Registry-Number-kruisverwijzingen — {n_bevestigd_eea} bevestigd (minstens één "
            f"bron komt overeen met CSOR's eea), {n_afwijkend_eea} afwijkend (een bron vond een "
            f"ander EC-nummer), {n_onbekend_eea} onbekend (geen van beide bronnen kent dit "
            "CAS-nummer — verwacht, gezien de 14 lijsten regelgevende deelverzamelingen zijn, "
            "geen volledige stoffendatabank; geen aanwijzing van een fout)."
        )
        afwijkend_eea_df = eea_df[eea_df["resultaat"] == "afwijkend"]
        sections.append(
            report.Section(
                heading="EC-nummercrosscheck (csor:eea)",
                discussion=disc_eea,
                figures=[fig_eea],
                table_df=afwijkend_eea_df if len(afwijkend_eea_df) else None,
                table_n=len(afwijkend_eea_df),
            )
        )

    if len(cas_ec_df):
        fig_cas_ec = report.bar_counts(
            cas_ec_df["resultaat"].value_counts(),
            title="CAS→EC-suggesties per resultaat",
            xaxis_title="resultaat",
        )
        n_suggestie = int((cas_ec_df["resultaat"] == "suggestie").sum())
        n_afwijkend_cas_ec = int((cas_ec_df["resultaat"] == "afwijkend").sum())
        n_niet_bevestigd = int((cas_ec_df["resultaat"] == "kandidaten_niet_bevestigd").sum())
        disc_cas_ec = (
            f"Omgekeerde, bredere check t.o.v. de vorige sectie: voor alle {len(cas_ec_df)} "
            "variabelen met een cas (ongeacht of eea al ingevuld is) EC-kandidaten gezocht bij "
            "ECHA en PubChem, elk onafhankelijk geverifieerd via InChIKey (het EC-nummer zelf "
            "als PubChem-zoekterm, vergeleken met de InChIKey van het cas-nummer). "
            f"{n_suggestie} variabelen hebben een geverifieerde EC-kandidaat maar nog geen "
            f"csor:eea (aanvulling, geen fout — volledige lijst in cas_ec_suggesties.csv). "
            f"{n_afwijkend_cas_ec} tonen een afwijking met de al ingevulde csor:eea. "
            f"{n_niet_bevestigd} hebben een kandidaat in de bronlijsten die de InChIKey-check "
            "niet kon bevestigen — mogelijk een foute koppeling in de bronlijst zelf, niet per "
            "se in CSOR."
        )
        aandacht_cas_ec_df = cas_ec_df[
            cas_ec_df["resultaat"].isin(["afwijkend", "kandidaten_niet_bevestigd"])
        ]
        sections.append(
            report.Section(
                heading="CAS→EC-suggesties (InChIKey-geverifieerd)",
                discussion=disc_cas_ec,
                figures=[fig_cas_ec],
                table_df=aandacht_cas_ec_df if len(aandacht_cas_ec_df) else None,
                table_n=len(aandacht_cas_ec_df),
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

    echa_df = pd.read_csv(SOURCE_DIR / "echa_lijsten_ec_cas.csv", dtype=str)

    # Columns: notatie/cas/label/stored_inchikey zoals cas_resolution.csv (subset met
    # status=unresolved en stored_inchikey niet leeg); pubchem_cid/pubchem_iupac van de
    # omgekeerde inchikey-lookup; pubchem_cas_kandidaten (";"-gescheiden CAS-vormige synoniemen);
    # pubchem_ec_kandidaten (";"-gescheiden EC-kandidaten, zelfde twee bronnen als de
    # EC-nummercrosscheck hieronder, maar hier verankerd op de al gekende inchikey — geen aparte
    # verificatiestap nodig, zie reverse_resolve_unresolved()); resultaat (niet_gevonden/
    # geen_cas_synoniem/cas_bevestigd/cas_afwijkend); label_in_synoniemen (True als
    # skos:prefLabel letterlijk als PubChem-synoniem voorkomt); pubchem_synoniemen (volledige
    # synoniemenlijst, ";"-gescheiden, voor handmatige review).
    print("\nOmgekeerde CAS-resolutie via InChIKey loopt (gecached, ~0.2s/live-call)...")
    reverse_df = reverse_resolve_unresolved(cas_df, echa_df)
    reverse_df.to_csv(OUTPUT_DIR / "cas_resolution_omgekeerd.csv", index=False)
    print(
        f"Omgekeerde CAS-resolutie: {len(reverse_df)} kandidaten — "
        f"{reverse_df['resultaat'].value_counts().to_dict() if len(reverse_df) else {}}"
    )

    # Columns: notatie/label/cas zoals hierboven; csor_eea (het opgeslagen csor:eea-veld);
    # echa_ec_kandidaten (";"-gescheiden EC-nummers gevonden voor dit cas in de 14
    # ECHA-regelgevingslijsten); echa_match (True als csor_eea daarin voorkomt);
    # pubchem_ec_kandidaten (";"-gescheiden EC-vormige entries uit PubChem's xrefs/RN);
    # pubchem_match (idem); resultaat (bevestigd/afwijkend/onbekend, zie METHODOLOGY).
    print("\nEC-nummercrosscheck voor csor:eea loopt (gecached, ~0.2s/live-call)...")
    eea_df = eea_ec_crosscheck(df, echa_df)
    eea_df.to_csv(OUTPUT_DIR / "eea_ec_crosscheck.csv", index=False)
    print(
        f"EC-nummercrosscheck: {len(eea_df)} kandidaten — "
        f"{eea_df['resultaat'].value_counts().to_dict() if len(eea_df) else {}}"
    )

    # Columns: notatie/label/cas/csor_eea zoals hierboven (csor_eea leeg mag hier, i.t.t.
    # eea_ec_crosscheck.csv); echa_ec_kandidaten/pubchem_ec_kandidaten (";"-gescheiden, ruwe
    # kandidaten vóór verificatie); geverifieerde_ec_kandidaten (";"-gescheiden, enkel de
    # kandidaten waarvan de InChIKey — via een onafhankelijke PubChem-naamzoekopdracht op het
    # EC-nummer zelf — overeenkomt met de InChIKey van het cas-nummer); resultaat (onbekend/
    # kandidaten_niet_bevestigd/suggestie/bevestigd/afwijkend, zie METHODOLOGY).
    print("\nCAS->EC-suggesties (InChIKey-geverifieerd) lopen (gecached, ~0.2s/live-call)...")
    cas_ec_df = cas_ec_suggestions(df, echa_df)
    cas_ec_df.to_csv(OUTPUT_DIR / "cas_ec_suggesties.csv", index=False)
    print(
        f"CAS->EC-suggesties: {len(cas_ec_df)} kandidaten — "
        f"{cas_ec_df['resultaat'].value_counts().to_dict() if len(cas_ec_df) else {}}"
    )

    print(f"\nlive PubChem-calls deze run: {pubchem.live_call_count}")

    report_path = build_html_report(flags_df, cid_df, cas_df, reverse_df, eea_df, cas_ec_df)
    print(f"\nRapport geschreven naar {report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
