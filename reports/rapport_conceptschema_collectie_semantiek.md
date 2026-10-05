# Semantische consistentie van conceptschemas en collecties binnen CSOR

**Datakwaliteitstoets: horen de concepten binnen elk `skos:ConceptScheme` en elke `skos:Collection`
semantisch thuis binnen de gepubliceerde scope-definitie van dat schema/die collectie?**

*Datum: 22 september 2026*

---

## 1. Aanleiding en vraagstelling

CSOR publiceert 14 `skos:ConceptScheme`-instanties (10 basis-codelijstschema's — drager, eenheid,
kwalificeerbaaraspect, kwantificeerbaaraspect, natuurkundigedimensie, parameter, parameteraspect,
resultaattype, soortwaardebepaling, variabele — plus 4 view-schema's onder `csor/view/rie-iepr/*`)
en 4 `skos:Collection`-instanties binnen `variabele` (bio_indicatoren, chemische_stoffen,
fysische_eigenschappen, groepsparameters). Elk daarvan draagt een publieke `skos:definition`/
`skos:prefLabel` die een inhoudelijke scope afbakent.

De vraag was: passen de concepten die er effectief inzitten, semantisch bij die afgebakende
scope? Dit is, net als `rapport_ontologie_definities.md`, in de eerste plaats een kwalitatieve
leesronde, maar aangevuld met een systematische, tabelgedreven doorlichting (zie §2.2) zodra de
eerste steekproeven een herkenbaar patroon lieten zien.

## 2. Methodologie

### 2.1 Bronnen, en een valkuil die tijdens dit onderzoek aan het licht kwam

Gebruikt: de 10 losse `codelijst-csor-*/…/conceptscheme/csor/*/*.ttl`-bronbestanden, rechtstreeks
uit elk project (niet `csor-testing/analyse/csor_merged.ttl`). Reden: `csor_merged.ttl` en een
naïeve samenvoeging van alle bronbestanden bevatten zowel `variabele.ttl` als het **verouderde**
`view.ttl`. Voor het notatiebereik V_2043–V_2240 declareren die twee bestanden **tegenstrijdige**
`skos:prefLabel`/`csor:cas`-waarden op dezelfde URI (zie §3.2) — een naïeve samenvoeging geeft dan
186 variabelen met twee `skos:prefLabel`-literals op één subject, en een alfabetisch-eerste-pick
kiest daaruit willekeurig de verkeerde. Voor alles wat aan de Variabele-node hangt (label, CAS,
InChIKey, collectielidmaatschap) is daarom uitsluitend `codelijst-csor-variabele/…/variabele.ttl`
gebruikt, bevestigd tegen het live dev-endpoint (`data-ontwikkel.omgeving.vlaanderen.be/sparql`).
Deze valkuil trof in een eerdere iteratie van dit onderzoek ook al een aantal voorlopige
bevindingen (foutief toegeschreven labels aan `fysische_eigenschappen`-leden) — na correctie
bleken die niet stand te houden en zijn ze niet in dit rapport opgenomen.

### 2.2 Platte relatietabel

Om niet enkel op steekproeven te varen is `output/tables/parameteraspect_matrix.csv` gebouwd: één
rij per actief (niet-gedeprecieerd) `csor:ParameterAspect` (8179 rijen), met Variabele
(+collectie, CAS, InChIKey), Parameter, Drager, SoortWaardebepaling, ParameterAspect, Aspect
(Kwantificeerbaar/Kwalificeerbaar +dimensie +resultaattype +uitgedruktIn) samengevoegd in één rij,
plus afgeleide kolommen (aantal verschillende aspecten per variabele, of variabelelabel het
aspectlabel letterlijk herhaalt, hoeveel variabelen eenzelfde dimensie delen). Kolommen: zie de
headerregel van het bestand zelf (zelfverklarende namen, Nederlandstalig). Dit liet toe
patroonmatig — niet enkel losse gevallen — te zoeken naar afwijkingen.

### 2.3 Git-geschiedenis als bewijslaag

`codelijst-csor-variabele` en `codelijst-csor-view` zijn elk hun eigen git-repository. Voor de
kernbevinding in §3.2 is de commit-geschiedenis van `variabele.ttl` geraadpleegd om de
gedocumenteerde inhoudsverandering aan een specifieke commit (hash, auteur, datum) op te hangen,
in plaats van enkel twee snapshots naast elkaar te leggen.

## 3. Resultaten per toets

### 3.1 De 14 conceptschema's: basisstructuur is gezond

Voor elk basis-codelijstschema geldt: `skos:hasTopConcept` == `skos:topConceptOf`-verzameling ==
`skos:inScheme`-verzameling, geen wees-leden, en elk concept typeert consequent naar precies één
`csor:<Klasse>`. De enige structurele afwijking op dit niveau: `eenheid` bevat lokaal één concept
(`E_xxx`, "aantal varkens jonger dan drie maanden") dat niet op het live endpoint bestaat (359
i.p.v. 360) — een lokaal, niet-gepubliceerd testconcept, geen registerfout.

### 3.2 Kritieke bevinding — identifier-hergebruik op een stabiele URI (V_2043–V_2240)

**Bevinding**: 186 URI's in het notatiebereik `V_2043`–`V_2240` verwijzen, afhankelijk van welk
bestand je raadpleegt, naar **twee volledig verschillende, ongerelateerde concepten**. Voorbeeld:

| Bestand | `V_2043` betekent |
|---|---|
| `codelijst-csor-view/…/view.ttl` | "1,3-Dichloorpropenen (som)" |
| `codelijst-csor-variabele/…/variabele.ttl` (huidig, en live bevestigd) | "2-Heptanon" (CAS 110-43-0) |

Dit is geen renaming of verplaatsing: "1,3-Dichloorpropenen (som)" komt in de huidige
`variabele.ttl` nergens meer voor, onder geen enkele URI. Het concept is verwijderd en de
vrijgekomen notatie is hergebruikt voor een nieuw, ongerelateerd concept — een schending van het
basisprincipe dat een gepubliceerde, dereferenceerbare concept-URI permanent naar hetzelfde ding
moet blijven verwijzen.

**Herleid tot een specifieke commit.** In `codelijst-csor-variabele`:

```
commit ab1c5371dc6a6a96d5e3be10e72246ba5880417a
Author: Pieter Fannes <pieter.fannes@vlaanderen.be>
Date:   2026-08-13 16:39:21 +0200

    ontwikkel versie 13/08/2026
```

Diff-omvang op dit ene bestand: 1224 regels toegevoegd, 2307 verwijderd — een grotendeels
volledige herschrijving, consistent met een bronsysteem dat dit deel van het bestand bij elke run
herbouwt in plaats van bestaande identifiers als onveranderlijk te behandelen. `git show` van
`V_2043` vóór (commit `3a2d647`, 03/07/2026) en na (`ab1c537`) bevestigt de omschakeling
rechtstreeks in de bronregels zelf:

```turtle
# vóór (3a2d647, 03/07/2026)
<.../variabele/V_2043>
    skos:notation      "V_2043";
    skos:prefLabel     "1,3-Dichloorpropenen (som)"@nl;
    csor:symbool       "13DCP" .

# na (ab1c537, 13/08/2026)
<.../variabele/V_2043>
    skos:notation      "V_2043";
    skos:prefLabel     "2-Heptanon"@nl;
    csor:cas           "110-43-0";
    csor:inchikey      "CATSNJVOTSVZJV-UHFFFAOYSA-N" .
```

`codelijst-csor-view` heeft slechts één commit (`925dcf0`, "initial commit", 2026-09-11) — bevat
dus nooit de wijziging van `ab1c537` (13/08) en is sindsdien nooit geregenereerd.

**Omvang, en waarom dit een geïsoleerd incident lijkt, geen structurele praktijk.** Binnen
`variabele` zelf gedraagt het overgrote deel van de nummering zich wél correct: het stabiele
bereik V_1–V_2042 telt 344 permanent onbezette "gaten" (verwijderde concepten waarvan het nummer
nooit hergebruikt is) tegenover **exact 0 gaten** in het notatiebereik V_2043–V_2240, ondanks
bevestigde uitval daar (121 labels uit de julisnapshot komen nergens meer voor in de huidige
`variabele.ttl`; zie `output/tables/variabele_identifier_drift.csv`). Ook `parameter` (0 gaten op
4593) en `parameteraspect` (0 gaten op 8194) lossen dit structureel wél goed op: ze bevatten elk
een aantal (29, resp. 15) `owl:deprecated true`-gemarkeerde, maar nog altijd aanwezige concepten,
verspreid over het hele notatiebereik — deprecatie in plaats van verwijdering, dus nooit een vrij
nummer om te hergebruiken. `eenheid` volgt hetzelfde veilige patroon als het gros van `variabele`
(16 van 375, 4,3% gaten). Het identifier-hergebruik lijkt dus beperkt tot één opschonings-/
importronde op één blok van één codelijst — maar toont aan dat de garantie niet overal even hard
afgedwongen wordt.

**Impact**: elke consument die `V_2043`–`V_2240` via `view.ttl` (of een oudere snapshot)
raadpleegt, krijgt zonder foutmelding het verkeerde concept. Dit trof rechtstreeks de
RIE-IEPR-views (zie §3.7).

Volledige lijst van 186 gedrifte + 109 spookconcepten (bestaan enkel in `view.ttl`, nergens meer
in `variabele.ttl` of live): `output/tables/variabele_identifier_drift.csv`.

### 3.3 `csor:Variabele` mengt twee ontologisch verschillende rollen

De klassecomment ("Een variabele is een kenmerk dat geobserveerd kan worden…") past bij een
minderheid van de instanties. Gemeten via het gemiddeld aantal verschillende
`KwantificeerbaarAspect`/`KwalificeerbaarAspect`-waarden per variabele, per collectie:

| Collectie | gem. #aspecten/variabele | % met precies 1 aspect | % waar variabele- en aspectlabel letterlijk gelijk zijn |
|---|---|---|---|
| fysische_eigenschappen | 2,01 | 60% | 7% |
| bio_indicatoren | 1,25 | 78% | 0% |
| chemische_stoffen | 3,48 | 20% | 0% |
| groepsparameters | 2,92 | 11% | 0% |

Voor `fysische_eigenschappen` valt de variabele vrijwel samen met het kenmerk zelf (bv.
`Doorzichtigheid` → precies 1 aspect, `lengte`, dat enkel de eenheid herhaalt); voor
`chemische_stoffen` is de variabele overduidelijk het *onderwerp* waaraan tien-plus orthogonale
kenmerken gekoppeld kunnen worden (bv. `Nitraat`: 15 verschillende aspecten — massaconcentratie,
massaverhouding, vracht, mol per oppervlakte, …). Twee ontologisch verschillende rollen — "is het
kenmerk" versus "draagt het kenmerk" — onder één `rdfs:Class` zonder onderscheid.

**Concreet gevolg van deze mismatch**: `Doorzichtigheid` (Secchi-diepte) heeft geen eigen
`NatuurkundigeDimensie`/`KwantificeerbaarAspect` en leunt op het generieke `lengte`, terwijl het
optisch nauw verwante `Turbiditeit` wél zijn eigen dimensie (`ND_13`) en aspect (`KWA_17`) heeft.
Dat generieke `lengte`-aspect wordt gedeeld door 8 semantisch ongerelateerde variabelen:
`Bemonsteringsdiepte`, `Breedte`, `Dikte`, `Doorzichtigheid`, `Lengte`, `Neerslag`, `Volume`,
`Zwevende stoffen, afmeting` — een monsterdiepte en een doorzichtigheid zijn beide "in meter" maar
betekenen niets van elkaar; enkel de variabelenaam, niet het aspect, houdt ze uit elkaar.

Hetzelfde patroon zit in de dimensie `Geen` (31 variabelen): naast legitiem dimensieloze grootheden
(pH ×3, verhoudingen, isotopenverhoudingen) staan er **rauwe taxonnamen zonder eenheid** in:
`Fytobenthos`, `Fytoplankton`, `Macrofyten`, `Vis` (in `fysische_eigenschappen`) en `Hyalella`,
`Ostracod` (in `bio_indicatoren`) — hetzelfde soort concept (een organismegroep), hetzelfde
generieke aspect, maar verdeeld over twee verschillende collecties (zie ook §3.6).

### 3.4 Eén concrete datafout gevonden via de matrix: `turbiditeit`-aspect misbruikt

Van de 13 aspecten die in de matrix gedeeld blijken tussen variabelen uit verschillende collecties,
zijn er 12 chemisch/analytisch verklaarbaar (courante conventies om een resultaat "als N", "als
O₂" of "als Ca-hardheid" uit te drukken — bv. `massaconcentratie zuurstof` gedeeld door `Zuurstof`
(stof) en `Biochemisch zuurstofverbruik na 5d.`/`Chemisch zuurstofverbruik` (fysisch, BZV/CZV
conventioneel als O₂-equivalent)). **Eén aspect is dat niet**: `turbiditeit` (`KWA_17`) wordt naast
`Turbiditeit` zelf ook gebruikt door `Fecale coliformen (bio_indicatoren)` en
`Kwaliteits Index (fysische_eigenschappen)` — een fecaalcoliformentelling of een samengestelde
kwaliteitsindex is geen turbiditeitsmeting. Dat de systematische doorzoeking deze ene afwijking uit
twaalf onschuldige gevallen haalt, bevestigt dat de methode discrimineert i.p.v. ruis genereert.

Twee kleinere, precies afgebakende bevindingen uit dezelfde matrix:
- `uitgedruktIn` ontbreekt bij een element-aspect in slechts 2 gevallen: `V_1958`
  (`massaconcentratie koolstof (Nm³)`) en `V_1503` (`vracht fluor`).
- `resultaattype` is **volledig consistent** per aspectlabel (geen enkel aspect met
  tegenstrijdige resultaattypes) — dit sluit een categorie fouten uit.
- `V_1350` ("Perfluoroctaanzuur (PFOA) lineair (nvt)") is de enige `chemische_stoffen`-variabele
  zonder CAS, zonder InChIKey én met slechts 1 aspect — de "(nvt)" in het eigen label suggereert
  dat dit al intern als twijfelgeval bekend stond.
- `KWA_146` heet letterlijk "Fout aangemaakt" en wordt gebruikt door parameteraspect
  `TFA (standaard in biota)`.

### 3.5 De vier variabele-collecties: grotendeels coherent, met afwijkingen

De 4 collecties vormen samen een perfecte partitie van het variabele-schema (1896/1896, geen
overlap, geen gat) — geen dekkingsprobleem. Per collectie:

- **`chemische_stoffen` (1242) — ✔ grotendeels coherent.** 1212 van de 1242 (97,6%) hebben een
  CAS-nummer; van de 30 zonder CAS zijn er 22 elementen (periodiek systeem, terecht zonder
  CAS-registratie). De prefLabel bevat een grammaticafout ("Lijst van zuivere **chemisch**
  stoffen").
- **`groepsparameters` (440) — ⚠.** Naast legitieme somparameters/groepen staan er minstens 12
  concrete, ondubbelzinnig niet-chemische conventionele parameters in: `Zwevende stoffen`,
  `Vluchtige stof`, `Permanganaatverbruik`, `Toxiciteit`, `Ionenbalans`, `Latex`,
  `Zwarte koolstof`, `Fytotox`, en de vijf `PM0,1`/`PM1`/`PM10`/`PM2,5`/`PM2,5 - PM10`-fracties.
  Geen enkel lid van deze collectie heeft een InChIKey — consistent met "groep", maar bevestigt
  ook dat de bovenstaande individuele, niet-somgebaseerde parameters hier niet thuishoren.
- **`fysische_eigenschappen` (142) — ⚠.** Circa 40 leden (28%) zijn niet fysisch in de strikte
  zin: zuurstofverbruik (`BZV5`, `CZV`, `BZV-10`), pH/redox/alkaliteit (7), gehaltes en
  samenstelling (9: `Vetgehalte`, `Asgehalte`, `Droge stof`, …), asbestmineralen met eigen
  CAS-nummer (8: `Chrysotiel`, `Crosidoliet`, `Tremoliet`, `Actinoliet`, `Anthophylliet`, …),
  afgeleide rendementen/verhoudingen (9), en vier losse gevallen (`Hydromorfologie`,
  `Kwaliteits Index`, `Biodegradeerbaarheid`, `Oxidatief Potentieel`).
- **`bio_indicatoren` (72) — ✔/⚠.** Microbiologische indicatoren, taxa/testorganismen en
  bioassays (CALUX, Microtox) passen goed bij de collectiedefinitie. Grensinconsistentie met
  `fysische_eigenschappen`: dezelfde soort concepten (organismegroepen: `Hyalella`, `Ostracod`
  hier, maar `Vis`, `Fytoplankton`, `Fytobenthos`, `Macrofyten` in `fysische_eigenschappen`) staan
  in twee verschillende collecties zonder duidelijk onderscheidend criterium.

### 3.6 De rie-iepr views: zelfde identifier-probleem, plus een scope-vraag

`waterzuiveringsinstallatie-stoffen` (1765 leden) en `luchtzuiveringsinstallatie-stoffen` (534
leden) erven het probleem uit §3.2 rechtstreeks: 186 leden wijzen door de identifier-drift naar
een ander concept dan bedoeld, en 109 (water) / 13 (lucht) leden bestaan enkel nog in `view.ttl` —
niet in de huidige `variabele.ttl`, niet live. Van de resterende, stabiele leden (ID < V_2043) is
68% (water) resp. 75% (lucht) effectief een chemische stof; de rest bestaat uit groepsparameters
(25%/16%) en, in de waterview, ook bio-indicatoren (4%) en fysische eigenschappen als `Kleur`,
`Korrelgrootte` en `Bemonsteringsdiepte` (3%/9%). Of deze bredere scope ("stoffen te rapporteren")
bewust zo bedoeld is voor de RIE-IEPR-rapportageverplichting, is een vraag voor de domeinexpert,
geen vastgestelde fout.

### 3.7 Overige bevindingen per scheme

- **`NatuurkundigeDimensie` (49)**: vijf leden zijn geen natuurkundige dimensie — `ND_18` "Geen",
  `ND_21` "inwonersequivalent" (een afgeleide grootheid), `ND_22` "mol" (dat is een eenheid, geen
  dimensie), `ND_25` "Effect eenheden", `ND_43` "arbitraire eenheid per volume".
- **`SoortWaardebepaling` (80)**: mengt vijf soorten informatie onder één klasse: fractie/
  speciatie (`opgelost`, `totaal`), analysetechniek (`LC-MS`, `GC-MS`), ecotox-eindpunt met duur
  (`LC50 (48h)`, en kale `48h`/`72h`), monstervoorbereiding (`Eluaat LS…`, `Zahn Wellens`), en
  projectnamen (`MUC`/`MUCd project`, 6×). `SWB_41` "pesticiden sampler" (45 parameters) is een
  toestel, geen waardebepalingswijze.
- **`Drager` (12)**: `DR_4` "passiveSamplingFilter" heeft nul parameters — volledig ongebruikt.
  TSP/PM10/PM2.5 zijn deeltjesfracties, geen dragermedia in dezelfde zin als water/lucht/bodem.
- **`Eenheid` (360)**: 187 (52%) coderen element-/verbindingsbasis (`mgN/L`), matrixbasis
  (droge stof/nat gewicht), equivalenten-met-referentiestof (TEQ, PFOA-eq) of normaalcondities
  (Nm³) in de eenheid zelf — informatie die al bij het `KwantificeerbaarAspect` hoort via
  `uitgedruktIn`. Dat het register dit deels zelf al erkent, blijkt uit `skos:broader`: 181 van
  die 187 hebben een `skos:broader`-link naar hun zuivere basiseenheid.

## 4. Aanbevelingen

1. **(hoogste prioriteit) V_2043–V_2240 herstellen.** Vraag bij Pieter Fannes na welke bron/tool
   commit `ab1c5371d` (13/08/2026) genereerde; voeg `owl:deprecated`/`dcterms:isReplacedBy` toe
   voor de 121 verdwenen concepten in plaats van stilzwijgende verwijdering; regenereer
   `view.ttl` vanaf de huidige `variabele.ttl`/live-toestand; overweeg een technische waarborg
   (bv. een validatiestap die weigert een reeds gepubliceerde notatie te hergebruiken) tegen
   herhaling bij een volgende opschoning van eender welke codelijst.
2. Herformuleer `csor:Variabele`'s `rdfs:comment` van "een kenmerk" naar een onderwerp-begrip
   (zie §3.3) — consistent met hoe `csor:Parameter` Variabele al gebruikt ("uitspraak **over**
   een variabele").
3. Geef `Doorzichtigheid` een eigen `NatuurkundigeDimensie`/`KwantificeerbaarAspect`, naar
   analogie van `Turbiditeit`, in plaats van het generieke `lengte` te delen met zeven
   ongerelateerde variabelen.
4. Corrigeer het `turbiditeit`-aspect bij `Fecale coliformen` en `Kwaliteits Index` (§3.4).
5. Licht `groepsparameters` en `fysische_eigenschappen` door op de concrete, niet-passende leden
   uit §3.5 en herclassificeer waar aangewezen.
6. Trek een consistente grens voor organismegroepen tussen `bio_indicatoren` en
   `fysische_eigenschappen` (voorstel: alles waarvan de meting een levend systeem vereist naar
   `bio_indicatoren`).
7. Bevestig bij de domeinexpert of de bredere scope van de rie-iepr-views (niet enkel chemische
   stoffen) bewust is (§3.6), en herbouw de viewselectie vanaf actuele bronnen.
8. Vul de 2 ontbrekende `uitgedruktIn`-waarden aan (`V_1958`, `V_1503`) en hernoem `KWA_146`.

## 5. Buiten scope (v1)

- **Geen geautomatiseerd, herhaalbaar `check_*.py`-script** gebouwd voor deze ronde — net als
  `rapport_ontologie_definities.md` is dit een kwalitatieve, tabelgedreven eenmalige review.
  Vervolgstap: `check_conceptschema_semantiek.py`, dat `output/tables/parameteraspect_matrix.csv`
  bij elke `run_all.py`-run herberekent en de hier gedocumenteerde regex-/drempel-heuristieken
  (aspectdiversiteit, gedeelde generieke dimensies, cross-collectie aspectdeling) automatisch
  herevalueert.
- **Geen git-archeologie voor de andere codelijsten** (`eenheid`, `parameter`,
  `parameteraspect`, …) — enkel `variabele`/`view` zijn onderzocht, omdat daar de aanleiding
  (view/variabele-drift) zich concreet voordeed. Niet uitgesloten dat gelijkaardige incidenten
  elders in de geschiedenis van andere codelijsten zitten.
- **Geen SHACL-validatie** van de hier beschreven bevindingen — dit rapport signaleert
  semantische pasvorm, geen schema-conformiteit.
- **Geen kwantitatieve afronding van de "niet-chemisch in groepsparameters"-telling** — §3.5 geeft
  een concrete, manueel geverifieerde ondergrens (12), geen uitputtende regex-gebaseerde telling,
  om overclaiming op een ruwe heuristiek te vermijden.

---

*Bijlage: brondata voor dit rapport zijn de 10 losse `codelijst-csor-*/…/*.ttl`-bestanden (zie
§2.1) en de git-geschiedenis van `codelijst-csor-variabele` (commit `ab1c5371d`) en
`codelijst-csor-view` (commit `925dcf0`). Ondersteunende tabellen:
`output/tables/parameteraspect_matrix.csv` (8179 rijen, één per actief ParameterAspect) en
`output/tables/variabele_identifier_drift.csv` (295 rijen: 186 gedrifte + 109 spookconcepten in
`view.ttl`).*
