"""
Plot AE Fiscal Risks horizontal bar chart from 2026AprFiscalMonitorDatabase.xlsx, Figure 1.35.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, get_chart_dims_px


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    xl_path = resolve_from_config("../data/fmData/2026AprFiscalMonitorDatabase.xlsx")
    df = pd.read_excel(xl_path, sheet_name='Figure 1.35', header=None, skiprows=1)
    df.columns = ['risk', 'percent']
    df['percent'] = pd.to_numeric(df['percent'])

    # Reverse order so highest bar is at top
    df = df.iloc[::-1].reset_index(drop=True)

    # Color grading: higher value = more opaque/saturated blue
    max_val = df['percent'].max()
    bar_colors = [f'rgba(106, 27, 154, {0.15 + 0.85 * (v / max_val) ** 1.5})' for v in df['percent']]

    fig = go.Figure(go.Bar(
        x=df['percent'],
        y=df['risk'],
        orientation='h',
        marker_color=bar_colors,
        text=df['percent'].astype(int).astype(str),
        textposition='inside',
        insidetextanchor='end',
        textfont=dict(color='white', size=chart_cfg['legend']['font_size'])
    ))

    w_px, h_px = get_chart_dims_px("ae_fiscal_risks.png")
    fig.update_layout(
        template=chart_cfg['template'],
        width=w_px,
        height=h_px,
        margin=dict(t=20, b=40, l=250, r=40),
        font=dict(size=chart_cfg['font_size']),
    )

    fig.update_xaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes'].get('gridcolor'),
        linecolor=chart_cfg['axes']['linecolor'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        range=[0, max(df['percent']) * 1.15]
    )

    fig.update_yaxes(
        linecolor=chart_cfg['axes']['linecolor'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )

    save_path = output_dir / "ae_fiscal_risks"
    pio.write_image(fig, f"{save_path}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, f"{save_path}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(f"{save_path}.html", auto_open=auto_open, include_plotlyjs='cdn')

    # CSV export
    df_out = df.iloc[::-1].reset_index(drop=True)  # back to original order for CSV
    df_out.to_csv(f"{save_path}.csv", index=False)

    print(f"AE Fiscal Risks chart saved to {save_path}.png")


if __name__ == "__main__":
    main()
