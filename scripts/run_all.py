"""
run_all.py — draait alle datakwaliteitschecks en regenereert het datamodel-diagram

PURPOSE
-------
Eén ingang om alle herhaalbare analyses (samenstellende variabelen, chemische identiteit,
conceptschema-structuur/-volledigheid, QUDT-koppelingskwaliteit, inhoudelijke Parameter-/
ParameterAspect-consistentie, terminologie-/VMM-woordenboekdekking) na elkaar uit te voeren, met
een korte samenvatting op stdout, en aansluitend het TikZ-datamodeldiagram te regenereren
(README.md). Analoog aan run_all.R in het zusterproject A-Substance-Is-Not-Always-a-Substance.

DATA PROVENANCE
----------------
Roept de zes scripts/check_*.py en scripts/generate_diagram.py aan als submodules (geen
subprocess) zodat een gedeelde Python-sessie/venv volstaat. Regenereert vóór de checks de
lokale volledige-registersnapshot (`analyse/csor_merged.ttl`, zie
scripts/common/dataset.py::fetch_and_save()) en geeft die éénmalig opgehaalde graph door aan
elke check — zo draaien alle checks in één run tegen exact dezelfde snapshot en gebeurt de
live-fetch maar één keer i.p.v. vijf keer.

METHODOLOGY
-----------
Geen eigen logica — orchestratie. De diagramgeneratie staat bewust apart van CHECKS (het is
geen datakwaliteitscheck maar documentatiegeneratie), maar draait wel standaard mee zodat
README.md nooit stilzwijgend achterloopt op het register. Ook generate_diagram.py draait
lokaal tegen dezelfde snapshot als de vijf checks.

OUTPUTS
-------
Zie de OUTPUTS-secties van de vier check-scripts en van generate_diagram.py.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import dataset  # noqa: E402
import check_samenstellende_variabelen  # noqa: E402
import check_variabele_identity  # noqa: E402
import check_conceptschemas  # noqa: E402
import check_eenheden_qudt  # noqa: E402
import check_parameter_inhoud  # noqa: E402
import check_terminologie  # noqa: E402
import generate_diagram  # noqa: E402

CHECKS = [
    ("check_samenstellende_variabelen.py", check_samenstellende_variabelen),
    ("check_variabele_identity.py", check_variabele_identity),
    ("check_conceptschemas.py", check_conceptschemas),
    ("check_eenheden_qudt.py", check_eenheden_qudt),
    ("check_parameter_inhoud.py", check_parameter_inhoud),
    ("check_terminologie.py", check_terminologie),
]


def main() -> None:
    start = time.monotonic()

    print("=" * 78)
    print("Lokale snapshot regenereren (analyse/csor_merged.ttl)")
    print("=" * 78)
    graph = dataset.fetch_and_save()
    print()

    for i, (name, module) in enumerate(CHECKS, 1):
        print("=" * 78)
        print(f"{i}/{len(CHECKS)} — {name}")
        print("=" * 78)
        module.main(graph)
        print()

    print("=" * 78)
    print("generate_diagram.py (datamodel-diagram, README.md)")
    print("=" * 78)
    generate_diagram.main(graph)

    elapsed = time.monotonic() - start
    print()
    print("=" * 78)
    print(
        f"Alle {len(CHECKS)} checks + diagramgeneratie voltooid in {elapsed:.0f}s. "
        "Zie output/tables/ voor de resultaten en output/reports/ voor de HTML-rapporten."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
