"""
Plot social unrest / political instability charts from FM Database:
- Figure 1.27.1: Multi-line chart (number of events by income group)
- Figure 1.27.2: Impulse response with band (fiscal impact of social unrest)
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import (
    load_config, resolve_from_config, ensure_output_dir,
    load_chart_config, get_chart_dims_px,
)


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    xl_path = resolve_from_config("../data/fmData/2026AprFiscalMonitorDatabase.xlsx")

    plot_events(xl_path, chart_cfg, output_dir)
    plot_irf(xl_path, chart_cfg, output_dir)
    print("Social unrest charts complete.")


def plot_events(xl_path, cfg, output_dir):
    df = pd.read_excel(xl_path, sheet_name='Figure 1.27.1', header=0)
    df.columns = ['year'] + list(df.columns[1:])
    df['year'] = df['year'].astype(int)
    df.loc[df['year'] < 100, 'year'] += 2000

    rename = {
        'World': 'Global',
        'Advanced economies': 'Advanced Economies',
        'Emerging markets': 'Emerging Markets',
        'Low-income countries': 'Low-Income Developing Countries',
    }
    colors = {
        'Global': '#6A1B9A',
        'Advanced Economies': '#1E88E5',
        'Emerging Markets': '#E65100',
        'Low-Income Developing Countries': '#00897B',
    }
    widths = {
        'Global': 6,
    }

    df = df.rename(columns=rename)
    fig = go.Figure()
    for col in df.columns[1:]:
        fig.add_trace(go.Scatter(
            x=df['year'], y=df[col],
            mode='lines', name=col,
            line=dict(color=colors.get(col, '#757575'), width=widths.get(col, cfg['line_widths']['standard'])),
        ))

    w_px, h_px = get_chart_dims_px("social_unrest_events.png")
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
    years = sorted(df['year'].unique())
    fig.update_xaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
        tickmode='array',
        tickvals=years,
        ticktext=[str(y) if i == 0 else (str(y % 100) if i % 2 == 0 else '') for i, y in enumerate(years)],
    )
    fig.update_yaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
        zeroline=True, zerolinecolor=cfg['axes']['linecolor'],
    )

    base = "social_unrest_events"
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=True, include_plotlyjs='cdn')
    df.round(2).to_csv(output_dir / f"{base}.csv", index=False)
    print(f"Saved {base}.png")


def plot_irf(xl_path, cfg, output_dir):
    df = pd.read_excel(xl_path, sheet_name='Figure 1.27.2', header=0)
    df.columns = ['step', 'impulse_response', 'irf', 'lower', 'band_width']
    df['step'] = df['step'].astype(int)
    df['upper'] = df['lower'] + df['band_width']

    fig = go.Figure()

    # Central estimate (first so it appears first in legend)
    fig.add_trace(go.Scatter(
        x=df['step'], y=df['irf'],
        mode='lines', name='Impulse response',
        line=dict(color='#6A1B9A', width=cfg['line_widths']['thick']),
    ))

    # Band (10th-90th)
    fig.add_trace(go.Scatter(
        x=list(df['step']) + list(df['step'][::-1]),
        y=list(df['upper']) + list(df['lower'][::-1]),
        fill='toself',
        fillcolor='rgba(106, 27, 154, 0.2)',
        line=dict(color='rgba(0,0,0,0)'),
        name='10th–90th percentile',
        showlegend=True,
    ))

    # Zero line
    fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.6)

    w_px, h_px = get_chart_dims_px("social_unrest_irf.png")
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
        xaxis_title=dict(text="Years after shock", font=dict(size=cfg['axes']['tickfont_size'])),
    )
    fig.update_xaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
    )
    fig.update_yaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
    )

    base = "social_unrest_irf"
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=True, include_plotlyjs='cdn')
    df.round(4).to_csv(output_dir / f"{base}.csv", index=False)
    print(f"Saved {base}.png")


if __name__ == "__main__":
    main()
