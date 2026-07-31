"""
report.py — gedeelde opbouwlaag voor Plotly/HTML-rapporten per check-script

PURPOSE
-------
Bouwsteen waarmee elk scripts/check_*.py, aan het einde van zijn eigen main(), één
zelfstandig HTML-rapport (output/reports/<naam>.html) genereert: Plotly-figuren plus een
korte, data-gedreven "bespreking" per sectie. Geen vervanging van de handgeschreven
Nederlandstalige rapporten in reports/ (die bevatten beleidsmatige duiding die niet uit de
data zelf valt af te leiden) — enkel een per-run gegenereerde, visuele aanvulling op de CSV's
in output/tables/.

DATA PROVENANCE
----------------
Geen eigen data — ontvangt kant-en-klare pandas DataFrames en plotly.graph_objects.Figure-
objecten van het aanroepende check-script.

METHODOLOGY
-----------
- Kleurregel: één meetwaarde verdeeld over categorieën (bv. "aantal per flag_type") krijgt
  ÉÉN vlakke kleur (FLAT_COLOR) en geen legende — de x-as-labels dragen de identiteit al; een
  kleur per staaf zou redundante encodering zijn (en plotly.express past anders impliciet een
  regenboogkleur toe zodra color=<categorische kolom> gezet wordt zonder vaste map). Twee of
  meer meetwaarden naast elkaar per categorie (bv. "totaal" vs "metScheme" per klasse) krijgen
  wél color= met een vaste, hardgecodeerde color_discrete_map (nooit afgeleid van
  runtime-sortering/telling), mét legende. Bewust geen taartdiagrammen. Kleurwaarden zijn
  verbatim overgenomen uit het gevalideerde categorische referentiepalet van de dataviz-skill
  (light mode) — geen nieuwe validatie-run nodig zolang de hexwaarden ongewijzigd blijven.
- Plotly.js wordt éénmaal per pagina via CDN ingesloten (include_plotlyjs="cdn" op het eerste
  figuur, include_plotlyjs=False op alle volgende) — kleine bestanden, consistent met de
  bewust minimale dependency-set (CLAUDE.md §2); vereist internet bij bekijken, niet bij
  genereren.
- Elke figuur loopt door _house_style() voor een consistente, rustige chart-chrome (surface/
  ink/gridline-kleuren uit hetzelfde referentiepalet, systeemlettertype, geen Plotly-logo).
- Enkel light mode — intern analistenrapport, geen publieksdashboard.
- Geen determinisme-garantie (in tegenstelling tot scripts/generate_diagram.py's .tex-
  determinisme, CLAUDE.md §6): fig.to_html() genereert per aanroep een uniek div-id, dus twee
  identieke runs geven geen byte-identieke HTML. Niet vereist door dit rapporttype.

INTERPRETATION
--------------
Niet van toepassing — dit script interpreteert zelf niets, het rendert wat het aanroepende
check-script aanlevert.

OUTPUTS
-------
output/reports/<naam>.html (per aanroepend check-script, mkdir bij eerste gebruik)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "output" / "reports"

# Categorisch palet — verbatim uit de dataviz-skill (references/palette.md), light mode,
# vaste volgorde (nooit cycled, nooit herordend op basis van data).
PALETTE = [
    "#2a78d6",  # 1 blauw   — ook FLAT_COLOR
    "#eb6834",  # 2 oranje
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 geel
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 groen
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 rood
]
FLAT_COLOR = PALETTE[0]

CHART_SURFACE = "#fcfcfb"
PAGE_PLANE = "#f9f9f7"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS_BASELINE = "#c3c2b7"
FONT_STACK = "system-ui, -apple-system, 'Segoe UI', sans-serif"


@dataclass
class Section:
    """Eén sectie van het rapport: een kop, een bespreking, en optioneel figuren/een tabel."""

    heading: str
    discussion: str
    figures: list[go.Figure] = field(default_factory=list)
    table_df: pd.DataFrame | None = None
    table_n: int = 10
    table_columns: list[str] | None = None


def _house_style(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        plot_bgcolor=CHART_SURFACE,
        paper_bgcolor=CHART_SURFACE,
        font=dict(family=FONT_STACK, color=INK_PRIMARY, size=13),
        margin=dict(l=60, r=30, t=50, b=60),
    )
    fig.update_xaxes(gridcolor=GRIDLINE, linecolor=AXIS_BASELINE, zerolinecolor=AXIS_BASELINE)
    fig.update_yaxes(gridcolor=GRIDLINE, linecolor=AXIS_BASELINE, zerolinecolor=AXIS_BASELINE)
    return fig


def bar_counts(
    series_or_df,
    x_col: str | None = None,
    title: str = "",
    xaxis_title: str = "",
    yaxis_title: str = "Aantal",
) -> go.Figure:
    """Vlakke-kleur telling-per-categorie-staafdiagram (FLAT_COLOR, geen legende).

    Accepteert ofwel een pandas Series (bv. df["kolom"].value_counts()) ofwel een DataFrame
    met een categorische kolom `x_col` en een numerieke telkolom — in dat laatste geval wordt
    verondersteld dat het DataFrame al één rij per categorie bevat (bv. "aantal per klasse").
    """
    if isinstance(series_or_df, pd.Series):
        x = series_or_df.index.astype(str).tolist()
        y = series_or_df.values.tolist()
    else:
        if x_col is None:
            raise ValueError("x_col is verplicht wanneer series_or_df een DataFrame is")
        value_cols = [c for c in series_or_df.columns if c != x_col]
        x = series_or_df[x_col].astype(str).tolist()
        y = series_or_df[value_cols[0]].tolist()

    fig = go.Figure(go.Bar(x=x, y=y, marker_color=FLAT_COLOR))
    fig.update_layout(title=title, xaxis_title=xaxis_title, yaxis_title=yaxis_title)
    return _house_style(fig)


def format_value_counts(series: pd.Series, noun_singular: str, noun_plural: str) -> str:
    """Eén-zinssamenvatting van een value_counts()-verdeling.

    Bv. format_value_counts(df["flag_type"], "vlag", "vlaggen") ->
    "42 vlaggen: exactMatch (30), broadMatch (8), geen (4)."
    """
    counts = series.value_counts()
    total = int(counts.sum())
    noun = noun_singular if total == 1 else noun_plural
    if total == 0:
        return f"Geen {noun_plural}."
    breakdown = ", ".join(f"{idx} ({int(n)})" for idx, n in counts.items())
    return f"{total} {noun}: {breakdown}."


def build_report(name: str, title: str, intro: str, sections: list[Section]) -> Path:
    """Schrijft output/reports/<name>.html en geeft het pad terug.

    Enkel het eerste figuur van de hele pagina krijgt include_plotlyjs="cdn" — alle volgende
    figuren delen dezelfde globale Plotly-instantie via include_plotlyjs=False, zodat het
    CDN-<script>-tag precies één keer per pagina voorkomt.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    body_parts: list[str] = []
    first_figure_written = False

    for section in sections:
        body_parts.append(f"<h2>{section.heading}</h2>")
        for paragraph in section.discussion.split("\n\n"):
            body_parts.append(f"<p>{paragraph}</p>")
        for fig in section.figures:
            _house_style(fig)
            include_js: bool | str = "cdn" if not first_figure_written else False
            first_figure_written = True
            body_parts.append(
                fig.to_html(
                    full_html=False,
                    include_plotlyjs=include_js,
                    config={"displaylogo": False},
                )
            )
        if section.table_df is not None:
            table_df = section.table_df
            if section.table_columns is not None:
                table_df = table_df[section.table_columns]
            body_parts.append(
                f'<div class="table-wrap">{table_df.head(section.table_n).to_html(index=False)}</div>'
            )

    html = f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{
    background: {PAGE_PLANE};
    color: {INK_PRIMARY};
    font-family: {FONT_STACK};
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1.5rem;
    line-height: 1.5;
  }}
  h1 {{ margin-bottom: 0.25rem; }}
  .intro {{ color: {INK_SECONDARY}; margin-top: 0; }}
  h2 {{
    margin-top: 2.5rem;
    border-bottom: 1px solid {GRIDLINE};
    padding-bottom: 0.4rem;
  }}
  p {{ color: {INK_PRIMARY}; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }}
  th, td {{
    border-bottom: 1px solid {GRIDLINE};
    padding: 0.35rem 0.6rem;
    text-align: left;
    white-space: nowrap;
  }}
  th {{ color: {INK_MUTED}; font-weight: 600; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="intro">{intro}</p>
{"".join(body_parts)}
</body>
</html>
"""

    out_path = OUTPUT_DIR / f"{name}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
