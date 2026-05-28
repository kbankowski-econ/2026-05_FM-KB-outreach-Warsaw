import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config

# =============================================================================
# 1. CONFIGURATION & METADATA
# =============================================================================
BASE_NAME = "obbb_fiscal_effects"
INPUT_PATH = "../data/fmData/OBBB-deficit-impact.xlsx"
SHEET_NAME = "OBBBA"

# Data Mapping (Excel 1-based indices -> Python 0-based)
YEAR_ROW = 23    # Row 24
DATA_COLS = slice(4, 14) # E to N (index 4 to 13)
LABEL_COL = 2    # Col C
BAR_ROWS = [36, 37, 38, 39, 40, 41] # Rows 37 to 42
TOTAL_ROW = 43   # Row 44

# Series Colors (Option 1: Structural Contrast)
SERIES_COLORS = [
    "#4A148C", # Dark purple - Labor Tax
    "#CE93D8", # Light purple - Low-Income Transfers
    "#AD1457", # Magenta - General Transfers
    "#E65100", # Deep orange - Business Tax
    "#00897B", # Teal - Investment Subsidies
    "#757575"  # Gray - Public Consumption
]

METADATA = {
    "title": "United States: Impact of the OBBB Program on the Fiscal Deficit",
    "units": "Percent of GDP",
    "sources": "Congressional Budget Office; and IMF staff calculations.",
    "narrative": (
        "This chart decomposes the fiscal impact of the OBBB program across various tax and spending categories. "
        "The stacked bars represent individual components, while the black line shows the total net effect on the primary balance."
    ),
    "codes": "N/A"
}

# =============================================================================
# 2. DATA PROCESSING
# =============================================================================
def load_and_clean_data(file_path):
    """Loads OBBBA sheet and extracts relevant ranges."""
    if not file_path.exists():
        raise FileNotFoundError(f"Input missing: {file_path}")

    # Read the whole sheet without headers
    df_raw = pd.read_excel(file_path, sheet_name=SHEET_NAME, header=None)
    
    # Extract years
    years = [str(int(y)) if pd.notnull(y) else "" for y in df_raw.iloc[YEAR_ROW, DATA_COLS]]
    # Prepend '20' if they are 2-digit years
    years = ["20" + y if len(y) == 2 else y for y in years]
    
    # Extract Bar Series
    bar_data = []
    for i, row_idx in enumerate(BAR_ROWS):
        label = df_raw.iloc[row_idx, LABEL_COL]
        # Apply sentence case: capitalize first letter only
        if isinstance(label, str) and len(label) > 0:
            label = label[0].upper() + label[1:].lower()
        values = pd.to_numeric(df_raw.iloc[row_idx, DATA_COLS], errors='coerce').fillna(0).tolist()
        bar_data.append({
            "label": label,
            "values": values,
            "color": SERIES_COLORS[i]
        })
        
    # Extract Total Line
    total_values = pd.to_numeric(df_raw.iloc[TOTAL_ROW, DATA_COLS], errors='coerce').fillna(0).tolist()
    
    # Abbreviated year labels: full for first, short for every other, blank in between
    year_labels = [y if i == 0 else (y[-2:] if i % 2 == 0 else "") for i, y in enumerate(years)]
    return years, year_labels, bar_data, total_values

# =============================================================================
# 3. CHART CONSTRUCTION
# =============================================================================
def build_chart(years, year_labels, bar_data, total_values, styling):
    """Constructs a stacked bar chart with a total line."""
    fig = go.Figure()

    # Add Stacked Bar Traces
    for series in bar_data:
        fig.add_trace(go.Bar(
            x=years,
            y=series['values'],
            name=series['label'],
            marker_color=series['color'],
            opacity=0.8
        ))

    # Add Total Line Trace
    fig.add_trace(go.Scatter(
        x=years,
        y=total_values,
        name='Total effect',
        line=dict(color='black', width=3),
        mode='lines+markers',
        marker=dict(size=8, symbol='circle')
    ))

    # Prepare legend config with overrides
    legend_cfg = styling['legend'].copy()
    legend_cfg.update({
        "y": 1.01,
        "font": {"size": styling['legend']['font_size']},
        "title": None
    })

    # Apply Standard Layout Logic
    from fiscal_common import get_chart_dims_px
    _w, _h = get_chart_dims_px("obbb_fiscal_effects.png")
    fig.update_layout(
        template=styling['template'],
        width=_w,
        height=_h,
        margin=styling['margins'],
        font=dict(size=styling['font_size']),
        barmode='relative',
        legend=legend_cfg,
        xaxis=dict(
            showgrid=False,
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            tickmode='array',
            tickvals=years,
            ticktext=year_labels,
            tickangle=0
        ),
        yaxis=dict(
            showgrid=styling['axes']['showgrid'],
            gridcolor=styling['axes'].get('gridcolor'),
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            zeroline=True,
            zerolinecolor=styling['axes']['linecolor']
        ),
        yaxis_title=None
    )
    return fig

# =============================================================================
# 4. OUTPUTS & EXECUTION
# =============================================================================
def export_csv(years, bar_data, total_values, output_dir, base_name):
    """Export plotted data to CSV."""
    csv_dict = {"Year": years}
    for series in bar_data:
        csv_dict[series['label']] = [round(v, 2) for v in series['values']]
    csv_dict["Total effect"] = [round(v, 2) for v in total_values]
    pd.DataFrame(csv_dict).to_csv(output_dir / f"{base_name}.csv", index=False)

def export_results(fig, output_dir, base_name):
    """Exports PNG, HTML, and metadata text file."""
    pio.write_image(fig, output_dir / f"{base_name}.png", scale=2)
    pio.write_image(fig, output_dir / f"{base_name}.svg", scale=2)
    fig.write_html(output_dir / f"{base_name}.html", auto_open=True, include_plotlyjs='cdn')

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
    
    try:
        data_path = resolve_from_config(INPUT_PATH)
        years, year_labels, bar_data, total_values = load_and_clean_data(data_path)
        
        fig = build_chart(years, year_labels, bar_data, total_values, styling)
        export_csv(years, bar_data, total_values, output_dir, BASE_NAME)
        export_results(fig, output_dir, BASE_NAME)
        
        print(f"Success: '{BASE_NAME}' generated in {output_dir}")
        
    except Exception as e:
        print(f"Error generating {BASE_NAME}: {e}")

if __name__ == "__main__":
    main()
