import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import os
import json
import webbrowser
import platform
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CACHE_CSV = os.path.join(ROOT_DIR, 'data/fmData/term_premia_cache.csv')
OUTPUT_PNG = os.path.join(ROOT_DIR, 'docu/term_premia_plot.png')
LOG_FILE = os.path.join(SCRIPT_DIR, 'plotTermPremia.log')

DOWNLOAD_DATA = True

# Bloomberg tickers for 10Y and 2Y yields (term spread = 10Y - 2Y)
# Format: {country: (ticker_10y, ticker_2y, color)}
YIELD_TICKERS = {
    'United States':  ('USGG10YR_INDEX', 'USGG2YR_INDEX', '#4A148C'),
    'Germany':        ('GDBR10_INDEX',   'GDBR2_INDEX',   '#F9A825'),
    'United Kingdom': ('GUKG10_INDEX',   'GUKG2_INDEX',   '#E65100'),
    'Japan':          ('GTJPY10Y_GOVT',  'GTJPY2Y_GOVT',  '#00897B'),
    'Canada':         ('GCAN10YR_INDEX', 'GCAN2YR_INDEX', '#00838F'),
    'France':         ('GFRN10_INDEX',   'GFRN2_INDEX',   '#6A1B9A')
}

# =============================================================================
# LOGGING
# =============================================================================
_log_handle = None

def log(msg=""):
    print(msg)
    if _log_handle:
        _log_handle.write(msg + "\n")
        _log_handle.flush()

# =============================================================================
# DATA RETRIEVAL
# =============================================================================
def download_term_spread_data():
    """Download 10Y and 2Y yields from Bloomberg and calculate term spread."""
    log("[Download] Fetching 10Y and 2Y yields from Bloomberg...")
    try:
        from imf_datatools import idata_utilities
        idata_utilities.PRIVATE = True
    except ImportError as e:
        log(f"[Download] FAILED - imf_datatools not available: {e}")
        return None

    # Build ticker string (all 10Y and 2Y tickers)
    all_tickers = []
    for ticker_10y, ticker_2y, _ in YIELD_TICKERS.values():
        all_tickers.extend([ticker_10y, ticker_2y])
    tickers = '+'.join(all_tickers)

    try:
        df = idata_utilities.get_idata_data('IMF.CSF:BBGDL', key=tickers + '.PX_LAST.D')
    except Exception as e:
        log(f"[Download] FAILED - API error: {e}")
        return None

    # Clean column names
    df.columns = [col.replace(".PX_LAST.D", "") for col in df.columns]
    df = df.reset_index().rename(columns={'index': 'date', 'dates': 'date'})
    df['date'] = pd.to_datetime(df['date'])

    log(f"[Download] Database: IMF.CSF:BBGDL")
    log(f"[Download] Retrieved {len(df)} rows, last date: {df['date'].max().strftime('%Y-%m-%d')}")

    # Calculate term spread for each country
    result = pd.DataFrame({'date': df['date']})
    last_row = df.iloc[-1]

    for country, (ticker_10y, ticker_2y, _) in YIELD_TICKERS.items():
        if ticker_10y in df.columns and ticker_2y in df.columns:
            result[country] = df[ticker_10y] - df[ticker_2y]
            val_10y = last_row[ticker_10y] if pd.notna(last_row[ticker_10y]) else None
            val_2y = last_row[ticker_2y] if pd.notna(last_row[ticker_2y]) else None
            spread = result[country].iloc[-1] if pd.notna(result[country].iloc[-1]) else None
            spread_str = f"{spread:.3f}%" if spread is not None else "N/A"
            log(f"  {country}: {spread_str} (10Y: {ticker_10y}, 2Y: {ticker_2y})")
        else:
            log(f"  {country}: N/A - missing tickers")

    result.to_csv(CACHE_CSV, index=False)
    log(f"[Download] Saved to {CACHE_CSV}")
    return result

# =============================================================================
# MAIN
# =============================================================================
def plot_term_premia():
    global _log_handle
    _log_handle = open(LOG_FILE, 'w', encoding='utf-8')
    log(f"=== plotTermPremia.py - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    # Load data
    if DOWNLOAD_DATA:
        df = download_term_spread_data()
        if df is None and os.path.exists(CACHE_CSV):
            log("[Load] Falling back to cache...")
            df = pd.read_csv(CACHE_CSV, parse_dates=['date'])
    elif os.path.exists(CACHE_CSV):
        df = pd.read_csv(CACHE_CSV, parse_dates=['date'])
        log(f"[Load] Loaded {len(df)} rows from cache")
        log(f"[Load] Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    else:
        log("[Load] ERROR - No data source available (no cache, DOWNLOAD_DATA=False)")
        _log_handle.close()
        return

    # Filter to 2015+ and cap at April 1, 2026
    df = df[(df['date'] >= '2015-01-01') & (df['date'] <= '2026-04-01')].copy()
    df = df.sort_values('date')
    log(f"[Data] {len(df)} rows from {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")

    # Load chart config
    config_path = os.path.join(SCRIPT_DIR, "chartConfig.json")
    with open(config_path, "r") as f:
        cfg = json.load(f)["styling"]

    from fiscal_common import get_chart_dims_px
    w_px, h_px = get_chart_dims_px("term_premia_plot.png")

    # Build plot
    cutoff = pd.Timestamp('2026-01-01')
    recent = df[df['date'] >= cutoff]
    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.1)

    countries = [c for c in YIELD_TICKERS.keys() if c in df.columns]

    for country in countries:
        _, _, color = YIELD_TICKERS[country]
        hover = f"<b>{country}</b><br>Date: %{{x|%b %d, %Y}}<br>Term Spread: %{{y:.3f}}%<extra></extra>"

        fig.add_trace(go.Scatter(
            x=df['date'], y=df[country], name=country, mode='lines',
            line=dict(color=color, width=cfg['line_widths']['standard']),
            hovertemplate=hover
        ), row=1, col=1)

        if not recent.empty:
            fig.add_trace(go.Scatter(
                x=recent['date'], y=recent[country], mode='lines',
                line=dict(color=color, width=cfg['line_widths']['thick']),
                showlegend=False, hovertemplate=hover
            ), row=1, col=2)

    # Y-range for main chart (full history)
    vals = df[countries].values.flatten()
    vals = vals[~pd.isna(vals)]
    y_min, y_max = vals.min() - 0.1, vals.max() + 0.1

    # Y-range for magnification chart (recent data only)
    if not recent.empty:
        recent_vals = recent[countries].values.flatten()
        recent_vals = recent_vals[~pd.isna(recent_vals)]
        y_min_recent, y_max_recent = recent_vals.min() - 0.05, recent_vals.max() + 0.05
    else:
        y_min_recent, y_max_recent = y_min, y_max

    # Layout
    fig.update_layout(
        template=cfg['template'], width=w_px, height=h_px,
        margin=cfg['margins'], font=dict(size=cfg['font_size']),
        legend=dict(**{k: v for k, v in cfg['legend'].items() if k != 'font_size'}, font=dict(size=cfg['legend']['font_size']), itemwidth=30)
    )
    fig.update_yaxes(range=[y_min, y_max], showgrid=cfg['axes']['showgrid'],
                     gridcolor=cfg['axes'].get('gridcolor'), linecolor=cfg['axes']['linecolor'],
                     tickfont=dict(size=cfg['axes']['tickfont_size']),
                     zeroline=True, zerolinecolor=cfg['axes']['linecolor'], row=1, col=1)
    fig.update_yaxes(range=[y_min_recent, y_max_recent], showgrid=cfg['axes']['showgrid'],
                     gridcolor=cfg['axes'].get('gridcolor'), linecolor=cfg['axes']['linecolor'],
                     tickfont=dict(size=cfg['axes']['tickfont_size']),
                     showticklabels=True, row=1, col=2)
    fig.update_xaxes(showgrid=True, gridcolor=cfg['axes'].get('gridcolor'),
                     tickfont=dict(size=cfg['axes']['tickfont_size']))
    x_ticks = pd.date_range(start="2015-01-01", end=df['date'].max(), freq='5YS')
    fig.update_xaxes(tickvals=x_ticks,
                     ticktext=[d.strftime("%Y") if i == 0 else str(d.year % 100) for i, d in enumerate(x_ticks)],
                     tickangle=0, range=["2015-01-01", df['date'].max()], row=1, col=1)
    if not recent.empty:
        fig.update_xaxes(dtick="M1", tick0="2026-01-01", tickformat="%b<br>%y", tickangle=0,
                         range=[recent['date'].min(), recent['date'].max()], row=1, col=2)

    # Vertical line marking Middle East war start (Feb 28, 2026)
    war_date = pd.Timestamp('2026-02-28')
    vline = dict(type="line", y0=y_min, y1=y_max, line=dict(color="red", width=2.5, dash="dot"))
    vline_recent = dict(type="line", y0=y_min_recent, y1=y_max_recent, line=dict(color="red", width=2.5, dash="dot"))
    fig.add_shape(**vline, x0=war_date, x1=war_date, xref="x", yref="y")
    if not recent.empty:
        fig.add_shape(**vline_recent, x0=war_date, x1=war_date, xref="x2", yref="y2")

    # CSV export: plotted series
    csv_df = pd.DataFrame({'date': df['date']})
    for country in countries:
        csv_df[country] = df[country].round(2).values
    csv_path = OUTPUT_PNG.replace('.png', '.csv')
    csv_df.to_csv(csv_path, index=False)
    log(f"[Output] CSV: {csv_path}")

    # Save outputs
    os.makedirs(os.path.dirname(OUTPUT_PNG), exist_ok=True)
    if platform.system() == "Darwin":
        pio.write_image(fig, OUTPUT_PNG, format='png', scale=2)
        pio.write_image(fig, OUTPUT_PNG.replace('.png', '.svg'), format='svg', scale=2)
        log(f"[Output] PNG: {OUTPUT_PNG}")

    html_out = OUTPUT_PNG.replace('.png', '.html')
    fig.write_html(html_out, include_plotlyjs='cdn')
    log(f"[Output] HTML: {html_out}")
    webbrowser.open(f'file://{os.path.abspath(html_out)}')

    log("\n=== Done ===")
    _log_handle.close()

if __name__ == "__main__":
    plot_term_premia()
