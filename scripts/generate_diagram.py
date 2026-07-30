"""
generate_diagram.py — deterministisch TikZ/LaTeX-diagram van het CSOR-datamodel

PURPOSE
-------
Genereert een diagram van de 10 CSOR-"codelijst"-klassen, hun onderlinge relaties, én hun
koppeling met externe referentievocabularia (QUDT voor Eenheid, PubChem voor Variabele),
rechtstreeks afgeleid uit een live query op de graph (geen handmatig getekend schema),
gerenderd als TikZ en gecompileerd naar PDF (+ een PNG-preview voor README.md). Vervangt een
eerdere Mermaid-versie: die bleek bij complexere relaties (dubbele/tegengestelde koppelingen
tussen dezelfde twee klassen) minder leesbaar dan een expliciet gelayoute TikZ-figuur.

DATA PROVENANCE
----------------
Bron: de lokale volledige-registersnapshot (`analyse/csor_merged.ttl`), bij elke
`scripts/run_all.py`-run vers geregenereerd door `scripts/common/dataset.py::fetch_and_save()`
(zelfde snapshot als de vijf check_*.py-scripts).
Voor elke relatie in RELATION_PROPERTIES wordt empirisch bepaald tot welke `csor:`-klasse de
subjecten/objecten behoren — `rdfs:domain`/`rdfs:range` staan in CSOR zelf niet betrouwbaar
ingevuld (meestal leeg) en zijn dus geen bruikbare bron.

METHODOLOGY
-----------
- Datalaag: RELATION_PROPERTIES is een curated lijst van de relaties tussen de 10
  codelijst-klassen (dezelfde lijst als Bevinding 1 in
  reports/rapport_conceptschemas_en_qudt.md); domein/bereik en kardinaliteit worden empirisch
  bepaald en per domeinklasse/bereikklasse geschaald (zie cardinality()) — via directe
  `graph.subject_objects()`-iteratie + Python dict/set-telling, niet via SPARQL-subqueries: een
  geneste-aggregaat-SPARQL-query per domein/bereik-combinatie (tot 12 properties x 10 x 10 x 2
  richtingen) bleek in rdflib's pure-Python-engine catastrofaal traag (één zo'n query mat 88s op
  de 274.931-triple lokale graph) — zie ook CLAUDE.md §6. Own addition —
  volledigheidscontrole van deze lijst: gevalideerd tegen een automatische schema-extractie
  (`CONSTRUCT {{?type ?p ?datatype}} WHERE {{?s a ?type ; ?p ?o . ...}}`, naar het patroon van
  `/home/gehau/git/RIE-IEPR/documentatie/datamodel/archief/model.rq`) op de volledige, lokaal
  samengevoegde CSOR-graph (alle 10 named graphs via `sparql_client.fetch_graph`, gemerged met
  rdflib). Die kruiscontrole bracht twee eerder gemiste relaties aan het licht die nu wél in
  RELATION_PROPERTIES staan: `csor:heeftAspect` (ParameterAspect -> Kwantificeerbaar-
  /KwalificeerbaarAspect) en `skos:broader` (Eenheid -> Eenheid, zelfreferentieel — zie de
  self-loop-rendering hieronder). Curated blijft niettemin bewust de keuze: de overige, bij de
  schema-extractie ook gevonden relaties naar de 7 structurele/rekenkundige klassen
  (afleidingen, termen) zijn er bewust uitgelaten voor leesbaarheid — zie CODELIJST_CLASSES.
- Layout (own addition, geïnspireerd op de aanpak in
  ../A-Substance-Is-Not-Always-a-Substance/poster/poster/kgdiagram.py — vaste rijen i.p.v.
  een force-directed layout, zodat de output altijd deterministisch en overlap-vrij is):
  ROWS legt de klassen in een vaste, inhoudelijk gemotiveerde volgorde vast (Variabele boven-
  aan, via Parameter naar Drager/ParameterAspect/SoortWaardebepaling, naar Eenheid, naar
  KwantificeerbaarAspect/NatuurkundigeDimensie, naar Resultaattype/KwalificeerbaarAspect).
  Boxposities worden per rij programmatisch berekend (gecentreerd, vaste breedte/gap) — nooit
  handmatig met de hand geplaatste coördinaten.
- Randen tussen aangrenzende rijen: rechte lijn tussen node-ankers. Randen tussen twee
  klassen die *twee* relaties in tegengestelde richting hebben (bv. Eenheid<->
  KwantificeerbaarAspect: heeftKwantificeerbaarAspect + toepasbareEenheid) of tussen klassen
  in dezelfde rij: `bend left`/`bend right` (TikZ-ingebouwd), zodat ze nooit exact
  overlappen. Een zelfreferentiële relatie (domein == bereik, bv. `skos:broader` tussen
  Eenheid-concepten onderling) krijgt een `loop above`-lus i.p.v. een gewone rand. Elke rand
  die meerdere rijen overslaat (bv. `uitgedruktIn`, `heeftAspect`) wordt expliciet via de
  linkermarge geroute: eerst recht omlaag uit de onderkant van de bronbox (in de lege ruimte
  tussen twee rijen, niet dwars door een buur in dezelfde rij zoals Drager), dan pas naar
  links; elke zo'n rand krijgt bovendien een eigen, gestaggerde x-positie in de marge, anders
  overlappen meerdere lange-sprong-randen exact zodra hun y-bereik overlapt.
- Externe koppelingen (QUDT, PubChem, zie external_relations()): geen CSOR-interne
  object-property, dus apart van RELATION_PROPERTIES/build_relations() gehouden. Elk als
  extra kolom in dezelfde rij als de klasse waaraan gekoppeld wordt (PubChem naast Variabele,
  QUDT naast Eenheid — bewust links van Eenheid geplaatst, niet rechts: rechts zitten al de
  Eenheid<->NatuurkundigeDimensie-bochten, en de korte externe rand zou daar middenin
  terechtkomen). Gestippelde rand/lijn in een aparte kleur (extern/extrel-stijl) om ze visueel
  te onderscheiden van CSOR-interne relaties. Own addition: het label staat LOS boven de
  verbindingslijn (`\\node ... above at ($(A)!0.5!(B)$)`) i.p.v. als pad-node erop — bij de
  korte afstand tussen een klasse en haar externe koppeling zou een pad-node de hele lijn
  aan het zicht onttrekken.
- Determinisme: klassen/relaties eerst gesorteerd (alfabetisch), daarna pas gerenderd; een
  overlap-validatie (zoals kgdiagram.py) faalt hard als twee boxen elkaar toch raken.
- Compilatie: `pdflatex` (non-interactief, `-halt-on-error`), daarna `pdftoppm` voor een
  PNG-preview (GitHub rendert geen inline PDF in Markdown, wel PNG).

INTERPRETATION
--------------
Het diagram toont de STRUCTUUR (klassen, relaties, kardinaliteit als "1"/"0..1"/"1..N"/"0..N"
i.p.v. crow's-foot-symbolen, voor leesbaarheid zonder ER-notatiekennis) — voor de concrete
datakwaliteitsbevindingen zie de volledige rapporten in reports/.

OUTPUTS
-------
output/diagrams/csor_model.tex
output/diagrams/csor_model.pdf
output/diagrams/csor_model.png
README.md, bijgewerkt tussen de markers <!-- CSOR-DIAGRAM:START/END -->
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dataset, sparql_client as sc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAM_DIR = REPO_ROOT / "output" / "diagrams"
README_PATH = REPO_ROOT / "README.md"
TEX_NAME = "csor_model"

PREFIXES = (
    "PREFIX csor: <https://data.omgeving.vlaanderen.be/ns/csor#>\n"
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
)


def qualify(prop: str) -> str:
    """Geeft `prop` terug als volledige CURIE — properties zonder ':' worden verondersteld
    csor:-eigen te zijn (de meerderheid); `skos:broader` e.d. worden ongewijzigd doorgegeven."""
    return prop if ":" in prop else f"csor:{prop}"


MARKER_START = "<!-- CSOR-DIAGRAM:START -->"
MARKER_END = "<!-- CSOR-DIAGRAM:END -->"

# Own addition: deze lijst is niet met de hand samengesteld maar gecontroleerd tegen een
# automatische schema-extractie (CONSTRUCT ?type ?p ?datatype WHERE {...}, naar het patroon
# van /home/gehau/git/RIE-IEPR/documentatie/datamodel/archief/model.rq) op de volledige,
# lokaal samengevoegde CSOR-graph — dat is exact hoe `heeftAspect` en `skos:broader` aan het
# licht kwamen, beide eerder gemist in een handmatig samengestelde lijst. Zie METHODOLOGY.
RELATION_PROPERTIES = [
    "heeftVariabele",
    "heeftDrager",
    "heeftParameterAspect",
    "heeftAspect",
    "heeftSoortWaardebepaling",
    "heeftNatuurkundigeDimensie",
    "heeftKwantificeerbaarAspect",
    "toepasbareEenheid",
    "referentieEenheid",
    "heeftResultaattype",
    "uitgedruktIn",
    "skos:broader",
]

CODELIJST_CLASSES = [
    "Variabele",
    "Parameter",
    "ParameterAspect",
    "Eenheid",
    "Drager",
    "KwalificeerbaarAspect",
    "KwantificeerbaarAspect",
    "NatuurkundigeDimensie",
    "SoortWaardebepaling",
    "Resultaattype",
]

# Externe referentievocabularia (geen csor:-klasse, dus geen skos:inScheme/class_totals) —
# zie reports/rapport_variabele_identiteit.md (PubChem) en
# reports/rapport_conceptschemas_en_qudt.md §3.4 (QUDT). Elk gekoppeld aan precies één
# CSOR-klasse via een vast predicaat.
EXTERNAL_NODES = ["QUDT", "PubChem"]
PUBCHEM_PRED = "<https://pubchem.ncbi.nlm.nih.gov/rest/rdf/compound>"

# Vaste, inhoudelijk gemotiveerde rij-indeling (zie METHODOLOGY) — bepaalt enkel de layout,
# niet welke relaties bestaan (die komen uit de live query). Externe nodes staan als extra
# kolom naast de CSOR-klasse waaraan ze gekoppeld zijn (PubChem naast Variabele, QUDT naast
# Eenheid), zodat de koppelrelatie een korte, rechte rand blijft.
ROWS: list[list[str]] = [
    ["Variabele", "PubChem"],
    ["Parameter"],
    ["Drager", "ParameterAspect", "SoortWaardebepaling"],
    ["QUDT", "Eenheid"],
    ["KwantificeerbaarAspect", "NatuurkundigeDimensie"],
    ["KwalificeerbaarAspect", "Resultaattype"],
]
ROW_OF = {cls: i for i, row in enumerate(ROWS) for cls in row}

BOX_W, BOX_H = 4.4, 1.5  # cm
COL_GAP, ROW_PITCH = 1.8, 3.6  # cm
# Extra verticale ruimte vóór een specifieke rij-index (own addition) — rij 4
# (KwantificeerbaarAspect/NatuurkundigeDimensie) heeft vier randen naar/van Eenheid samen op
# een kluitje, dat vraagt meer ademruimte dan de rest van het diagram.
EXTRA_ROW_GAP = {4: 1.6}


# ------------------------------------------------------------ datalaag

# Own addition, performance: class_membership()/cardinality() waren oorspronkelijk SPARQL-query's
# per aanroep, met cardinality() zelfs een geneste-subquery-aggregaat (SELECT MIN/MAX/COUNT
# WHERE { SELECT ?s (COUNT(DISTINCT ?o)...) GROUP BY ?s }). build_relations() roept die op voor
# elke domein x bereik-combinatie van elke property — tot 12 x 10 x 10 x 2 keer. Eén zo'n geneste
# query mat empirisch 88 seconden op de 274.931-triple lokale graph (rdflib's pure-Python
# SPARQL-engine evalueert geneste aggregaten zeer inefficiënt); dat zou de volledige pijplijnrun
# tot ver over een uur oprekken. De onderstaande helpers reproduceren exact dezelfde semantiek
# via directe graph.subject_objects()-iteratie + Python dict/set-telling, in milliseconden.

NS_MAP = {
    "csor": "https://data.omgeving.vlaanderen.be/ns/csor#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}


def resolve_predicate(prop: str) -> rdflib.URIRef:
    prefix, local = qualify(prop).split(":", 1)
    return rdflib.URIRef(NS_MAP[prefix] + local)


def build_type_index(graph: rdflib.Graph) -> dict:
    """{subject: {klasse-naam, ...}} voor elke instantie van een CODELIJST_CLASSES-klasse."""
    idx: dict = {}
    for cls in CODELIJST_CLASSES:
        cls_uri = rdflib.URIRef(f"{NS_MAP['csor']}{cls}")
        for s in graph.subjects(rdflib.RDF.type, cls_uri):
            idx.setdefault(s, set()).add(cls)
    return idx


def class_totals(type_idx: dict) -> dict[str, int]:
    totals = {cls: 0 for cls in CODELIJST_CLASSES}
    for classes in type_idx.values():
        for cls in classes:
            totals[cls] += 1
    return totals


def property_pairs(prop: str, graph: rdflib.Graph) -> list[tuple]:
    return list(graph.subject_objects(resolve_predicate(prop)))


def class_membership(pairs: list[tuple], position: str, type_idx: dict) -> dict[str, int]:
    """position: 's' (subject) of 'o' (object). Geeft {klasse: aantal distincte instanties} terug."""
    idx = 0 if position == "s" else 1
    per_class: dict = {}
    for pair in pairs:
        node = pair[idx]
        for cls in type_idx.get(node, ()):
            per_class.setdefault(cls, set()).add(node)
    return {cls: len(instances) for cls, instances in per_class.items()}


def cardinality(
    pairs: list[tuple], direction: str, domain_class: str, range_class: str, type_idx: dict
) -> dict:
    """Kardinaliteit, geschaald op zowel de domein- als de bereikklasse — nodig omdat sommige
    properties meerdere domeinklassen (bv. heeftNatuurkundigeDimensie op zowel Eenheid als
    KwantificeerbaarAspect) én meerdere bereikklassen hebben (bv. heeftAspect naar zowel
    KwantificeerbaarAspect als KwalificeerbaarAspect) — zonder deze dubbele scoping zouden
    per-klasse-verschillen samenklappen tot één (mogelijk misleidend) cijfer."""
    filtered = [
        (s, o)
        for s, o in pairs
        if domain_class in type_idx.get(s, ()) and range_class in type_idx.get(o, ())
    ]
    group: dict = {}
    if direction == "forward":
        for s, o in filtered:
            group.setdefault(s, set()).add(o)
    else:
        for s, o in filtered:
            group.setdefault(o, set()).add(s)
    counts = [len(v) for v in group.values()]
    return {
        "min": min(counts) if counts else 0,
        "max": max(counts) if counts else 0,
        "aantal": len(counts),
    }


def split_camel_case(name: str) -> str:
    """'heeftNatuurkundigeDimensie' -> 'heeft Natuurkundige Dimensie' — own addition, puur
    voor leesbaarheid/regelafbreking in het diagram (de property-URI zelf blijft camelCase,
    dit is enkel de weergave)."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


def cardinality_label(max_val: int, zero_allowed: bool) -> str:
    many = max_val > 1
    if many:
        return "0..N" if zero_allowed else "1..N"
    return "0..1" if zero_allowed else "1"


def build_relations(totals: dict[str, int], graph: rdflib.Graph, type_idx: dict) -> list[dict]:
    relations = []
    for prop in RELATION_PROPERTIES:
        pairs = property_pairs(prop, graph)
        subj_classes = class_membership(pairs, "s", type_idx)
        obj_classes = class_membership(pairs, "o", type_idx)
        for domain_class in sorted(subj_classes):
            for range_class in sorted(obj_classes):
                fwd = cardinality(pairs, "forward", domain_class, range_class, type_idx)
                if fwd["aantal"] == 0:
                    continue  # deze domein/bereik-combinatie komt niet voor
                bwd = cardinality(pairs, "backward", domain_class, range_class, type_idx)
                zero_fwd = fwd["aantal"] < totals.get(domain_class, 0)
                zero_bwd = bwd["aantal"] < totals.get(range_class, 0)
                relations.append(
                    {
                        "domain": domain_class,
                        "range": range_class,
                        "property": prop,
                        "left_label": cardinality_label(bwd["max"], zero_bwd),
                        "right_label": cardinality_label(fwd["max"], zero_fwd),
                    }
                )
    return sorted(relations, key=lambda r: (r["domain"], r["property"], r["range"]))


def external_relations(totals: dict[str, int], graph: rdflib.Graph) -> list[dict]:
    """Koppelingen naar externe referentievocabularia (QUDT, PubChem) — apart van
    build_relations() omdat het geen CSOR-interne object-property met domein/bereik binnen
    CODELIJST_CLASSES is, en de kardinaliteit hier als dekkingsbreuk (n/totaal) i.p.v.
    (kant-A, kant-B) leesbaarder is."""
    qudt_q = (
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        + PREFIXES
        + """
    SELECT ?matchType (COUNT(DISTINCT ?e) AS ?n) WHERE {
      ?e a csor:Eenheid .
      { ?e skos:exactMatch ?q . BIND("exactMatch" AS ?matchType) }
      UNION { ?e skos:closeMatch ?q . BIND("closeMatch" AS ?matchType) }
      UNION { ?e skos:broadMatch ?q . BIND("broadMatch" AS ?matchType) }
      UNION { ?e skos:narrowMatch ?q . BIND("narrowMatch" AS ?matchType) }
      UNION { ?e skos:relatedMatch ?q . BIND("relatedMatch" AS ?matchType) }
      FILTER(STRSTARTS(STR(?q), "http://qudt.org/"))
    }
    GROUP BY ?matchType
    ORDER BY ?matchType
    """
    )
    qudt_df = sc.select_dataframe_local(qudt_q, graph)
    qudt_breakdown = ", ".join(f"{n} {mt}" for mt, n in zip(qudt_df["matchType"], qudt_df["n"]))
    qudt_total = int(qudt_df["n"].astype(int).sum()) if len(qudt_df) else 0

    pubchem_q = (
        PREFIXES
        + f"""
    SELECT (COUNT(DISTINCT ?v) AS ?n) WHERE {{
      ?v a csor:Variabele .
      ?v {PUBCHEM_PRED} ?cid .
    }}
    """
    )
    pubchem_total = int(sc.select_dataframe_local(pubchem_q, graph).iloc[0]["n"])

    return [
        {
            "domain": "Eenheid",
            "range": "QUDT",
            "coverage": f"{qudt_total}/{totals.get('Eenheid', 0)} eenheden",
            "detail": qudt_breakdown,
        },
        {
            "domain": "Variabele",
            "range": "PubChem",
            "coverage": f"{pubchem_total}/{totals.get('Variabele', 0)} variabelen",
            "detail": "pubchem:compound (CID-koppeling)",
        },
    ]


# ------------------------------------------------------------ layout


def compute_boxes() -> dict[str, tuple[float, float, float, float]]:
    """{klasse: (x_links, y_boven, w, h)} in cm, oorsprong linksboven, y neemt toe naar onder."""
    row_widths = [len(row) * BOX_W + (len(row) - 1) * COL_GAP for row in ROWS]
    canvas_w = max(row_widths)
    boxes = {}
    y = 0.0
    for i, row in enumerate(ROWS):
        if i > 0:
            y += ROW_PITCH + EXTRA_ROW_GAP.get(i, 0.0)
        row_w = row_widths[i]
        x = (canvas_w - row_w) / 2
        for cls in row:
            boxes[cls] = (x, y, BOX_W, BOX_H)
            x += BOX_W + COL_GAP
    return boxes


def validate_layout(boxes: dict[str, tuple[float, float, float, float]]) -> None:
    names = list(boxes)
    for i, a in enumerate(names):
        ax, ay, aw, ah = boxes[a]
        for b in names[i + 1 :]:
            bx, by, bw, bh = boxes[b]
            overlap = not (
                ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
            )
            if overlap:
                raise SystemExit(f"LAYOUT-FOUT: {a} en {b} overlappen — pas ROWS/BOX_W aan.")


# ------------------------------------------------------------ rendering


def render_tikz(
    totals: dict[str, int],
    relations: list[dict],
    external_rel: list[dict],
    boxes: dict[str, tuple[float, float, float, float]],
) -> str:
    canvas_w = max(x + w for x, _, w, _ in boxes.values())
    canvas_h = max(y + h for _, y, _, h in boxes.values())

    lines = [
        "% Automatisch gegenereerd door scripts/generate_diagram.py — niet handmatig bewerken.",
        "\\documentclass[tikz,border=4mm]{standalone}",
        "\\usetikzlibrary{arrows.meta,positioning,calc}",
        "\\definecolor{csorbox}{HTML}{EDF2FB}",
        "\\definecolor{csorline}{HTML}{1B3A6B}",
        "\\definecolor{extbox}{HTML}{FBF2E3}",
        "\\definecolor{extline}{HTML}{8A5A00}",
        "\\begin{document}",
        "\\begin{tikzpicture}[",
        "  every node/.style={font=\\sffamily\\small},",
        "  klasse/.style={draw=csorline, fill=csorbox, line width=0.5mm, rounded corners=1.5mm,",
        "    minimum width=" + f"{BOX_W}cm, minimum height={BOX_H}cm, text width={BOX_W - 0.5}cm,",
        "    align=center, anchor=north west},",
        "  extern/.style={draw=extline, fill=extbox, line width=0.5mm, rounded corners=1.5mm,",
        "    dash pattern=on 2.4mm off 1.2mm,",
        "    minimum width=" + f"{BOX_W}cm, minimum height={BOX_H}cm, text width={BOX_W - 0.5}cm,",
        "    align=center, anchor=north west},",
        "  rel/.style={-{Stealth[length=2.2mm]}, line width=0.35mm, csorline},",
        "  extrel/.style={-{Stealth[length=2.2mm]}, line width=0.35mm, extline,",
        "    dash pattern=on 2.4mm off 1.2mm},",
        "  lbl/.style={font=\\sffamily\\tiny, fill=white, inner sep=0.4mm, align=center,",
        "    text=csorline, text width=2.1cm},",
        "  extlbl/.style={font=\\sffamily\\tiny, fill=white, inner sep=0.4mm, align=center,",
        "    text=extline, text width=2.4cm}",
        "]",
    ]

    for cls in sorted(boxes):
        x, y, _, _ = boxes[cls]
        if cls in EXTERNAL_NODES:
            lines.append(
                f"\\node[extern] ({cls}) at ({x:.3f},{-y:.3f}) "
                f"{{\\textbf{{{cls}}}\\\\[0.5mm]\\footnotesize extern vocabularium}};"
            )
        else:
            count = totals.get(cls, 0)
            lines.append(
                f"\\node[klasse] ({cls}) at ({x:.3f},{-y:.3f}) "
                f"{{\\textbf{{{cls}}}\\\\[0.5mm]\\footnotesize {count} concepten}};"
            )

    # Randen: rechte lijn tussen aangrenzende rijen (default); bend bij duplicaat-paar of
    # zelfde rij; expliciete linkermarge-route bij een sprong van >=2 rijen. Labels op
    # meerdere randen die in hetzelfde vlak samenkomen (bv. Parameter -> 3 kinderen) worden
    # op verschillende `pos`-fracties langs hun rand geplaatst, anders vallen ze samen.
    pair_seen: dict[tuple[str, str], int] = {}
    leftmost = min(x for x, _, _, _ in boxes.values())
    straight_pos_cycle = [0.52, 0.30, 0.74, 0.40, 0.64]
    straight_index_by_box: dict[str, int] = {}
    long_jump_index = 0

    for r in relations:
        a, b, prop = r["domain"], r["range"], r["property"]
        row_delta = abs(ROW_OF[a] - ROW_OF[b])
        pair_key = tuple(sorted((a, b)))
        pair_seen[pair_key] = pair_seen.get(pair_key, 0) + 1
        is_second_of_pair = pair_seen[pair_key] == 2

        prop_display = split_camel_case(prop)
        label = f"({r['left_label']}, {r['right_label']})\\\\{prop_display}"
        if a == b:
            # Zelfreferentiële relatie (bv. skos:broader tussen Eenheid-concepten onderling):
            # een gewone rand heeft geen zin tussen een node en zichzelf — teken een lus boven
            # de box.
            lines.append(
                f"\\draw[rel] ({a}) edge[loop above, looseness=6, min distance=14mm] "
                f"node[lbl, pos=0.5] {{{label}}} ({a});"
            )
        elif row_delta >= 2:
            # Lange sprong: routeren via de linkermarge. Eerst RECHTDOOR OMLAAG uit de
            # onderkant van de bronbox (in de lege ruimte tussen twee rijen), pas dan naar
            # links — anders zou een rechte lijn op boxhoogte dwars door een andere box in
            # dezelfde rij snijden (bv. Drager, dat links van ParameterAspect staat). Elke
            # lange-sprong-rand krijgt een eigen x-positie in de marge (gestaggerd), anders
            # lopen meerdere zulke randen exact over elkaar heen zodra hun y-bereik overlapt
            # (bv. uitgedruktIn en heeftAspect delen een deel van de marge).
            ax, ay, aw, ah = boxes[a]
            bx, by, bw, bh = boxes[b]
            corridor_x = leftmost - 1.4 - long_jump_index * 0.55
            long_jump_index += 1
            a_cx = ax + aw / 2
            a_bottom = -(ay + ah)
            gap_y = a_bottom - 0.5
            b_mid_y = -(by + bh / 2)
            lines.append(
                f"\\draw[rel, dashed] ({a_cx:.3f},{a_bottom:.3f}) -- "
                f"({a_cx:.3f},{gap_y:.3f}) -- "
                f"({corridor_x:.3f},{gap_y:.3f}) -- "
                f"({corridor_x:.3f},{b_mid_y:.3f}) -- "
                f"({bx:.3f},{b_mid_y:.3f});"
            )
            lines.append(
                f"\\node[lbl, anchor=south] at ({corridor_x:.3f},{(gap_y + b_mid_y) / 2:.3f}) "
                f"{{\\rotatebox{{90}}{{\\begin{{minipage}}{{2.1cm}}\\centering {label}"
                f"\\end{{minipage}}}}}};"
            )
        elif row_delta == 0 or is_second_of_pair:
            bend = "bend left=35" if not is_second_of_pair else "bend right=35"
            bend_pos = 0.32 if not is_second_of_pair else 0.68
            lines.append(
                f"\\draw[rel] ({a}) to[{bend}] node[lbl, pos={bend_pos}] {{{label}}} ({b});"
            )
        else:
            idx = straight_index_by_box.get(a, 0)
            straight_index_by_box[a] = idx + 1
            pos = straight_pos_cycle[idx % len(straight_pos_cycle)]
            lines.append(f"\\draw[rel] ({a}) -- node[lbl, pos={pos}] {{{label}}} ({b});")

    # Externe koppelingen (QUDT, PubChem) — altijd een korte rechte rand binnen dezelfde rij
    # (zie ROWS), gestippeld en in een eigen kleur om ze duidelijk te onderscheiden van
    # CSOR-interne relaties.
    for r in external_rel:
        a, b = r["domain"], r["range"]
        ext_label = f"{r['coverage']}\\\\{{\\ttfamily {r['detail']}}}"
        # Label ernaast i.p.v. erop: bij de korte afstand tussen een klasse en haar externe
        # koppeling (zelfde rij, kleine COL_GAP) zou een pad-node de hele lijn aan het zicht
        # onttrekken — dus de rand blijft ononderbroken en het label komt er los boven.
        lines.append(f"\\draw[extrel] ({a}) -- ({b});")
        lines.append(f"\\node[extlbl, above] at ($({a})!0.5!({b})$) {{{ext_label}}};")

    lines.append("\\end{tikzpicture}")
    lines.append("\\end{document}")
    return "\n".join(lines) + "\n"


def compile_pdf() -> None:
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"{TEX_NAME}.tex"],
        cwd=DIAGRAM_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"pdflatex-compilatie mislukt (zie {DIAGRAM_DIR / (TEX_NAME + '.log')}):\n"
            + result.stdout[-3000:]
        )
    # Ruim LaTeX-bijproducten op; enkel .tex/.pdf/.png worden gecommit.
    for ext in ("aux", "log"):
        (DIAGRAM_DIR / f"{TEX_NAME}.{ext}").unlink(missing_ok=True)


def make_preview_png() -> None:
    subprocess.run(
        ["pdftoppm", "-png", "-r", "200", f"{TEX_NAME}.pdf", TEX_NAME],
        cwd=DIAGRAM_DIR,
        check=True,
    )
    produced = sorted(DIAGRAM_DIR.glob(f"{TEX_NAME}-*.png"))
    if produced:
        produced[0].replace(DIAGRAM_DIR / f"{TEX_NAME}.png")
    for extra in produced[1:]:
        extra.unlink()


def update_readme() -> None:
    content = README_PATH.read_text()
    section = (
        f"{MARKER_START}\n"
        f"![CSOR-datamodel](output/diagrams/{TEX_NAME}.png)\n\n"
        f"*Bron: `output/diagrams/{TEX_NAME}.tex` ([PDF]"
        f"(output/diagrams/{TEX_NAME}.pdf)), gegenereerd door `scripts/generate_diagram.py`. "
        f"Elke box toont het aantal actieve concepten van die klasse; elke pijllabel toont de "
        f"CSOR-property en de kardinaliteit als (bron-klasse per één doel-instantie, "
        f"doel-klasse per één bron-instantie) — bv. bij `Parameter -> Variabele` betekent "
        f"(0..N, 1): een variabele heeft 0..N parameters, een parameter heeft precies 1 "
        f"variabele.*\n"
        f"{MARKER_END}"
    )
    if MARKER_START in content and MARKER_END in content:
        pre = content.split(MARKER_START)[0]
        post = content.split(MARKER_END)[1]
        new_content = pre + section + post
    else:
        new_content = content.rstrip("\n") + "\n\n## CSOR-datamodel\n\n" + section + "\n"
    README_PATH.write_text(new_content)


def main(graph: rdflib.Graph | None = None) -> None:
    if graph is None:
        graph = dataset.fetch_and_save()

    type_idx = build_type_index(graph)
    totals = class_totals(type_idx)
    relations = build_relations(totals, graph, type_idx)
    external_rel = external_relations(totals, graph)
    boxes = compute_boxes()
    validate_layout(boxes)
    tikz = render_tikz(totals, relations, external_rel, boxes)

    DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    (DIAGRAM_DIR / f"{TEX_NAME}.tex").write_text(tikz)
    compile_pdf()
    make_preview_png()
    update_readme()

    print("=== generate_diagram.py ===")
    print(
        f"Klassen: {len(totals)}, relaties: {len(relations)}, "
        f"externe koppelingen: {len(external_rel)} ({', '.join(r['range'] for r in external_rel)})"
    )
    print(
        f"Geschreven naar output/diagrams/{TEX_NAME}.{{tex,pdf,png}} "
        f"en bijgewerkt in {README_PATH.name}."
    )


if __name__ == "__main__":
    main()
