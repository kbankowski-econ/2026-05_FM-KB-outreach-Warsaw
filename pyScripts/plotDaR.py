"""
Plot Debt-at-Risk (DaR) density chart.
Uses f3 sheet from global_dar.xlsx (2024 and 2025 WEO baselines)
and density_scenario3_WLD_h3.xlsx (severe scenario).
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, get_chart_dims_px


def extract_stats(df, suffix):
    """Extract percentile/mean/mode values from the data."""
    stats = {}
    for stat in ['p5', 'p50', 'p95', 'mean', 'mode']:
        col = f'{stat}_combined{suffix}'
        if col in df.columns:
            vals = df[col].dropna()
            if not vals.empty:
                stats[stat] = df.loc[vals.index[0], 'debt_gdpg_support']
    return stats


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    # Load f3 sheet (baseline densities)
    dar_path = resolve_from_config("../data/fmData/global_dar.xlsx")
    df = pd.read_excel(dar_path, sheet_name='f3')

    fig = go.Figure()

    # April 2026 baseline
    fig.add_trace(go.Scatter(
        x=df['debt_gdpg_support'], y=df['density_combined_w2025WLD'],
        mode='lines', name='April 2026 (reference)',
        line=dict(color='rgba(106, 27, 154, 0.4)', width=chart_cfg['line_widths']['thick'] + 1),
        showlegend=False
    ))

    # Add percentile markers for baseline
    import numpy as np
    stats_2025 = extract_stats(df, '2025WLD')
    density_col = 'density_combined_w2025WLD'
    ann_font = chart_cfg['font_size'] - 6
    for stat, x_val in stats_2025.items():
        if stat in ['p50', 'p95']:
            closest_idx = (df['debt_gdpg_support'] - x_val).abs().idxmin()
            y_val = df.loc[closest_idx, density_col]
            # p50: above; p95: to the left
            ax_off = -55 if stat == 'p95' else 0
            ay_off = 0 if stat == 'p95' else 28
            fig.add_trace(go.Scatter(
                x=[x_val], y=[y_val],
                mode='markers',
                marker=dict(symbol='circle', size=14, color='white', line=dict(width=4, color='#6A1B9A')),
                showlegend=False,
                hovertemplate=f"<b>{stat}</b>: {x_val:.1f}<extra></extra>"
            ))
            label_val = 98.8 if stat == 'p50' else x_val
            fig.add_annotation(
                x=x_val, y=y_val,
                text=f"{label_val:.1f} <sub>({stat})</sub>",
                showarrow=False, xshift=ax_off, yshift=ay_off,
                font=dict(size=ann_font, color='#6A1B9A'),
                bgcolor='rgba(225, 190, 231,1)', borderwidth=0
            )

    # Layout
    density_w, density_h = get_chart_dims_px("debt_at_risk_density.png")
    fig.update_layout(
        template=chart_cfg['template'],
        width=density_w,
        height=density_h,
        margin=dict(t=30, b=40, l=50, r=20),
        font=dict(size=chart_cfg['font_size']),
        showlegend=False,
        xaxis_title=dict(text="2028 Debt-to-GDP ratio (Percent)", font=dict(size=chart_cfg['font_size'] - 4)),
        yaxis_title=dict(text="Density", font=dict(size=chart_cfg['font_size'] - 4))
    )

    fig.update_xaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes'].get('gridcolor'),
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth'),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        range=[80, 120]
    )

    y_max = df['density_combined_w2025WLD'].max()
    fig.update_yaxes(
        showgrid=True,
        gridcolor=chart_cfg['axes'].get('gridcolor'),
        linecolor=chart_cfg['axes']['linecolor'],
        showticklabels=False,
        ticks='',
        zeroline=False,
        range=[0, y_max * 1.15]
    )

    # Save outputs
    save_path = output_dir / "debt_at_risk_density"
    pio.write_image(fig, f"{save_path}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, f"{save_path}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(f"{save_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
    print(f"DaR density chart saved to {save_path}.png")

    # --- Scenario bar chart ---
    plot_scenario_bars(chart_cfg, output_dir, auto_open)


def plot_scenario_bars(chart_cfg, output_dir, auto_open):
    """Create a 1x2 bar chart: Adverse Scenario vs AI Scenario."""
    from plotly.subplots import make_subplots

    xl_path = resolve_from_config("../data/fmData/2026AprFiscalMonitorDatabase.xlsx")

    # Adverse scenario (Figure 1.25)
    df_adv = pd.read_excel(xl_path, sheet_name='Figure 1.25', header=None)
    adv_data = df_adv.iloc[9:12, [1, 2]].copy()
    adv_data.columns = ['group', 'value']
    adv_data['value'] = pd.to_numeric(adv_data['value'])

    # AI scenario (Figure 1.33, column E = difference)
    df_ai = pd.read_excel(xl_path, sheet_name='Figure 1.33', header=None)
    ai_data = df_ai.iloc[6:9, [1, 4]].copy()
    ai_data.columns = ['group', 'value']
    ai_data['value'] = pd.to_numeric(ai_data['value'])

    # Three shades per scenario (dark -> light) for the three groups
    adv_shades = ['#BF360C', '#E65100', '#FB8C00']  # Middle East war (orange family)
    ai_shades = ['#006064', '#00838F', '#26C6DA']   # AI investment shock (teal family)

    bar_w, bar_h = get_chart_dims_px("debt_at_risk_adverse.png")
    common_layout = dict(
        template=chart_cfg['template'],
        width=bar_w,
        height=bar_h,
        margin=dict(t=40, b=40, l=50, r=20),
        font=dict(size=chart_cfg['font_size']),
    )
    common_xaxes = dict(
        linecolor=chart_cfg['axes']['linecolor'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )
    common_yaxes = dict(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes'].get('gridcolor'),
        linecolor=chart_cfg['axes']['linecolor'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        title=dict(text="Percentage points of GDP", font=dict(size=chart_cfg['font_size'] - 4)),
        range=[0, 7],
        dtick=1,
        autorange=False,
    )

    def make_bar_chart(data, shades):
        fig = go.Figure()
        for i, (_, row) in enumerate(data.iterrows()):
            fig.add_trace(go.Bar(
                x=[row['group']], y=[row['value']],
                marker_color=shades[i % len(shades)],
                showlegend=False,
                text=f"{row['value']:.1f}", textposition='inside', insidetextanchor='end',
                textfont=dict(size=chart_cfg['legend']['font_size'], color='white')
            ))
        fig.update_layout(**common_layout)
        fig.update_xaxes(**common_xaxes)
        fig.update_yaxes(**{k: v for k, v in common_yaxes.items() if k != 'title'})
        return fig

    # Adverse scenario chart
    fig_adv = make_bar_chart(adv_data, adv_shades)
    save_adv = output_dir / "debt_at_risk_adverse"
    pio.write_image(fig_adv, f"{save_adv}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig_adv, f"{save_adv}.svg", format='svg', engine='kaleido', scale=2)
    fig_adv.write_html(f"{save_adv}.html", auto_open=auto_open, include_plotlyjs='cdn')
    adv_data.round(2).to_csv(f"{save_adv}.csv", index=False)
    print(f"DaR adverse scenario chart saved to {save_adv}.png")

    # AI scenario chart
    fig_ai = make_bar_chart(ai_data, ai_shades)
    save_ai = output_dir / "debt_at_risk_ai"
    pio.write_image(fig_ai, f"{save_ai}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig_ai, f"{save_ai}.svg", format='svg', engine='kaleido', scale=2)
    fig_ai.write_html(f"{save_ai}.html", auto_open=auto_open, include_plotlyjs='cdn')
    ai_data.round(2).to_csv(f"{save_ai}.csv", index=False)
    print(f"DaR AI scenario chart saved to {save_ai}.png")


if __name__ == "__main__":
    main()
