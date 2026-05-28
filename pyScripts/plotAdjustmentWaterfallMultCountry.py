"""
Multi-country fiscal-gap waterfall panel (1x3): Germany, Japan, Poland.

Each subplot decomposes the change in the fiscal gap (2014-19 -> 2024-29) into
government revenue, primary spending, and the snowball components, mirroring the
single-country plotAdjustmentWaterfall charts. Layout follows the
globe_debt_decomposition_waterfall panel (shared step labels on the left,
per-subplot x-scales, no legend).
"""
import pandas as pd
import plotly.io as pio
from plotly.subplots import make_subplots
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, get_chart_dims_px

# Reuse data loading and waterfall construction from the single-country script
from plotAdjustmentWaterfall import get_data, create_waterfall_chart

COUNTRIES = [('DEU', 'Germany'), ('JPN', 'Japan'), ('POL', 'Poland')]
PNG_NAME = "adjustmentNeeded_waterfall_multi_2014-19_vs_2024-29.png"


def main():
    config = load_config()
    cfg = load_chart_config()['styling']
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    target = [iso for iso, _ in COUNTRIES]
    agg_p1 = get_data(data_path, 2014, 2019, target)
    agg_p2 = get_data(data_path, 2024, 2029, target)
    if agg_p1.empty or agg_p2.empty:
        print("Error: missing data for one or both periods.")
        return

    fig = make_subplots(
        rows=1, cols=3,
        shared_yaxes=True,
        horizontal_spacing=0.04,
        subplot_titles=[name for _, name in COUNTRIES],
    )

    x_ranges = []
    for col, (iso, name) in enumerate(COUNTRIES, start=1):
        d1 = agg_p1[agg_p1['isocode'] == iso]
        d2 = agg_p2[agg_p2['isocode'] == iso]
        if d1.empty or d2.empty:
            print(f"  WARNING: no data for {name} ({iso})")
            x_ranges.append(None)
            continue
        subfig, xr = create_waterfall_chart(d1, d2)
        trace = subfig.data[0]
        trace.showlegend = False
        fig.add_trace(trace, row=1, col=col)
        x_ranges.append(xr)

    w_px, h_px = get_chart_dims_px(PNG_NAME)
    fig.update_layout(
        template=cfg['template'],
        width=w_px, height=h_px,
        margin={**cfg['margins'], "l": 180, "t": 55},
        font={"size": cfg['font_size']},
        showlegend=False,
    )

    # Shared category axis (labels on left only), first step on top
    fig.update_yaxes(
        showgrid=False,
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont={"size": cfg['axes']['tickfont_size']},
        autorange="reversed",
    )
    for col, xr in enumerate(x_ranges, start=1):
        fig.update_xaxes(
            showgrid=cfg['axes']['showgrid'],
            gridcolor=cfg['axes'].get('gridcolor'),
            linecolor=cfg['axes']['linecolor'],
            linewidth=cfg['axes'].get('linewidth'),
            ticks=cfg['axes']['ticks'],
            tickfont={"size": cfg['axes']['tickfont_size']},
            range=xr,
            zeroline=True,
            zerolinecolor=cfg['axes']['linecolor'],
            row=1, col=col,
        )

    # Subplot titles: keep default font, nudge up slightly (like globe panel)
    for i in range(len(fig.layout.annotations)):
        fig.layout.annotations[i].y += 0.01

    base = PNG_NAME[:-4]
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=auto_open, include_plotlyjs='cdn')

    # CSV (one column per country)
    csv_labels = ["2014–19 fiscal gap", "Government revenue", "Government primary spending",
                  "Snowball: r", "Snowball: g (real)", "Snowball: price", "2024–29 fiscal gap"]
    out = {"Label": csv_labels}
    for iso, name in COUNTRIES:
        d1 = agg_p1[agg_p1['isocode'] == iso]
        d2 = agg_p2[agg_p2['isocode'] == iso]
        if d1.empty or d2.empty:
            continue
        rev = d2['gov_revenue'].iloc[0] - d1['gov_revenue'].iloc[0]
        exp = -(d2['primary_exp'].iloc[0] - d1['primary_exp'].iloc[0])
        r = -(d2['snow_ball_r'].iloc[0] - d1['snow_ball_r'].iloc[0])
        g_real = -(d2['snow_ball_g_real'].iloc[0] - d1['snow_ball_g_real'].iloc[0])
        g_defl = -(d2['snow_ball_g_deflator'].iloc[0] - d1['snow_ball_g_deflator'].iloc[0])
        out[name] = [round(v, 2) for v in [
            d1['adjustment_needed'].iloc[0], rev, exp, r, g_real, g_defl, d2['adjustment_needed'].iloc[0]
        ]]
    pd.DataFrame(out).to_csv(output_dir / f"{base}.csv", index=False)

    print(f"Saved {base}.png")


if __name__ == "__main__":
    main()
