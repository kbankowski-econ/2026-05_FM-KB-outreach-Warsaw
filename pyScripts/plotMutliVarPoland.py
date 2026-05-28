"""
Generate a 32x12 cm fiscal-variable panel (2 rows x 5 cols) for Poland.

Adapted from the RV LAM presentation `plotMutliVar.py`, but restricted to a
single entity (Poland). Poland's own series is the highlighted line; two P10-P90
peer-group bands sit behind it: Advanced Europe (blue) and CESEE (Central,
Eastern, and Southeastern Europe; purple). Membership is read from the
`forAdvEurope` and `forCESEE` flags in countryTable.csv.

Layout:
    Row 1: Gross Debt (period change) | Gross Debt | Primary Balance | Revenue | Primary Spending
    Row 2: Snowball effect            | Real GDP growth (g) | Effective interest rate (r) | GDP deflator inflation (pi) | Stock-Flow Adjustment
"""
import csv
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fiscal_common import (
    load_config,
    ensure_output_dir,
    load_chart_config,
    smart_save_image,
    get_chart_dims_px,
    resolve_project_path,
)
from plotGlobalPrimBalanceForGap import load_data


def load_flagged_members(flag_col, flag_value):
    """Return iso3c codes whose `flag_col` equals `flag_value` in countryTable.csv.

    Used to read peer-group memberships (CESEE, Advanced Europe) from the shared
    country metadata. Members absent from the WEO dataset are silently dropped
    from the band at plot time (e.g. Kosovo for CESEE).
    """
    csv_path = resolve_project_path("+environment", "csvFiles", "countryTable.csv")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return [row["iso3c"] for row in csv.DictReader(handle)
                if row.get(flag_col) == flag_value]


CESEE_MEMBERS = load_flagged_members("forCESEE", "CESEE")
ADV_EUROPE_MEMBERS = load_flagged_members("forAdvEurope", "AdvEurope")

# Peer-group P10-P90 bands drawn behind Poland's line. `key` is used to name the
# per-band quantile columns; `fillcolor` is the translucent band fill.
BANDS = [
    {'key': 'adv_europe', 'name': 'AE Europe P10-P90 range',
     'members': ADV_EUROPE_MEMBERS, 'fillcolor': 'rgba(30, 136, 229, 0.25)'},
    {'key': 'cesee', 'name': 'CESEE P10-P90 range',
     'members': CESEE_MEMBERS, 'fillcolor': 'rgba(255, 179, 0, 0.35)'},
]

# Single entity to plot. The highlighted line is Poland's own series; the bands
# above provide peer-group context.
ENTITY_CONFIGS = [
    {'stem': 'poland', 'display': 'Poland', 'type': 'country', 'isocode': 'POL'},
]

# (variable, display_name, aggregation, style, good_dir)
# style:    'horizontal_avg' draws two flat period-average bars.
#           'endpoint_slope' draws two sloped lines connecting the start-of-period
#           and end-of-period values.
# good_dir: direction of change that is FAVORABLE for debt dynamics — used to tag
#           each subtitle with a teal (+) if Poland's 2024-29 average moved the
#           good way vs 2014-19, or a deep-orange (-) if it moved adversely.
#           'up' = higher is better; 'down' = lower is better.
VARIABLES_PANEL = [
    # Row 1
    ('ggxwdg_gdp',       'Gross Debt (period change)',   'topdown',  'endpoint_slope', 'down'),
    ('ggxwdg_gdp',       'Gross Debt',                   'weighted', 'horizontal_avg', 'down'),
    ('primary_balance',  'Primary Balance',              'weighted', 'horizontal_avg', 'up'),
    ('gov_revenue',      'Revenue',                      'weighted', 'horizontal_avg', 'up'),
    ('primary_exp',      'Primary Spending',             'weighted', 'horizontal_avg', 'down'),
    # Row 2
    ('snow_ball',        'Snowball effect',              'topdown',  'horizontal_avg', 'down'),
    ('g_real',           'Real GDP growth (g)',          'topdown',  'horizontal_avg', 'up'),
    ('implicit_rate',    'Effective interest rate (r)',  'topdown',  'horizontal_avg', 'down'),
    ('g_price',          'GDP deflator inflation (pi)',  'topdown',  'horizontal_avg', 'up'),
    ('sfa_gdp',          'Stock-Flow Adjustment',        'topdown',  'horizontal_avg', 'down'),
]
N_COLS = 5

# Subtitle change markers (project palette: teal = good, deep orange = bad).
FAVORABLE_COLOR = '#00897B'
ADVERSE_COLOR = '#E65100'


def _period_avgs(stats, slope_context, style):
    """Poland's 2014-19 and 2024-29 representative values for a panel."""
    if style == 'endpoint_slope':
        a = slope_context.get((2014, 2019)) if slope_context else None
        b = slope_context.get((2024, 2029)) if slope_context else None
        if not a or not b:
            return None, None
        return a[2], b[2]                       # period-average annual change
    old = stats[(stats['year'] >= 2014) & (stats['year'] <= 2019)]['w_avg'].mean()
    new = stats[(stats['year'] >= 2024) & (stats['year'] <= 2029)]['w_avg'].mean()
    return old, new


def _favorability_marker(stats, slope_context, style, good_dir):
    """Return ' (+)'/' (-)' coloured markup for the subtitle, or '' if flat/NA."""
    old, new = _period_avgs(stats, slope_context, style)
    if old is None or new is None or pd.isna(old) or pd.isna(new):
        return ''
    delta = new - old
    if abs(delta) < 1e-9:
        return ''
    improved = delta > 0 if good_dir == 'up' else delta < 0
    color = FAVORABLE_COLOR if improved else ADVERSE_COLOR
    sym = '+' if improved else '−'
    return f'<span style="color:{color}"><b>({sym})</b></span> '

_ANNOTATION_KWARGS = dict(
    showarrow=False,
    yshift=18,
    bgcolor='rgba(255, 249, 196, 0.9)',
    bordercolor='rgba(0, 0, 0, 0.2)',
    borderwidth=0.5,
    borderpad=2,
    font=dict(size=14),
)


def calculate_entity_stats(df, var_name, entity, bands):
    """Return a per-year stats DataFrame for the entity.

    Columns: year, w_avg (the country's own series) and, for each band in
    `bands`, `{key}_p10` / `{key}_p90` quantiles computed across that band's
    members. Years with no data anywhere are dropped.
    """
    band_pools = {}
    for band in bands:
        pool = df[df['isocode'].isin(band['members'])]
        pool = pool[pool['year'].between(2014, 2031)]
        pool = pool[pool[var_name].notna()]
        band_pools[band['key']] = pool

    country_by_year = dict(zip(
        df[df['isocode'] == entity['isocode']]['year'],
        df[df['isocode'] == entity['isocode']][var_name],
    ))

    rows = []
    for year in range(2014, 2032):
        record = {'year': year}
        any_band = False
        for band in bands:
            pool = band_pools[band['key']]
            yd = pool[pool['year'] == year]
            if not yd.empty:
                record[f"{band['key']}_p10"] = yd[var_name].quantile(0.10)
                record[f"{band['key']}_p90"] = yd[var_name].quantile(0.90)
                any_band = True
            else:
                record[f"{band['key']}_p10"] = float('nan')
                record[f"{band['key']}_p90"] = float('nan')

        w_avg = country_by_year.get(year)
        if w_avg is not None and pd.isna(w_avg):
            w_avg = None
        record['w_avg'] = float(w_avg) if w_avg is not None and not pd.isna(w_avg) else float('nan')

        if w_avg is None and not any_band:
            continue
        rows.append(record)

    return pd.DataFrame(rows)


def _period_avg_annual_change(df, var_name, entity, lo, hi):
    """Period-averaged annual change in `var_name` for the entity over [lo..hi]:
    (v_hi - v_{lo-1}) / (hi - lo + 1)."""
    sub = df[df['isocode'] == entity['isocode']].set_index('year')[var_name]
    if (lo - 1) not in sub.index or hi not in sub.index:
        return None
    v_prev = sub.loc[lo - 1]
    v_hi = sub.loc[hi]
    if pd.isna(v_prev) or pd.isna(v_hi):
        return None
    return float(v_prev), float(v_hi), (float(v_hi) - float(v_prev)) / (hi - lo + 1)


def _add_variable_traces(fig, stats, row, col,
                         show_shared_legend=False, show_style_legend=False,
                         style='horizontal_avg',
                         slope_context=None,
                         agg_line_name='Poland',
                         bands=()):
    for rank, band in enumerate(bands):
        p10_col, p90_col = f"{band['key']}_p10", f"{band['key']}_p90"
        if p10_col not in stats.columns or stats[p10_col].isna().all():
            continue
        fig.add_trace(go.Scatter(
            x=list(stats['year']) + list(stats['year'][::-1]),
            y=list(stats[p90_col]) + list(stats[p10_col][::-1]),
            fill='toself',
            fillcolor=band['fillcolor'],
            line=dict(color='rgba(0,0,0,0)'),
            name=band['name'],
            legendgroup=band['key'],
            showlegend=show_shared_legend,
            legendrank=10 + rank,
        ), row=row, col=col)

    fig.add_trace(go.Scatter(
        x=stats['year'], y=stats['w_avg'], mode='lines',
        name=agg_line_name,
        line=dict(color='rgba(106, 27, 154, 0.9)', width=4),
        legendgroup='agg',
        showlegend=show_shared_legend,
        legendrank=1,
    ), row=row, col=col)

    if style == 'endpoint_slope':
        for (lo, hi, color) in [(2014, 2019, '#00897B'), (2024, 2029, '#E65100')]:
            ctx = slope_context.get((lo, hi)) if slope_context else None
            if ctx is None:
                continue
            v_prev, v_hi, avg_annual = ctx
            fig.add_trace(go.Scatter(
                x=[lo - 1, hi], y=[v_prev, v_hi], mode='lines',
                name=f'{lo}-{hi} change',
                line=dict(color=color, width=4),
                showlegend=False,
            ), row=row, col=col)
            fig.add_annotation(
                x=(lo - 1 + hi) / 2, y=(v_prev + v_hi) / 2,
                text=f"Delta = {avg_annual:+.1f}",
                row=row, col=col, **_ANNOTATION_KWARGS,
            )
        return

    avg_2014_19 = stats[(stats['year'] >= 2014) & (stats['year'] <= 2019)]['w_avg'].mean()
    avg_2024_29 = stats[(stats['year'] >= 2024) & (stats['year'] <= 2029)]['w_avg'].mean()

    if pd.notna(avg_2014_19):
        fig.add_trace(go.Scatter(
            x=[2014, 2019], y=[avg_2014_19, avg_2014_19], mode='lines',
            name='2014-19 avg',
            line=dict(color='#00897B', width=4),
            legendgroup='avg_p1',
            showlegend=show_style_legend,
            legendrank=2,
        ), row=row, col=col)
        fig.add_annotation(
            x=(2014 + 2019) / 2, y=avg_2014_19,
            text=f"{avg_2014_19:.1f}",
            row=row, col=col, **_ANNOTATION_KWARGS,
        )
    if pd.notna(avg_2024_29):
        fig.add_trace(go.Scatter(
            x=[2024, 2029], y=[avg_2024_29, avg_2024_29], mode='lines',
            name='2024-29 avg',
            line=dict(color='#E65100', width=4),
            legendgroup='avg_p2',
            showlegend=show_style_legend,
            legendrank=3,
        ), row=row, col=col)
        fig.add_annotation(
            x=(2024 + 2029) / 2, y=avg_2024_29,
            text=f"{avg_2024_29:.1f}",
            row=row, col=col, **_ANNOTATION_KWARGS,
        )


def build_panel(df, entity, chart_cfg, output_dir, auto_open):
    # Precompute stats, slope context and the favourability marker per variable
    # so the markers can be baked into the subplot titles before make_subplots.
    prepared = []
    for (var_name, display, _aggregation, style, good_dir) in VARIABLES_PANEL:
        if var_name not in df.columns:
            prepared.append((var_name, display, style, None, None, ''))
            continue
        stats = calculate_entity_stats(df, var_name, entity, BANDS)
        slope_context = None
        if style == 'endpoint_slope':
            slope_context = {
                (lo, hi): _period_avg_annual_change(df, var_name, entity, lo, hi)
                for (lo, hi) in [(2014, 2019), (2024, 2029)]
            }
        marker = '' if stats.empty else _favorability_marker(stats, slope_context, style, good_dir)
        prepared.append((var_name, display, style, stats, slope_context, marker))

    subplot_titles = [marker + display for (_, display, _, _, _, marker) in prepared]
    while len(subplot_titles) < 2 * N_COLS:
        subplot_titles.append("")

    fig = make_subplots(
        rows=2, cols=N_COLS,
        subplot_titles=subplot_titles,
        horizontal_spacing=0.05,
        vertical_spacing=0.14,
    )
    for ann in fig.layout.annotations:
        ann.font = dict(size=14)

    first_by_style = {}
    for i, entry in enumerate(VARIABLES_PANEL):
        first_by_style.setdefault(entry[3], i)

    agg_line_name = entity['display']

    for idx, (var_name, _display, style, stats, slope_context, _marker) in enumerate(prepared):
        row = idx // N_COLS + 1
        col = idx % N_COLS + 1
        if stats is None:
            print(f"  {var_name}: NOT available — skipping.")
            continue
        if stats.empty:
            continue
        _add_variable_traces(
            fig, stats, row=row, col=col,
            show_shared_legend=(idx == 0),
            show_style_legend=(idx == first_by_style.get(style)),
            style=style,
            slope_context=slope_context,
            agg_line_name=agg_line_name,
            bands=BANDS,
        )

    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)",
                  layer="below", line_width=0)

    base_name = f"{entity['stem']}_fiscal_variables_panel"
    w_px, h_px = get_chart_dims_px(f"{base_name}.png")
    fig.update_layout(
        template=chart_cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=85, b=30, l=50, r=20),
        font=dict(size=chart_cfg['font_size'] - 2),
        showlegend=True,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.12, xanchor='center', x=0.5,
            font=dict(size=16),
            tracegroupgap=2,
        ),
    )
    fig.update_xaxes(
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        dtick=5, tick0=2015, range=[2013.5, 2031.5],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        zeroline=True, zerolinecolor='black',
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    )

    smart_save_image(fig, output_dir / f"{base_name}.png")
    smart_save_image(fig, output_dir / f"{base_name}.svg")
    fig.write_html(output_dir / f"{base_name}.html", auto_open=auto_open, include_plotlyjs='cdn')
    print(f"  Saved {base_name}.png")


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    df = load_data()

    for entity in ENTITY_CONFIGS:
        print(f"\nGenerating panel for {entity['display']}...")
        build_panel(df, entity, chart_cfg, output_dir, auto_open=auto_open)


if __name__ == "__main__":
    main()
