# Consistentie en duidelijkheid van class- en property-definities in de csor-namespace

**Datakwaliteitstoets: `rdfs:label`, `rdfs:comment` en URI-conventies van de eigen CSOR-ontologie,
met een verkenning van hergebruik van externe vocabularia**

*Datum: 3 augustus 2026*

---

## 1. Aanleiding en vraagstelling

Naast de instantiedata (parameters, variabelen, eenheden, ...) definieert het CSO-register ook
zijn eigen vocabulaire: 17 `rdfs:Class`- en 37 `rdf:Property`-declaraties in de `csor:`-namespace
(`https://data.omgeving.vlaanderen.be/ns/csor#`), elk voorzien van een `rdfs:label` en (op één
uitzondering na) een `rdfs:comment`. Deze declaraties zijn zelf nog niet aan een datakwaliteitstoets
onderworpen — bestaande checks raken er wel aan (`check_conceptschemas.py` haalt prop/label/
domain/range op in `output/tables/csor_relaties.csv`) maar zonder `rdfs:comment`, en classes worden
nergens opgehaald.

Drie vragen stonden centraal:

1. Is het `rdfs:label` consistent met de URI-lokale naam, en met de `rdfs:comment`?
2. Is de `rdfs:comment` inhoudelijk correct en voldoende duidelijk?
3. Zijn eigen properties/classes nodig voor elk concept, of bestaan er al gevestigde externe
   vocabularia (bv. DBpedia, OBO Foundry) die hergebruikt hadden kunnen worden?

## 2. Methodologie

Dit is, in tegenstelling tot de overige rapporten in `reports/`, **geen geautomatiseerde,
herhaalbare check** via een `scripts/check_*.py`-script — er is bewust voor gekozen dit als
eenmalige, kwalitatieve review op te leveren (zie §5, "Buiten scope"). De 17 class- en 37
property-declaraties zijn rechtstreeks gelezen uit `analyse/csor_merged.ttl` (de lokale
samenvoeging van alle CSOR-graphs — de ontologiedeclaraties zelf blijken te leven in het
`drager`-graph, regels 82-176 voor classes en 90027-90284 voor properties).

Voor vraag 3 zijn drie externe bronnen rechtstreeks bevraagd (niet enkel via zoekresultaat-
samenvattingen — zie de kanttekening hieronder):

- **DBpedia-ontologie**: elke kandidaat-term rechtstreeks opgevraagd op zijn ontologie-URI
  (`https://dbpedia.org/ontology/<term>`) om type, label, comment en domain/range te bevestigen.
- **OBO Foundry / EBI OLS** (Ontology Lookup Service): het registratiebestand
  `registry/ontologies.ttl` doorzocht op chemie- en meetgerelateerde ontologieën, met
  vervolgopzoekingen via de OLS-API (een gestructureerde databron) om specifieke termen te
  bevestigen.
- **Het zusterproject** `A-Substance-Is-Not-Always-a-Substance` (`data/source/chebi/chebi.ttl` en
  `data/processed/rdf/substances.ttl`) — dezelfde `data.omgeving.vlaanderen.be`-organisatie,
  dus een direct vergelijkbaar precedent i.p.v. een abstract extern voorbeeld.

**Methodologische kanttekening**: een eerste doorzoeking via WebSearch suggereerde dat
`dbo:InChIKey` zou bestaan bij DBpedia. Rechtstreekse bevraging van de ontologie-URI zelf
(`https://dbpedia.org/ontology/inchikey`) gaf een HTTP 404 — de term bestaat niet. Alle
hieronder vermelde externe-vocabulaire-claims zijn nadien stuk voor stuk herbevestigd tegen de
primaire bron (ontologie-URI, OLS-API of een lokaal bestand), niet tegen een zoekresultaat-
samenvatting.

## 3. Resultaten per toets

### 3.1 Classes: labels zijn 1:1 gelijk aan de URI, comments wisselen sterk in kwaliteit

Alle 17 class-labels zijn letterlijk gelijk aan de URI-lokale naam (bv. `ns1:KwalificeerbaarAspect`
→ label `"KwalificeerbaarAspect"`) — 100% consistent, maar geen mensleesbare Nederlandse term,
in tegenstelling tot de meeste property-labels (zie §3.2).

Een cluster afleidingsgerelateerde classes heeft dunne, circulaire comments die vooral de naam
herformuleren zonder echt te verklaren:

| Class | Comment |
|---|---|
| `ParameterAfleidingRWZIRendement` | "Een afleiding van een parameter op basis van RWZI-rendement." |
| `ParameterAfleidingVeelterm` | "Een afleiding van een parameter via een veelterm." |
| `ParameterTerm` | "Een term binnen afleidingen van een parameter." |

**Concreet label/comment-mismatch**: `VeeltermParameterTerm`'s comment ("Een veelterm is een
optelling van meerdere termen. Niet elke term is verplicht om de optelling te mogen maken.")
beschrijft het begrip "veelterm" in het algemeen, niet de klasse zelf — die is een *term binnen*
een veelterm, geen veelterm. Een lezer die enkel de comment leest, begrijpt niet wat deze klasse
specifiek modelleert.

**Grammaticafout**: `OrganisatieSpecifiekeReferentie` — "Een referentie naar een concept **die**
specifiek is voor een bepaalde organisatie." — moet "**dat**" zijn (het concept is onzijdig).

### 3.2 Properties: het `heeft`-voorzetsel volgt geen voorspelbare regel

Van de 19 `heeft*`-URI's krijgt slechts 7 een label met "heeft"/"Heeft" (`heeftAspect`→"Heeft
aspect", `heeftBronParameter`→"heeft bronparameter"); de overige 12 krijgen een kale
naamwoord-label zonder werkwoord (`heeftDrager`→"Drager", `heeftTerm`→"Term",
`heeftNoemer`→"noemer"). Binnen de "heeft"-groep zelf wisselt bovendien de hoofdletter
willekeurig ("heeft afleiding" vs. "Heeft aspect").

Het Bron/Doel-paar wordt bovendien **inconsistent vertaald tussen properties van hetzelfde
patroon**:

| Property | Label |
|---|---|
| `heeftBronParameter` / `heeftDoelParameter` | "heeft bronparameter" / "heeft doelparameter" (bron/doel behouden) |
| `heeftBronEenheid` / `heeftDoelEenheid` | "Eenheid van" / "Eenheid naar" (bron/doel verdwijnt) |
| `heeftBronParameterAspect` / `heeftDoelParameterAspect` | "Parameteraspect van" / "Parameteraspect naar" |

Drie labels (`inchikey`, `iupacNaam`, `verplicht`) zijn daarnaast gewoon de camelCase-identifier
hergebruikt als label, geen Nederlandse term — inconsistent met bv. `Omkeerbaar`,
`Conversiefactor`.

### 3.3 Comments: sterk wisselend detailniveau, en één inhoudelijke fout

`cas`, `eea`, `eionetDD` en `saroadCode` krijgen elk enkel het sjabloon *"X-code gekoppeld aan de
parameter"* — geen uitleg wat de code betekent of vandaan komt. `geldigTot`'s comment ("Is geldig
tot.") herhaalt gewoon het label zonder iets toe te voegen. `heeftAfleiding` heeft als enige
property **helemaal geen** `rdfs:comment`.

**Inhoudelijke fout**: de comment bij `inchikey` luidt *"De International Chemical Identifier,
afgekort InChI, is een tekstuele identificatiecode voor chemische stoffen..."* — dat beschrijft
**InChI**, niet **InChIKey**. InChIKey is een gehashte, vaste-lengte (25 tekens) afgeleide van de
volledige InChI-string, specifiek bedoeld om snel te zoeken/indexeren in databanken — het
praktische voordeel t.o.v. de volledige InChI-string, die te lang is als sleutel. Dat dit
onderscheid ertoe doet, bevestigt ook de externe ChEBI-ontologie (via `chemrof:`, zie het
zusterproject `A-Substance-Is-Not-Always-a-Substance/data/source/chebi/chebi.ttl`, regels
~11294186-11294189): die houdt `inchi_string` en `inchi_key_string` bewust als twee losse
annotation properties uit elkaar. De property `ns1:inchikey` is duidelijk bedoeld als InChIKey,
maar de bijhorende uitleg beschrijft het verwante maar andere concept.

**Open modelleringsvraag** (geen vastgestelde fout): `uitgedruktIn` ("Uitgedrukt in") heeft als
`rdfs:range` de klasse `ns1:Variabele`, niet `ns1:Eenheid`. Label en comment ("De variabele
waarin het resultaat uitgedrukt wordt.") zijn intern consistent, maar dit wijkt af van de
intuïtie dat "uitgedrukt in" naar een eenheid zou verwijzen. Voorleggen aan de domeinexpert, niet
als fout corrigeren.

### 3.4 Taal-/grammaticafouten

- `factor`: *"...die de grootte of schaal van **een de** term bepaalt..."* — dubbel lidwoord.
- `verplicht`: *"**Duid** aan welke term verplicht is..."* — moet "**Duidt** aan" zijn (3e
  persoon enkelvoud tegenwoordige tijd).
- `verkorteNotatie`: *"Samengestelde **omschrijving** van de variabele **omschrijving** en
  soortwaardebepaling **omschrijving**..."* — drievoudige herhaling van "omschrijving", moeilijk
  leesbaar.

### 3.5 Hergebruik vs. zelf-minten: bestaan er al externe alternatieven?

Voor generieke, elders al gestandaardiseerde chemische-identifier-concepten definieert csor eigen
properties. Elk van onderstaande is rechtstreeks bij de bron geverifieerd (zie §2):

| csor-property | Extern alternatief | Bevinding |
|---|---|---|
| `cas` | DBpedia-ontologie `dbo:casNumber` | **Bevestigd**: `owl:DatatypeProperty`, label "CAS number", comment "Chemical Abstracts Service number. Applicable to ChemicalCompound or Biomolecule", range `xsd:string`. Sterk, goed gedocumenteerd alternatief. |
| `eea` (empirisch het EC/EINECS-nummer, zie `check_variabele_identity.py::eea_ec_crosscheck`) | DBpedia-ontologie `dbo:ecNumber` | **Bevestigd**: `owl:DatatypeProperty`, label "EC number", range `xsd:string`, maar domain is `dbo:Biomolecule` (smaller dan een algemene stof) en geen `rdfs:comment`. Bruikbaar, niet perfecte domain-fit. |
| `iupacNaam` | DBpedia-ontologie `dbo:iupacName` | **Bevestigd**: `owl:DatatypeProperty`, label "IUPAC name", maar domain is `dbo:Drug` (niet algemeen) en range `rdf:langString`. Bruikbaar, niet perfecte domain-fit. |
| `inchikey` | — | **Geen gecureerd DBpedia-alternatief**: `dbo:inchikey`/`dbo:InChIKey` bestaat niet (404, rechtstreeks geverifieerd). Enkel `dbp:inchikey` bestaat — de ongecureerde infobox-extractie-namespace: kaal `rdfs:label`, geen `owl:DatatypeProperty`-typering, geen comment, geen domain/range. Wél een gecureerd alternatief bij **OBO Foundry/CHEMINF**: `CHEMINF:000059` "InChIKey" (bevestigd via EBI OLS). Belangrijke nuance: CHEMINF modelleert dit als een *class* (informatie-content-entiteit, gekoppeld via een `is_about`-objectproperty), niet als een simpele datatype-property zoals csor's huidige `csor:inchikey "waarde"` — reuse hier is dus geen 1-op-1 vervanging maar een architecturale keuze. |
| `eionetDD`, `saroadCode` | — | Geen extern alternatief gevonden — EU/Vlaamse regelgevings- en meetnetcodes, geen generiek chemisch concept. Eigen property hier verdedigbaar. |

**Eigen precedent binnen dezelfde organisatie**: `A-Substance-Is-Not-Always-a-Substance` — ook
onder `data.omgeving.vlaanderen.be` — gebruikt in `data/processed/rdf/substances.ttl` vandaag al
rechtstreeks `dbo:casNumber` (22.535×), `dbo:ecNumber` (27.272×) en `dbp:inchikey` (17.523×),
zonder een eigen property te minten voor deze drie concepten. Dit is geen abstracte "best
practice elders", maar een zusterproject binnen dezelfde organisatie dat voor exact dezelfde drie
concepten al voor hergebruik koos (met de kanttekening dat het de losser-getypeerde
`dbp:inchikey` gebruikt, niet een gecureerd alternatief — dat bestaat voor InChIKey dan ook niet
bij DBpedia, wel bij CHEMINF, zie boven).

**Stijlvraag `heeft`-voorzetsel**: onafhankelijk van de externe-vocabulaire-vraag is er ook een
interne stijlinconsistentie (§3.2) rond het "heeft"-voorzetsel. Gevestigde vocabularia vermijden
dit doorgaans (FOAF `knows`, Dublin Core `creator`, DBpedia `author` — geen "has"-voorzetsel,
want de property drukt de relatie al uit). Csor's eigen labels vertonen dit instinct al half
(12/19 laten "heeft" weg in het label, maar behouden het in de URI) — een aanwijzing dat dit
structureel opgelost kan worden, niet enkel per geval.

## 4. Aanbevelingen

1. **Corrigeer de `inchikey`-comment** (§3.3) — enige echte inhoudelijke fout in dit onderzoek:
   herschrijf naar een definitie van InChIKey specifiek (gehashte, vaste-lengte afgeleide van
   InChI), niet van InChI zelf.
2. **Vul de ontbrekende comment aan bij `heeftAfleiding`** — enige property zonder `rdfs:comment`.
3. **Herschrijf de dunne/circulaire comments**: `cas`/`eea`/`eionetDD`/`saroadCode` (leg uit wat
   de code betekent en wie ze uitgeeft) en `geldigTot` (leg uit wat ongeldig worden concreet
   betekent voor de betrokken klasse, niet enkel het label herhalen).
4. **Herstel de taalfouten** uit §3.4 (`OrganisatieSpecifiekeReferentie`, `factor`, `verplicht`,
   `verkorteNotatie`).
5. **Standaardiseer het `heeft`-voorzetsel** in property-URI's én -labels — kies één conventie
   (bv. altijd weglaten, consistent met FOAF/Dublin Core/DBpedia-praktijk, zie §3.5) en pas ze
   overal toe, inclusief het Bron/Doel-paar (nu inconsistent vertaald als "bron/doel" vs.
   "van/naar").
6. **Leg de hergebruik-vraag (§3.5) voor aan de CSOR-modeleigenaar** als open architecturale
   vraag, niet als verplichte wijziging: overweeg `dbo:casNumber`/`dbo:ecNumber`/`dbo:iupacName`
   voor `cas`/`eea`/`iupacNaam` (met de domain-kanttekening), en CHEMINF `CHEMINF:000059` als
   referentiepunt voor `inchikey` (met de architecturale kanttekening over reïficatie). Wijs op
   het precedent binnen het eigen zusterproject.
7. **Bevestig de `uitgedruktIn`-range** (`ns1:Variabele` i.p.v. het intuïtieve `ns1:Eenheid`,
   §3.3) met de domeinexpert.

## 5. Buiten scope (v1)

Bewust niet meegenomen in deze eerste versie, als vervolgtraject:

- **Geen geautomatiseerd, herhaalbaar check-script** (`scripts/check_*.py`) gebouwd voor deze
  review — in tegenstelling tot de overige rapporten in dit project is dit een eenmalige,
  kwalitatieve lezing. Een vervolgstap zou een `check_ontologie_definities.py` kunnen zijn dat
  label/URI/comment-heuristieken (lengte, "heeft"-detectie, camelCase-als-label-detectie)
  automatisch herberekent bij elke registerwijziging, per de conventie in `CLAUDE.md` §3/§9/§10.
- **Geen volledige semantische audit** van alle 37 properties' en 17 classes' `rdfs:domain`/
  `rdfs:range`-correctheid — enkel wat tijdens deze label/comment-lezing opviel (`uitgedruktIn`)
  is vermeld.
- **Geen architecturale herevaluatie richting een gereïficeerd descriptor-patroon** (zoals
  ChEBI/CHEMINF hanteren voor InChIKey/IUPAC-naam via `hasSynonymType`/`is_about`) — enkel als
  observatie vermeld in §3.5, niet uitgewerkt als concreet voorstel.
- **Geen bredere vergelijking met eenheden-/metingontologieën** (UO, CMO, XCO uit het OBO
  Foundry-register) — csor gebruikt voor eenheden al QUDT (`check_eenheden_qudt.py`), dus geen
  onmiddellijke vervangingsvraag daar.

---

*Bijlage: alle geciteerde class-/property-triples zijn rechtstreeks gelezen uit
`../analyse/csor_merged.ttl` (regels 82-176 voor classes, 90027-90284 voor properties — dit
bestand wordt bij elke `scripts/run_all.py`-run vers geregenereerd en is niet gecommit, zie
`../CLAUDE.md` §1/§4). Externe-vocabulaire-referenties: DBpedia-ontologie
(`https://dbpedia.org/ontology/{casNumber,ecNumber,iupacName,inchikey}`), EBI OLS
(`https://www.ebi.ac.uk/ols4/`) voor CHEMINF:000059, en
`../../A-Substance-Is-Not-Always-a-Substance/data/source/chebi/chebi.ttl` /
`.../data/processed/rdf/substances.ttl` voor het zusterproject-precedent.*
