# CLAUDE.md — projectconventies csor-testing

Dit document beschrijft de werkwijze en conventies voor dit project. Het is geïnspireerd op
`SKILL.md` uit het zusterproject `A-Substance-Is-Not-Always-a-Substance`, maar aangepast aan
csor-testing: Python in plaats van R, en een lichter gewicht (geen bookdown-/publicatiepijplijn
— wel tabellen, per-check-script gegenereerde Plotly-HTML-rapporten, en Markdown-rapporten, zie
§10).

`csor-testing` test de **datakwaliteit van het Vlaamse CSO-register (CSOR)**: SPARQL-analyses
over de RDF-data op `https://data-ontwikkel.omgeving.vlaanderen.be/sparql`, uitgevoerd op een
herhaalbare manier (niet als eenmalige, statische analyse) en gedocumenteerd in Nederlandstalige
rapporten.

---

## 1. Projectstructuur

```
csor-testing/
├── CLAUDE.md                # dit bestand
├── README.md
├── requirements.txt         # rdflib, requests, pandas, pyarrow, plotly
├── .venv/                   # gitignored — python3 -m venv .venv
├── sparql/                  # SPARQL-querydefinities: de "wat meten we"-laag
├── analyse/
│   └── csor_merged.ttl       # gitignored — lokale volledige-registersnapshot, bij elke run
│                              # vers geregenereerd (zie §4)
├── scripts/
│   ├── common/               # gedeelde bouwstenen (dataset-fetch/merge, lokale SPARQL-laag,
│   │                          # PubChem-/QUDT-client)
│   ├── check_*.py            # één script per analyse, herhaalbaar
│   ├── generate_diagram.py   # datamodeldiagram (TikZ/PDF, zie §6)
│   └── run_all.py            # regenereert de snapshot, draait dan alle checks + diagram
├── data/
│   ├── source/                # gecommitte snapshots van externe bronvocabularia (VMM-woordenboek,
│   │                          # OpenTaal-woordenlijst) — ververst door hun eigen fetch_*.py-script
│   │                          # (niet via run_all.py, zie §4)
│   ├── raw/                  # gitignored — losse .ttl-snapshots van individuele scripts
│   ├── interim/               # gitignored — tussentijdse pandas-tabellen (.parquet)
│   └── cache/{pubchem,qudt}/  # gitignored — API-cache (JSON per lookup)
├── output/
│   ├── tables/                # gegenereerde CSV's — WEL gecommit (reproduceerbare resultaten)
│   ├── diagrams/              # gegenereerd TikZ/PDF/PNG-diagram — WEL gecommit
│   └── reports/                # gegenereerde Plotly-HTML-rapporten per check-script — WEL
│                                # gecommit (zie §10)
└── reports/                  # Nederlandstalige Markdown-rapporten: de "wat vonden we"-laag
```

**Wat wordt gecommit**: `sparql/`, `scripts/`, `data/source/*` (externe-bronsnapshots — zie
hieronder), `output/tables/*.csv`, `output/diagrams/*.{tex,pdf,png}`, `output/reports/*.html`,
`reports/*.md`, en de gegenereerde diagram-sectie in `README.md` zelf.
**Wat wordt gitignored**: `.venv/`, `analyse/`, `data/raw/`, `data/interim/`, `data/cache/`,
`__pycache__/`. `analyse/csor_merged.ttl` is een volledige lokale samenvoeging van alle 10
CSOR-graphs — bij elke `scripts/run_all.py`-run vers opgehaald en overschreven, dus net zo
regenereerbaar als `data/raw/` en bewust niet gecommit (zie §4).

`data/source/` is anders: geen CSOR-registerdata maar externe-bronvocabularia die
`check_terminologie.py` gebruikt (zie §10-rapporttabel) — `vmm-woordenboek.ttl`/`.rdf` (SKOS-
thesaurus van VMM's publieke milieu-/waterglossarium) en `opentaal-wordlist.txt`/
`opentaal-corrections.tsv` (de officiële Nederlandse woordenlijst resp. curated
foutief->correctie-lijst van Stichting OpenTaal). Elk bestand wordt ververst door zijn eigen
`scripts/fetch_*.py`-script (`fetch_vmm_woordenboek.py`, `fetch_opentaal_wordlist.py`) —
handmatig herdraaid, bewust **niet** onderdeel van `scripts/run_all.py` (dat betreft uitsluitend
de CSOR-registerpijplijn zelf). Wél gecommit (i.t.t. `data/raw/`/`analyse/`), want het zijn
kant-en-klare, direct bruikbare brondata-snapshots, geen tussentijdse/regenereerbare CSOR-data.

## 2. Venv en dependencies

```
python3 -m venv .venv
.venv/bin/pip install --index-url https://pypi.org/simple -r requirements.txt
```

**Let op**: de globale pip-configuratie in deze omgeving wijst naar een intern Artifactory-mirror
(`artifactory-pr.lb.cumuli.be`) dat vanuit sommige sandboxes niet bereikbaar is. Gebruik in dat
geval expliciet `--index-url https://pypi.org/simple` (publieke PyPI is wel bereikbaar). Dit is
geen projectkeuze maar een omgevingsgebonden workaround — vermeld dit als het install-commando
faalt met een DNS-fout naar `artifactory-*`.

Bewust minimale dependency-set (`rdflib`, `requests`, `pandas`, `pyarrow` voor parquet, `plotly`
voor de per-check-script HTML-rapporten, zie §10) — geen tidyverse-equivalent zwaargewicht nodig
voor ~2000 rijen. `plotly` zelf breekt die ethos niet: geen Dash, geen Kaleido/orca — rendering
gebeurt clientside in de browser via een CDN-`<script>`-tag, niet ingebonden of serverside.

## 3. Vast scriptheader-formaat

Elk script in `scripts/` begint met een docstring in dit formaat (analoog aan SKILL.md §2, maar
als Python-docstring):

```python
"""
check_<naam>.py — <één-zin-samenvatting>

PURPOSE
-------
<Welke vraag beantwoordt dit script? Eén paragraaf.>

DATA PROVENANCE
----------------
Bron: <SPARQL-endpoint + graph-URI('s), of extern API>
Input: <welk(e) bestand(en) worden gelezen, hoe geproduceerd>

METHODOLOGY
-----------
<Welke checks worden uitgevoerd en waarom; wat is intern (geen externe afhankelijkheid) en
wat vergt een externe bron (PubChem)?>

INTERPRETATION
--------------
<Hoe moet de lezer de output lezen? Wat is een verwacht patroon, wat is een rode vlag?>

OUTPUTS
-------
output/tables/<naam>.csv
data/interim/<naam>.parquet (tussentijds, niet gecommit)
"""
```

Elk script eindigt met een korte samenvatting op stdout (aantallen, percentages) zodat resultaten
te verifiëren zijn zonder de CSV's te openen.

## 4. SPARQL-conventies

- Eén `.sparql`-bestand per analyse in `sparql/`, met genummerde, becommentarieerde queries
  (zie `sparql/samenstellende_variabelen_check.sparql` als referentiestijl) — dit blijft de
  **bron van waarheid** voor elke querytekst, ook al draait de uitvoering nu lokaal (zie
  hieronder).
- **Architectuur: één live fetch per run, daarna uitsluitend lokale queries.** Elke
  `scripts/check_*.py` en `scripts/generate_diagram.py` bevragen niet langer individueel de
  live endpoint. In plaats daarvan regenereert `scripts/run_all.py` bij elke run eerst
  `analyse/csor_merged.ttl` (alle 10 CSOR-graphs, samengevoegd) via
  `scripts/common/dataset.py::fetch_and_save()`, en geeft die ene `rdflib.Graph` door aan elk
  script (`main(graph)`). Elk script blijft ook standalone draaibaar (`python3
  scripts/check_x.py`) — zonder meegegeven graph haalt het dan zelf een verse snapshot op.
  Reden: sneller (één fetch i.p.v. tientallen HTTP-rondritten per run) en consistent (alle
  checks in dezelfde run zien exact dezelfde snapshot). Externe bronnen (PubChem, QUDT) blijven
  per definitie live.
- **Lokale queryuitvoering**: `sparql_client.select_dataframe_local(query, graph)` en
  `construct_local(query, graph)` voeren dezelfde SPARQL-querytekst uit tegen een reeds geladen
  `rdflib.Graph` (rdflib's eigen SPARQL-engine i.p.v. een HTTP-call) — bestaande querydefinities
  zijn dus ongewijzigd herbruikbaar. **Val op bij migratie**: een query met een expliciete
  `GRAPH <...> {...}`-clausule levert lokaal niets op, want de samengevoegde graph bewaart geen
  graph-context; zulke clausules moeten weggehaald worden (veilig zolang de betrokken klasse
  toch al 1:1 op dat ene graph afgebeeld is, wat voor alle CSOR-codelijstklassen het geval is).
- **Gedocumenteerde valkuil — geneste-subquery-aggregaten zijn lokaal onbruikbaar traag**:
  rdflib's pure-Python SPARQL-engine evalueert een geneste aggregaat (`SELECT MIN/MAX/COUNT
  WHERE { SELECT ?s (COUNT(DISTINCT ?o)...) GROUP BY ?s }`, zoals gebruikt voor kardinaliteits-
  berekeningen) extreem traag — één zo'n query mat empirisch 88 seconden op de 274.931-triple
  lokale graph. Bij tientallen tot honderden van zulke aanroepen (elke property x elke
  domein/bereik-combinatie) loopt dat op tot ver over een uur. **Verplichte aanpak voor
  kardinaliteits-/groeperingslogica op de lokale graph**: `graph.subject_objects(predicate)` +
  Python `dict`/`set`-telling — reproduceert exact dezelfde semantiek in milliseconden. Zie
  `check_conceptschemas.py::cardinalities()` en `generate_diagram.py`'s datalaag (§6) als
  referentie-implementatie. Enkelvoudige (niet-geneste) SPARQL SELECT/CONSTRUCT-queries zijn
  lokaal wél snel genoeg — dit geldt specifiek voor geneste aggregaten.
- **Gedocumenteerde valkuil — 10.000-triple CONSTRUCT-cap** (geldt voor de live fetch binnen
  `dataset.py`/`sparql_client.py`, niet meer voor de check-scripts zelf): de endpoint
  (`data-ontwikkel.omgeving.vlaanderen.be/sparql`) knipt CONSTRUCT-resultaten stil af op 10.000
  triples, zonder foutmelding. Een query die meerdere/grote graphs in één CONSTRUCT combineert
  (zoals de oorspronkelijke `sparql/csor-construct.sparql`) levert daardoor **onvolledige data**
  zonder dat dit opvalt. **Verplichte aanpak**: per graph pagineren met
  `CONSTRUCT {?s ?p ?o} WHERE { GRAPH <...> {?s ?p ?o} } LIMIT 10000 OFFSET n`, ophogen tot een
  pagina < 10.000 triples teruggeeft, en het totaal verifiëren tegen een losse `COUNT`-query.
  **Voeg geen `ORDER BY` toe** aan de gepagineerde CONSTRUCT — dat gaf een HTTP 500 op deze
  endpoint. Zie `scripts/common/sparql_client.py::fetch_graph()`, aangeroepen door
  `scripts/common/dataset.py::fetch_and_save()` voor elk van de 10 graphs.
- **Gedocumenteerde valkuil — blanke-knoop-identiteit gaat verloren over gepagineerde CONSTRUCT-
  pagina's heen.** Elke pagina van `fetch_construct()`/`fetch_graph()` wordt apart geparset
  (`g.parse(data=page, format="turtle")`) — RDF/Turtle-blanke-knoopscoping is per document, dus
  een blanke knoop (`_:xxx`) wiens samenhorende triples over twee pagina's verspreid raken,
  wordt na het samenvoegen tot TWEE losse, niet-gerelateerde blanke knopen in de lokale graph.
  Een lokale query die zo'n knoop probeert te joinen (bv. via een property path als
  `csor:heeftTerm/csor:heeftBronParameter`) breekt **stil** (0 resultaten, geen foutmelding).
  Empirisch bevestigd op `csor:ParameterTerm` (de anonieme tussenobjecten van
  `csor:ParameterAfleidingVeelterm`, in het 155.530-triple `parameter`-graph over 16 pagina's):
  lokaal 0/1279 joins i.p.v. 1279/1279 live. **Geldt niet** voor URI-getypeerde entiteiten
  (Parameter, Variabele, Eenheid, ...) — enkel voor klassen die van nature als blanke knoop
  gemodelleerd zijn. **Verplichte aanpak**: elke query die een blanke-knoop-tussenobject moet
  joinen, blijft **live** draaien (zie `scripts/check_samenstellende_variabelen.py` queries
  1c/2/3/4/5) — enkel queries die uitsluitend URI-getypeerde entiteiten raken, mogen tegen de
  lokale snapshot (§ hierboven) draaien.
- Endpoint-default: **dev-endpoint** (`https://data-ontwikkel.omgeving.vlaanderen.be/sparql`) —
  dit is een testproject; een productie-/versioned-distributie-variant is een bewust vervolgtraject,
  geen v1-scope.

## 5. Pandas-conventie

- RDF/SPARQL-resultaten worden zo snel mogelijk omgezet naar een tidy `pandas.DataFrame`
  (`scripts/common/sparql_client.py::to_dataframe`).
- Tussentijdse DataFrames → `.parquet` in `data/interim/` (gitignored, regenereerbaar).
- Finale, leesbare resultaten → `.csv` in `output/tables/` (gecommit).
- Elke CSV krijgt een "Columns:"-toelichting vlak boven de `to_csv()`-aanroep in het script:
  wat elke kolom betekent, wat een lege/NA-waarde betekent.

## 6. Diagramgeneratie

- Diagrammen van het datamodel worden **niet handmatig getekend** maar gegenereerd door een
  deterministisch script (`scripts/generate_diagram.py`) op basis van een live query op de
  graph — zelfde principe als de rest van de pijplijn: geen bron van waarheid buiten het
  register zelf.
- Formaat: **TikZ, gecompileerd naar PDF** (`pdflatex`, standalone-documentclass), met een
  PNG-preview (`pdftoppm`) voor inline weergave in `README.md` — GitHub rendert geen PDF
  inline in Markdown, wel PNG. Own addition, na een eerdere Mermaid-versie: bij relaties met
  twee tegengestelde koppelingen tussen dezelfde twee klassen (bv. Eenheid↔
  KwantificeerbaarAspect) bleek Mermaid's automatische layout minder leesbaar dan een
  expliciet gelayout TikZ-figuur met eigen bend-/routeringslogica.
- **Layout**: vaste, inhoudelijk gemotiveerde rijen (`ROWS`) i.p.v. een force-directed
  algoritme — geïnspireerd op
  `../A-Substance-Is-Not-Always-a-Substance/poster/poster/kgdiagram.py`, maar sterk
  vereenvoudigd (geen brute-force volgorde-optimalisatie, wel dezelfde geest: coördinaten
  programmatisch berekend, nooit met de hand geplaatst, en een expliciete
  overlap-validatie die hard faalt bij een layoutfout — zie `validate_layout()`).
  Randen tussen aangrenzende rijen zijn recht; een duplicaat-paar (twee relaties tussen
  dezelfde klassen) of een rand binnen dezelfde rij krijgt `bend left`/`bend right`; de ene
  rand die meerdere rijen overslaat wordt expliciet via de linkermarge geroute (drie rechte
  segmenten) zodat ze nooit door een tussenliggende rij snijdt.
- **Determinisme**: klassen en relaties worden vóór het renderen expliciet gesorteerd (nooit
  op Python-dict/set-iteratievolgorde of SPARQL-resultaatvolgorde vertrouwen) — een
  ongewijzigde graph geeft altijd een byte-identiek `.tex`-bestand. Geverifieerd door het
  script twee keer te draaien en de `.tex`-output te diffen (de PDF zelf kan
  compiler-metadata zoals een tijdstempel bevatten — dat is `pdflatex`-gedrag, geen
  non-determinisme in de gegenereerde inhoud).
- Vereist `pdflatex` en `pdftoppm` (TeX Live resp. poppler-utils) in `PATH` — beide al
  aanwezig in deze omgeving; geen extra dependency in `requirements.txt` nodig (geen
  Python-package).
- Output: `output/diagrams/<naam>.{tex,pdf,png}` (alle drie gecommit — `.tex` is de bron,
  `.pdf`/`.png` zijn afgeleid maar bewust wel gecommit zodat het diagram zichtbaar is zonder
  zelf te compileren) én, voor het hoofddiagram, automatisch geïnjecteerd in `README.md`
  tussen de markers `<!-- CSOR-DIAGRAM:START -->` / `<!-- CSOR-DIAGRAM:END -->` — nooit
  handmatig tussen die markers bewerken, dat wordt bij de volgende run overschreven.
- Kardinaliteit wordt afgeleid uit dezelfde forward-/backward-tellingen als
  `check_conceptschemas.py::cardinalities()`, maar dan geschaald per domeinklasse (zie
  `generate_diagram.py::cardinality()`) — nodig omdat een aantal properties meerdere
  domeinklassen heeft (bv. `heeftNatuurkundigeDimensie` op zowel Eenheid als
  KwantificeerbaarAspect) en een niet-geschaalde telling die verschillen zou samenklappen.
  Weergegeven als `(kant-A, kant-B)` tekst (bv. `(0..N, 1)`), niet als crow's-foot-symbolen —
  leesbaar zonder ER-notatiekennis.
- Zie ook §10 (Rapportgeneratie) voor de analoge aanpak bij de per-check-script Plotly-HTML-
  rapporten — zelfde principe (gegenereerd, niet handmatig), ander formaat en andere scope (per
  check-script i.p.v. één centraal diagram).

## 7. PubChem-etiquette

- Alle PubChem PUG-REST-calls gaan via `scripts/common/pubchem.py`, dat **altijd eerst** de
  cache (`data/cache/pubchem/{by_cid,by_cas,by_name}/<key>.json`) checkt.
- `time.sleep(0.2)` tussen live calls; geen sleep bij cache-hit.
- Geen bulk-hercalls zonder cache-check — een tweede run met gevulde cache mag nul live calls
  doen (zie verificatiecriteria in het plan).

## 8. Rapportconventie

- Nederlandstalig, in `reports/`.
- Structuur: **Aanleiding** → **Methodologie** → **Resultaten per toets** → **Aanbevelingen**
  (zie `reports/rapport_samenstellende_variabelen.md` als referentie).
- Concrete bevindingen citeren specifieke notaties (bv. `V_1533`), niet enkel aggregaten.
- Een expliciete paragraaf "buiten scope" voor bewust uitgestelde checks (bv. ChEBI-crosscheck,
  EC/EEA-consistentie) in plaats van deze stilzwijgend weg te laten.

## 9. Iteratieve verificatiechecklist

Voor een check als voltooid wordt beschouwd:

- [ ] Scriptheader bevat PURPOSE, DATA PROVENANCE, METHODOLOGY, INTERPRETATION, OUTPUTS.
- [ ] Paginatie-fetch geverifieerd tegen een onafhankelijke `COUNT`-query.
- [ ] Een bekend record (self-test) wordt correct geparsed vóór de volledige batch draait.
- [ ] Elke output-CSV heeft een "Columns:"-toelichting.
- [ ] Het script draait end-to-end zonder errors vanuit een schone venv.
- [ ] Een tweede run met gevulde cache doet nul live externe calls en geeft identieke output.
- [ ] De stdout-samenvatting is inhoudelijk plausibel (aantallen kloppen met eerdere/verwachte
      cijfers).
- [ ] Het check-script genereert een geldig HTML-rapport (`output/reports/<naam>.html`) met
      minstens 1 figuur en een niet-lege bespreking per sectie.

## 10. Rapportgeneratie (Plotly/HTML)

Naast de CSV's in `output/tables/` genereert elk `scripts/check_*.py`-script, aan het einde van
zijn eigen `main()`, één zelfstandig HTML-rapport (`output/reports/<naam>.html`) met Plotly-
figuren en een korte, data-gedreven "bespreking" per sectie — zodat resultaten visueel en
tekstueel te scannen zijn zonder de CSV's te moeten openen. Dit is een aanvulling op, geen
vervanging van, de bestaande handgeschreven Nederlandstalige rapporten in `reports/` — die
bevatten beleidsmatige duiding (Aanleiding/Advies/Conclusies) die niet uit de data zelf valt af
te leiden en blijven ongewijzigd.

- **Per script, niet centraal.** In tegenstelling tot `generate_diagram.py` (§6, één gedeeld
  diagram, enkel aangeroepen vanuit `run_all.py`) genereert elk check-script zijn eigen rapport
  zelf, binnen zijn eigen `main()` — dit werkt zowel standalone (`python3 scripts/check_x.py`)
  als via `scripts/run_all.py`, consistent met hoe elk script nu al zelf zijn CSV's wegschrijft.
- **Gedeelde opbouwlogica**: `scripts/common/report.py` — geen templating-engine, een
  handgebouwde HTML-string, in dezelfde geest als hoe `generate_diagram.py` zijn TikZ-string
  handbouwt. Biedt een `Section`-dataclass (kop, bespreking, figuren, optionele tabel) en
  `build_report()`.
- **Plotly.js via CDN**, éénmaal per pagina (`include_plotlyjs="cdn"` op het eerste figuur,
  `False` op de rest) — klein gecommit bestand; vereist internet bij bekijken, niet bij
  genereren.
- **Kleurregel**: één meetwaarde verdeeld over categorieën (bv. "aantal per flag_type") krijgt
  één vlakke kleur (geen legende — de x-as-labels dragen de identiteit al). Twee of meer
  meetwaarden naast elkaar per categorie (bv. "totaal" vs "metScheme" per klasse) krijgen een
  vaste, hardgecodeerde kleurenkaart, mét legende. Bewust geen taartdiagrammen. Kleurwaarden
  zijn verbatim overgenomen uit het gevalideerde categorische referentiepalet van de
  `dataviz`-skill (light mode, `scripts/common/report.py::PALETTE`).
- **Bespreking is data-gedreven**: tellingen/percentages/top-N, qua interpretatiekader
  identiek aan de bestaande `INTERPRETATION`-alinea van elk scriptheader (§3), maar als
  template die elke run herevalueert — geen vrije narratieve synthese.
- **Geen determinisme-garantie** (in tegenstelling tot §6's `.tex`-determinisme): Plotly's
  `fig.to_html()` genereert per aanroep een uniek div-id, dus twee identieke runs geven geen
  byte-identieke HTML. Niet vereist voor dit rapporttype.
- Vereist `plotly` in `requirements.txt` (§2), geen andere nieuwe dependency.

De zes gegenereerde rapporten (bestandsnaam = scriptnaam zonder `check_`-prefix):

| Rapport | Gegenereerd door |
|---|---|
| `output/reports/conceptschemas.html` | `scripts/check_conceptschemas.py` |
| `output/reports/eenheden_qudt.html` | `scripts/check_eenheden_qudt.py` |
| `output/reports/parameter_inhoud.html` | `scripts/check_parameter_inhoud.py` |
| `output/reports/samenstellende_variabelen.html` | `scripts/check_samenstellende_variabelen.py` |
| `output/reports/variabele_identity.html` | `scripts/check_variabele_identity.py` |
| `output/reports/terminologie.html` | `scripts/check_terminologie.py` |
