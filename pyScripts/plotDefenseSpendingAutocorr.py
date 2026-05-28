import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
from fiscal_common import load_config, ensure_output_dir, load_chart_config

# =============================================================================
# 1. CONFIGURATION & METADATA
# =============================================================================
BASE_NAME = "defense_spending_autocorr"
INPUT_PATH = Path("/Users/kk/Documents/0000-00_work/2025-11_defense-rigidity/defense_spending_autocorr_bar_chart.csv")
PLOT_COL = "simple_average_autocorr"

# Series Colors - Purple-centered scheme
PRIMARY_COLOR = "#6A1B9A"   # Purple primary
SECONDARY_COLOR = "#CE93D8" # Purple light

METADATA = {
    "title": "Persistence of Public Spending Categories",
    "units": "Autocorrelation Coefficient",
    "sources": "IMF staff calculations.",
    "narrative": (
        "This chart compares the persistence of defense spending with other public spending categories. "
        "Persistence is measured by the AR(1) coefficient using a simple average."
    )
}

# =============================================================================
# 2. DATA PROCESSING
# =============================================================================
def load_and_prepare_data(file_path):
    """Loads autocorrelation data and prepares for horizontal bar chart."""
    if not file_path.exists():
        raise FileNotFoundError(f"Input missing: {file_path}")

    df = pd.read_csv(file_path)
    
    # Sort by the simple average column for better visualization
    df = df.sort_values(by=PLOT_COL, ascending=True)

    # Standardize spelling: Defence -> Defense
    df['description'] = df['description'].replace('Defence', 'Defense')

    # Assign colors
    df['color'] = df['description'].apply(lambda x: PRIMARY_COLOR if x == 'Defense' else SECONDARY_COLOR)
    
    return df

# =============================================================================
# 3. CHART CONSTRUCTION
# =============================================================================
def build_chart(df, styling):
    """Constructs a horizontal bar chart."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df[PLOT_COL],
        y=df['description'],
        orientation='h',
        marker_color=df['color'],
        text=df[PLOT_COL].round(2),
        textposition='outside',
        textfont=dict(size=styling['font_size'] - 6, color='black'),
        opacity=0.9
    ))

    # Apply Standard Layout Logic
    from fiscal_common import get_chart_dims_px
    _w, _h = get_chart_dims_px("defense_spending_autocorr.png")
    fig.update_layout(
        template=styling['template'],
        width=_w,
        height=_h,
        margin=dict(t=styling['margins']['t'], b=styling['margins']['b'], l=150, r=styling['margins']['r']),
        font=dict(size=styling['font_size']),
        xaxis=dict(
            showgrid=styling['axes']['showgrid'],
            gridcolor=styling['axes'].get('gridcolor'),
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            range=[0, 1.0],
            title=None
        ),
        yaxis=dict(
            showgrid=False,
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            title=None
        ),
        showlegend=False
    )
    return fig

# =============================================================================
# 4. OUTPUTS & EXECUTION
# =============================================================================
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
        df = load_and_prepare_data(INPUT_PATH)

        # Export CSV of plotted data
        csv_data = pd.DataFrame({
            'Spending category': df['description'].values,
            'Autocorrelation coefficient': df[PLOT_COL].values
        }).round(2)
        output_csv = output_dir / f"{BASE_NAME}.csv"
        csv_data.to_csv(output_csv, index=False)
        print(f"CSV saved as {output_csv}")

        fig = build_chart(df, styling)
        export_results(fig, output_dir, BASE_NAME, auto_open=auto_open)
        print(f"Success: '{BASE_NAME}' generated in {output_dir}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
