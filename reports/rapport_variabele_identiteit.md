# Chemische identiteit van variabelen in het CSO-register

**Datakwaliteitstoets: CAS-nummers, InChIKeys en IUPAC-namen op `csor:Variabele`, getoetst tegen PubChem**

*Datum: 30 juli 2026*

---

## 1. Aanleiding en vraagstelling

Op `csor:Variabele` — het abstracte, dragervrije stofbegrip in het CSOR-model (zie
`reports/rapport_samenstellende_variabelen.md`, §3) — worden naast notatie en label ook
chemische-identiteitsvelden bijgehouden: `csor:cas` (CAS Registry Number), `csor:inchikey`
(InChIKey), `csor:iupacNaam` (IUPAC-naam), `csor:eea` (een EC/EINECS-achtig nummer) en, voor
een deel van de variabelen, een rechtstreekse koppeling naar een PubChem-compound (via het
predicaat `https://pubchem.ncbi.nlm.nih.gov/rest/rdf/compound`).

De vraag was tweeledig: (1) in hoeverre kunnen CAS-nummers betrouwbaar naar een InChIKey
herleid worden, en komt dat overeen met wat het register zelf al vastlegt; en (2) zijn de
opgeslagen eigenschappen consistent met een externe referentiebron? Als externe bron is
PubChem gebruikt (v1-scope; zie §5 "Buiten scope").

## 2. Methodologie

De volledige `codelijst-csor-variabele`-graph (25.312 triples, 2008 actieve — niet-
gedeprecieerde — `csor:Variabele`-concepten) is gepagineerd opgehaald tegen
`https://data-ontwikkel.omgeving.vlaanderen.be/sparql` (zie `sparql/csor-variabele-fetch.sparql`
en `CLAUDE.md` §4 voor de reden waarom paginatie verplicht is: de endpoint knipt
CONSTRUCT-resultaten stil af op 10.000 triples). Vier toetsen zijn uitgevoerd, in oplopende
mate van externe afhankelijkheid:

1. **Interne consistentie** (`scripts/check_variabele_identity.py::internal_checks`, kruisgecontroleerd met `sparql/variabele_identity_checks.sparql`): CAS-checksum (standaard mod-10-controlegetal), InChIKey-vormvalidatie, dubbele InChIKey/CAS over notaties heen.
2. **PubChem CID-crosscheck**: voor variabelen met zowel een `inchikey` als een PubChem-CID-koppeling — de sterkste, ondubbelzinnige toets, want er is geen naam-matching nodig; CSOR's InChIKey/IUPAC-naam wordt rechtstreeks vergeleken met wat PubChem voor exact die CID teruggeeft.
3. **CAS-resolutie**: voor elke variabele met een CAS-nummer wordt PubChem bevraagd via het CAS-nummer zelf (PUG-REST "name"-endpoint accepteert CAS-nummers); als dat niets oplevert én er nog geen InChIKey gekend is, volgt een fallback-lookup op de substantienaam (`prefLabel`). Waar CSOR al een InChIKey had, wordt vergeleken (match/mismatch); waar niet, wordt het resultaat gerapporteerd als suggestie.
4. Alle PubChem-lookups lopen via een bestandscache (`data/cache/pubchem/`); deze run deed 2.479 live calls.

## 3. Resultaten

### 3.1 Dekking

| Veld | Aantal (van 2008 actieve variabelen) |
|---|---|
| `csor:cas` | 1257 |
| `csor:inchikey` | 1235 |
| `csor:iupacNaam` | 1216 |
| PubChem-CID-koppeling | 1219 |
| `csor:eea` | 166 |

### 3.2 Interne consistentie — schoon, op één patroon na

CAS-checksum en InChIKey-vormvalidatie leverden **geen enkele afwijking** op: alle 1257
CAS-nummers zijn checksum-geldig, alle 1235 InChIKeys volgen het correcte vormpatroon. Er zijn
**geen dubbele InChIKeys** over verschillende notaties heen.

Wel zijn er **10 CAS-nummers die door twee of drie verschillende `V_xxx`-notaties gedeeld
worden** (`output/tables/internal_flags.csv`, flag_type `duplicate_cas`):

| CAS | Notaties |
|---|---|
| 1763-23-1 | V_1357, V_1367, V_962 |
| 104-76-7 | V_2055, V_2166 |
| 12001-28-4 | V_2125, V_2349 |
| 71-55-6 | V_432, V_835 |
| 59729-33-8 | V_2119, V_2347 |
| 77536-67-5 | V_2086, V_2341 |
| 71675-85-9 | V_2082, V_2340 |
| 288-88-0 | V_1533, V_1534 |
| 115-29-7 | V_1, V_2168 |
| 12172-73-5 | V_2083, V_2339 |

Niet elk van deze paren is per se een fout: V_1 ("alfa+beta Endosulfan") en V_2168 ("Endosulfan
(a+b+sulfaat)") delen CAS 115-29-7 omdat de tweede variabele een bredere som is die de eerste
omvat — vergelijkbaar met de *PFAS individueel*-discussie in
`reports/rapport_samenstellende_variabelen.md` §2. **288-88-0 (V_1533/V_1534) is wél
inhoudelijk relevant**: V_1533 is exact de "1,2,4-Triazool"-somvariabele die in dat eerdere
rapport (§4.2) al gedeprecieerde-tautomeer-varianten zonder `dcterms:isReplacedBy` bleek te
hebben — dit CAS-duplicaat bevestigt vanuit een andere hoek dat dat lifecycle-punt nog open
staat. De overige acht paren verdienen een korte handmatige blik (asbestmineralen,
farmaceutica, isomerenmengsels) maar zijn niet per definitie incorrect.

### 3.3 PubChem CID-crosscheck — sterk positief resultaat

Van de 1219 variabelen met zowel een InChIKey als een PubChem-CID-koppeling werden er **1218
teruggevonden bij PubChem** (CID 38854, gekoppeld aan V_25, gaf geen resultaat meer — mogelijk
een ondertussen samengevoegde/verwijderde CID bij PubChem, geen CSOR-probleem). Van die 1218
kwam de door PubChem geretourneerde InChIKey in **alle gevallen (1218/1218, 0 mismatches)**
overeen met wat CSOR zelf al opsloeg. Dit is de sterkste toets in dit rapport en het resultaat
is ondubbelzinnig geruststellend: waar CSOR een expliciete CID-koppeling heeft, is de
InChIKey-registratie betrouwbaar.

### 3.4 CAS-resolutie — één systematisch, goed te lokaliseren defect

Van de 1257 variabelen met een CAS-nummer:

| Status | Aantal | Betekenis |
|---|---|---|
| `match` | 1146 | PubChem's CAS-resolutie bevestigt de al opgeslagen InChIKey |
| `mismatch` | 53 | PubChem's CAS-resolutie geeft een àndere InChIKey dan opgeslagen |
| `resolved_new` | 24 | Geen InChIKey opgeslagen; PubChem kon er wél één afleiden (suggestie, niet teruggeschreven) |
| `unresolved` | 34 | Geen InChIKey opgeslagen; ook PubChem kon niets afleiden (via CAS én naam) |

**De 53 mismatches vallen in drie duidelijk te onderscheiden groepen** (`output/tables/cas_resolution.csv`):

1. **11 gevallen met een systematische InChIKey-typefout** — de op één na laatste letter van
   het tweede blok is `N` waar die `S` hoort te zijn (bv. `...UHFFFAOYNA-N` in CSOR tegenover
   het correcte `...UHFFFAOYSA-N`). Voor **9 van de 11** is dit de énige afwijking: skelet-hash
   én volledige stereolaag komen exact overeen met PubChem, enkel die ene letter is fout —
   ondubbelzinnig een InChIKey-typefout bij invoer, geen inhoudelijk verschil van mening. Het
   gaat om V_2052, V_2138, V_2127, V_2166, V_2082, V_2057, V_2309, V_2324, V_2119. Voor **2**
   verdere gevallen (V_378 "beta-Endosulfan" en V_390 "epsilon-Hexachloorcyclohexaan") is de
   volledige stereolaag anders dan bij PubChem, niet enkel die ene letter — hier is de InChIKey
   vermoedelijk helemaal niet correct (her)berekend bij invoer. Noemenswaardig: V_378 deelt zijn
   skelet-hash (`RDYMFSUJUZBWLH`) met het steekproefrecord V_1 uit dit onderzoek — beide zijn
   Endosulfan-gerelateerd.
2. **24 gevallen waar skelet-hash overeenkomt maar de stereolaag anders is**, zonder het
   specifieke `N`/`S`-patroon van groep 1 — vermoedelijk stereo-isomeer- of
   tautomeer-verwarring bij de oorspronkelijke InChIKey-berekening. Verdient dossier-per-dossier
   nazicht.
3. **18 gevallen met een volledig ander skelet** (V_1030, V_1239, V_1253, V_1283, V_144, V_149,
   V_156, V_1814, V_328, V_618, V_660, V_790, V_822, V_823, V_844, V_88, V_887, V_960). Dit is
   de minst betrouwbare categorie om als "CSOR-fout" te bestempelen: PubChem's CAS-als-naam-
   lookup is berucht onbetrouwbaar bij zouten/hydraten/elementen (bv. V_1814 Stikstofmonoxide,
   V_328 Antimoon) en kan zelf een verwant maar ander compound teruggeven. **Aanbeveling:
   handmatig nazicht per rij, niet automatisch corrigeren.**

De **34 onopgeloste CAS-nummers** zijn overwegend geen CSOR-tekortkoming maar een illustratie
van de these uit het zusterproject *A-Substance-Is-Not-Always-a-Substance*: PubChem is een
databank van discrete moleculen en kan minerale/vezelachtige stoffen (tremoliet, actinoliet,
anthofylliet — asbestvariëteiten), mengsels (kerosine, gehydrogeneerd terfenyl,
tolueendiisocyanaat-isomerenmengsel) en UVCB's niet als één InChIKey uitdrukken. Dat een CAS-
nummer hier "onoplosbaar" is bij PubChem is dus verwacht en geen datakwaliteitsprobleem van
CSOR.

De **24 `resolved_new`-suggesties** (`output/tables/cas_resolution.csv`, kolom
`resolved_inchikey`) zijn concrete, direct bruikbare aanvullingen voor variabelen die nu geen
InChIKey dragen maar wel een CAS-nummer — bv. V_2168 (Endosulfan a+b+sulfaat, zie §3.2),
V_2125 (Crocidoliet), V_2118 (Chrysotiel).

## 4. Aanbevelingen

1. **Corrigeer de 9 duidelijke InChIKey-typefouten** (groep 1a hierboven: V_2052, V_2138,
   V_2127, V_2166, V_2082, V_2057, V_2309, V_2324, V_2119) — de correcte waarde staat al klaar
   in `output/tables/cas_resolution.csv` (kolom `resolved_inchikey`).
2. **Onderzoek V_378 en V_390 afzonderlijk** — de InChIKey lijkt hier niet met de juiste
   stereo-informatie berekend.
3. **Vul de 24 `resolved_new`-suggesties in** als InChIKey voor de betrokken variabelen, na een
   korte steekproefcontrole (het zijn suggesties, geen automatisch teruggeschreven waarden).
4. **Handmatig nazicht, geen automatische correctie**, voor de 18 volledig-andere-skelet-
   mismatches en de 24 zelfde-skelet-andere-stereo-mismatches — de CAS-als-naam-lookup bij
   PubChem is hier zelf een bron van onzekerheid.
5. **Rond het CAS 288-88-0-duplicaat (V_1533/V_1534) mee af** samen met het al gekende
   triazool-lifecycle-punt uit `reports/rapport_samenstellende_variabelen.md` §4.2.
6. Geen actie nodig voor de 34 onopgeloste CAS-nummers (minerale stoffen/mengsels) — enkel
   documenteren dat dit een verwachte, structurele beperking van PubChem als referentiebron is.

## 5. Buiten scope (v1)

Bewust niet meegenomen in deze eerste versie, als vervolgtraject:

- **ChEBI als tweede, PubChem-onafhankelijke bron** (via `bash/exact_match_chebi.rq` /
  `bash/chebi_to_table.rq` uit het zusterproject `A-Substance-Is-Not-Always-a-Substance` als
  sjabloon) — zou vooral waarde toevoegen bij groep 2 en 3 van §3.4, waar PubChem's eigen
  naam-matching de bron van onzekerheid is.
- **Consistentie van `csor:eea`** (166 variabelen) met een EC/EINECS-referentielijst — geen
  pasklare bron voorhanden binnen v1-scope.
- Automatische terugschrijving van correcties naar het register — dit rapport levert enkel
  bevindingen en suggesties aan, geen schrijfacties.

---

*Bijlage: `../sparql/csor-variabele-fetch.sparql` (paginatie-template) en
`../sparql/variabele_identity_checks.sparql` (interne consistentiechecks). Herproduceerbaar via
`python3 scripts/check_variabele_identity.py` (zie `../CLAUDE.md` voor venv-opzet). Volledige
resultaten in `../output/tables/cas_resolution.csv`, `../output/tables/cid_crosscheck.csv` en
`../output/tables/internal_flags.csv`.*
