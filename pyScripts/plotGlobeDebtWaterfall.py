import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, get_chart_dims_px

GLOBE_IFSCODE = 9999
POLAND_IFSCODE = 964

# Shared waterfall step labels (same decomposition for every entity)
Y_LABELS = [
    "2025 debt",
    "Primary deficit",
    "Snowball: <i>r</i>",
    "Snowball: <i>g</i> (real)",
    "Snowball: π (price)",
    "Stock-flow adjustment",
    "2031 debt",
]
MEASURES = ["absolute", "relative", "relative", "relative", "relative", "relative", "total"]
CSV_LABELS = ["2025 debt", "Primary deficit", "Snowball: r", "Snowball: g (real)",
              "Snowball: price", "Stock-flow adjustment", "2031 debt"]


def load_data():
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    return pd.read_stata(data_path)


def compute_components(df, ifscode):
    """Return the 2025->2031 waterfall x-values for one entity."""
    g = df[df['ifscode'] == ifscode].sort_values('year').copy()
    debt_2025 = g[g['year'] == 2025]['ggxwdg_gdp'].iloc[0]
    debt_2031 = g[g['year'] == 2031]['ggxwdg_gdp'].iloc[0]

    period = g[(g['year'] >= 2026) & (g['year'] <= 2031)]
    sum_primary_deficit = -period['primary_balance'].sum()  # deficit = -balance
    sum_snow_r = period['snow_ball_r'].sum()
    sum_snow_g_real = period['snow_ball_g_real'].sum()       # already negative in data
    sum_snow_g_deflator = period['snow_ball_g_deflator'].sum()
    sum_sfa = period['sfa_gdp'].sum()

    calculated = debt_2025 + sum_primary_deficit + sum_snow_r + sum_snow_g_real + sum_snow_g_deflator + sum_sfa
    if abs(calculated - debt_2031) > 0.1:
        print(f"WARNING ({ifscode}): components don't sum. Calc {calculated:.2f} vs actual {debt_2031:.2f}")

    return [debt_2025, sum_primary_deficit, sum_snow_r, sum_snow_g_real, sum_snow_g_deflator, sum_sfa, debt_2031]


def waterfall_trace(x_vals, cfg, show_legend=False):
    text_vals = [f"{v:+.1f}" if i in [1, 2, 3, 4, 5] else f"{v:.0f}" for i, v in enumerate(x_vals)]
    return go.Waterfall(
        orientation="h",
        measure=MEASURES,
        y=Y_LABELS,
        x=x_vals,
        text=text_vals,
        textposition="outside",
        textfont={"size": cfg['legend']['font_size']},
        width=0.5,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#00897B"}},  # debt reduction (teal)
        increasing={"marker": {"color": "#E65100"}},  # debt increase (orange)
        totals={"marker": {"color": "#6A1B9A"}},       # totals (purple)
        showlegend=False,
    )


def _x_range(x_vals):
    cumulative = [x_vals[0]]
    for val in x_vals[1:-1]:
        cumulative.append(cumulative[-1] + val)
    x_min = min(cumulative + [x_vals[0], x_vals[-1]])
    x_max = max(cumulative + [x_vals[0], x_vals[-1]])
    span = x_max - x_min
    # Room on both sides so outside value labels (left for decreases, right for
    # increases) are not clipped at the subplot edges.
    return [x_min - span * 0.42, x_max + span * 0.55]


def main():
    config = load_config()
    cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)

    df = load_data()

    globe_vals = compute_components(df, GLOBE_IFSCODE)
    poland_vals = compute_components(df, POLAND_IFSCODE)

    fig = make_subplots(
        rows=1, cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.04,
        subplot_titles=['Global<br>(Percent of global GDP)', 'Poland<br>(Percent of GDP)']
    )
    fig.add_trace(waterfall_trace(globe_vals, cfg), row=1, col=1)
    fig.add_trace(waterfall_trace(poland_vals, cfg), row=1, col=2)

    w_px, h_px = get_chart_dims_px("globe_debt_decomposition_waterfall_2025-31.png")
    fig.update_layout(
        template=cfg['template'],
        width=w_px,
        height=h_px,
        margin={**cfg['margins'], "l": 180, "t": 55},  # t/b matched to country panel
        font={"size": cfg['font_size']},
        showlegend=False,
    )

    # Shared category axis (labels on the left only), first step on top
    fig.update_yaxes(
        showgrid=False,
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont={"size": cfg['axes']['tickfont_size']},
        autorange="reversed",
    )
    for col, vals in [(1, globe_vals), (2, poland_vals)]:
        fig.update_xaxes(
            showgrid=cfg['axes']['showgrid'],
            gridcolor=cfg['axes'].get('gridcolor'),
            linecolor=cfg['axes']['linecolor'],
            linewidth=cfg['axes'].get('linewidth'),
            ticks=cfg['axes']['ticks'],
            tickfont={"size": cfg['axes']['tickfont_size']},
            range=_x_range(vals),
            zeroline=True,
            zerolinecolor=cfg['axes']['linecolor'],
            row=1, col=col,
        )

    # Subplot titles: keep Plotly's default font (matches the country
    # decomposition panel on the same slide); only nudge them up slightly.
    for i in range(len(fig.layout.annotations)):
        fig.layout.annotations[i].y += 0.01

    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    base_name = "globe_debt_decomposition_waterfall_2025-31"
    csv_df = pd.DataFrame({
        "Label": CSV_LABELS,
        "Global": [round(v, 2) for v in globe_vals],
        "Poland": [round(v, 2) for v in poland_vals],
    })
    csv_df.to_csv(output_dir / f"{base_name}.csv", index=False)

    pio.write_image(fig, output_dir / f"{base_name}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base_name}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base_name}.html", auto_open=auto_open, include_plotlyjs='cdn')

    create_metadata(output_dir / f"{base_name}.txt")
    print(f"Workflow complete. Saved {base_name}.png")


def create_metadata(output_path):
    content = [
        "CHART METADATA: DEBT DECOMPOSITION WATERFALL PANEL (2025-31)",
        "=" * 50,
        "TITLE: Decomposition of the Change in General Government Debt, 2025–31 (Global and Poland)",
        "UNITS: Percent of GDP",
        "SOURCES: IMF, World Economic Outlook database; and IMF staff calculations.",
        "",
        "NOTE: Each panel decomposes the change in the debt-to-GDP ratio between 2025 and 2031 into its primary drivers: the cumulative primary deficit, the snowball effect components (interest rate r, real GDP growth g, and GDP deflator growth), and stock-flow adjustments. Left: global aggregate. Right: Poland. Positive values increase the debt ratio.",
        "=" * 50,
    ]
    with open(output_path, 'w') as f:
        f.write('\n'.join(content))


if __name__ == "__main__":
    main()
