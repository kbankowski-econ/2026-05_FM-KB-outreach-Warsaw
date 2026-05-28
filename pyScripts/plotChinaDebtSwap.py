import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import warnings
import os
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config

# =============================================================================
# 1. CONFIGURATION & METADATA
# =============================================================================
BASE_NAME = "chn_debt_swap"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CACHE_CSV = os.path.join(ROOT_DIR, 'data/fmData/chn_debt_swap_cache.csv')

# Set to True to fetch fresh data from Haver (requires imf_datatools)
# Set to False to use cached CSV data
DOWNLOAD_DATA = True

# Data Series Definitions (Unit: 100M RMB -> 1T RMB translation factor: 10000)
CONV_FACTOR = 10000
SERIES = {
    "swap": {
        "haver_code": "N924FIWL@EMERGEPR",
        "label": "Refinancing/swap bonds",
        "color": "#00897B", # Forest Green
        "opacity": 0.8
    },
    "repay": {
        "haver_code": "N924FIRL@EMERGEPR",
        "label": "Official bond repayments",
        "color": "#000000", # Black
        "width": 3
    }
}

METADATA = {
    "title": "Local Government Debt Maturity and the 'Swap' Effect",
    "units": "RMB Trillion",
    "sources": "Ministry of Finance (MoF); China Electronic Local Government Bond Market Access (CELMA); and Haver Analytics.",
    "narrative": (
        "Visualizes the RMB 10 trillion debt swap program. The massive spike in refinancing bond issuance "
        "in late 2024 is designed to 'cover' peaking LGFV maturities, effectively moving 'hidden' debt into official "
        "bonds to reduce interest costs. The more the bars exceed the line, the faster the 'Hidden Debt' is being cleaned up."
    ),
    "codes": "N924FIWL (Swap/Refinancing), N924FIRL (Repayments)"
}

# =============================================================================
# 2. DATA PROCESSING
# =============================================================================
def safe_get_haver_data(ticker):
    """Safely fetch data from Haver using imf_datatools."""
    try:
        import imf_datatools
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                obj = imf_datatools.get_haver_data(ticker, native_precision=True)
            except TypeError:
                obj = imf_datatools.get_haver_data(ticker)

        # Convert to DataFrame
        if obj is None:
            return None
        if isinstance(obj, pd.Series):
            df = obj.to_frame(name=ticker)
        elif isinstance(obj, pd.DataFrame):
            df = obj.copy()
        else:
            return None

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors='coerce')

        df = df[~df.index.isna()].sort_index()
        return df
    except Exception as e:
        print(f"  Error fetching {ticker}: {e}")
        return None


def download_haver_data():
    """Download data from Haver and save to cache."""
    print("[Download] Fetching data from Haver...")

    collected = {}
    for key, cfg in SERIES.items():
        ticker = cfg['haver_code']
        print(f"  Fetching {key} ({ticker})...", end="", flush=True)
        df = safe_get_haver_data(ticker)
        if df is not None and not df.empty:
            # Get the first column (the actual data)
            col = df.columns[0] if len(df.columns) > 0 else ticker
            collected[key] = df[col]
            print(" SUCCESS")
        else:
            print(" FAILED")

    if not collected:
        print("[Download] No data retrieved. Check Haver connection.")
        return None

    # Combine into single DataFrame
    df = pd.DataFrame(collected)
    df.index.name = 'date'
    df = df.reset_index()
    df['date'] = pd.to_datetime(df['date'])

    # Convert units (100M RMB -> Trillion RMB)
    for key in SERIES.keys():
        if key in df.columns:
            df[key] = df[key] / CONV_FACTOR

    # Save to cache
    os.makedirs(os.path.dirname(CACHE_CSV), exist_ok=True)
    df.to_csv(CACHE_CSV, index=False)
    print(f"[Download] Saved to {CACHE_CSV}")
    print(f"[Download] Data range: {df['date'].min().strftime('%Y-%m')} to {df['date'].max().strftime('%Y-%m')}")

    return df


def load_cached_data():
    """Load data from cache CSV."""
    if not os.path.exists(CACHE_CSV):
        return None
    df = pd.read_csv(CACHE_CSV, parse_dates=['date'])
    print(f"[Cache] Loaded {len(df)} rows from {CACHE_CSV}")
    return df


def load_data():
    """Load data from Haver or cache based on DOWNLOAD_DATA flag."""
    if DOWNLOAD_DATA:
        df = download_haver_data()
        if df is None:
            print("[Load] Falling back to cache...")
            df = load_cached_data()
    else:
        df = load_cached_data()

    if df is None:
        raise FileNotFoundError("No data available. Set DOWNLOAD_DATA=True and ensure Haver access.")

    # Filter for 2023 onwards
    df = df[df['date'] >= '2023-01-01'].copy()

    # Only keep rows where both series have values
    df = df.dropna(subset=['swap', 'repay'])

    return df

# =============================================================================
# 3. CHART CONSTRUCTION
# =============================================================================
def build_chart(df, styling):
    """Constructs the Plotly figure with standardized project layout."""
    fig = go.Figure()

    # Add Bar Trace (Swap)
    fig.add_trace(go.Bar(
        x=df['date'], 
        y=df['swap'], 
        name=SERIES['swap']['label'], 
        marker_color=SERIES['swap']['color'],
        opacity=SERIES['swap']['opacity']
    ))

    # Add Line Trace (Repayments)
    fig.add_trace(go.Scatter(
        x=df['date'], 
        y=df['repay'], 
        name=SERIES['repay']['label'], 
        line=dict(color=SERIES['repay']['color'], width=SERIES['repay']['width']),
        mode='lines'
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
    _w, _h = get_chart_dims_px("chn_debt_swap.png")
    fig.update_layout(
        template=styling['template'],
        width=_w,
        height=_h,
        margin=styling['margins'],
        font=dict(size=styling['font_size']),
        legend=legend_cfg,
        xaxis=dict(
            showgrid=styling['axes']['showgrid'],
            gridcolor=styling['axes'].get('gridcolor'),
            linecolor=styling['axes']['linecolor'],
            linewidth=styling['axes'].get('linewidth'),
            ticks=styling['axes']['ticks'],
            tickfont=dict(size=styling['axes']['tickfont_size']),
            tickformat="%b<br>%y",
            dtick="M6",
            tick0="2023-06-01",
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
        yaxis_title=None # Consistent with visual standard
    )
    return fig

# =============================================================================
# 4. OUTPUTS & EXECUTION
# =============================================================================
def export_results(fig, output_dir, base_name):
    """Exports PNG, HTML, and metadata text file."""
    # 1. Image & HTML
    pio.write_image(fig, output_dir / f"{base_name}.png", scale=2)
    pio.write_image(fig, output_dir / f"{base_name}.svg", scale=2)

    fig.write_html(output_dir / f"{base_name}.html", auto_open=True, include_plotlyjs='cdn')

    # 2. Metadata TXT
    metadata_lines = [
        f"CHART: {METADATA['title'].upper()}",
        "=" * 60,
        f"UNITS:   {METADATA['units']}",
        f"SOURCES: {METADATA['sources']}",
        f"CODES:   {METADATA['codes']}",
        "",
        "NARRATIVE:",
        METADATA['narrative'],
        "=" * 60
    ]
    with open(output_dir / f"{base_name}.txt", 'w') as f:
        f.write("\n".join(metadata_lines))

def main():
    # Environment Setup
    config = load_config()
    styling = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)

    try:
        df_clean = load_data()

        fig = build_chart(df_clean, styling)
        export_results(fig, output_dir, BASE_NAME)

        # CSV export: plotted series
        csv_df = pd.DataFrame({
            'date': df_clean['date'],
            SERIES['swap']['label']: df_clean['swap'].round(2).values,
            SERIES['repay']['label']: df_clean['repay'].round(2).values
        })
        csv_df.to_csv(output_dir / f"{BASE_NAME}.csv", index=False)

        print(f"Success: '{BASE_NAME}' generated in {output_dir}")

    except Exception as e:
        print(f"Error generating {BASE_NAME}: {e}")

if __name__ == "__main__":
    main()
