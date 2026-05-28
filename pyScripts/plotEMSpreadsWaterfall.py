import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config

# =============================================================================
# 1. CONFIGURATION & METADATA
# =============================================================================
BASE_NAME = "em_spreads_waterfall"
INPUT_PATH = "../data/fmData/Waterfall chart_1212.xlsx"
SHEET_NAME = "Sheet1"

METADATA = {
    "title": "EM Spreads: Decomposition of Recent Changes",
    "units": "Basis Points",
    "sources": "IMF staff calculations.",
    "narrative": (
        "This waterfall chart decomposes the changes in Emerging Market spreads into various contributing factors. "
        "The bars show the relative impact of each factor, starting from a baseline and reaching the final observed spread change."
    )
}
# =============================================================================
# 2. DATA PROCESSING: HARD-CODED DATA & SORTING
# =============================================================================
WATERFALL_DATA = [
    {"label": "Median EMBIG (Oct 22)",        "value": 424.67,  "measure": "absolute", "group": "total"},
    {"label": "Industrial production",        "value": -4.49,   "measure": "relative", "group": "local"},
    {"label": "Short-term rate",              "value": 0.59,    "measure": "relative", "group": "local"},
    {"label": "S&P 500",                      "value": -63.29,  "measure": "relative", "group": "global"},
    {"label": "Financial conditions (NFCI)",  "value": -91.29,  "measure": "relative", "group": "global"},
    {"label": "US dollar (DXY)",              "value": -24.97,  "measure": "relative", "group": "global"},
    {"label": "Residual",                     "value": -58.03,  "measure": "relative", "group": "residual"},
    {"label": "Median EMBIG (Nov 25)",        "value": 183.19,  "measure": "total",    "group": "total"}
]

# Color Mapping
GROUP_COLORS = {
    "total":    "#6A1B9A", # Purple
    "global":   "#00897B", # Teal
    "local":    "#E65100", # Deep orange
    "residual": "#757575"  # Gray
}

def load_and_prepare_data():
    """Returns the hard-coded waterfall data, sorting contributions by relevance."""
    # Separate parts
    start = [d for d in WATERFALL_DATA if d['measure'] == 'absolute']
    end = [d for d in WATERFALL_DATA if d['measure'] == 'total']
    contribs = [d for d in WATERFALL_DATA if d['measure'] == 'relative']
    
    # Sort contributions by absolute value (relevance)
    contribs_sorted = sorted(contribs, key=lambda x: abs(x['value']), reverse=True)
    
    # Reassemble
    df = pd.DataFrame(start + contribs_sorted + end)
    measures = df['measure'].tolist()
    colors = [GROUP_COLORS[g] for g in df['group']]
    
    return df, measures, colors

# =============================================================================
# 3. CHART CONSTRUCTION
# =============================================================================
def build_chart(df, measures, colors, styling):
    """Constructs a horizontal bar chart simulating a waterfall with category-based coloring."""
    # Calculate baseline for each bar
    vals = df['value'].tolist()
    base = [0] * len(vals)
    current = 0
    
    for i in range(len(vals)):
        m = measures[i]
        if m == "absolute":
            base[i] = 0
            current = vals[i]
        elif m == "relative":
            # For relative, if value is negative, base is current + value
            # if value is positive, base is current
            if vals[i] < 0:
                base[i] = current + vals[i]
            else:
                base[i] = current
            current += vals[i]
        elif m == "total":
            base[i] = 0
            # current should already be the total, but we use 0 base for full bars
    
    fig = go.Figure(go.Bar(
        orientation="h",
        y=df['label'],
        x=[abs(v) if m == "relative" else v for v, m in zip(df['value'], measures)],
        base=base,
        marker_color=colors,
        text=[f"{v:+.0f}" if m == "relative" else f"{v:.0f}" for v, m in zip(df['value'], measures)],
        textposition="outside",
        textfont=dict(size=styling['legend']['font_size']),
        opacity=0.9
    ))

    # Add connector lines manually if needed, or skip for cleaner look
    
    # Apply Standard Layout Logic
    from fiscal_common import get_chart_dims_px
    _w, _h = get_chart_dims_px("em_spreads_waterfall.png")
    fig.update_layout(
        template=styling['template'],
        width=_w,
        height=_h,
        margin=dict(t=styling['margins']['t'], b=styling['margins']['b'], l=220, r=styling['margins']['r']),
        font=dict(size=styling['font_size']),
        xaxis=dict(
            showgrid=styling['axes']['showgrid'],
            gridcolor=styling['axes'].get('gridcolor'),
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            zeroline=True,
            zerolinecolor=styling['axes']['linecolor'],
            range=[0, 550],
            title=None
        ),
        yaxis=dict(
            showgrid=False,
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            title=None,
            autorange="reversed" 
        ),
        showlegend=False
    )
    return fig

# =============================================================================
# 4. OUTPUTS & EXECUTION
# =============================================================================
def export_csv(df, output_dir, base_name):
    """Export plotted data to CSV."""
    csv_df = df[['label', 'value']].copy()
    csv_df.columns = ['Label', 'Value']
    csv_df['Value'] = csv_df['Value'].round(2)
    csv_df.to_csv(output_dir / f"{base_name}.csv", index=False)

def export_results(fig, output_dir, base_name, auto_open=False):
    """Exports PNG, HTML, and metadata text file."""
    pio.write_image(fig, output_dir / f"{base_name}.png", scale=2)
    pio.write_image(fig, output_dir / f"{base_name}.svg", scale=2)
    fig.write_html(output_dir / f"{base_name}.html", auto_open=auto_open, include_plotlyjs='cdn')

    metadata_lines = [
        f"CHART: {METADATA['title'].upper()}",
        "=" * 60,
        f"UNITS:   {METADATA['units']}",
        f"SOURCES: {METADATA['sources']}",
        "",
        "NARRATIVE:",
        METADATA['narrative'],
        "=" * 60
    ]
    with open(output_dir / f"{base_name}.txt", 'w') as f:
        f.write("\n".join(metadata_lines))

def main():
    config = load_config()
    styling = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    try:
        df, measures, colors = load_and_prepare_data()

        fig = build_chart(df, measures, colors, styling)
        export_csv(df, output_dir, BASE_NAME)
        export_results(fig, output_dir, BASE_NAME, auto_open=auto_open)

        print(f"Success: '{BASE_NAME}' generated in {output_dir}")
        
    except Exception as e:
        print(f"Error generating {BASE_NAME}: {e}")

if __name__ == "__main__":
    main()
