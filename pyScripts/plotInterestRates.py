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
CACHE_CSV = os.path.join(ROOT_DIR, 'data/fmData/10-30y-bond-yields_cache.csv')
OUTPUT_PNG = os.path.join(ROOT_DIR, 'docu/interest_rates_plot.png')
LOG_FILE = os.path.join(SCRIPT_DIR, 'plotInterestRates.log')

DOWNLOAD_DATA = True

YIELD_TICKERS = {
    'us_10y':      ('USGG10YR_INDEX', 'United States (10-year)',  '#102A71'),
    'us_30y':      ('USGG30YR_INDEX', 'United States (30-year)',  '#B1C9F5'),
    'germany_10y': ('GDBR10_INDEX',   'Germany (10-year)',        '#966000'),
    'germany_30y': ('GDBR30_INDEX',   'Germany (30-year)',        '#F7E1B5'),
    'uk_10y':      ('GUKG10_INDEX',   'United Kingdom (10-year)', '#8F1D21'),
    'uk_30y':      ('GUKG30_INDEX',   'United Kingdom (30-year)', '#F1C6C8'),
    'japan_10y':   ('GTJPY10Y_GOVT',  'Japan (10-year)',          '#1D5B41'),
    'japan_30y':   ('GTJPY30Y_GOVT',  'Japan (30-year)',          '#C1DACD')
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
def download_yield_data():
    """Download bond yield data from Bloomberg."""
    log("[Download] Fetching data from Bloomberg...")
    try:
        from imf_datatools import idata_utilities
        idata_utilities.PRIVATE = True
    except ImportError as e:
        log(f"[Download] FAILED - imf_datatools not available: {e}")
        return None

    tickers = '+'.join([t[0] for t in YIELD_TICKERS.values()])
    try:
        df = idata_utilities.get_idata_data('IMF.CSF:BBGDL', key=tickers + '.PX_LAST.D')
    except Exception as e:
        log(f"[Download] FAILED - API error: {e}")
        return None

    # Clean columns and rename
    df.columns = [col.replace(".PX_LAST.D", "") for col in df.columns]
    ticker_to_col = {v[0]: k for k, v in YIELD_TICKERS.items()}
    df.rename(columns=ticker_to_col, inplace=True)
    df = df.reset_index().rename(columns={'index': 'date', 'dates': 'date'})
    df['date'] = pd.to_datetime(df['date'])

    # Log last observations
    log(f"[Download] Database: IMF.CSF:BBGDL")
    log(f"[Download] Retrieved {len(df)} rows, last date: {df['date'].max().strftime('%Y-%m-%d')}")
    last_row = df.iloc[-1]
    for col in [c for c in df.columns if c != 'date']:
        ticker, name, _ = YIELD_TICKERS[col]
        val = last_row[col] if col in last_row and pd.notna(last_row[col]) else None
        val_str = f"{val:.2f}%" if val is not None else "N/A"
        log(f"  {name}: {val_str} [{ticker}]")

    df.to_csv(CACHE_CSV, index=False)
    log(f"[Download] Saved to {CACHE_CSV}")
    return df

# =============================================================================
# MAIN
# =============================================================================
def plot_interest_rates():
    global _log_handle
    _log_handle = open(LOG_FILE, 'w', encoding='utf-8')
    log(f"=== plotInterestRates.py - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    # Load data
    if DOWNLOAD_DATA:
        df = download_yield_data()
        if df is None and os.path.exists(CACHE_CSV):
            log("[Load] Falling back to cache...")
            df = pd.read_csv(CACHE_CSV, parse_dates=['date'])
    elif os.path.exists(CACHE_CSV):
        df = pd.read_csv(CACHE_CSV, parse_dates=['date'])
        log(f"[Load] Loaded {len(df)} rows from cache")
    else:
        log("[Load] ERROR - No data source available")
        return

    # Filter to 2015+ and cap at April 1, 2026
    df = df[(df['date'] >= '2015-01-01') & (df['date'] <= '2026-04-01')].copy()
    log(f"[Data] {len(df)} rows from {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")

    # Load chart config
    with open(os.path.join(SCRIPT_DIR, "chartConfig.json"), "r") as f:
        cfg = json.load(f)["styling"]

    from fiscal_common import get_chart_dims_px
    w_px, h_px = get_chart_dims_px("interest_rates_plot.png")

    # Build plot
    cutoff = pd.Timestamp('2026-01-01')
    recent = df[df['date'] >= cutoff]
    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.1)

    legend_order = ['us_10y', 'us_30y', 'germany_10y', 'germany_30y', 'uk_10y', 'uk_30y', 'japan_10y', 'japan_30y']
    plot_order = ['japan_30y', 'uk_30y', 'germany_30y', 'us_30y', 'japan_10y', 'uk_10y', 'germany_10y', 'us_10y']

    for key in plot_order:
        if key not in df.columns:
            continue
        _, name, color = YIELD_TICKERS[key]
        rank = legend_order.index(key) + 1
        hover = f"<b>{name}</b><br>Date: %{{x|%b %d, %Y}}<br>Yield: %{{y:.2f}}%<extra></extra>"

        fig.add_trace(go.Scatter(
            x=df['date'], y=df[key], name=name, mode='lines',
            line=dict(color=color, width=cfg['line_widths']['standard']),
            legendrank=rank, hovertemplate=hover
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=recent['date'], y=recent[key], mode='lines',
            line=dict(color=color, width=cfg['line_widths']['thick']),
            showlegend=False, hovertemplate=hover
        ), row=1, col=2)

    # Y-range for main chart (full history)
    cols = [k for k in YIELD_TICKERS.keys() if k in df.columns]
    vals = df[cols].values.flatten()
    vals = vals[~pd.isna(vals)]
    y_min, y_max = vals.min() - 0.2, vals.max() + 0.2

    # Y-range for magnification chart (recent data only)
    recent_vals = recent[cols].values.flatten()
    recent_vals = recent_vals[~pd.isna(recent_vals)]
    y_min_recent, y_max_recent = recent_vals.min() - 0.1, recent_vals.max() + 0.1

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
    fig.update_xaxes(
        tickvals=x_ticks,
        ticktext=[d.strftime("%Y") if i == 0 else str(d.year % 100) for i, d in enumerate(x_ticks)],
        row=1, col=1
    )
    fig.update_xaxes(dtick="M1", tick0="2026-01-01", tickformat="%b<br>%y", tickangle=0, range=[recent['date'].min(), recent['date'].max()], row=1, col=2)

    # Vertical line marking Middle East war start (Feb 28, 2026)
    war_date = pd.Timestamp('2026-02-28')
    vline = dict(type="line", y0=y_min, y1=y_max, line=dict(color="red", width=2.5, dash="dot"))
    vline_recent = dict(type="line", y0=y_min_recent, y1=y_max_recent, line=dict(color="red", width=2.5, dash="dot"))
    fig.add_shape(**vline, x0=war_date, x1=war_date, xref="x", yref="y")
    fig.add_shape(**vline_recent, x0=war_date, x1=war_date, xref="x2", yref="y2")

    # CSV export: plotted series
    csv_df = pd.DataFrame({'date': df['date']})
    for key in legend_order:
        if key in df.columns:
            _, name, _ = YIELD_TICKERS[key]
            csv_df[name] = df[key].round(2).values
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
    plot_interest_rates()
