"""
Generate a 1x3 panel chart for fiscal outlook, overlaying Globe and Poland:
1. Real GDP Growth (%)
2. Overall Balance (% of GDP)
3. Gross Government Debt (% of GDP)

Each entity is shown for two vintages: April 2026 FM (solid) and April 2025 FM
(dashed). Entity is encoded by color (Globe = purple, Poland = teal).
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, get_chart_dims_px

POLAND_IFSCODE = 964

# Entity styling. Globe dominates: bold purple, drawn on top. Poland is a
# lighter, thinner teal sitting behind. Vintage encoded by width/shade
# (April 2026 = thicker/darker, April 2025 = thinner/lighter).
ENTITY_STYLE = {
    'Globe':  dict(color='#6A1B9A', light='#B39DDB', bg='rgba(225, 190, 231, 0.9)',
                   main_w=5.5, comp_w=3, marker=12, rank_main=1, rank_comp=2),
    'Poland': dict(color='#4DB6AC', light='#B2DFDB', bg='rgba(224, 242, 241, 0.9)',
                   main_w=3, comp_w=2, marker=9, rank_main=3, rank_comp=4),
}


def load_data():
    """Load WEO enhanced data (April 2026 FM fiscal database)."""
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    return pd.read_stata(data_path)


def load_apr2025_data():
    """Load April 2025 WEO public data."""
    data_path = resolve_from_config("../data/fmData/WEOApr2025Pub.dta")
    return pd.read_stata(data_path)


def load_weo_growth():
    """Load current-vintage WEO (has country-level real GDP growth)."""
    data_path = resolve_from_config("../data/fmData/WEO.dta")
    return pd.read_stata(data_path)


def add_entity(fig, main_data, comp_data, var_name, col, entity, show_legend=False, label_above=True):
    """Overlay one entity's two vintages (April 2026 solid + April 2025 dashed) on a subplot column."""
    style = ENTITY_STYLE[entity]

    # April 2025 FM (dashed, lighter)
    if comp_data is not None and var_name in comp_data.columns:
        cs = comp_data[comp_data[var_name].notna()]
        if len(cs) > 0:
            fig.add_trace(go.Scatter(
                x=cs['year'], y=cs[var_name], mode='lines',
                name=f'{entity} (April 2025 FM)',
                line=dict(color=style['light'], width=style['comp_w']),
                showlegend=show_legend, legendgroup=f'{entity}_2025',
                legendrank=style['rank_comp']
            ), row=1, col=col)

    # April 2026 FM (solid, thick)
    fig.add_trace(go.Scatter(
        x=main_data['year'], y=main_data[var_name], mode='lines',
        name=f'{entity} (April 2026 FM)',
        line=dict(color=style['color'], width=style['main_w']),
        showlegend=show_legend, legendgroup=f'{entity}_2026',
        legendrank=style['rank_main']
    ), row=1, col=col)

    # Markers at 2025 and 2031 on the main (April 2026) line
    md = main_data[main_data['year'].isin([2025, 2031])]
    fig.add_trace(go.Scatter(
        x=md['year'], y=md[var_name], mode='markers',
        marker=dict(symbol='circle-open', size=style['marker'], color=style['color'], line=dict(width=3, color=style['color'])),
        showlegend=False
    ), row=1, col=col)

    # Value labels at 2025 and 2031 for the main line.
    # label_above may be a bool (all years) or a {year: bool} mapping.
    for year in [2025, 2031]:
        above = label_above[year] if isinstance(label_above, dict) else label_above
        yshift = 30 if above else -34
        rd = main_data[main_data['year'] == year]
        if len(rd) > 0:
            val = rd[var_name].values[0]
            if pd.isna(val):
                continue
            fig.add_annotation(
                x=year, y=val, text=f'{val:.1f}', showarrow=False, yshift=yshift,
                font=dict(size=13, color=style['color']),
                bgcolor=style['bg'], borderpad=2, row=1, col=col
            )


def build_region(df_enh, df_apr2025, df_weo, ifscode):
    """Assemble main (April 2026 FM) and comparison (April 2025 FM) frames for one entity."""
    main = df_enh[df_enh['ifscode'] == ifscode].copy()
    main = main[main['year'].between(2015, 2031)].sort_values('year')
    growth = df_weo[df_weo['ifscode'] == ifscode][['year', 'ngdp_rpch']]
    main = main.drop(columns=['ngdp_rpch'], errors='ignore').merge(growth, on='year', how='left')

    comp = df_apr2025[df_apr2025['ifscode'] == ifscode].copy()
    comp = comp[comp['year'].between(2015, 2031)].sort_values('year')
    return main, comp


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)

    df = load_data()
    df_apr2025 = load_apr2025_data()
    df_weo = load_weo_growth()

    # --- Globe (curated global growth series) ---------------------------------
    global_data = df[df['ifscode'] == 9999].copy()
    global_data = global_data[global_data['year'].between(2015, 2031)].sort_values('year')

    growth_path = resolve_from_config("../data/fmData/global_real_gdp_growth.csv")
    growth = pd.read_csv(growth_path)
    global_data = global_data.drop(columns=['ngdp_rpch'], errors='ignore').merge(
        growth[['year', 'ngdp_rpch_2026apr']].rename(columns={'ngdp_rpch_2026apr': 'ngdp_rpch'}),
        on='year', how='left'
    )

    apr2025_global = df_apr2025[df_apr2025['ifscode'] == 1].copy()
    apr2025_global = apr2025_global[apr2025_global['year'].between(2015, 2031)].sort_values('year')
    apr2025_global = apr2025_global.drop(columns=['ngdp_rpch'], errors='ignore').merge(
        growth[['year', 'ngdp_rpch_2025apr']].rename(columns={'ngdp_rpch_2025apr': 'ngdp_rpch'}),
        on='year', how='left'
    )

    # --- Poland ---------------------------------------------------------------
    poland_data, apr2025_poland = build_region(df, df_apr2025, df_weo, POLAND_IFSCODE)

    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    print("Generating Globe + Poland Outlook panel chart...")

    fig = make_subplots(
        rows=1, cols=3,
        horizontal_spacing=0.08,
        subplot_titles=['Real GDP<br>(Annual percentage change)', 'Overall Balance<br>(Percent of GDP)', 'Gross Debt<br>(Percent of GDP)']
    )

    vars_by_col = {1: 'ngdp_rpch', 2: 'ggxcnl_gdp', 3: 'ggxwdg_gdp'}
    for col, var in vars_by_col.items():
        # Globe labels above, Poland labels below by default. For Real GDP (col 1)
        # in 2025 Poland sits higher than Globe, so swap that year's labels.
        if col == 1:
            globe_la = {2025: False, 2031: True}
            poland_la = {2025: True, 2031: False}
        elif col == 3:
            # Gross Debt: lift Poland's 2031 label above its point so it clears
            # the April 2025 line running just below.
            globe_la = True
            poland_la = {2025: False, 2031: True}
        else:
            globe_la, poland_la = True, False
        # Draw Poland first (behind), Globe last (on top) so Globe dominates.
        add_entity(fig, poland_data, apr2025_poland, var, col, 'Poland', show_legend=(col == 1), label_above=poland_la)
        add_entity(fig, global_data, apr2025_global, var, col, 'Globe', show_legend=(col == 1), label_above=globe_la)
        # Forecast horizon shading (once per column)
        fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0, row=1, col=col)

    # Layout
    w_px, h_px = get_chart_dims_px("global_outlook_panel.png")
    fig.update_layout(
        template=chart_cfg['template'],
        width=w_px,
        height=h_px,
        margin=dict(t=70, b=30, l=40, r=20),
        font=dict(size=chart_cfg['font_size']),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.28,
            xanchor='center',
            x=0.5,
            font=dict(size=chart_cfg['legend']['font_size'])
        )
    )

    # Move subplot titles higher
    for annotation in fig['layout']['annotations']:
        annotation['y'] = annotation['y'] + 0.08
        annotation['font'] = dict(size=chart_cfg['axes']['tickfont_size'])

    # Update all x-axes
    for col in [1, 2, 3]:
        fig.update_xaxes(
            showgrid=True,
            gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
            dtick=5,
            tick0=2015,
            range=[2014.5, 2031.5],
            linecolor=chart_cfg['axes']['linecolor'],
            linewidth=chart_cfg['axes'].get('linewidth', 1.5),
            ticks=chart_cfg['axes']['ticks'],
            tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
            row=1, col=col
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
            zeroline=True,
            zerolinecolor='black',
            linecolor=chart_cfg['axes']['linecolor'],
            linewidth=chart_cfg['axes'].get('linewidth', 1.5),
            ticks=chart_cfg['axes']['ticks'],
            tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
            row=1, col=col
        )

    # Save outputs
    save_path = output_dir / 'global_outlook_panel'
    pio.write_image(fig, f"{save_path}.png", format='png', engine='kaleido', scale=2)
    fig.write_html(f"{save_path}.html", auto_open=auto_open)
    print(f"  Saved global_outlook_panel.png")

    # Export CSV (globe + Poland)
    def tidy(frame, region):
        out = frame[['year', 'ggxcnl_gdp', 'ggxwdg_gdp', 'ngdp_rpch']].copy()
        out.columns = ['year', 'overall_balance', 'gross_debt', 'real_gdp_growth']
        out.insert(0, 'region', region)
        return out.round(2)

    csv_data = pd.concat([tidy(global_data, 'Globe'), tidy(poland_data, 'Poland')], ignore_index=True)
    csv_path = output_dir / 'global_outlook.csv'
    csv_data.to_csv(csv_path, index=False)
    print(f"  Exported data to {csv_path}")

    print("Globe + Poland Outlook panel complete.")


if __name__ == "__main__":
    main()
