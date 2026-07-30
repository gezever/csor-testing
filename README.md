# csor-testing

Testproject voor het Vlaamse CSO-register (CSOR): herhaalbare SPARQL-analyses en Python-scripts
die de datakwaliteit van CSOR toetsen (interne consistentie én consistentie met externe bronnen
zoals PubChem).

Zie `CLAUDE.md` voor projectconventies (mapstructuur, scriptheader-formaat, SPARQL-valkuilen),
`sparql/` voor de querydefinities en `reports/` voor de resulterende rapporten.

## Snel starten

```bash
python3 -m venv .venv
.venv/bin/pip install --index-url https://pypi.org/simple -r requirements.txt
.venv/bin/python scripts/run_all.py
```