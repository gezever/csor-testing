# Relaties tussen variabelen in het CSO-register

**Advies over compositierelaties, hiërarchie en vervanging — met empirische onderbouwing**

*Datum: 27 juli 2026*

---

## 1. Aanleiding en vraagstelling

In het CSO-register kunnen relaties tussen variabelen worden vastgelegd via `skos:broader` en `skos:narrower`, bijvoorbeeld om de verhouding tussen trichloorethyleen en zijn isomeren uit te drukken. Naar aanleiding daarvan zijn vier vragen gesteld.

De eerste vraag betreft de variabele *PFAS individueel*, die in lozingsvergunningen wordt gebruikt om aan te geven dat een reeks individuele PFAS elk afzonderlijk een normwaarde niet mag overschrijden. Inhoudelijk is bekend welke stoffen bedoeld worden, maar op codelijstniveau is die koppeling niet gelegd. Is `skos:related` daarvoor geschikt, of is een ander relatietype beter?

De tweede vraag betreft somparameters zoals *nitraat + nitriet in water*: moeten de samenstellende delen als relatie worden meegegeven, of bestaat die relatie al impliciet via de parameterafleiding? En mag `skos:broader`/`skos:narrower` daarvoor gebruikt worden?

De derde vraag betreft inactieve variabelen: kan met `dcterms:replaces` en `dcterms:isReplacedBy` worden aangegeven door welke variabele ze vervangen zijn?

De vierde vraag is overkoepelend: is het beter om eigen relaties te definiëren als subproperty van `skos:related`?

## 2. Advies op hoofdlijnen

`skos:broader` en `skos:narrower` blijven best gereserveerd voor echte generieke hiërarchie, waarbij het smallere concept een specialisatie is van het bredere (trichloorethyleen en zijn isomeren). Zowel de PFAS-koppeling als de somparameterrelatie is van een andere aard: de eerste is een normconstruct dat op stoffen van toepassing is, de tweede is compositioneel. Voor beide geldt bovendien dat `skos:related` op zich niet fout maar semantisch arm is: de property is symmetrisch en richtingloos en zegt niets over de aard van de relatie. Relevant is ook dat de SKOS-specificatie (integriteitsvoorwaarde S27) `skos:related` en `skos:broaderTransitive` disjunct verklaart: dezelfde twee concepten mogen niet én hiërarchisch én associatief gelinkt zijn.

Het advies is daarom om eigen, gerichte properties te definiëren als `rdfs:subPropertyOf skos:related`, telkens als invers paar met een heldere definitie in het csor-vocabularium. Generieke SKOS-tooling ziet dan nog steeds een related-link, terwijl de betekenis machine-leesbaar behouden blijft. Merk op dat een subproperty de symmetrie van `skos:related` niet erft; daarom worden per relatie twee inverse properties gedefinieerd. Voor de compositierelatie zijn dat `csor:heeftSamenstellendeVariabele` en `csor:isSamenstellendeVariabeleVan` (en desgewenst het analoge paar op parameterniveau). Voor *PFAS individueel* is een property in de trant van `csor:isVanToepassingOpStof` (met inverse) denkbaar; een alternatief is een `skos:Collection` met de betrokken stoffen als members, een mechanisme dat het register al kent (V_230 is lid van de collectie "Lijst van groepsparameters"), al verliest men daarmee de gerichte semantiek per stof.

### 2.1 Het SKOS-Thes-alternatief (ISO 25964) — overwogen en niet weerhouden

Een gestandaardiseerd alternatief voor de compositierelatie is SKOS-Thes, de SKOS-extensie op basis van het ISO 25964-datamodel (thesaurusnorm), gepubliceerd door DCMI op https://www.dublincore.org/specifications/skos-thes/. Die extensie definieert onder meer `iso-thes:broaderPartitive` en `iso-thes:narrowerPartitive` (de BTP/NTP-relatie uit ISO 25964-1) als subproperties van `skos:broader`/`skos:narrower`, precies bedoeld voor geheel-deel-verhoudingen. Op het eerste gezicht past dat op somvariabelen: *nitraat+nitriet* als geheel, *nitraat* en *nitriet* als delen, uitgedrukt met een bestaande, gedocumenteerde standaardproperty in plaats van een eigen vocabulariumuitbreiding.

Bij nadere afweging is deze optie om drie redenen niet weerhouden.

Ten eerste stelt ISO 25964 zelf een strikte gebruiksvoorwaarde aan BTP/NTP: de partitieve relatie is alleen bedoeld wanneer het deel *uniek* tot het geheel behoort. De specificatie illustreert dat met het fietswiel: een "bicycle wheel" hoort uniek bij een "bicycle", maar tussen "wheels" en "bicycles" mag géén BTP/NTP gelegd worden, omdat een wiel ook deel kan zijn van een auto of een kruiwagen. De CSOR-situatie is structureel het tweede geval: de empirische analyse (paragraaf 4) toont dat samenstellende variabelen typisch in *meerdere* sommen voorkomen — nitraat en nitriet zitten elk in vier somvariabelen, benzo(a)pyreen in zeven, en de PFAS-bestanddelen in tot zes geneste sommen. Volgens de gebruiksregel van de standaard zelf is BTP/NTP hier dus niet van toepassing.

Ten tweede zou de partitieve relatie, als subproperty van `skos:broader`, de somvariabelen alsnog in de SKOS-hiërarchie trekken. Dat botst met de uitgangspositie om `skos:broader`/`skos:narrower` te reserveren voor echte generieke hiërarchie (type-subtype, zoals trichloorethyleen en zijn isomeren), en het activeert bovendien SKOS-integriteitsvoorwaarde S27: concepten die hiërarchisch gelinkt zijn, mogen niet óók associatief (`skos:related`) gelinkt worden. Elke generieke SKOS-browser zou de bestanddelen bovendien als "narrower concepts" tonen, wat gebruikers op het verkeerde been zet over de aard van de relatie.

Ten derde, een praktisch punt: de partitieve properties dragen in de SKOS-Thes-namespace de status *proposed* (niet *released*), en ISO 25964 verwacht dat BTP/NTP-relaties in een conforme thesaurus voor transitieve sluiting kwalificeren — een verwachting waar de gegenereerde compositierelatie (die bewust vlak en niet-transitief per afleiding is) niet aan hoeft te voldoen.

De conclusie blijft daarom dat eigen inverse properties onder `skos:related` de juiste keuze zijn. SKOS-Thes blijft wel op twee punten relevant als referentie. De definities van `csor:heeftSamenstellendeVariabele`/`csor:isSamenstellendeVariabeleVan` kunnen in hun documentatie expliciet verwijzen naar de BTP/NTP-afweging (inclusief de reden waarom die niet gevolgd is), wat de keuze voor externe partijen navolgbaar maakt. En voor de *PFAS individueel*-vraag biedt SKOS-Thes met `iso-thes:ConceptGroup` (een subklasse van `skos:Collection`, bedoeld voor groepen concepten uit verschillende hiërarchieën) een net iets rijker gestandaardiseerd alternatief voor een kale `skos:Collection`, mocht voor de collectie-route gekozen worden.

### 2.2 Vervanging van inactieve variabelen

Voor vervanging van inactieve variabelen is `dcterms:isReplacedBy` (op het oude concept) met eventueel `dcterms:replaces` (op de opvolger) de gangbare en juiste keuze; dit patroon wordt breed toegepast in vocabularium-lifecycle-management, onder meer bij EU Vocabularies, vaak gecombineerd met `owl:deprecated true` en een `skos:changeNote`. Hier is géén eigen subproperty van `skos:related` nodig: vervanging is een lifecycle-relatie, geen associatieve begripsrelatie, en dcterms dekt dat precies.

## 3. Het CSOR-model: waar de compositiekennis zit

Uit inspectie van drie resources (parameter P_269 *Nitraat+nitriet in water*, afleiding AFL_38 en variabele V_230 *Nitraat+nitriet*) blijkt hoe het model in elkaar zit. De compositiekennis zit op parameterniveau volledig en machine-leesbaar in de afleiding: P_269 verwijst via `csor:heeftAfleiding` naar AFL_38 (een `csor:ParameterAfleidingVeelterm`), die via `csor:heeftTerm` termen bevat met elk een `csor:factor`, een vlag `csor:verplicht` en een `csor:heeftBronParameter` naar P_297 (*Nitraat in water*) en P_299 (*Nitriet in water*). De afleiding is daarmee méér dan een relatie: het is een rekenkundige specificatie. Op parameterniveau is de relatie tussen som en delen dus niet impliciet maar expliciet — alleen twee stappen diep, en via blank nodes, waardoor ze voor gebruikers van de HTML-weergave of generieke SKOS-browsers verstopt zit.

De variabele bleek verrassend kaal: V_230 draagt enkel een notatie, label, symbool en scheme-lidmaatschap — geen drager, eenheid, context of aspect. De variabele is dus niet "parameter plus extra dimensies" maar het abstracte, dragervrije stofbegrip; de parameter bindt dat begrip aan een drager (P_269 heeft `csor:heeftDrager` "water"), en de parameteraspecten voegen daar de grootheden aan toe (P_269 heeft er vijf, van massaconcentratie tot vracht per tijd). De koppeling loopt via `csor:heeftVariabele` van parameter naar variabele.

Dat heeft twee gevolgen voor de vraagstelling. Ten eerste is een inhoudelijke matchingregel op variabeleniveau onmogelijk én overbodig: er valt bij een variabele niets te matchen. De afleidbaarheid van samenstellende variabelen hangt daardoor volledig af van kardinaliteit. Ten tweede is het uitgangspunt dat relaties alleen expliciet worden vastgelegd waar ze informatie toevoegen die niet afleidbaar is: op parameterniveau is de compositie afleidbaar (hoogstens automatisch te materialiseren), en de vraag was of dat op variabeleniveau ook geldt.

## 4. Empirische toetsing

De afleidbaarheid is met een reeks SPARQL-queries op het register getoetst (zie het bijgevoegde querybestand). De resultaten worden hieronder samengevat.

### 4.1 Kardinaliteit (queries 1a en 1b)

Query 1a toetste of een parameter ooit meer dan één actieve variabele heeft: het antwoord is **nee** (0 records). Het pad somvariabele → doelparameter → afleiding → bronparameter → variabele levert dus altijd hoogstens één kandidaat op, waarmee de samenstellende variabelen in beginsel deterministisch afleidbaar zijn.

Query 1b toetste de omgekeerde richting en leverde een omvangrijk resultaat: **1046 variabelen** worden door meerdere parameters gedeeld, met als uitschieters Koolstof (27 parameters), Arseen (26) en een reeks metalen rond de 25. Dit bevestigt dat de variabele het matrix-onafhankelijke stofbegrip is. Het blokkeert de generatie niet, maar bleek later wel de verklaring voor een klasse van artefacten (zie 4.3).

### 4.2 Volledigheid (query 2) en het triazool-geval

Query 2 telde voor elke somvariabele en elke bronparameter de kandidaat-variabelen. Op het hele register bleven precies twee probleemrijen over, beide met nul kandidaten en beide behorend tot één geval: de somvariabele *1,2,4-Triazool* (V_1533) met als bronparameters *3H-1,2,4-Triazool in water* (P_2344) en *4H-1,2,4-Triazool in water* (P_2345). Verder is met een aparte controle vastgesteld dat **elke actieve parameter in het register een variabele heeft** (0 records zonder): het registratiebeleid is dus volledige dekking, en het triazool-geval is de enige afwijking.

Detailonderzoek van die afwijking bracht de werkelijke toedracht aan het licht. De variabelen voor de tautomeren bestáán wel degelijk (V_1535 *3H-1,2,4-Triazool* en V_1536 *4H-1,2,4-Triazool*), maar zijn **gedeprecieerd**, terwijl de bijbehorende parameters actief zijn en er géén `dcterms:isReplacedBy` op de gedeprecieerde variabelen staat. Query 2 kwam op nul kandidaten uit doordat ze — correct — op `owl:deprecated` filtert.

Deze toedracht laat zich chemisch goed lezen. Tautomeren zijn gedaanten van dezelfde verbinding die enkel in de positie van één proton verschillen, in oplossing continu in elkaar overgaan en analytisch niet afzonderlijk bepaald worden. Op het niveau van het abstracte stofbegrip — precies wat de variabele in het CSOR-model is — zijn de tautomeren dus één stof, en het deprecieren van de afzonderlijke tautomeer-variabelen ten gunste van het generieke triazool-begrip is op dat niveau een verdedigbare, zelfs elegante keuze. De parameters kunnen daarnaast blijven bestaan omdat zij een andere rol vervullen (registratie van entries uit externe stoffenlijsten met eigen identificatie). Of dit inderdaad de intentie was, dient wel bij de registerbeheerders geverifieerd te worden; het is een reconstructie op basis van de data.

Wat er in elk geval ontbreekt, is de lifecycle-administratie — en daarmee sluit dit geval rechtstreeks aan bij de derde vraag uit de oorspronkelijke mail (paragraaf 2.2): V_1535 en V_1536 zijn gedeprecieerd zonder `dcterms:isReplacedBy`, terwijl dat er behoort te staan (vermoedelijk verwijzend naar V_1533, het generieke triazool-begrip). De aanbeveling is daarom drieledig: de deprecatie behouden (mits de intentie bevestigd wordt), `dcterms:isReplacedBy` toevoegen op V_1535 en V_1536 conform het vervanging­spatroon uit paragraaf 2.2, en bij V_1533 een `skos:editorialNote` opnemen die uitlegt dat de compositie voor dit geval bewust alleen op parameterniveau gepubliceerd wordt — op variabeleniveau vallen de bestanddelen immers samen met het geheel. De generatie (query 3) handelt dit vanzelf correct af door de deprecated-filter. Als bewaking verdient het aanbeveling een integriteitscheck toe te voegen op het patroon dat dit geval verried: actieve parameters waarvan de (enige) variabele gedeprecieerd is.

### 4.3 Semantische zuivering (CONSTRUCT-proef, queries 4 en 5)

Een eerste proefgeneratie van de relaties legde twee patronen bloot die in een compositierelatie niet thuishoren.

Het eerste patroon zijn **zelfverwijzingen**: onder meer Arseen, Cadmium, Chroom, Koper, Kwik, Lood, Nikkel en Zink (V_329, V_333, V_335, V_339, V_340, V_341, V_344, V_351) en verder V_420 en V_47 "bestonden uit zichzelf". De oorzaak is het gedeelde-variabele-patroon uit 4.1: afleidingen tussen twee parameters van dezelfde variabele — bijvoorbeeld tussen opgeloste en totale fractie van eenzelfde metaal — klappen op variabeleniveau samen tot een betekenisloze zelfloop.

Het tweede patroon zijn **wederzijdse paren** (V_231 ↔ V_798, V_47 ↔ V_424, V_787 ↔ V_860): variabelen die elkaar over en weer als bestanddeel hadden. Dat verraadt een fundamenteler punt: een veelterm-afleiding drukt *berekenbaarheid* uit, en die valt alleen met *samenstelling* samen als het om een echte som gaat.

Query 4 lijstte alle afleidingen met niet-positieve factoren op en bevestigde dit exact. Het gaat om zeven verschil-afleidingen in twee families:

| Afleiding | Doelparameter | Aard |
|---|---|---|
| AFL_62 | Kjeldahlstikstof in water = N totaal − nitriet − nitraat | verschilberekening (verklaart cyclus V_231 ↔ V_798) |
| AFL_1, AFL_5, AFL_20, AFL_33, AFL_66, AFL_76 | "= X-totaal − X in water" voor PFOS, PFOA, MePFOSA, EtPFOSA, PFOSA, PFHxS | PFAS-precursorbepaling: verschil tussen totaal (na oxidatie) en directe meting |

Van deze grootheden wil men uitdrukkelijk niet zeggen dat ze "bestaan uit" de afgetrokken stof.

Query 5 lijstte vervolgens alle afleidingen met precies één term op. Alle zeven bleken omrekeningen of schattingen, geen composities:

| Afleiding | Relatie | Factor |
|---|---|---|
| AFL_82 / AFL_2 | Chemisch zuurstofverbruik ↔ Koolstof organisch totaal | 3 / 0,3333 |
| AFL_4 / AFL_85 | Geleidbaarheid 20 °C ↔ 25 °C | 0,9045 / 1,0955 |
| AFL_111 | Chloor en anorganische verbindingen ← Chloorverbindingen (lucht) | 1,0288 |
| AFL_110 | Fluor en anorganische verbindingen ← Fluorverbindingen (lucht) | 1,0526 |
| AFL_90 | Koolstof organisch totaal ← Koolstof organisch niet purgeerbaar | 1 |

De paren CZV ↔ TOC en EC20 ↔ EC25 verklaren de resterende cycli V_47 ↔ V_424 en V_787 ↔ V_860. Belangrijk is dat gevallen als V_1533 → V_1534 (triazool) *niet* in deze lijst voorkomen: daar heeft de afleiding zelf meerdere termen en ontbreekt slechts een variabele bij een bronparameter. Een filter op "minstens twee termen" snijdt dus precies de conversies weg en raakt de echte composities niet.

## 5. Definitie en generatie van de compositierelatie

De relatie `csor:heeftSamenstellendeVariabele` (met inverse `csor:isSamenstellendeVariabeleVan`) wordt gedefinieerd als: afgeleid uit veelterm-afleidingen die **echte sommen** zijn. Concreet betekent dat drie criteria, elk met een inhoudelijke rechtvaardiging uit paragraaf 4:

alle factoren van de afleiding zijn positief (verschilberekeningen zoals Kjeldahlstikstof en de PFAS-precursorbepalingen zijn berekeningen, geen composities); de afleiding telt minstens twee termen (eenledige afleidingen zijn omrekeningen of schattingen); en doel- en bronvariabele verschillen (fractie-relaties binnen eenzelfde stof zijn parameterniveau-kennis).

De relaties worden **niet handmatig beheerd** maar bij elke publicatie vers gegenereerd uit de afleidingen, zodat ze per constructie nooit uit de pas kunnen lopen met de bron van waarheid. De generatie gebeurt met onderstaande SPARQL CONSTRUCT (query 3 in het bijgevoegde bestand):

```sparql
PREFIX csor: <https://data.omgeving.vlaanderen.be/ns/csor#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>

CONSTRUCT {
  ?somVariabele csor:heeftSamenstellendeVariabele ?kandidaat .
  ?kandidaat csor:isSamenstellendeVariabeleVan ?somVariabele .
}
WHERE {
  ?doelParameter csor:heeftVariabele ?somVariabele ;
                 csor:heeftAfleiding ?afleiding .
  ?afleiding a csor:ParameterAfleidingVeelterm ;
             csor:heeftTerm ?term .
  ?term csor:heeftBronParameter ?bronParameter .
  ?bronParameter csor:heeftVariabele ?kandidaat .

  # (b) geen zelfverwijzingen
  FILTER (?somVariabele != ?kandidaat)

  # (a) alleen afleidingen waarvan alle termen een positieve factor hebben
  FILTER NOT EXISTS {
    ?afleiding csor:heeftTerm/csor:factor ?f .
    FILTER (?f <= 0)
  }

  # (c) alleen afleidingen met minstens twee termen (echte sommen)
  ?afleiding csor:heeftTerm ?t1 , ?t2 .
  FILTER (?t1 != ?t2)

  FILTER NOT EXISTS { ?somVariabele owl:deprecated true }
  FILTER NOT EXISTS { ?kandidaat owl:deprecated true }
}
```

Hetzelfde principe kan desgewenst op parameterniveau worden toegepast (`csor:heeftSamenstellendeParameter`), gegenereerd uit exact hetzelfde pad zonder de variabele-stap. Aangezien variabelen breed gedeeld worden over dragers heen, is het parameterniveau eigenlijk het natuurlijkere niveau voor compositie (daar zit de drager-context); de variabele-relatie is vooral een gebruiksvriendelijke afgeleide voor toepassingen — zoals lozingsvergunningen — die op variabeleniveau werken. Beide uit dezelfde afleidingen genereren houdt het geheel consistent.

Aanbevolen wordt in de publicatiepijplijn een sanity check op te nemen die faalt zodra de gegenereerde output een zelfloop of een wederzijds paar (`A heeftSamenstellendeVariabele B` én `B heeftSamenstellendeVariabele A`) bevat. Zo wordt het meteen zichtbaar wanneer een toekomstige afleiding het patroon doorbreekt.

## 6. Conclusies

De relatie tussen somvariabelen en hun bestanddelen hoeft niet gemodelleerd maar kan afgeleid worden — mits "afleiding" en "samenstelling" scherp onderscheiden worden. Het register bleek zelf de drie gevallen te bevatten die dat onderscheid noodzakelijk maken: verschilberekeningen, omrekeningen en fractie-relaties. De compositierelatie is daarmee een gedefinieerde, reproduceerbare projectie van de afleidingen, met één bekend restpunt: de gedeprecieerde tautomeer-variabelen bij triazool, waar geen inhoudelijke ingreep maar lifecycle-administratie (`dcterms:isReplacedBy` en een editorial note) nodig is (paragraaf 4.2).

Samengevat per oorspronkelijke vraag: echte generieke hiërarchie blijft bij `skos:broader`/`skos:narrower`; de compositie van somvariabelen wordt automatisch gegenereerd als eigen invers property-paar onder `skos:related`, waarbij het gestandaardiseerde alternatief `iso-thes:broaderPartitive`/`narrowerPartitive` uit SKOS-Thes bewust niet gevolgd wordt omdat de bestanddelen niet uniek tot één geheel behoren en de compositie niet in de `skos:broader`-hiërarchie thuishoort (paragraaf 2.1); vervanging van inactieve variabelen verloopt via `dcterms:isReplacedBy`/`dcterms:replaces` met `owl:deprecated`; en alleen *PFAS individueel* vergt nog een echte modelleerbeslissing — een eigen gerichte property onder `skos:related`, dan wel een `skos:Collection` of `iso-thes:ConceptGroup` — omdat die koppeling nergens formeel in het model zit en dus handmatig vastgelegd en beheerd zal moeten worden.

---

*Bijlage: `../sparql/samenstellende_variabelen_check.sparql` met de queries 0 t.e.m. 5 (verkenning, kardinaliteitstoetsen, consistentietoets, volledigheids­toets, generatie en diagnoses).*