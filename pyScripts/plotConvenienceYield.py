"""
Plot Declining Convenience Yield of U.S. Treasuries:
- Figure 1.29.1: Daily convenience yield (basis points) from 2019
- Figure 1.29.2: 10-year and 3-month median convenience yield (long history)
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import (
    load_config, resolve_from_config, ensure_output_dir,
    load_chart_config, get_chart_dims_px,
)


def main():
    config = load_config()
    cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    xl_path = resolve_from_config("../data/fmData/2026AprFiscalMonitorDatabase.xlsx")

    plot_daily(xl_path, cfg, output_dir)
    plot_medians(xl_path, cfg, output_dir)
    print("Convenience yield charts complete.")


def plot_daily(xl_path, cfg, output_dir):
    df = pd.read_excel(xl_path, sheet_name='Figure 1.29.1', header=0)
    df = df.iloc[:, 1:]  # drop empty first column
    df.columns = ['date', 'bps']
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['bps'] = pd.to_numeric(df['bps'], errors='coerce')
    df = df.dropna(subset=['date', 'bps']).sort_values('date')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['bps'],
        mode='lines', name='Convenience yield',
        line=dict(color='#6A1B9A', width=cfg['line_widths']['standard']),
        showlegend=False,
    ))

    fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.6)

    # Cap y-axis to keep the COVID spike from dominating; annotate the peak
    y_cap = 140
    peak_row = df.loc[df['bps'].idxmax()]
    fig.add_annotation(
        x=peak_row['date'], y=y_cap,
        text=f"Peak: {peak_row['bps']:.0f}",
        showarrow=True, arrowhead=2, arrowcolor='#6A1B9A',
        ax=40, ay=-30,
        font=dict(size=cfg['legend']['font_size'], color='#6A1B9A'),
        bgcolor='rgba(225, 190, 231, 0.5)', borderwidth=0,
    )

    w_px, h_px = get_chart_dims_px("convenience_yield_daily.png")
    fig.update_layout(
        template=cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=30, b=40, l=50, r=20),
        font=dict(size=cfg['font_size']),
        showlegend=False,
    )
    x_ticks = pd.date_range(start='2020-01-01', end=df['date'].max(), freq='YS')
    fig.update_xaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
        tickvals=x_ticks,
        ticktext=[d.strftime("%Y") if i == 0 else str(d.year % 100) for i, d in enumerate(x_ticks)],
    )
    fig.update_yaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
        range=[20, y_cap + 20],
        dtick=25,
    )

    base = "convenience_yield_daily"
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=True, include_plotlyjs='cdn')
    df.round(2).to_csv(output_dir / f"{base}.csv", index=False)
    print(f"Saved {base}.png")


def plot_medians(xl_path, cfg, output_dir):
    raw = pd.read_excel(xl_path, sheet_name='Figure 1.29.2', header=0)
    raw.columns = ['date_raw', 'ten_yr', 'three_mo']

    import datetime as dt

    raw['ten_yr'] = pd.to_numeric(raw['ten_yr'], errors='coerce')
    raw['three_mo'] = pd.to_numeric(raw['three_mo'], errors='coerce')

    # Parse dates: actual datetimes for early rows; 2-digit year integers
    # for later rows (daily data within each year, ~260 biz days)
    parsed_dates = []
    for v in raw['date_raw']:
        if isinstance(v, (pd.Timestamp, dt.datetime)):
            parsed_dates.append(pd.Timestamp(v))
        else:
            parsed_dates.append(None)

    # For rows with integer year labels, distribute across biz days
    raw['_parsed'] = parsed_dates
    year_groups = {}
    for idx, (v, p) in enumerate(zip(raw['date_raw'], parsed_dates)):
        if p is None and isinstance(v, (int, float)) and not np.isnan(v):
            yr = int(v)
            if yr < 100:
                yr += 2000
            year_groups.setdefault(yr, []).append(idx)

    for yr, idxs in year_groups.items():
        bdays = pd.bdate_range(start=f'{yr}-01-01', end=f'{yr}-12-31')
        n = len(idxs)
        step = max(1, len(bdays) // n)
        for i, idx in enumerate(idxs):
            raw.loc[raw.index[idx], '_parsed'] = bdays[min(i * step, len(bdays) - 1)]

    raw['date'] = raw['_parsed']
    raw = raw.dropna(subset=['date']).sort_values('date').drop(columns=['_parsed'])
    raw = raw[raw['date'] >= '2010-01-01']

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=raw['date'], y=raw['ten_yr'],
        mode='lines', name='10-year median',
        line=dict(color='#6A1B9A', width=cfg['line_widths']['thick']),
    ))
    fig.add_trace(go.Scatter(
        x=raw['date'], y=raw['three_mo'],
        mode='lines', name='3-month median',
        line=dict(color='#00897B', width=cfg['line_widths']['standard']),
    ))

    fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.6)

    w_px, h_px = get_chart_dims_px("convenience_yield_medians.png")
    fig.update_layout(
        template=cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=30, b=40, l=50, r=20),
        font=dict(size=cfg['font_size']),
        legend=dict(
            **{k: v for k, v in cfg['legend'].items() if k not in ('font_size', 'y')},
            y=1.08,
            font=dict(size=cfg['legend']['font_size']),
        ),
    )
    x_ticks = pd.date_range(start='2010-01-01', end=raw['date'].max(), freq='5YS')
    fig.update_xaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
        tickvals=x_ticks,
        ticktext=[d.strftime("%Y") if i == 0 else str(d.year % 100) for i, d in enumerate(x_ticks)],
    )
    fig.update_yaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
    )

    base = "convenience_yield_medians"
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=True, include_plotlyjs='cdn')
    csv_out = raw[['date', 'ten_yr', 'three_mo']].copy()
    csv_out['date'] = csv_out['date'].dt.strftime('%Y-%m-%d')
    csv_out.round(2).to_csv(output_dir / f"{base}.csv", index=False)
    print(f"Saved {base}.png")


if __name__ == "__main__":
    main()
