"""
run_all.py — draait alle datakwaliteitschecks na elkaar

PURPOSE
-------
Eén ingang om beide herhaalbare analyses (samenstellende variabelen, chemische identiteit)
na elkaar uit te voeren, met een korte samenvatting op stdout. Analoog aan run_all.R in het
zusterproject A-Substance-Is-Not-Always-a-Substance.

DATA PROVENANCE
----------------
Roept scripts/check_samenstellende_variabelen.py en scripts/check_variabele_identity.py aan
als submodules (geen subprocess) zodat een gedeelde Python-sessie/venv volstaat.

METHODOLOGY
-----------
Geen eigen logica — orchestratie.

OUTPUTS
-------
Zie de OUTPUTS-secties van de twee aangeroepen scripts.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_samenstellende_variabelen  # noqa: E402
import check_variabele_identity  # noqa: E402


def main() -> None:
    start = time.monotonic()

    print("=" * 78)
    print("1/2 — check_samenstellende_variabelen.py")
    print("=" * 78)
    check_samenstellende_variabelen.main()

    print()
    print("=" * 78)
    print("2/2 — check_variabele_identity.py")
    print("=" * 78)
    check_variabele_identity.main()

    elapsed = time.monotonic() - start
    print()
    print("=" * 78)
    print(f"Beide checks voltooid in {elapsed:.0f}s. Zie output/tables/ voor de resultaten.")
    print("=" * 78)


if __name__ == "__main__":
    main()
