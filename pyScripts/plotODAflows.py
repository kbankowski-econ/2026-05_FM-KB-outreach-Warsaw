import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config

# =============================================================================
# 1. CONFIGURATION & METADATA
# =============================================================================
INPUT_PATH = "../data/fmData/Summary tables and charts.xlsx"
SHEET_NAME = "Charts"

# Metadata
METADATA_GROUPED = {
    "title": "Official Development Assistance by Economy Group",
    "units": "Percent of GDP",
    "sources": "IMF staff calculations.",
    "base_name": "oda_flows_grouped"
}

METADATA_WATERFALL = {
    "title": "Components of ODA Reduction: 2025 vs. 2024",
    "units": "Percent of 2024 ODA",
    "sources": "IMF staff calculations.",
    "base_name": "oda_flows_waterfall"
}

# =============================================================================
# 2. DATA PROCESSING
# =============================================================================
def load_data(file_path):
    """Loads the ODA data from specific Excel ranges."""
    if not file_path.exists():
        raise FileNotFoundError(f"Input missing: {file_path}")

    df_raw = pd.read_excel(file_path, sheet_name=SHEET_NAME, header=None)
    
    # --- Grouped Bar Range: B7:D9 ---
    # Rows index 6 to 8, Labels in col 1 (B), 2024 in col 2 (C), 2025 in col 3 (D)
    grouped_labels = df_raw.iloc[6:9, 1].tolist()
    # Clean up labels (remove newlines, normalize spaces)
    grouped_labels = [' '.join(str(l).split()) for l in grouped_labels]
    # Apply label transformations
    grouped_labels = [l.replace('All Economies', 'All economies').replace('LICs', 'LIDCs') for l in grouped_labels]
    val_2024 = pd.to_numeric(df_raw.iloc[6:9, 2], errors='coerce').fillna(0).tolist()
    val_2025 = pd.to_numeric(df_raw.iloc[6:9, 3], errors='coerce').fillna(0).tolist()
    
    # --- Waterfall Range: B26:F30 ---
    # Rows index 25 to 29, Labels in col 1 (B), Flow values in col 5 (F)
    wf_labels = df_raw.iloc[25:30, 1].tolist()
    wf_values = pd.to_numeric(df_raw.iloc[25:30, 5], errors='coerce').fillna(0).tolist()
    
    # The last row is the total
    wf_total = wf_values[-1]
    wf_components = wf_values[:-1]
    wf_comp_labels = wf_labels[:-1]
    wf_total_label = wf_labels[-1]

    return (grouped_labels, val_2024, val_2025), (wf_comp_labels, wf_components, wf_total_label, wf_total)

# =============================================================================
# 3. CHART CONSTRUCTION
# =============================================================================
def build_grouped_bar(labels, val_2024, val_2025, styling):
    """Constructs a grouped bar chart for ODA flows."""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=labels,
        y=val_2024,
        name='2024',
        marker_color='#6A1B9A', # Purple
        opacity=0.9
    ))

    fig.add_trace(go.Bar(
        x=labels,
        y=val_2025,
        name='2025',
        marker_color='#E65100', # Deep orange
        opacity=0.9
    ))

    # Apply Styling
    update_common_layout(fig, styling)
    return fig

def build_waterfall(labels, values, total_label, total_value, styling):
    """Constructs a horizontal waterfall chart for ODA reduction components."""
    
    # Manual label cleaning for horizontal layout
    clean_labels = [
        "Spending reprioritization",
        "Additional spending",
        "No longer needed",
        "Financing shortfall",
        "Total ODA reduction"
    ]
    
    # Standard ODA Waterfall sequence: Components first, then Total
    # Since we want it to flow from Top to Bottom, we'll keep the order 
    # and use autorange="reversed" in the Y-axis.
    
    y_labels = clean_labels
    y_values = values + [total_value]
    y_measures = ["relative"] * len(values) + ["total"]
    y_text = [f"{v:.2f}" for v in values] + [f"{total_value:.2f}"]

    # Plotly Waterfall Trace
    fig = go.Figure(go.Waterfall(
        name="Reduction",
        orientation="h",
        measure=y_measures,
        y=y_labels,
        x=y_values,
        textposition="outside",
        text=y_text,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#E67E22"}}, # Burnt Orange
        decreasing={"marker": {"color": "#5D6D7E"}}, # Steel Blue
        totals={"marker": {"color": "#2C3E50"}}      # Midnight Blue
    ))

    update_common_layout(fig, styling, is_horizontal=True)
    return fig

def update_common_layout(fig, styling, is_horizontal=False):
    """Applies standardized project-wide styling."""
    legend_cfg = styling['legend'].copy()
    legend_cfg.update({
        "y": 1.01,
        "font": {"size": styling['legend']['font_size']},
        "title": None
    })

    margins = styling['margins'].copy()
    if is_horizontal:
        margins['l'] = 180 # Extra space for longer horizontal labels
        margins['r'] = 20 # Increased right margin for horizontal data labels
    else:
        margins['b'] = 60 # Balanced bottom margin

    from fiscal_common import get_chart_dims_px
    _w, _h = get_chart_dims_px("oda_flows_grouped.png")
    fig.update_layout(
        template=styling['template'],
        width=_w,
        height=_h,
        margin=margins,
        font=dict(size=styling['font_size']),
        legend=legend_cfg,
        xaxis=dict(
            showgrid=styling['axes']['showgrid'] if is_horizontal else False,
            gridcolor=styling['axes'].get('gridcolor'),
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            tickangle=0,
            # Add padding to prevent label clipping
            range=[None, None] if not is_horizontal else [-0.2, 1.0]
        ),
        yaxis=dict(
            autorange="reversed" if is_horizontal else None, # Flow from Top to Bottom
            showgrid=False if is_horizontal else styling['axes']['showgrid'],
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

# =============================================================================
# 4. OUTPUTS & EXECUTION
# =============================================================================
def export_chart(fig, output_dir, base_name, metadata):
    """Exports PNG, HTML, and metadata."""
    pio.write_image(fig, output_dir / f"{base_name}.png", scale=2)
    pio.write_image(fig, output_dir / f"{base_name}.svg", scale=2)

    fig.write_html(output_dir / f"{base_name}.html", auto_open=True, include_plotlyjs='cdn')

    metadata_lines = [
        f"CHART: {metadata['title'].upper()}",
        "=" * 60,
        f"UNITS:   {metadata['units']}",
        f"SOURCES: {metadata['sources']}",
        "",
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
        grouped_data, waterfall_data = load_data(data_path)
        
        # Build Grouped Bar
        fig_grouped = build_grouped_bar(*grouped_data, styling)
        export_chart(fig_grouped, output_dir, METADATA_GROUPED['base_name'], METADATA_GROUPED)

        # CSV export: grouped bar data
        grouped_labels, val_2024, val_2025 = grouped_data
        df_grouped = pd.DataFrame({
            'Economy Group': grouped_labels,
            '2024': [round(v, 2) for v in val_2024],
            '2025': [round(v, 2) for v in val_2025]
        })
        df_grouped.to_csv(output_dir / f"{METADATA_GROUPED['base_name']}.csv", index=False)

        print(f"Success: ODA grouped chart generated in {output_dir}")
        
    except Exception as e:
        print(f"Error generating ODA charts: {e}")

if __name__ == "__main__":
    main()
