# Conceptschema-structuur, volledigheid en QUDT-koppeling in het CSO-register

**Hoe verhouden de elementen in de CSOR-conceptschema's zich tot elkaar, behoort ieder
element tot een conceptschema, en hoe goed zijn de eenheden aan QUDT gekoppeld?**

*Datum: 30 juli 2026*

---

## 1. Aanleiding en vraagstelling

Na de eerdere datakwaliteitstoetsen op compositierelaties
(`reports/rapport_samenstellende_variabelen.md`) en chemische identiteit
(`reports/rapport_variabele_identiteit.md`) is de structuur van het CSOR-datamodel zelf
onderzocht: welke conceptschema's bestaan er, hoe hangen hun klassen samen, is elk element
lid van een conceptschema, wat zijn de kardinaliteiten van de onderlinge relaties, en — voor
`csor:Eenheid` specifiek — in welke mate en met welke kwaliteit is er een koppeling naar de
externe QUDT-eenhedenontologie?

## 2. Methodologie

Alle bevindingen zijn empirisch getoetst tegen de live endpoint
(`https://data-ontwikkel.omgeving.vlaanderen.be/sparql`) en, voor QUDT, tegen de live QUDT
Linked-Data-publicatie (`http://qudt.org/vocab/unit/...`). Twee herhaalbare scripts zijn
toegevoegd aan de bestaande pijplijn:

- `scripts/check_conceptschemas.py` — klasse-ontdekking (elke `csor:`-getypeerde klasse,
  niet een hardgecodeerde lijst), dekking per klasse, relatie-kaart (object-properties),
  kardinaliteiten, inverse-paar-consistentie, orphan-detectie.
- `scripts/check_eenheden_qudt.py` — QUDT-koppelingsdekking, live HTTP- en
  edit-distance-gebaseerde symboolcontrole, en een interne spelling-/label-symbool-
  consistentiecheck op alle 357 eenheden (los van QUDT-beschikbaarheid).

Queries: `sparql/conceptschema_checks.sparql`, `sparql/eenheid_qudt_checks.sparql`.

## 3. Resultaten

### 3.1 De 10 CSOR-conceptschema's en hun onderlinge relaties

De endpoint serveert het **hele codelijstenlandschap** van `data.omgeving.vlaanderen.be` (47
conceptschema's, van zakelijk recht tot leegstand) in één default/union-graph. CSOR is
daarbinnen **10 schema's**, elk exact overeenkomend met één named graph
(`codelijst-csor-<naam>`):

| Conceptschema | Leden | Klasse |
|---|---|---|
| Variabelen | 2020 (2016 concepten + 4 `skos:Collection`) | `csor:Variabele` |
| Parameters | 4890 | `csor:Parameter` |
| Parameter aspecten | 8547 | `csor:ParameterAspect` |
| Eenheden | 357 | `csor:Eenheid` |
| Kwantificeerbaar aspect | 137 | `csor:KwantificeerbaarAspect` |
| Natuurkundige dimensies | 49 | `csor:NatuurkundigeDimensie` |
| Soort waardebepalingen | 80 | `csor:SoortWaardebepaling` |
| Dragers | 12 | `csor:Drager` |
| Kwalificeerbaar aspect | 3 | `csor:KwalificeerbaarAspect` |
| Resultaattype | 4 | `csor:Resultaattype` |

Deze klassen zijn verbonden via 24 object-properties (`output/tables/csor_relaties.csv`).
**Correcties t.o.v. een eerdere versie van dit rapport**: `rdfs:domain`/`rdfs:range` staan in
CSOR zelf niet betrouwbaar ingevuld (meestal leeg); domein en bereik zijn daarom empirisch
herbepaald door voor elke property te kijken tot welke `csor:`-klasse de subjecten/objecten
in de praktijk behoren (zie `scripts/generate_diagram.py`). Dat leverde twee correcties op
t.o.v. de aanname bij het eerste schrijven: `heeftSoortWaardebepaling` heeft als domein
**Parameter**, niet ParameterAspect; en `uitgedruktIn` loopt van **KwantificeerbaarAspect naar
Variabele**, niet Variabele-naar-Variabele.

Daarnaast bleken bij een handmatig samengestelde lijst twee relaties **volledig ontbrekend**.
Om dat structureel uit te sluiten is de lijst nadien gevalideerd tegen een **automatische
schema-extractie**: een generieke `CONSTRUCT`-query (naar het patroon van
`/home/gehau/git/RIE-IEPR/documentatie/datamodel/archief/model.rq`) die voor elk
(subject-type, property)-paar in de volledige, lokaal samengevoegde CSOR-graph het bereik-type
van het object afleidt — dus zonder enige aanname vooraf over welke relaties bestaan. Die
kruiscontrole bracht exact de twee gemiste relaties aan het licht:

- `ParameterAspect --heeftAspect--> KwantificeerbaarAspect` (8544×) / `KwalificeerbaarAspect`
  (3×), functioneel (exact 1 per ParameterAspect, alle 8547 gedekt, geen enkele orphan) — de
  schakel die specificeert wélke grootheid een parameteraspect meet; zonder deze relatie leek
  ParameterAspect in het diagram dood te lopen.
- `Eenheid --skos:broader--> Eenheid`, zelfreferentieel binnen de eenhedenlijst (187 van de
  357 eenheden, functioneel). Steekproef bevestigt exact hetzelfde patroon als de
  QUDT-`broadMatch`-bevinding in §3.4: een stofgekwalificeerde eenheid (bv. "kilogram
  stikstof per dag") is `skos:broader`-gekoppeld aan haar generieke, stofloze ouder
  ("kilogram per dag") — dezelfde stofkwalificatie-hiërarchie, nu ook *intern* in CSOR
  vastgelegd, niet enkel zichtbaar via de externe QUDT-koppeling.

De volledige, empirisch geverifieerde en gevalideerde relatie-kaart:
`Parameter --heeftVariabele--> Variabele`, `--heeftDrager--> Drager`,
`--heeftParameterAspect--> ParameterAspect`, `--heeftSoortWaardebepaling-->
SoortWaardebepaling`; `ParameterAspect --heeftAspect--> KwantificeerbaarAspect` (of
`KwalificeerbaarAspect`); `Eenheid/KwantificeerbaarAspect --heeftNatuurkundigeDimensie-->
NatuurkundigeDimensie`; `Eenheid --heeftKwantificeerbaarAspect--> KwantificeerbaarAspect`;
`Eenheid --skos:broader--> Eenheid`; `KwantificeerbaarAspect --toepasbareEenheid--> Eenheid`;
`NatuurkundigeDimensie --referentieEenheid--> Eenheid`;
`KwantificeerbaarAspect/KwalificeerbaarAspect --heeftResultaattype--> Resultaattype`;
`KwantificeerbaarAspect --uitgedruktIn--> Variabele` (koppelt een grootheid als "uitgedrukt
als stikstof" aan de variabele Stikstof — verklaart meteen de stofkwalificaties die in §3.4 de
`broadMatch`-koppelingen naar QUDT verklaren: de 7 doelvariabelen van `uitgedruktIn` zijn
exact de 7 elementen N/C/O/P/S/Cl/F die daar terugkomen). Structuur: **Variabele** is het
abstracte stofbegrip; **Parameter** bindt dat aan een **Drager**; **ParameterAspect** voegt
een grootheid toe via **Eenheid**, die zelf een **NatuurkundigeDimensie** en
**KwantificeerbaarAspect** draagt. Dit bevestigt en verfijnt het model uit
`reports/rapport_samenstellende_variabelen.md` §3. Zie `output/diagrams/csor_model.tex`
(gecompileerd naar `.pdf`/`.png`, of het diagram onderaan de README) voor een visuele
weergave van dit model.

Ter info, niet verder onderzocht: er bestaan aanpalende, niet-CSOR-genaamde schema's
"Conceptschema Chemische Stoffen" (6868 leden) en "Codelijst groeperingen en sommaties van
chemische stoffen" (1902 leden — de Vlaamse VMM-"sommatie stoffen"-lijst, ook bron in het
zusterproject `A-Substance-Is-Not-Always-a-Substance`). Geen kruiskoppeling met
`csor:Variabele` vastgesteld binnen deze verkenning.

### 3.2 Volledigheid: 10 "codelijst"-klassen wél, 7 "structurele" klassen bij ontwerp nooit

`scripts/check_conceptschemas.py` inventariseert **alle 17 `csor:`-klassen** (niet enkel de
10 bekende) en telt per klasse instanties vs. schema-leden (`output/tables/conceptschema_dekking.csv`).

**Alle 10 codelijst-klassen scoren 100%** — elk element van deze klassen is lid van zijn
conceptschema. Twee schijnbare afwijkingen tijdens de verkenning bleken bij nazicht geen
gaten: `csor:Variabele`-concepten (2016) plus 4 legitieme `skos:Collection`-instanties
(`bio_indicatoren`, `chemische_stoffen`, `fysische_eigenschappen`, `groepsparameters`) tellen
samen op tot de 2020 schema-leden; en 4 externe DCAT-thema-URI's (EuroVoc/GEMET/EU
data-theme/Belgif) die de dataset-*metadata* van `codelijst-csor-drager` classificeren, zijn
toevallig ook `a skos:Concept` maar geen CSOR-domeinconcepten.

**Het CSOR-vocabularium definieert daarnaast 7 klassen die nergens `skos:inScheme` dragen**:

| Klasse | Aantal | Aard |
|---|---|---|
| `OrganisatieSpecifiekeReferentie` | 8772 | organisatie-eigen referentiecodes op een parameter |
| `VeeltermParameterTerm` | 1279 | term binnen een veelterm-afleiding |
| `ParameterAfleidingVeelterm` | 129 | veelterm-afleiding (som-/verschilberekening) |
| `ParameterAspectOmzetting` | 10 | omzetting tussen parameteraspecten |
| `ParameterTerm` | 8 | generieke term |
| `ParameterAfleidingRWZIRendement` | 5 | RWZI-rendementsafleiding |
| `ParameterAfleidingVerhouding` | 4 | verhoudingsafleiding |

Dit zijn geen catalogus-termen maar **rekenkundige/relationele objecten** die een berekening
of koppeling specificeren tussen catalogus-termen (vgl. hoe `ParameterAfleidingVeelterm` in
`reports/rapport_samenstellende_variabelen.md` §3 al werd omschreven als "meer dan een
relatie: een rekenkundige specificatie"). Of het ontbreken van conceptschema-lidmaatschap
hier een bewuste modelleerkeuze is dan wel een onbedoeld gat, is niet uit de data zelf af te
leiden — zie Aanbeveling 1.

**Antwoord op "behoort ieder element tot een conceptschema?"**: ja, voor alle
codelijst-elementen (100%); nee, bij ontwerp, voor de 7 rekenkundige/relationele klassen.

### 3.3 Kardinaliteiten van de onderlinge relaties

Voor elke gevonden object-property is de forward- en backward-kardinaliteit gemeten
(`output/tables/csor_relatie_kardinaliteiten.csv`). Kernpatronen:

| Relatie | Kardinaliteit | Interpretatie |
|---|---|---|
| `Parameter→Variabele` | N:1 (backward 1–27, gem. 2,44) | bevestigt query 1a/1b uit het compositie-rapport |
| `Parameter→Drager` | N:1 (backward 25–2131, **11 van 12 dragers gebruikt**) | `DR_4` "passiveSamplingFilter" ongebruikt |
| `Parameter→ParameterAspect` (+ inverse) | 1:N (forward 1–7, **4819 van 4890**) | **71 parameters zonder ParameterAspect**; inverse-paar 100% consistent |
| `Eenheid→KwantificeerbaarAspect` (+ inverse) | N:M (forward 1–3, **342 van 357**) | **15 eenheden zonder KwantificeerbaarAspect**; inverse-paar 100% consistent |
| `NatuurkundigeDimensie→Eenheid` (referentie) | 1:1 bijectief | schoon, voor alle 49 dimensies |
| `Parameter→SoortWaardebepaling` | N:1, sterk scheef (backward tot 3960) | gedomineerd door enkele veelgebruikte soorten |
| `KwantificeerbaarAspect→Variabele` (uitgedruktIn) | N:1, klein (29 subj., 7 doelen) | koppelt een grootheid aan de stof waarin ze is uitgedrukt — de 7 doelen zijn precies de 7 elementen (N/C/O/P/S/Cl/F) uit de QUDT-`broadMatch`-stofkwalificaties in §3.4 |
| `ParameterAfleidingVeelterm→VeeltermParameterTerm` | 1:N (forward tot 49 termen) | één afleiding met 49 termen — een zeer grote som |
| `Verhoudingsafleiding→Teller/Noemer` | 1:1 bijectief | schoon, voor alle 4 verhoudingsafleidingen |
| `ParameterAspect→KwantificeerbaarAspect`/`KwalificeerbaarAspect` (heeftAspect) | N:1, functioneel | forward exact 1, **alle 8547 ParameterAspecten gedekt** — pas via de automatische schema-extractie (§3.1) ontdekt |
| `Eenheid→Eenheid` (skos:broader, zelfreferentieel) | N:1, klein (187 van 357) | stofgekwalificeerde eenheid → generieke ouder, zelfde patroon als de QUDT-`broadMatch`-bevinding — ook pas via de schema-extractie ontdekt |

**Twee concrete, niet eerder gerapporteerde onvolledigheden**: 71 van de 4890 parameters
(1,5%) hebben geen `ParameterAspect` (geen gedefinieerde grootheid), en 15 van de 357
eenheden (4,2%) hebben geen `KwantificeerbaarAspect`. Beide getoetste inverse-paren
(`heeftParameterAspect`↔`heeftParameter`, `heeftKwantificeerbaarAspect`↔`toepasbareEenheid`)
zijn daarentegen **perfect consistent**: 0 asymmetrieën.

### 3.4 QUDT-koppeling: 45% dekking, met een helder kwaliteitspatroon

Van de 357 actieve eenheden hebben er **162 (45%)** een `skos:*Match` naar
`qudt.org/vocab/unit/`: **50 `exactMatch`** en **112 `broadMatch`** (geen enkele eenheid met
meer dan één koppeling). Alle 50 unieke QUDT-URI's zijn live gedereferentieerd: **100% HTTP
200**, geen dode links.

**URI-schema geverifieerd (http vs. https)**: CSOR slaat de QUDT-koppelingen consequent op
als `http://qudt.org/vocab/unit/...`, niet `https://`. Dit is expliciet en herhaalbaar
getoetst — niet enkel de resolutie, ook de correctheid van het schema zelf — via
`common/qudt.py::fetch()`, dat voor elke koppeling het HTTP-redirect-verloop registreert en
controleert of de opgehaalde RDF-payload de exact door CSOR opgeslagen URI (inclusief schema)
zelf als subject gebruikt. Resultaat over **alle 162 koppelingen** (`output/tables/
eenheid_qudt_koppeling.csv`, kolommen `redirect_statuses`/`permanent_redirect`/
`payload_subject_matches`): elke `http://`-URI geeft een **HTTP 302**-redirect naar de
`https://`-variant — **0 van de 162 permanent (301)**, dus louter TLS-afdwinging op
transportniveau, geen aanwijzing voor een verhuisde identifier. En voor **alle 162**
koppelingen gebruikt de RDF-payload zelf `http://` als subject (`payload_subject_matches` =
`True` voor 162/162). QUDT heeft zijn semantische identifiers dus niet naar https
gemigreerd, enkel de transportlaag. CSOR's `http://`-schrijfwijze is de correcte, canonieke
QUDT-identifier, geen fout.

Symboolvergelijking via Levenshtein-edit-distance (na normalisatie van µ→μ, jr→a, /u→/h;
`output/tables/eenheid_qudt_koppeling.csv`):

- **`exactMatch` (50)**: 38 exact, **10 bijkomend op edit-distance 0 na normalisatie**
  (Vlaamse/SI-notatieverschillen: `kg/jr` vs. `kg/a`, en vooral een Unicode-valkuil —
  CSOR's `µ` MICRO SIGN (U+00B5) vs. QUDT's `μ` GREEK SMALL LETTER MU (U+03BC), visueel
  identiek maar byte-verschillend). Slechts **2/50 blijven inhoudelijk afwijkend** na
  normalisatie (`/L` vs. `#/L` voor "per liter"; `-` vs. `一` voor "Geen"/dimensieloos —
  QUDT's eigen, ongebruikelijke symboolkeuze, geen CSOR-fout).
- **`broadMatch` (112)**: 0/112 exact — **verwacht en correct**. CSOR-eenheden met een
  stofkwalificatie in het symbool (`mgC/L`, `µgN/d`, `kgO2/jr`, …) koppelen aan QUDT's
  generieke, stofloze eenheid, omdat QUDT dat onderscheid niet modelleert. De edit-distance
  loopt netjes op met de lengte van de stofkwalificatie (1 teken voor `N`/`C`/`P`/`S`/`F`, 2
  voor `O2`/`Sn`/`Cl`, verder oplopend voor samengestelde kwalificaties als `NH4`, `PO4`,
  `CaCO3`).
- **Ontbrekende koppelingen (195/357, 55%)**: deels structureel niet QUDT-mapbaar
  (bio-assay-equivalentie-eenheden zoals `ng eq/L`, `µgTEQ/kg`), deels wél plausibel
  koppelbaar maar nog niet gelinkt — bevestigd voor "ton per jaar" (`t/jr` →
  `qudt-unit:TONNE-PER-YR`, live HTTP 200) en "petajoule" (`PJ` → `qudt-unit:PetaJ`, live
  HTTP 200).

### 3.5 Spelfouten en label/symbool-inconsistenties, gevonden via de QUDT-payload-vergelijking

Op vraag om niet enkel op HTTP-fouten te controleren maar ook op spelfouten in CSOR, is naast
de edit-distance-symboolcontrole een generieke, **QUDT-onafhankelijke** interne check
toegevoegd die op **alle 357 eenheden** draait: near-duplicate-labelwoorddetectie
(frequentie + edit-distance) en een woordgrens-bewuste label/symbool-stofconsistentiecheck.
`scripts/check_eenheden_qudt.py` produceerde 13 vlaggen
(`output/tables/eenheid_spelling_vlaggen.csv`); bij handmatige beoordeling:

**Bevestigde echte fouten (7)**:

| Eenheid | Label | Fout |
|---|---|---|
| `E_105` | "kilogram stifkstof  per dag" | tikfout: moet "stikstof" zijn (+ dubbele spatie) |
| `E_113` | "kilogram stifstof" | tikfout: moet "stikstof" zijn |
| `E_104` | "micorgram stikstof per liter" | tikfout: moet "microgram" zijn |
| `E_130` | "millgram fosfor per kilogram droge stof" | tikfout: moet "milligram" zijn |
| `E_328` | "miligram koolstof per normaal kubieke meter" | tikfout: moet "milligram" zijn |
| `E_240` | "parts par million - methaanequivalenten" | tikfout: "par" moet "per" zijn (Engels/Frans-verwarring) |
| `E_323` | "milligram koolstofdisulfide per liter", symbool `mg Cl/kg` | **symbool hoort niet bij het label**: verkeerde stof (Cl i.p.v. koolstofdisulfide/CS2) én verkeerde noemer (/kg i.p.v. /L) — vermoedelijk een kopieerfout uit een chloor-eenheid |

**Vals-positieve vlaggen (6)**, ter illustratie van de precisie van de automatische check:
`E_231`/`E_235` "zuurequivalent" (legitiem samengesteld woord, geen tikfout van
"equivalent"), `E_232` "met." (correcte afkorting van "meter"), `E_240`'s tweede vlag
("methaanequivalenten", zelf correct — de échte fout in dat label is "par"), `E_203`
"eenheid" vs. "eenheden" (enkelvoud/meervoud, geen tikfout), `E_54` "mL" vs. "mol"
(twee verschillende, beide legitieme eenheden). `E_30` "gram ter ton" is twijfelgeval:
mogelijk een tikfout voor "gram per ton", niet met zekerheid vast te stellen uit de data
alleen.

Een eerste, bredere poging om de stofconsistentie te toetsen via kale substring-matching
(zoeken naar "C" in het symbool voor koolstof) bleek onbetrouwbaar: chemische afkortingen
overlappen lexicaal (`C` matcht ook binnen `Cl`/`Ca`; `N` binnen `Na`/`Nm³`; `S` binnen
`Sn`/`Si`; `P` binnen `Pa`/`PJ`), wat zowel valse alarmen als gemiste fouten geeft (de
`E_323`-fout werd er zelfs door gemaskeerd). De uiteindelijke check matcht daarom enkel op
het volledige, woordgrens-bewust geëxtraheerde stofkwalificatie-token.

## 4. Aanbevelingen

1. **Verifieer bij de registerbeheerders** of het ontbreken van conceptschema-lidmaatschap
   bij de 7 rekenkundige/relationele klassen (met name `ParameterAfleidingVeelterm`) een
   bewuste modelleerkeuze is — dit rapport bevestigt het feitelijke patroon, niet de intentie.
2. **Corrigeer de 7 bevestigde spelfouten** (§3.5): `E_105`, `E_113`, `E_104`, `E_130`,
   `E_328`, `E_240` (labelteksten) en `E_323` (symbool hoort niet bij het label — controleer
   welk correct symbool "milligram koolstofdisulfide per liter" wél moet dragen).
3. **Documenteer de µ (U+00B5) vs. μ (U+03BC) Unicode-conventie** als bekende valkuil voor
   wie CSOR- en QUDT-symbolen ooit programmatisch vergelijkt.
4. **Onderzoek QUDT-koppeling** voor de plausibel-koppelbare subset van de 195 ontbrekende
   eenheden, te beginnen met de bevestigde `t/jr`- en `PJ`-kandidaten.
5. **Verifieer de 71 parameters zonder `ParameterAspect`** en de **15 eenheden zonder
   `KwantificeerbaarAspect`** — bewust onvolledig (nieuw, nog niet afgewerkt) of een
   registratiegat?
6. **Evalueer `DR_4`** (passiveSamplingFilter) — terecht gedefinieerd zonder ooit gebruikt te
   worden, of een codelijst-restant?

## 5. Buiten scope

- Kruiskoppeling tussen `csor:Variabele` en de aanpalende schema's "Conceptschema Chemische
  Stoffen" / "Codelijst groeperingen en sommaties van chemische stoffen" (§3.1) — niet
  onderzocht binnen deze scope.
- Automatische kandidaat-matching voor de 195 QUDT-ontbrekende eenheden — vergt
  naam-/eenheid-parsing tegen de volledige QUDT-catalogus.
- Automatische correctie van de gevonden spelfouten — dit rapport levert bevindingen, geen
  schrijfacties naar het register.

---

*Bijlage: `../sparql/conceptschema_checks.sparql`, `../sparql/eenheid_qudt_checks.sparql`.
Herproduceerbaar via `python3 scripts/check_conceptschemas.py` en
`python3 scripts/check_eenheden_qudt.py` (of `scripts/run_all.py` voor de volledige
pijplijn — zie `../CLAUDE.md`). Volledige resultaten in `../output/tables/conceptschema_dekking.csv`,
`../output/tables/csor_relaties.csv`, `../output/tables/csor_relatie_kardinaliteiten.csv`,
`../output/tables/csor_orphans.csv`, `../output/tables/eenheid_qudt_koppeling.csv`,
`../output/tables/eenheid_qudt_ontbrekend.csv` en `../output/tables/eenheid_spelling_vlaggen.csv`.*
