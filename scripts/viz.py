#!/usr/bin/env python3
"""
viz.py  –  build Plotly dashboard from synthetic Alabama-charges data
--------------------------------------------------------------------

Reads
    data/charges.csv
    data/provider_locations.csv
    data/kpi.json            (optional)

Writes
    outputs/fig_sankey.html
    outputs/fig_treemap.html
    outputs/fig_heatmap.html
    outputs/dashboard.html
"""

import json, sys, re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ──────────────────────────────────────────────────────────────────────
# 1.  Folders / file paths
# ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]          # …/Scatter2
DATA_DIR     = PROJECT_ROOT / "data"
BUILD_DIR    = PROJECT_ROOT / "outputs"                     #  <-- plural
BUILD_DIR.mkdir(parents=True, exist_ok=True)

PATH_CHARGES = DATA_DIR / "charges.csv"
PATH_LOC     = DATA_DIR / "provider_locations.csv"
PATH_KPI     = DATA_DIR / "kpi.json"                        # optional

for p in (PATH_CHARGES, PATH_LOC):
    if not p.exists():
        sys.exit(f"Required file missing: {p}")


# ──────────────────────────────────────────────────────────────────────
# 2.  Load & harmonise data
# ──────────────────────────────────────────────────────────────────────
charges = pd.read_csv(PATH_CHARGES)
loc     = pd.read_csv(PATH_LOC)

# ---- normalise charge column ----------------------------------------
charge_col = next((c for c in charges.columns if "charge" in c.lower()), None)
if not charge_col:
    sys.exit("No column containing the word 'charge' found.")
if charge_col != "charge":
    charges.rename(columns={charge_col: "charge"}, inplace=True)

# ---- merge with location table --------------------------------------
if "provider_id" not in charges.columns or "provider_id" not in loc.columns:
    sys.exit("Both CSVs must contain provider_id for merging.")

df = charges.merge(loc, on="provider_id", how="left")

# ---- robust city / lat / lon handling -------------------------------
def _get_first_matching(cols, pattern: str):
    return next((c for c in cols if re.fullmatch(pattern, c, flags=re.I)), None)

if "provider_city" not in df.columns:
    city_col = _get_first_matching(df.columns, r"city(_[xy])?")
    if city_col:
        df.rename(columns={city_col: "provider_city"}, inplace=True)
    else:
        df["provider_city"] = "Unknown City"

for wanted, pattern in [("lat", r"lat(_[xy])?"), ("lon", r"(lon|lng)(_?[xy])?")]:
    if wanted not in df.columns:
        alt = _get_first_matching(df.columns, pattern)
        if alt:
            df.rename(columns={alt: wanted}, inplace=True)

# ---- rename procedure columns to generic names ----------------------
rename_map = {
    "procedure_category": "proc_category",
    "procedure_sub":      "proc_subcategory",
}
df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns},
          inplace=True)

# ---- numeric coercions ----------------------------------------------
for col in ("charge", "lat", "lon"):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")


# ──────────────────────────────────────────────────────────────────────
# 3a. Sankey   (Payer ▸ Procedure ▸ City)
# ──────────────────────────────────────────────────────────────────────
sankey_dims = ["payer_type", "proc_category", "provider_city"]

all_nodes = pd.concat([df[c] for c in sankey_dims]).unique().tolist()
node_idx  = {name: i for i, name in enumerate(all_nodes)}

src, trg, val = [], [], []
for a, b in zip(sankey_dims[:-1], sankey_dims[1:]):
    g = df.groupby([a, b], as_index=False)["charge"].sum()
    src += g[a].map(node_idx).tolist()
    trg += g[b].map(node_idx).tolist()
    val += g["charge"].tolist()

sankey_fig = go.Figure(
    go.Sankey(
        node=dict(label=all_nodes, pad=15, thickness=15,
                  color="rgba(44,160,101,0.8)"),
        link=dict(source=src, target=trg, value=val),
    )
)
sankey_fig.update_layout(
    title="Medical-Charge Flow: Payer → Procedure → City",
    font_size=12, height=550
)

# ──────────────────────────────────────────────────────────────────────
# 3b. Treemap
# ──────────────────────────────────────────────────────────────────────
treemap_fig = px.treemap(
    df,
    path=["proc_category", "proc_subcategory", "payer_type"],
    values="charge",
    color="proc_category",
    title="Charge Distribution by Procedure Hierarchy",
    height=550,
)
treemap_fig.update_traces(root_color="lightgrey")
treemap_fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))

# ──────────────────────────────────────────────────────────────────────
# 3c. Heat-map
# ──────────────────────────────────────────────────────────────────────
heat = (
    df.groupby(["provider_city", "proc_category"])["charge"]
      .median()
      .reset_index()
      .pivot(index="provider_city", columns="proc_category", values="charge")
      .fillna(0)
)
heatmap_fig = px.imshow(
    heat, aspect="auto", color_continuous_scale="Viridis",
    labels=dict(color="Median Charge (USD)"),
    title="Median Charge by City & Procedure Category",
    height=550,
)
heatmap_fig.update_layout(yaxis_title="", xaxis_title="", margin=dict(t=50, l=25, r=25, b=25))


# ──────────────────────────────────────────────────────────────────────
# 4.  Export individual figures  (official Plotly way)
# ──────────────────────────────────────────────────────────────────────
FIGS = {
    "fig_sankey.html": sankey_fig,
    "fig_treemap.html": treemap_fig,
    "fig_heatmap.html": heatmap_fig,
}
for fname, fig in FIGS.items():
    out = BUILD_DIR / fname
    fig.write_html(
        out,
        include_plotlyjs="cdn", full_html=True,
        config={"displayModeBar": True, "displaylogo": False}
    )
    print("✓", out.relative_to(PROJECT_ROOT))


# ──────────────────────────────────────────────────────────────────────
# 5.  KPI snippet  (optional)
# ──────────────────────────────────────────────────────────────────────
kpi_div = ""
try:
    kpi = json.loads(PATH_KPI.read_text())
    rows = "".join(
        f"<tr><td><strong>{k}</strong></td>"
        f"<td style='text-align:right'>{v:,}</td></tr>"
        for k, v in kpi.items()
    )
    kpi_div = (
        "<div class='card' style='grid-column: span 2;'>"
        "<h3>Key Metrics</h3>"
        f"<table style='width:100%; border-collapse:collapse;'>{rows}</table>"
        "</div>"
    )
except Exception:
    pass  # KPI is optional


# ──────────────────────────────────────────────────────────────────────
# 6.  Assemble dashboard  (Plotly HTML-export best practice)
# ──────────────────────────────────────────────────────────────────────
def fig_div(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": True, "displaylogo": False})

dashboard_html = f"""
<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><title>Alabama Medical-Charges Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f5f5f7}}
 header{{background:#2D63C8;color:#fff;padding:1rem 2rem}}
 h1{{margin:0;font-size:1.75rem}}
 .grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;padding:1.5rem}}
 .card{{background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);padding:1.25rem}}
 @media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>Alabama Medical-Charges Dashboard</h1></header>
<section class="grid">
 {kpi_div}
 <div class="card" style="grid-column:span 2">{fig_div(sankey_fig)}</div>
 <div class="card">{fig_div(treemap_fig)}</div>
 <div class="card">{fig_div(heatmap_fig)}</div>
</section></body></html>
"""

dash_path = BUILD_DIR / "dashboard.html"
dash_path.write_text(dashboard_html, encoding="utf-8")
print("✓", dash_path.relative_to(PROJECT_ROOT))


# ──────────────────────────────────────────────────────────────────────
# 7.  Auto-open unless --no-browser
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__" and "--no-browser" not in sys.argv:
    import webbrowser
    webbrowser.open(dash_path.as_uri())
fig.write_html("./golden_image.html")
fig.write_image("./golden_image.png")