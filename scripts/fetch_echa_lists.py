"""
fetch_echa_lists.py — ververst een gecombineerde ECHA-CAS/EC-referentietabel in data/source/

PURPOSE
-------
Haalt 14 publieke ECHA-regelgevingslijsten op (SVHC-kandidatenlijst, restrictielijst, POPs-lijst,
geharmoniseerde classificatielijst, en de bijhorende procesluik-lijsten) en combineert ze tot één
platte `{bron_lijst, substance_name, ec_number, cas_number}`-tabel, zodat
`scripts/check_variabele_identity.py::eea_ec_crosscheck()` CSOR's `csor:eea` (voor individuele
stoffen empirisch vaak het EC/EINECS-nummer, zie DATA PROVENANCE) lokaal tegen een echte
EC↔CAS-koppeling kan toetsen, zonder per stof een live ECHA-aanroep nodig te hebben. Dit is geen
CSOR-datakwaliteitscheck (vandaar geen check_-prefix, geen output/tables/-CSV en geen
HTML-rapport, zie CLAUDE.md §3/§10) maar een ververbare externe-bronfetch, analoog in geest aan
fetch_vmm_woordenboek.py/fetch_opentaal_wordlist.py.

DATA PROVENANCE
----------------
Bron: `chem.echa.europa.eu`'s publieke lijst-export-API's (`api-obligation-list`,
`api-activity-list`, `api-harmonised-list`), telkens `.xlsx`. Own addition: het R-script
`A-Substance-Is-Not-Always-a-Substance/R/01_download.R` (zusterproject) haalt deze en 3 andere
bestanden op mét sessie-cookies — bij navraag bleken die **niet nodig**: elk van de 14 hieronder
gaf tijdens de verkenning HTTP 200 zonder enige cookie, enkel met een gewone User-Agent-header.
Drie bestanden uit dat script zijn bewust **niet** overgenomen: de legacy
`candidate-list-of-svhc-for-authorisation-export.csv` (duplicaat van `candidateList`, maar via
een oudere route die wél een cookie/POST-formulier vereist), `euPositiveList` (19 rijen, geen
EC/CAS-substancetabel — enkel juridische tekst) en de EU-pesticidendatabank
(`ec.europa.eu`, andere bron, kolomkop niet op rij 1, vereist een cookie + een grote
hardgecodeerde ID-lijst om te bevragen) — buiten scope voor v1. Ook `reach_registrations.xlsx`
(zelfde zusterproject, 25.231 rijen, de breedste CAS↔EC-lijst) is bewust **niet** gebruikt: enkel
opvraagbaar via `api-substance/v1/substance/generated-export` zonder cookie-issue op zich, maar
op uitdrukkelijk verzoek buiten scope gehouden ten voordele van de 14 regelgevingslijsten
hieronder + een aparte PubChem-crosscheck (zie check_variabele_identity.py).

METHODOLOGY
-----------
Elke lijst wordt live opgehaald (`requests.get()`, geen paginatie — elk endpoint levert de
volledige lijst in één `.xlsx`-respons) en met `pandas.read_excel(engine="openpyxl")` ingelezen.
Own addition, dependency: `openpyxl` is de enige afwijking van de bewust minimale dependency-set
(CLAUDE.md §2) in dit project — noodzakelijk om `.xlsx` te parsen, geen alternatief zonder een
volledige Excel-parser. Elke lijst deelt dezelfde drie kernkolommen (`Substance name`,
`EC number`, `CAS number`, al dan niet met extra proces-specifieke kolommen erbij) — enkel die
drie worden bewaard, samen met een `bron_lijst`-kolom (bestandsnaam zonder extensie) voor
herleidbaarheid. Rijen zonder `EC number` én zonder `CAS number` worden weggelaten (zuiver
tekstuele/lege rijen die in sommige exports voorkomen).

INTERPRETATION
--------------
n.v.t. — bouwsteen/brondata, geen eigen bevindingen. Dit zijn regelgevende deelverzamelingen
(SVHC/POPs/restricties/geharmoniseerde classificatie), geen volledige ECHA-stoffendatabank — een
stof die hier niet in voorkomt, is daarom niet per se onbekend bij ECHA, enkel niet op een van
deze specifieke lijsten (zie check_variabele_identity.py's `eea_ec_crosscheck()` voor hoe dat
verrekend wordt: PubChem als aanvullende, bredere crosscheck).

OUTPUTS
-------
data/source/echa_lijsten_ec_cas.csv (gecommit)

USAGE
-----
python3 scripts/fetch_echa_lists.py
Geen parameters; herdraaien overschrijft het bestand volledig (idempotent). Bedoeld om af en toe
handmatig herdraaid te worden, niet als onderdeel van scripts/run_all.py (dat betreft uitsluitend
de CSOR-registerpijplijn zelf).
"""

from __future__ import annotations

import io
import warnings
from pathlib import Path

import pandas as pd
import requests

# Onschuldige openpyxl-waarschuwing ("Workbook contains no default style") die bij elk van de 14
# ECHA-exports afgaat — de bestanden missen een expliciete stylesheet, niet relevant voor de hier
# gebruikte kolomdata.
warnings.filterwarnings("ignore", message="Workbook contains no default style", module="openpyxl")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = REPO_ROOT / "data" / "source" / "echa_lijsten_ec_cas.csv"

HEADERS = {
    "User-Agent": "csor-testing/echa-lists-fetch (+geert.vanhaute@vlaanderen.be)",
    "Accept": "application/json, text/plain, */*",
}

# (bron_lijst, url) — telkens de volledige, cookie-vrij opgehaalde .xlsx-export van één ECHA-lijst
# (zie DATA PROVENANCE voor de 3 bewust weggelaten bestanden uit het zusterproject).
LISTS: list[tuple[str, str]] = [
    ("candidate_list", "https://chem.echa.europa.eu/api-obligation-list/v1/candidateList/fullExport"),
    ("restriction_list", "https://chem.echa.europa.eu/api-obligation-list/v1/restrictionList/fullExport"),
    ("pops_list", "https://chem.echa.europa.eu/api-obligation-list/v1/popsList/fullExport"),
    ("authorisation_list", "https://chem.echa.europa.eu/api-obligation-list/v1/authorisationList/fullExport"),
    (
        "harmonised_list",
        "https://chem.echa.europa.eu/api-harmonised-list/v1/export"
        "?orderBy=indexNumber&orderType=asc&showMembers=false&zoneId=Europe/Amsterdam",
    ),
    ("restriction_process", "https://chem.echa.europa.eu/api-activity-list/v1/restrictionProcess/fullExport"),
    ("svhc_identification", "https://chem.echa.europa.eu/api-activity-list/v1/svhcIdentification/fullExport"),
    ("authorisation_process", "https://chem.echa.europa.eu/api-activity-list/v1/authorisationProcess/fullExport"),
    ("dossier_evaluation", "https://chem.echa.europa.eu/api-activity-list/v1/dossierEvaluation/fullExport"),
    ("clh_process", "https://chem.echa.europa.eu/api-activity-list/v1/clhProcess/fullExport"),
    ("substance_evaluation", "https://chem.echa.europa.eu/api-activity-list/v1/substanceEvaluation/fullExport"),
    ("pops_process", "https://chem.echa.europa.eu/api-activity-list/v1/popsProcess/fullExport"),
    (
        "pbt_assessment",
        "https://chem.echa.europa.eu/api-activity-list/v1/pbtAssessment/export"
        "?orderBy=currentStageDate&orderType=desc&showMembers=false&zoneId=Europe/Amsterdam",
    ),
    (
        "ed_assessment",
        "https://chem.echa.europa.eu/api-activity-list/v1/edAssessment/export"
        "?orderBy=currentStageDate&orderType=desc&showMembers=false&zoneId=Europe/Amsterdam",
    ),
]

KEEP_COLUMNS = {"Substance name": "substance_name", "EC number": "ec_number", "CAS number": "cas_number"}


def fetch_list(bron_lijst: str, url: str) -> pd.DataFrame:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content), engine="openpyxl")
    df = df[[c for c in KEEP_COLUMNS if c in df.columns]].rename(columns=KEEP_COLUMNS)
    df["bron_lijst"] = bron_lijst
    # ECHA-exports gebruiken "-" als lege-veld-placeholder i.p.v. een echte lege cel.
    df[["ec_number", "cas_number"]] = df[["ec_number", "cas_number"]].replace("-", pd.NA)
    df = df.dropna(subset=["ec_number", "cas_number"], how="all")
    print(f"  {bron_lijst}: {len(df)} rijen")
    return df[["bron_lijst", "substance_name", "ec_number", "cas_number"]]


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    print(f"{len(LISTS)} ECHA-lijsten ophalen...")
    frames = [fetch_list(bron_lijst, url) for bron_lijst, url in LISTS]
    combined = pd.concat(frames, ignore_index=True)

    combined.to_csv(OUT_CSV, index=False)
    print(f"\nKlaar: {len(combined)} rijen over {len(LISTS)} lijsten -> {OUT_CSV.relative_to(REPO_ROOT)}")
    print(f"Distincte CAS-nummers: {combined['cas_number'].nunique()}")
    print(f"Distincte EC-nummers: {combined['ec_number'].nunique()}")


if __name__ == "__main__":
    main()
