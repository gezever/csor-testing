# Inhoudelijke consistentiechecks op Parameter en ParameterAspect

**Steekproef per klasse-type: wat blijkt er als je de inhoud van de velden zelf toetst, niet
enkel de structuur?**

*Datum: 30 juli 2026*

---

## 1. Aanleiding en vraagstelling

De eerdere rapporten toetsten *structurele* datakwaliteit: conceptschema-volledigheid,
kardinaliteit, QUDT-koppeling. Naar aanleiding van een diepgaande handmatige analyse van één
record (`KWA_72`, een `csor:KwantificeerbaarAspect` — "vracht tin per tijd") is dezelfde soort
steekproef getrokken op elk klasse-type: een volledige predicaat-inventaris plus 3 volledige
voorbeeldrecords voor de zeven CSOR-"codelijst"-klassen die nog niet eerder diepgaand bekeken
waren (`Parameter`, `ParameterAspect`, `Drager`, `KwalificeerbaarAspect`,
`NatuurkundigeDimensie`, `SoortWaardebepaling`, `Resultaattype`). Doel: niet enkel structuur
maar de **inhoud** van de velden zelf toetsen.

## 2. Methodologie

Om elke hypothese die uit een steekproef van 3 records ontstond te toetsen op de **volledige
populatie**, is het volledige register lokaal samengevoegd (alle 10 CSOR-graphs, 274.931
triples, elk gepagineerd opgehaald en geverifieerd tegen een onafhankelijke `COUNT`-query —
zelfde methode als `scripts/common/sparql_client.py::fetch_graph`). Wat tijdens deze verkenning
begon als een eenmalig hulpmiddel is nadien de standaardarchitectuur van de hele pijplijn
geworden: `scripts/run_all.py` regenereert deze snapshot (`analyse/csor_merged.ttl`) bij elke
run via `scripts/common/dataset.py::fetch_and_save()`, en alle vijf checks — inclusief deze —
draaien hun queries lokaal daartegen (`sparql_client.select_dataframe_local()`) in plaats van
elk apart de live endpoint te bevragen. Zie CLAUDE.md §4.

## 3. Resultaten per klasse

### 3.1 Parameter (4890) — het meest inhoudsrijke klasse-type

Nieuw ontdekte velden t.o.v. wat eerder gedocumenteerd was: `skos:altLabel`,
`csor:verkorteNotatie` (beide altijd aanwezig), `csor:saroadCode` (793/4890 — een externe
SAROAD-luchtkwaliteitscode, niet verder onderzocht), `csor:geldigTot`/`dcterms:valid`
(25/4890 — vervaldatum), en — opvallend — `csor:eea` (10/4890) en `csor:cas` (4/4890) blijken
**ook op Parameter-niveau** voor te komen, niet enkel op Variabele-niveau.

**`skos:altLabel` vs. `csor:verkorteNotatie`** (alle 4890 getoetst): **0 verschillen**. Schone
basislijn — deze twee velden lijken redundant maar zijn register-breed identiek.

**`csor:geldigTot` vs. `owl:deprecated`** (de 25 parameters met een vervaldatum): **0**
gevallen waar de datum al voorbij is terwijl de parameter nog actief staat. Schone basislijn,
maar wel een regel die met het verstrijken van de tijd kan gaan falen — vandaar opgenomen als
doorlopende check, niet als eenmalige toets.

**Parameter-niveau `cas` vs. de `cas` van de gekoppelde Variabele** — een concrete
verrijkingskans, geen fout: **4 parameters** hebben een eigen CAS-nummer
(`output/tables/parameter_cas_verrijking.csv`):

| Parameter | Label | CAS | Variabele |
|---|---|---|---|
| P_2650 | Koolstof elementair in lucht | 7440-44-0 | V_47 |
| P_2651 | Koolstof elementair in PM10 | 7440-44-0 | V_47 |
| P_2652 | Koolstof elementair in PM2.5 | 7440-44-0 | V_47 |
| P_3070 | Koolstof totaal in lucht | 7440-44-0 | V_47 |

In alle 4 gevallen (dezelfde Variabele, `V_47` "Koolstof") heeft die Variabele **geen**
CAS-nummer — dit kan rechtstreeks doorgezet worden.

**Parameter-niveau `eea` vs. Variabele-niveau `eea`** (10 parameters hebben er een,
overlappend met hun Variabele): **8 van de 10 paren verschillen**
(`output/tables/parameter_eea_mismatch.csv`), slechts 2 komen overeen. Niet per se een fout —
Parameter en Variabele kunnen legitiem een andere rol/fractie beschrijven (bv. "Zuurstof
verzadiging" als meting vs. de onderliggende stof) — maar wel vermeldenswaard en het verdient
handmatige review, dezelfde terughoudendheid als bij eerdere mismatch-bevindingen in dit
project.

### 3.2 Correctie op een eerdere aanname: `csor:eea` is de EEA-code, geen EC/EINECS-nummer

Bij nazicht van de property-definitie zelf (`rdfs:label "EEA-code"`, `rdfs:comment "EEA-code
gekoppeld aan de parameter"`) blijkt `csor:eea` de **EEA-code** (European Environment Agency)
te zijn — **niet** het EC/EINECS-nummer, zoals in een eerder rapport verondersteld op basis
van één toevallig EC-conform voorbeeld (`V_1`: `"204-079-4"`). Een formatcheck op basis van
het (foutieve) EC-patroon `XXX-XXX-X` gaf 56/176 "afwijkingen" die grotendeels vals waren. De
correcte, generieke toets — drie cijfergroepen van willekeurige lengte, gescheiden door een
koppelteken (`\d+-\d+-\d+`) — geeft een veel schonere en correcte uitkomst: **174/176
conform, precies 2 échte afwijkingen**:

- **`P_618`** ("Koolstof organisch opgelost in water"): EEA-code `"EEA_3133-05-9"` — de
  veldnaam zelf staat per ongeluk in de waarde. Vergelijk met het zustertweetal `P_619`/`P_620`
  (correct `"3133-06-0"`) en met de eigen Variabele (`"3133-05-9"`) — het correcte EEA-code
  voor `P_618` is vermoedelijk gewoon `"3133-05-9"`, zonder het `EEA_`-voorvoegsel.
- **`V_403`**: EEA-code `"200- 024-3"` — een storend spatie-teken na het eerste koppelteken
  (hoort `"200-024-3"` te zijn).

### 3.3 ParameterAspect (8547) — het label volledig ontrafeld en op de volle populatie bevestigd

Enige eigen velden: `heeftParameter`, `heeftAspect` (beide al bekend) en `geldigTot` (10×).
Door de samenstellende delen van twee voorbeelden (`PAS_5307`, `PAS_5311`) stuk voor stuk op
te zoeken, bleek het `skos:prefLabel` een **exact, herleidbaar patroon** te volgen:

```
ParameterAspect.prefLabel =
  "{Parameter.symbool} ({SoortWaardebepaling.prefLabel} in {Drager.prefLabel}): {KwantificeerbaarAspect.prefLabel}"
```

Bv. `PAS_5307`: `Parameter=P_1394` (symbool `"TCPP"`, drager `"water"`, soortwaardebepaling
`SWB_1`="standaard"), `heeftAspect=KWA_5`="vracht" → *"TCPP (standaard in water): vracht"* —
klopt exact.

**Op de volledige populatie getoetst**: alle 8537 actieve `ParameterAspect`-instanties
gereconstrueerd uit hun 4 samenstellende delen en vergeleken met het opgeslagen
`skos:prefLabel` — **0 mismatches**. Het label-generatieproces is register-breed 100%
consistent. Waardevol als **regressiebewaking**: een toekomstige mismatch zou wijzen op een
verouderd label na een latere hernoeming van de gekoppelde parameter, soortwaardebepaling,
drager of aspect zonder herberekening van het `ParameterAspect`-label.

### 3.4 KwalificeerbaarAspect (3) — informele waardenopsomming (observatie, geen check)

`skos:definition` bevat een informele, met `|` gescheiden opsomming van geldige kwalitatieve
waarden (bv. *"Migratie Handhaving - Niet bepaalbaar | Aanwezig | Afwezig"*) — geen formele
SKOS-enumeratie. Bij slechts 3 instanties te klein voor een zinvolle geautomatiseerde check,
maar het vermelden waard als modelleerobservatie: deze waarden zijn niet machineleesbaar
vastgelegd.

### 3.5 Een hypothese getoetst en verworpen: SoortWaardebepaling

Op de eerste steekproef van 3 (*"Eluaat LS10"* → *"ELUAAT-LS10"*, *"Eluaat LS2"* →
*"ELUAAT-LS2"*, *"Eluaat LS0.5"* → *"ELUAAT-LS0.5"*) leek `csor:symbool` een kanonieke
transformatie van `skos:prefLabel` (spaties → koppeltekens, hoofdletters). **Op de volledige
populatie van 80 getoetst bleek dat fout**: 67/80 "afwijkingen" — maar het zijn geen fouten.
`symbool` is een **handmatige afkorting**, geen deterministische afleiding: *"kiem-inhibitie"*
→ `"KI"`, *"EC50 (24h)"* → `"24EC"`, *"organisch niet purgeerbaar"* → `"NPO"`. De steekproef
van 3 bevatte toevallig enkel labels waar geen afkorting nodig was. **Geen check gebouwd** op
basis van dit patroon — een concreet voorbeeld waarom een op een kleine steekproef gebaseerd
patroon eerst op de volle populatie getoetst moet worden vóór implementatie.

### 3.6 NatuurkundigeDimensie, Resultaattype, Drager — geen nieuwe bevindingen

`NatuurkundigeDimensie`-symbolen (bv. `m.t(-1)` voor "massa per tijd") volgen een leesbare
exponentnotatie die in de steekproef consistent leek met het label, maar dit is bij slechts 49
records en zonder de SoortWaardebepaling-les uit §3.5 niet zonder volledige-populatietoets te
vertrouwen — **buiten scope v1**. `Resultaattype` en `Drager` hebben geen eigen inhoudelijke
velden buiten wat al bekend was (`Drager`'s ongebruikte `DR_4` is al gedekt door
`check_conceptschemas.py`).

## 4. Aanbevelingen

1. **Zet de 4 CAS-nummers door** van Parameter naar Variabele (V_47 "Koolstof").
2. **Corrigeer de 2 bevestigde EEA-code-fouten**: `P_618` (verwijder het `EEA_`-voorvoegsel)
   en `V_403` (verwijder de storende spatie).
3. **Review de 8 Parameter-vs-Variabele-EEA-mismatches** handmatig — mogelijk legitiem
   (andere rol/fractie), maar niet zonder nazicht aan te nemen.
4. **Werk eerdere documentatie bij** die `csor:eea` als EC/EINECS-nummer omschreef — het is de
   EEA-code.
5. Overweeg voor de registerbeheerders: **formaliseer de KwalificeerbaarAspect-waardenlijsten**
   (§3.4) als machineleesbare SKOS-enumeratie in plaats van vrije tekst.
6. Geen actie nodig voor `altLabel`/`verkorteNotatie`, `geldigTot`/`deprecated` en de
   ParameterAspect-labelconsistentie — alle drie schoon op de volledige populatie; wel
   waardevol als doorlopende regressiebewaking.

## 5. Buiten scope

- `NatuurkundigeDimensie`-symbool-label-consistentie (§3.6) — niet getoetst op de volledige
  populatie, dus geen check gebouwd.
- `csor:saroadCode`-formatvalidatie — nieuw ontdekt veld (793/4890 parameters), nog niet
  onderzocht.
- Automatische terugschrijving van de CAS-verrijking of EEA-correcties — dit rapport levert
  enkel bevindingen en suggesties aan, geen schrijfacties naar het register.

---

*Bijlage: `../sparql/parameter_inhoud_checks.sparql`. Herproduceerbaar via
`python3 scripts/check_parameter_inhoud.py` (zie `../CLAUDE.md` voor venv-opzet). Volledige
resultaten in `../output/tables/parameter_inhoud_vlaggen.csv`,
`../output/tables/parameter_cas_verrijking.csv` en
`../output/tables/parameter_eea_mismatch.csv`.*
