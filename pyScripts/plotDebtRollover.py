"""
Plot simulated change in debt-to-GDP from short-term borrowing cost increase.
Two-panel (2x1): Low Debt (60%) and High Debt (100%).
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

    df = pd.read_excel(xl_path, sheet_name='Figure 1.30', header=0)
    df.columns = ['debt_level', 'scenario', 'long_maturity', 'short_maturity']
    df['long_maturity'] = pd.to_numeric(df['long_maturity'])
    df['short_maturity'] = pd.to_numeric(df['short_maturity'])

    low = df[df['debt_level'].str.contains('Low')]
    high = df[df['debt_level'].str.contains('High')]

    colors = {'Long Maturity': '#6A1B9A', 'Short Maturity': '#E65100'}

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.15,
        subplot_titles=['Low Debt (60 percent of GDP)', 'High Debt (100 percent of GDP)'],
    )

    for col_idx, (subset, title) in enumerate([(low, 'Low'), (high, 'High')], start=1):
        for mat_col, mat_label in [('long_maturity', 'Long Maturity'), ('short_maturity', 'Short Maturity')]:
            fig.add_trace(go.Bar(
                x=subset['scenario'],
                y=subset[mat_col],
                name=mat_label,
                marker_color=colors[mat_label],
                text=[f"{v:.1f}" for v in subset[mat_col]],
                textposition='outside',
                textfont=dict(size=cfg['legend']['font_size']),
                showlegend=(col_idx == 1),
            ), row=1, col=col_idx)

    w_px, h_px = get_chart_dims_px("debt_rollover_simulation.png")
    fig.update_layout(
        template=cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=60, b=40, l=40, r=20),
        font=dict(size=cfg['axes']['tickfont_size']),
        barmode='group',
        legend=dict(
            **{k: v for k, v in cfg['legend'].items() if k not in ('font_size', 'y')},
            y=1.12,
            font=dict(size=cfg['legend']['font_size']),
        ),
    )

    for a in fig.layout.annotations:
        a.font.size = cfg['axes']['tickfont_size']

    y_max = df[['long_maturity', 'short_maturity']].max().max() * 1.2
    fig.update_xaxes(
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
        range=[0, y_max],
    )

    base = "debt_rollover_simulation"
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=True, include_plotlyjs='cdn')
    df.round(2).to_csv(output_dir / f"{base}.csv", index=False)
    print(f"Saved {base}.png")


if __name__ == "__main__":
    main()
