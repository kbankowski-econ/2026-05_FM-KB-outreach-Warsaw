"""
Plot International Spillovers from Shocks to US Treasury Supply:
- Figure 1.31.2: Spillover IRF (10-year scale)
- Figure 1.32.1: Spillover by external financing exposure
Two-panel (1x2) bar charts with 90% confidence intervals.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from fiscal_common import (
    load_config, resolve_from_config, ensure_output_dir,
    load_chart_config, get_chart_dims_px,
)


def main():
    config = load_config()
    cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    xl_path = resolve_from_config("../data/fmData/2026AprFiscalMonitorDatabase.xlsx")

    # Load Figure 1.31.1 (h, beta, ci90_lo, ci90_hi, +1se, -1se)
    raw1 = pd.read_excel(xl_path, sheet_name='Figure 1.31.1', header=None)
    df1 = raw1.iloc[3:].copy()
    df1 = df1[[1, 2, 7, 8, 9, 10]].copy()
    df1.columns = ['h', 'beta', 'ci90_lo', 'ci90_hi', 'se_hi', 'se_lo']
    df1 = df1.apply(pd.to_numeric, errors='coerce').dropna()
    df1['h'] = df1['h'].astype(int)

    # Load Figure 1.31.2 (h, beta, ci90_lo, ci90_hi, +1se, -1se)
    raw2 = pd.read_excel(xl_path, sheet_name='Figure 1.31.2', header=None)
    df2 = raw2.iloc[3:].copy()
    df2 = df2[[1, 2, 6, 7, 8, 9]].copy()
    df2.columns = ['h', 'beta', 'ci90_lo', 'ci90_hi', 'se_hi', 'se_lo']
    df2 = df2.apply(pd.to_numeric, errors='coerce').dropna()
    df2['h'] = df2['h'].astype(int)

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.12,
        subplot_titles=[
            'Response of 10-Year Yield to One-Basis-Point<br>Shock Arising from Treasury Auction<br>(Basis points)',
            'Response of Industrial Production to<br>One-Basis-Point Shock Arising from Treasury Auction<br>(Cumulative percent)',
        ],
    )

    for col_idx, df in enumerate([df1, df2], start=1):
        # Central estimate (first in legend)
        fig.add_trace(go.Scatter(
            x=df['h'], y=df['beta'],
            mode='lines',
            line=dict(color='#6A1B9A', width=cfg['line_widths']['thick']),
            name='Point estimate',
            showlegend=(col_idx == 1),
        ), row=1, col=col_idx)

        # ±1 SE band (narrower, darker)
        fig.add_trace(go.Scatter(
            x=list(df['h']) + list(df['h'][::-1]),
            y=list(df['se_hi']) + list(df['se_lo'][::-1]),
            fill='toself',
            fillcolor='rgba(106, 27, 154, 0.25)',
            line=dict(color='rgba(0,0,0,0)'),
            name='68 percent confidence interval',
            showlegend=(col_idx == 1),
        ), row=1, col=col_idx)

        # 90% CI band (wider, lighter)
        fig.add_trace(go.Scatter(
            x=list(df['h']) + list(df['h'][::-1]),
            y=list(df['ci90_hi']) + list(df['ci90_lo'][::-1]),
            fill='toself',
            fillcolor='rgba(106, 27, 154, 0.12)',
            line=dict(color='rgba(0,0,0,0)'),
            name='90 percent confidence interval',
            showlegend=(col_idx == 1),
        ), row=1, col=col_idx)

    fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.6)

    w_px, h_px = get_chart_dims_px("treasury_spillovers.png")
    fig.update_layout(
        template=cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=100, b=40, l=50, r=20),
        font=dict(size=cfg['axes']['tickfont_size']),
        legend=dict(
            **{k: v for k, v in cfg['legend'].items() if k not in ('font_size', 'y')},
            y=1.28,
            font=dict(size=cfg['legend']['font_size']),
        ),
    )

    for a in fig.layout.annotations:
        a.font.size = cfg['axes']['tickfont_size']

    fig.update_xaxes(
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
    )
    fig.update_xaxes(title=dict(text="Days after shock", font=dict(size=cfg['axes']['tickfont_size'])), row=1, col=1)
    fig.update_xaxes(title=dict(text="Quarters after shock", font=dict(size=cfg['axes']['tickfont_size'])), row=1, col=2)
    fig.update_yaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
        zeroline=True,
        zerolinecolor='black',
        zerolinewidth=1.5,
    )

    base = "treasury_spillovers"
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=True, include_plotlyjs='cdn')

    out_csv = pd.concat([
        df1.assign(panel='spillover_irf'),
        df2.assign(panel='financing_exposure'),
    ])
    out_csv.round(4).to_csv(output_dir / f"{base}.csv", index=False)
    print(f"Saved {base}.png")


if __name__ == "__main__":
    main()
