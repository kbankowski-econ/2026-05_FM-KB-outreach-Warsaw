"""
Generate a 1x2 panel chart for interest payments and primary balance,
overlaying Globe and Poland spaghetti (April 2021-2025 vintage fan + bold
April 2026 line):
1. Interest Payments (Percent of GDP) - ggei_gdp
2. Primary Balance (Percent of GDP) - primary_balance

Entity is encoded by color (Globe = purple over gray fan, Poland = teal over
a light-teal fan), consistent with the global outlook slide.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, get_chart_dims_px

GLOBE_IFSCODE = 9999
POLAND_IFSCODE = 964

# Historical vintage files with a per-entity color ramp (older = lighter).
VINTAGE_FILES = [
    (2021, "../data/fmData/WEOApr2021Pub_enhanced.dta"),
    (2022, "../data/fmData/WEOApr2022Pub_enhanced.dta"),
    (2023, "../data/fmData/WEOApr2023Pub_enhanced.dta"),
    (2024, "../data/fmData/WEOApr2024Pub_enhanced.dta"),
    (2025, "../data/fmData/WEOApr2025Pub_enhanced.dta"),
]

# Per-entity styling. Main (April 2026) color is the bold identity color;
# the fan is a light->dark ramp ending just below the main color.
ENTITY = {
    'Globe': dict(
        ifscode=GLOBE_IFSCODE, main='#6A1B9A', main_w=5, marker=12,
        bg='rgba(225, 190, 231, 0.9)',
        fan={2021: '#EDE7F6', 2022: '#D1C4E9', 2023: '#B39DDB', 2024: '#9575CD', 2025: '#7E57C2'},
    ),
    'Poland': dict(
        ifscode=POLAND_IFSCODE, main='#4DB6AC', main_w=4, marker=10,
        bg='rgba(224, 242, 241, 0.9)',
        fan={2021: '#DCEFEE', 2022: '#C0E5E1', 2023: '#A4DBD5', 2024: '#88D0C9', 2025: '#6CC6BD'},
    ),
}


def load_data():
    """Load WEO enhanced data (April 2026 FM)."""
    return pd.read_stata(resolve_from_config("../data/fmData/WEO_enhanced.dta"))


def load_historical(ifscode):
    """Load each historical vintage filtered to one entity."""
    out = []
    for year, file_path in VINTAGE_FILES:
        try:
            df = pd.read_stata(resolve_from_config(file_path))
        except FileNotFoundError:
            print(f"  WARNING: Historical file not found - {file_path}")
            continue
        sub = df[df['ifscode'] == ifscode].copy()
        sub = sub[sub['year'].between(2015, 2031)].sort_values('year')
        out.append((year, sub))
    return out


def add_historical(fig, historical, var, col, style, entity, show_legend, rank0):
    """Add an entity's vintage fan (drawn behind the main lines)."""
    for i, (year, hist_df) in enumerate(historical):
        if var not in hist_df.columns:
            continue
        hs = hist_df[hist_df[var].notna()]
        if len(hs) == 0:
            continue
        fig.add_trace(go.Scatter(
            x=hs['year'], y=hs[var], mode='lines',
            name=f'{entity} (April {year} FM)',
            line=dict(color=style['fan'][year], width=2.5),
            showlegend=show_legend, legendgroup=f'{entity}_apr{year}',
            legendrank=rank0 + i
        ), row=1, col=col)


def add_main(fig, data, var, col, style, entity, show_legend, label_above, rank):
    """Add an entity's bold April 2026 line, markers and value labels (on top)."""
    plot_data = data[data[var].notna()]
    if len(plot_data) == 0:
        return

    fig.add_trace(go.Scatter(
        x=plot_data['year'], y=plot_data[var], mode='lines',
        name=f'{entity} (April 2026 FM)',
        line=dict(color=style['main'], width=style['main_w']),
        showlegend=show_legend, legendgroup=f'{entity}_2026',
        legendrank=rank
    ), row=1, col=col)

    md = plot_data[plot_data['year'].isin([2025, 2031])]
    if len(md) > 0:
        fig.add_trace(go.Scatter(
            x=md['year'], y=md[var], mode='markers',
            marker=dict(symbol='circle-open', size=style['marker'], color=style['main'], line=dict(width=3, color=style['main'])),
            showlegend=False
        ), row=1, col=col)

    yshift = 30 if label_above else -34
    for year in [2025, 2031]:
        rd = plot_data[plot_data['year'] == year]
        if len(rd) > 0:
            val = rd[var].values[0]
            if pd.isna(val):
                continue
            fig.add_annotation(
                x=year, y=val, text=f'{val:.1f}', showarrow=False, yshift=yshift,
                font=dict(size=14, color=style['main']),
                bgcolor=style['bg'], borderpad=3, row=1, col=col
            )


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)

    df = load_data()

    def entity_data(ifscode):
        d = df[df['ifscode'] == ifscode].copy()
        return d[d['year'].between(2015, 2031)].sort_values('year')

    global_data = entity_data(GLOBE_IFSCODE)
    poland_data = entity_data(POLAND_IFSCODE)
    globe_hist = load_historical(GLOBE_IFSCODE)
    poland_hist = load_historical(POLAND_IFSCODE)

    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    print("Generating Globe + Poland Interest Rates panel chart...")

    fig = make_subplots(
        rows=1, cols=2,
        horizontal_spacing=0.12,
        subplot_titles=['Interest Payments', 'Primary Balance']
    )

    vars_by_col = {1: 'ggei_gdp', 2: 'primary_balance'}
    for col, var in vars_by_col.items():
        legend = (col == 1)
        # Fans behind, every vintage shown explicitly in the legend
        # (Globe 2021-2026 then Poland 2021-2026)...
        add_historical(fig, poland_hist, var, col, ENTITY['Poland'], 'Poland', show_legend=legend, rank0=7)
        add_historical(fig, globe_hist, var, col, ENTITY['Globe'], 'Globe', show_legend=legend, rank0=1)
        # ...main lines on top (Globe drawn last so it dominates)
        add_main(fig, poland_data, var, col, ENTITY['Poland'], 'Poland', show_legend=legend, label_above=False, rank=12)
        add_main(fig, global_data, var, col, ENTITY['Globe'], 'Globe', show_legend=legend, label_above=True, rank=6)
        # Forecast horizon shading
        fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0, row=1, col=col)

    # Layout
    w_px, h_px = get_chart_dims_px("global_interest_rates_panel.png")
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
    for col in [1, 2]:
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
    save_path = output_dir / 'global_interest_rates_panel'
    pio.write_image(fig, f"{save_path}.png", format='png', engine='kaleido', scale=2)
    fig.write_html(f"{save_path}.html", auto_open=auto_open)
    print(f"  Saved global_interest_rates_panel.png")

    # Export CSV (globe + Poland)
    def tidy(frame, region):
        cols = ['year']
        rename = {}
        for var, name in [('ggei_gdp', 'interest_payments'), ('primary_balance', 'primary_balance')]:
            if var in frame.columns:
                cols.append(var)
                rename[var] = name
        out = frame[cols].rename(columns=rename).copy()
        out.insert(0, 'region', region)
        return out.round(2)

    csv_data = pd.concat([tidy(global_data, 'Globe'), tidy(poland_data, 'Poland')], ignore_index=True)
    csv_path = output_dir / 'global_interest_rates.csv'
    csv_data.to_csv(csv_path, index=False)
    print(f"  Exported data to {csv_path}")

    print("Globe + Poland Interest Rates panel complete.")


if __name__ == "__main__":
    main()
