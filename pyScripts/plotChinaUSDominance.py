"""
Generate three separate charts for China/US dominance analysis:
1. Gross Government Debt (Percent of GDP) - by income group
2. Gross Government Debt (Percent of GDP) - global only
3. Gross Government Debt (Percent of GDP) - by region
Each chart is 15cm x 10cm (567 x 378 pixels at 96 DPI)
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config


# 15cm x 10cm at 96 DPI
CHART_WIDTH = 567
CHART_HEIGHT = 378

# Color palette 1: Income groups (warm colors)
# Series: (name, filter_type, filter_value, color, width, legendrank)
DEBT_SERIES_INCOME = [
    ('China', 'isocode', 'CHN', '#E53935', 3, 2),           # Red
    ('USA', 'isocode', 'USA', '#43A047', 3, 3),             # Green
    ('Advanced Economies excl. USA', 'ifscode', 9994, '#1E88E5', 2.5, 4),  # Blue (distinct from purple)
    ('Emerging Markets excl. China', 'ifscode', 9995, '#FF9800', 2.5, 5),  # Orange
    ('Low-Income Developing Countries', 'ifscode', 9993, '#795548', 2.5, 6),     # Brown
    ('Poland', 'ifscode', 964, '#4DB6AC', 4, 7),            # Teal - consistent with other slides
    ('Global', 'ifscode', 9999, '#6A1B9A', 6, 1),           # Blue - thickest, on top
]

# Color palette 2: Regions (cooler/distinct colors)
# Series: (name, region_code, color, width, legendrank)
DEBT_SERIES_REGION = [
    ('Americas', 'Americas', '#E91E63', 2.5, 2),            # Pink
    ('Asia-Pacific', 'Asia-Pacific', '#4CAF50', 2.5, 3),    # Green
    ('Europe', 'Europe', '#9C27B0', 2.5, 4),                # Purple
    ('MENAP', 'MENAP', '#FF5722', 2.5, 5),                  # Deep Orange
    ('SSA', 'SSA', '#795548', 2.5, 6),                      # Brown
    ('Global', None, '#6A1B9A', 6, 1),                      # Blue - same as income chart
]


def _filter_years(data, start=2015, end=2031):
    """Return rows within the requested year range."""
    return data[data['year'].between(start, end)]


def _filter_country_debt_rows(df):
    """Return country-level debt rows used in contribution analysis."""
    countries = df[df['ifscode'] < 9000].copy()
    countries = _filter_years(countries)
    return countries[countries['ggxwdg_gdp'].notna() & countries['ngdp_fy_usd'].notna()]


def _prepare_other_country_contributions(df):
    """Prepare country-level debt contribution table for countries excluding China and the US."""
    countries = _filter_country_debt_rows(df)
    global_gdp = countries.groupby('year')['ngdp_fy_usd'].sum().reset_index()
    global_gdp.columns = ['year', 'global_gdp']

    others = countries[~countries['isocode'].isin(['CHN', 'USA'])].copy()
    others_merged = others.merge(global_gdp, on='year')
    others_merged['debt_contrib'] = (
        (others_merged['ggxwdg_gdp'] / 100 * others_merged['ngdp_fy_usd']) / others_merged['global_gdp'] * 100
    )
    country_year_contrib = others_merged.pivot_table(
        index='year', columns='isocode', values='debt_contrib', aggfunc='sum'
    ).fillna(0)
    return countries, global_gdp, others, country_year_contrib


def _calc_group_contribution(group_df, global_gdp_df, years=None):
    """Calculate fiscal-year-GDP-weighted debt contribution for a group."""
    merged = group_df.merge(global_gdp_df, on='year')
    if years is not None:
        merged = merged[merged['year'].isin(years)]
    return merged.groupby('year').apply(
        lambda x: ((x['ggxwdg_gdp'] / 100 * x['ngdp_fy_usd']).sum() / x['global_gdp'].iloc[0] * 100),
        include_groups=False
    ).reset_index(name='contribution')


def _build_global_debt_total(countries, global_gdp):
    """Calculate global debt contribution totals."""
    countries_merged = countries.merge(global_gdp, on='year')
    countries_merged['debt_contrib'] = (
        (countries_merged['ggxwdg_gdp'] / 100 * countries_merged['ngdp_fy_usd']) / countries_merged['global_gdp'] * 100
    )
    global_total = countries_merged.groupby('year')['debt_contrib'].sum().reset_index()
    global_total.columns = ['year', 'global_debt']
    return global_total


def _merge_contribution_components(global_total, chn_contrib, usa_contrib, pos_contrib, neg_contrib):
    """Merge contribution components into a single frame."""
    contrib = global_total.copy()
    contrib = contrib.merge(chn_contrib, on='year', suffixes=('', '_chn'))
    contrib = contrib.merge(usa_contrib, on='year', suffixes=('', '_usa'))
    contrib = contrib.merge(pos_contrib, on='year', suffixes=('', '_pos'))
    contrib = contrib.merge(neg_contrib, on='year', suffixes=('', '_neg'))
    contrib.columns = ['year', 'global_debt', 'chn', 'usa', 'pos', 'neg']
    return contrib


def _apply_stacked_bar_columns(contrib):
    """Create positive/negative splits and stacking bases."""
    for grp in ['neg', 'pos', 'usa', 'chn']:
        contrib[f'{grp}_pos'] = contrib[f'{grp}_diff'].clip(lower=0)
        contrib[f'{grp}_neg'] = contrib[f'{grp}_diff'].clip(upper=0)

    contrib['base_neg_pos'] = contrib['base_level']
    contrib['base_pos_pos'] = contrib['base_level'] + contrib['neg_pos']
    contrib['base_usa_pos'] = contrib['base_level'] + contrib['neg_pos'] + contrib['pos_pos']
    contrib['base_chn_pos'] = contrib['base_level'] + contrib['neg_pos'] + contrib['pos_pos'] + contrib['usa_pos']

    contrib['base_neg_neg'] = contrib['base_level']
    contrib['base_pos_neg'] = contrib['base_level'] + contrib['neg_neg']
    contrib['base_usa_neg'] = contrib['base_level'] + contrib['neg_neg'] + contrib['pos_neg']
    contrib['base_chn_neg'] = contrib['base_level'] + contrib['neg_neg'] + contrib['pos_neg'] + contrib['usa_neg']


def _apply_standard_layout(fig, chart_cfg, y_range=None, barmode=None):
    """Apply the shared layout and axis configuration."""
    fig.update_layout(
        template=chart_cfg['template'],
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        margin=dict(t=50, b=40, l=50, r=20),
        font=dict(size=13),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(size=chart_cfg['legend']['font_size']),
            tracegroupgap=2
        ),
        barmode=barmode
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        dtick=5,
        tick0=2015,
        range=[2014.5, 2031.5],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )

    y_axis_config = dict(
        showgrid=True,
        gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        zeroline=True,
        zerolinecolor='black',
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )
    if y_range:
        y_axis_config['range'] = y_range
    fig.update_yaxes(**y_axis_config)


def _append_top10_section(lines, title, series, total_value, include_total_wrappers=False):
    """Append a top-10 block to a report, preserving the original text formatting."""
    if include_total_wrappers:
        lines.append("=" * 60)
        lines.append(f"{title}: {total_value:.2f} pp")
        lines.append("=" * 60)
    else:
        lines.append(f"{title}: {total_value:.2f} pp")
    lines.append("")
    lines.append(series['heading'])
    lines.append("-" * 40)

    top10 = series['values'].head(10)
    for iso, val in top10.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10.sum():.2f} pp")
    if series.get('show_explains', True) and total_value != 0:
        lines.append(f"  Top 10 explains: {top10.sum()/total_value*100:.1f}% of total")


def load_data():
    """Load WEO enhanced data."""
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    df = pd.read_stata(data_path)
    return df


def calculate_regional_aggregates(df, var_name='ggxwdg_gdp'):
    """Calculate GDP-weighted regional aggregates for a variable."""
    # Filter to single countries with valid region
    data = df[df['regionShort'].notna() & (df['regionShort'] != '')]
    data = data[data['isocode'].notna() & (data['isocode'] != '')]
    data = _filter_years(data)

    # Need GDP for weighting
    if 'ngdpd' not in data.columns:
        return pd.DataFrame()

    regional_data = []
    for region in data['regionShort'].unique():
        region_df = data[data['regionShort'] == region]
        for year in range(2015, 2032):
            year_data = region_df[region_df['year'] == year]
            year_data = year_data[year_data[var_name].notna() & year_data['ngdpd'].notna()]

            if len(year_data) > 0:
                # GDP-weighted average
                weighted_avg = (year_data[var_name] * year_data['ngdpd']).sum() / year_data['ngdpd'].sum()
                regional_data.append({
                    'region': region,
                    'year': year,
                    var_name: weighted_avg
                })

    return pd.DataFrame(regional_data)


def add_series(fig, data, var_name, show_legend=False, name='', color='#6A1B9A', width=3, legendrank=None, opacity=1.0):
    """Add a single series to the figure."""
    # Filter to non-null values
    plot_data = data[data[var_name].notna()]

    if len(plot_data) == 0:
        return

    # Line trace
    fig.add_trace(go.Scatter(
        x=plot_data['year'],
        y=plot_data[var_name],
        mode='lines',
        name=name,
        line=dict(color=color, width=width),
        opacity=opacity,
        showlegend=show_legend,
        legendgroup=name,
        legendrank=legendrank
    ))

    # Circle markers for 2025 and 2031 (scaled to line width)
    marker_data = plot_data[plot_data['year'].isin([2025, 2031])]
    if len(marker_data) > 0:
        marker_size = 8 + width  # Scale marker size with line width
        marker_line_width = width * 0.6  # Scale marker stroke with line width
        fig.add_trace(go.Scatter(
            x=marker_data['year'],
            y=marker_data[var_name],
            mode='markers',
            marker=dict(symbol='circle-open', size=marker_size, color=color, line=dict(width=marker_line_width, color=color)),
            opacity=opacity,
            showlegend=False,
            legendgroup=name
        ))


def create_multi_series_chart(df, var_name, series_list, chart_cfg, y_range=None):
    """Create a chart with multiple series (income groups)."""
    fig = go.Figure()

    for name, filter_type, filter_value, color, width, legendrank in series_list:
        if filter_type == 'ifscode':
            data = df[df['ifscode'] == filter_value].copy()
        else:  # isocode
            data = df[df['isocode'] == filter_value].copy()

        data = _filter_years(data).sort_values('year')
        # Highlight Global and Poland; fade the other groups.
        opacity = 1.0 if name in ('Global', 'Poland') else 0.4
        add_series(fig, data, var_name, show_legend=True, name=name, color=color, width=width, legendrank=legendrank, opacity=opacity)

    # Forecast horizon shading
    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0)

    _apply_standard_layout(fig, chart_cfg, y_range=y_range)

    return fig


def create_regional_chart(df, regional_data, var_name, series_list, chart_cfg, y_range=None):
    """Create a chart with regional series."""
    fig = go.Figure()

    for name, region_code, color, width, legendrank in series_list:
        if region_code is None:
            # Global aggregate
            data = df[df['ifscode'] == 9999].copy()
            data = _filter_years(data).sort_values('year')
        else:
            # Regional aggregate
            data = regional_data[regional_data['region'] == region_code].copy()
            data = data.sort_values('year')

        add_series(fig, data, var_name, show_legend=True, name=name, color=color, width=width, legendrank=legendrank)

    # Forecast horizon shading
    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0)

    _apply_standard_layout(fig, chart_cfg, y_range=y_range)

    return fig


def create_single_series_chart(data, var_name, chart_cfg, name='Global', color='#6A1B9A', width=6):
    """Create a chart with a single series."""
    fig = go.Figure()

    add_series(fig, data, var_name, show_legend=True, name=name, color=color, width=width)

    # Forecast horizon shading
    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0)

    _apply_standard_layout(fig, chart_cfg)

    return fig


def calculate_debt_contributions(df, base_year=2015):
    """Calculate debt contributions, grouping others by positive/negative contribution.

    For each year, countries (excl. CHN/USA) are classified based on whether their
    contribution change from the previous year is positive or negative.
    """
    # Filter to single countries only (ifscode < 9000)
    countries = _filter_country_debt_rows(df)
    global_gdp = countries.groupby('year')['ngdp_fy_usd'].sum().reset_index()
    global_gdp.columns = ['year', 'global_gdp']
    chn = countries[countries['isocode'] == 'CHN'].copy()
    usa = countries[countries['isocode'] == 'USA'].copy()
    others = countries[~countries['isocode'].isin(['CHN', 'USA'])].copy()
    chn_contrib = _calc_group_contribution(chn, global_gdp)
    usa_contrib = _calc_group_contribution(usa, global_gdp)

    # Calculate country-level contributions for others
    others_merged = others.merge(global_gdp, on='year')
    others_merged['debt_contrib'] = (others_merged['ggxwdg_gdp'] / 100 * others_merged['ngdp_fy_usd']) / others_merged['global_gdp'] * 100

    # Get contributions by country and year
    country_year_contrib = others_merged.pivot_table(
        index='year', columns='isocode', values='debt_contrib', aggfunc='sum'
    ).fillna(0)

    # For each year, calculate year-over-year changes and classify
    years = sorted(country_year_contrib.index.tolist())
    pos_by_year = []
    neg_by_year = []

    for i, year in enumerate(years):
        year_contrib = country_year_contrib.loc[year]

        if i == 0:
            # First year (2015): no change, all zero
            pos_sum = 0.0
            neg_sum = 0.0
        else:
            # Change from previous year
            prev_year = years[i - 1]
            prev_contrib = country_year_contrib.loc[prev_year]
            changes = year_contrib - prev_contrib

            # Sum positive and negative changes
            pos_sum = changes[changes >= 0].sum()
            neg_sum = changes[changes < 0].sum()

        pos_by_year.append({'year': year, 'contribution': pos_sum})
        neg_by_year.append({'year': year, 'contribution': neg_sum})

    pos_contrib = pd.DataFrame(pos_by_year)
    neg_contrib = pd.DataFrame(neg_by_year)

    # Calculate global total
    global_total = _build_global_debt_total(countries, global_gdp)
    contrib = _merge_contribution_components(global_total, chn_contrib, usa_contrib, pos_contrib, neg_contrib)

    # Get base values for anchoring
    base_2015 = contrib[contrib['year'] == base_year].iloc[0]
    base_2025 = contrib[contrib['year'] == 2025].iloc[0]

    # Calculate cumulative year-over-year differences for CHN and USA
    contrib = contrib.sort_values('year').reset_index(drop=True)
    contrib['chn_cumsum'] = contrib['chn'].diff().fillna(0).cumsum()
    contrib['usa_cumsum'] = contrib['usa'].diff().fillna(0).cumsum()

    # Cumulate pos and neg year-over-year changes
    contrib['pos_cumsum'] = contrib['pos'].cumsum()
    contrib['neg_cumsum'] = contrib['neg'].cumsum()

    # Get 2025 values for normalization
    idx_2025 = contrib[contrib['year'] == 2025].index[0]
    chn_2025 = contrib.loc[idx_2025, 'chn_cumsum']
    usa_2025 = contrib.loc[idx_2025, 'usa_cumsum']
    pos_2025 = contrib.loc[idx_2025, 'pos_cumsum']
    neg_2025 = contrib.loc[idx_2025, 'neg_cumsum']
    global_2025 = contrib.loc[idx_2025, 'global_debt']
    global_2015 = contrib['global_debt'].iloc[0]

    # For 2015-2025: use cumulative from 2015, base at 2015
    # For 2026-2031: subtract 2025 values, base at 2025
    contrib['chn_diff'] = contrib.apply(
        lambda row: row['chn_cumsum'] if row['year'] <= 2025 else row['chn_cumsum'] - chn_2025, axis=1)
    contrib['usa_diff'] = contrib.apply(
        lambda row: row['usa_cumsum'] if row['year'] <= 2025 else row['usa_cumsum'] - usa_2025, axis=1)
    contrib['pos_diff'] = contrib.apply(
        lambda row: row['pos_cumsum'] if row['year'] <= 2025 else row['pos_cumsum'] - pos_2025, axis=1)
    contrib['neg_diff'] = contrib.apply(
        lambda row: row['neg_cumsum'] if row['year'] <= 2025 else row['neg_cumsum'] - neg_2025, axis=1)

    # Base level: 2015 for first period, 2025 for second period
    contrib['base_level'] = contrib['year'].apply(
        lambda y: global_2015 if y <= 2025 else global_2025)

    _apply_stacked_bar_columns(contrib)

    return contrib, base_2015['global_debt'], base_2025['global_debt']


def calculate_debt_contributions_ver2(df, base_year=2015):
    """Calculate debt contributions - hybrid ver3/ver1 approach.

    Ver2: Mixed classification approach:
    - Period 1 (2015-2025): period-based classification by 2025-2015 change (like ver3)
    - Period 2 (2026-2031): year-over-year classification (like ver1)
    """
    # Filter to single countries only (ifscode < 9000)
    countries = _filter_country_debt_rows(df)
    global_gdp = countries.groupby('year')['ngdp_fy_usd'].sum().reset_index()
    global_gdp.columns = ['year', 'global_gdp']
    chn = countries[countries['isocode'] == 'CHN'].copy()
    usa = countries[countries['isocode'] == 'USA'].copy()
    others = countries[~countries['isocode'].isin(['CHN', 'USA'])].copy()
    chn_contrib = _calc_group_contribution(chn, global_gdp)
    usa_contrib = _calc_group_contribution(usa, global_gdp)

    # Calculate country-level contributions for others
    others_merged = others.merge(global_gdp, on='year')
    others_merged['debt_contrib'] = (others_merged['ggxwdg_gdp'] / 100 * others_merged['ngdp_fy_usd']) / others_merged['global_gdp'] * 100

    # Get contributions by country and year
    country_year_contrib = others_merged.pivot_table(
        index='year', columns='isocode', values='debt_contrib', aggfunc='sum'
    ).fillna(0)

    years = sorted(country_year_contrib.index.tolist())

    # === PERIOD 1 (2015-2025): Period-based classification (like ver3) ===
    # Classify countries by their 2025-2015 total change
    contrib_2015 = country_year_contrib.loc[2015]
    contrib_2025 = country_year_contrib.loc[2025]
    change_p1 = contrib_2025 - contrib_2015

    pos_countries_p1 = change_p1[change_p1 >= 0].index.tolist()
    neg_countries_p1 = change_p1[change_p1 < 0].index.tolist()

    # Calculate group contributions for period 1 years
    pos_by_year_p1 = []
    neg_by_year_p1 = []

    for year in years:
        if year > 2025:
            break
        year_contrib = country_year_contrib.loc[year]
        # Calculate difference from 2015 for each group
        pos_diff = year_contrib[pos_countries_p1].sum() - contrib_2015[pos_countries_p1].sum()
        neg_diff = year_contrib[neg_countries_p1].sum() - contrib_2015[neg_countries_p1].sum()

        pos_by_year_p1.append({'year': year, 'contribution': pos_diff})
        neg_by_year_p1.append({'year': year, 'contribution': neg_diff})

    # === PERIOD 2 (2026-2031): Year-over-year classification (like ver1) ===
    pos_by_year_p2 = []
    neg_by_year_p2 = []

    # Start from 2025 to get YoY change for 2026
    p2_years = [y for y in years if y >= 2025]
    for i, year in enumerate(p2_years):
        if year == 2025:
            continue  # Skip 2025, we need it only as reference
        year_contrib = country_year_contrib.loc[year]
        prev_year = p2_years[i - 1]
        prev_contrib = country_year_contrib.loc[prev_year]
        changes = year_contrib - prev_contrib
        pos_sum = changes[changes >= 0].sum()
        neg_sum = changes[changes < 0].sum()

        pos_by_year_p2.append({'year': year, 'contribution': pos_sum})
        neg_by_year_p2.append({'year': year, 'contribution': neg_sum})

    # Combine period 1 and period 2
    pos_contrib_p1 = pd.DataFrame(pos_by_year_p1)
    neg_contrib_p1 = pd.DataFrame(neg_by_year_p1)
    pos_contrib_p2 = pd.DataFrame(pos_by_year_p2)
    neg_contrib_p2 = pd.DataFrame(neg_by_year_p2)

    # For period 2, cumulate the YoY changes
    pos_contrib_p2['contribution'] = pos_contrib_p2['contribution'].cumsum()
    neg_contrib_p2['contribution'] = neg_contrib_p2['contribution'].cumsum()

    # Combine
    pos_contrib = pd.concat([pos_contrib_p1, pos_contrib_p2], ignore_index=True)
    neg_contrib = pd.concat([neg_contrib_p1, neg_contrib_p2], ignore_index=True)

    # Calculate global total
    global_total = _build_global_debt_total(countries, global_gdp)
    contrib = _merge_contribution_components(global_total, chn_contrib, usa_contrib, pos_contrib, neg_contrib)

    # Get base values for anchoring
    base_2015 = contrib[contrib['year'] == base_year].iloc[0]
    base_2025 = contrib[contrib['year'] == 2025].iloc[0]

    # Calculate cumulative year-over-year differences for CHN and USA
    contrib = contrib.sort_values('year').reset_index(drop=True)
    contrib['chn_cumsum'] = contrib['chn'].diff().fillna(0).cumsum()
    contrib['usa_cumsum'] = contrib['usa'].diff().fillna(0).cumsum()

    # Get 2025 values for normalization
    idx_2025 = contrib[contrib['year'] == 2025].index[0]
    chn_2025 = contrib.loc[idx_2025, 'chn_cumsum']
    usa_2025 = contrib.loc[idx_2025, 'usa_cumsum']
    global_2015 = contrib['global_debt'].iloc[0]
    global_2025 = contrib.loc[idx_2025, 'global_debt']

    # For CHN/USA: use cumulative from 2015 for period 1, subtract 2025 for period 2
    contrib['chn_diff'] = contrib.apply(
        lambda row: row['chn_cumsum'] if row['year'] <= 2025 else row['chn_cumsum'] - chn_2025, axis=1)
    contrib['usa_diff'] = contrib.apply(
        lambda row: row['usa_cumsum'] if row['year'] <= 2025 else row['usa_cumsum'] - usa_2025, axis=1)

    # For pos/neg: already prepared correctly (diff from 2015 for p1, cumsum for p2)
    contrib['pos_diff'] = contrib['pos']
    contrib['neg_diff'] = contrib['neg']

    # Base level: 2015 for first period, 2025 for second period
    contrib['base_level'] = contrib['year'].apply(
        lambda y: global_2015 if y <= 2025 else global_2025)

    _apply_stacked_bar_columns(contrib)

    return contrib, base_2015['global_debt'], base_2025['global_debt']


def calculate_debt_contributions_ver3(df, base_year=2015):
    """Calculate debt contributions, grouping others by positive/negative contribution.

    Ver3: Countries are classified based on total period change:
    - 2015-2025: classification based on 2025-2015 contribution difference
    - 2026-2031: classification based on 2031-2025 contribution difference
    """
    # Filter to single countries only (ifscode < 9000)
    countries = _filter_country_debt_rows(df)
    global_gdp = countries.groupby('year')['ngdp_fy_usd'].sum().reset_index()
    global_gdp.columns = ['year', 'global_gdp']
    chn = countries[countries['isocode'] == 'CHN'].copy()
    usa = countries[countries['isocode'] == 'USA'].copy()
    others = countries[~countries['isocode'].isin(['CHN', 'USA'])].copy()
    chn_contrib = _calc_group_contribution(chn, global_gdp)
    usa_contrib = _calc_group_contribution(usa, global_gdp)

    # Calculate country-level contributions for others
    others_merged = others.merge(global_gdp, on='year')
    others_merged['debt_contrib'] = (others_merged['ggxwdg_gdp'] / 100 * others_merged['ngdp_fy_usd']) / others_merged['global_gdp'] * 100

    # Get contributions by country and year
    country_year_contrib = others_merged.pivot_table(
        index='year', columns='isocode', values='debt_contrib', aggfunc='sum'
    ).fillna(0)

    # Calculate each country's contribution at key years
    contrib_2015 = country_year_contrib.loc[2015]
    contrib_2025 = country_year_contrib.loc[2025]
    contrib_2031 = country_year_contrib.loc[2031]

    # Period 1 (2015-2025): classify by 2025-2015 change
    change_p1 = contrib_2025 - contrib_2015
    pos_countries_p1 = change_p1[change_p1 >= 0].index.tolist()
    neg_countries_p1 = change_p1[change_p1 < 0].index.tolist()

    # Period 2 (2026-2031): classify by 2031-2025 change
    change_p2 = contrib_2031 - contrib_2025
    pos_countries_p2 = change_p2[change_p2 >= 0].index.tolist()
    neg_countries_p2 = change_p2[change_p2 < 0].index.tolist()

    # Calculate group contributions for period 1 (2015-2025)
    years_p1 = list(range(2015, 2026))
    pos_contrib_p1 = _calc_group_contribution(others[others['isocode'].isin(pos_countries_p1)], global_gdp, years_p1)
    neg_contrib_p1 = _calc_group_contribution(others[others['isocode'].isin(neg_countries_p1)], global_gdp, years_p1)

    # Calculate group contributions for period 2 (2025-2031, including 2025 for correct base)
    years_p2 = list(range(2025, 2032))
    pos_contrib_p2 = _calc_group_contribution(others[others['isocode'].isin(pos_countries_p2)], global_gdp, years_p2)
    neg_contrib_p2 = _calc_group_contribution(others[others['isocode'].isin(neg_countries_p2)], global_gdp, years_p2)

    # Store P2 group values at 2025 for correct normalization
    pos_p2_base_2025 = pos_contrib_p2[pos_contrib_p2['year'] == 2025]['contribution'].iloc[0]
    neg_p2_base_2025 = neg_contrib_p2[neg_contrib_p2['year'] == 2025]['contribution'].iloc[0]

    # Drop 2025 from P2 to avoid duplicate when concatenating
    pos_contrib_p2 = pos_contrib_p2[pos_contrib_p2['year'] > 2025]
    neg_contrib_p2 = neg_contrib_p2[neg_contrib_p2['year'] > 2025]

    # Combine period contributions
    pos_contrib = pd.concat([pos_contrib_p1, pos_contrib_p2], ignore_index=True)
    neg_contrib = pd.concat([neg_contrib_p1, neg_contrib_p2], ignore_index=True)

    # Calculate global total
    global_total = _build_global_debt_total(countries, global_gdp)
    contrib = _merge_contribution_components(global_total, chn_contrib, usa_contrib, pos_contrib, neg_contrib)

    # Normalize contributions with two base periods
    base_2015 = contrib[contrib['year'] == base_year].iloc[0]
    base_2025 = contrib[contrib['year'] == 2025].iloc[0]

    # Calculate differences for each period
    # For P2, use the P2 group values at 2025 as base for pos/neg (country sets differ between periods)
    for grp in ['chn', 'usa', 'pos', 'neg']:
        if grp == 'pos':
            p2_base = pos_p2_base_2025
        elif grp == 'neg':
            p2_base = neg_p2_base_2025
        else:
            p2_base = base_2025[grp]
        contrib[f'{grp}_diff'] = contrib.apply(
            lambda row, g=grp, b2=p2_base: row[g] - base_2015[g] if row['year'] <= 2025 else row[g] - b2,
            axis=1
        )

    # Base level resets in 2025
    contrib['base_level'] = contrib['year'].apply(
        lambda y: base_2015['global_debt'] if y <= 2025 else base_2025['global_debt']
    )

    _apply_stacked_bar_columns(contrib)

    return contrib, base_2015['global_debt'], base_2025['global_debt']


def calculate_debt_contributions_ver4(df, base_year=2015):
    """Calculate debt contributions by income group:
    China, USA, AE excl. US, EM excl. China, LIDCs.

    Ver4: Two-period normalization like ver3, but groups are income-based.
    """
    import csv as csv_mod
    countries = _filter_country_debt_rows(df)
    global_gdp = countries.groupby('year')['ngdp_fy_usd'].sum().reset_index()
    global_gdp.columns = ['year', 'global_gdp']

    # Load country classification
    ct_path = resolve_from_config("../+environment/csvFiles/countryTable.csv")
    ct = pd.read_csv(ct_path)
    ae_ifscodes = set(ct[ct['devClass'] == 'Advanced']['ifscode'].tolist())
    em_ifscodes = set(ct[ct['devClass'] == 'Emerging']['ifscode'].tolist())
    lic_ifscodes = set(ct[ct['devClass'] == 'Low-Income']['ifscode'].tolist())

    # Map isocodes to ifscodes for USA/CHN exclusion
    usa_ifscode = countries[countries['isocode'] == 'USA']['ifscode'].iloc[0]
    chn_ifscode = countries[countries['isocode'] == 'CHN']['ifscode'].iloc[0]

    chn = countries[countries['isocode'] == 'CHN'].copy()
    usa = countries[countries['isocode'] == 'USA'].copy()
    ae_excl_us = countries[(countries['ifscode'].isin(ae_ifscodes)) & (countries['ifscode'] != usa_ifscode)].copy()
    em_excl_chn = countries[(countries['ifscode'].isin(em_ifscodes)) & (countries['ifscode'] != chn_ifscode)].copy()
    lidc = countries[countries['ifscode'].isin(lic_ifscodes)].copy()

    chn_contrib = _calc_group_contribution(chn, global_gdp)
    usa_contrib = _calc_group_contribution(usa, global_gdp)
    ae_contrib = _calc_group_contribution(ae_excl_us, global_gdp)
    em_contrib = _calc_group_contribution(em_excl_chn, global_gdp)
    lic_contrib = _calc_group_contribution(lidc, global_gdp)

    # Global total
    global_total = _build_global_debt_total(countries, global_gdp)

    # Merge all components
    contrib = global_total.copy()
    for name, data in [('chn', chn_contrib), ('usa', usa_contrib),
                        ('ae', ae_contrib), ('em', em_contrib), ('lic', lic_contrib)]:
        contrib = contrib.merge(data, on='year', suffixes=('', f'_{name}'))
    contrib.columns = ['year', 'global_debt', 'chn', 'usa', 'ae', 'em', 'lic']

    # Normalize with two base periods
    base_2015 = contrib[contrib['year'] == base_year].iloc[0]
    base_2025 = contrib[contrib['year'] == 2025].iloc[0]

    for grp in ['chn', 'usa', 'ae', 'em', 'lic']:
        contrib[f'{grp}_diff'] = contrib.apply(
            lambda row, g=grp: row[g] - base_2015[g] if row['year'] <= 2025 else row[g] - base_2025[g],
            axis=1
        )

    contrib['base_level'] = contrib['year'].apply(
        lambda y: base_2015['global_debt'] if y <= 2025 else base_2025['global_debt']
    )

    # Stacking: lic, em, ae, usa, chn (bottom to top)
    groups_ordered = ['lic', 'em', 'ae', 'usa', 'chn']
    for grp in groups_ordered:
        contrib[f'{grp}_pos'] = contrib[f'{grp}_diff'].clip(lower=0)
        contrib[f'{grp}_neg'] = contrib[f'{grp}_diff'].clip(upper=0)

    # Positive stacking bases
    contrib['base_lic_pos'] = contrib['base_level']
    contrib['base_em_pos'] = contrib['base_level'] + contrib['lic_pos']
    contrib['base_ae_pos'] = contrib['base_level'] + contrib['lic_pos'] + contrib['em_pos']
    contrib['base_usa_pos'] = contrib['base_level'] + contrib['lic_pos'] + contrib['em_pos'] + contrib['ae_pos']
    contrib['base_chn_pos'] = contrib['base_level'] + contrib['lic_pos'] + contrib['em_pos'] + contrib['ae_pos'] + contrib['usa_pos']

    # Negative stacking bases
    contrib['base_lic_neg'] = contrib['base_level']
    contrib['base_em_neg'] = contrib['base_level'] + contrib['lic_neg']
    contrib['base_ae_neg'] = contrib['base_level'] + contrib['lic_neg'] + contrib['em_neg']
    contrib['base_usa_neg'] = contrib['base_level'] + contrib['lic_neg'] + contrib['em_neg'] + contrib['ae_neg']
    contrib['base_chn_neg'] = contrib['base_level'] + contrib['lic_neg'] + contrib['em_neg'] + contrib['ae_neg'] + contrib['usa_neg']

    return contrib, base_2015['global_debt'], base_2025['global_debt']


def create_contributions_chart_ver4(contrib, base_level_2015, base_level_2025, chart_cfg):
    """Create ver4 chart: debt contributions by income group."""
    fig = go.Figure()

    bar_opacity = 0.6
    groups = [
        ('lic', 'Low-income developing countries', '#795548', 6),       # Brown
        ('em', 'Emerging markets excl. China', f'rgba(255, 152, 0, {bar_opacity})', 5),  # Orange
        ('ae', 'Advanced economies excl. United States', f'rgba(123, 31, 162, {bar_opacity})', 4),    # Purple
        ('usa', 'United States', f'rgba(67, 160, 71, {bar_opacity})', 3),        # Green
        ('chn', 'China', f'rgba(229, 57, 53, {bar_opacity})', 2),               # Red
    ]

    # Positive bars
    for grp, name, color, legendrank in groups:
        fig.add_trace(go.Bar(
            x=contrib['year'], y=contrib[f'{grp}_pos'],
            base=contrib[f'base_{grp}_pos'],
            marker_color=color, name=name, legendrank=legendrank
        ))

    # Negative bars
    for grp, name, color, legendrank in groups:
        fig.add_trace(go.Bar(
            x=contrib['year'], y=contrib[f'{grp}_neg'],
            base=contrib[f'base_{grp}_neg'],
            marker_color=color, showlegend=False
        ))

    # Global debt line
    fig.add_trace(go.Scatter(
        x=contrib['year'], y=contrib['global_debt'],
        mode='lines', line=dict(color='#6A1B9A', width=4),
        name='Global', legendrank=1
    ))

    # Circle markers for 2025 and 2031
    marker_years = contrib[contrib['year'].isin([2025, 2031])]
    fig.add_trace(go.Scatter(
        x=marker_years['year'], y=marker_years['global_debt'],
        mode='markers',
        marker=dict(symbol='circle-open', size=14, color='#6A1B9A', line=dict(width=3.6, color='#6A1B9A')),
        showlegend=False
    ))

    # Base level lines
    fig.add_trace(go.Scatter(
        x=[2015, 2025], y=[base_level_2015, base_level_2015],
        mode='lines', line=dict(color='#A0A0A0', width=2), showlegend=False
    ))
    fig.add_trace(go.Scatter(
        x=[2025, 2031], y=[base_level_2025, base_level_2025],
        mode='lines', line=dict(color='#A0A0A0', width=2), showlegend=False
    ))

    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0)
    _apply_standard_layout(fig, chart_cfg, barmode='overlay')

    return fig


def create_contributions_chart(contrib, base_level_2015, base_level_2025, chart_cfg):
    """Create a chart showing debt contributions with stacked bars."""
    fig = go.Figure()

    # Color scheme
    bar_opacity = 0.6
    chn_color = f'rgba(229, 57, 53, {bar_opacity})'    # Red
    usa_color = f'rgba(67, 160, 71, {bar_opacity})'    # Green
    pos_color = 'rgba(141, 153, 174, 0.5)'   # Blue-grey - positive contributors
    neg_color = 'rgba(161, 136, 127, 0.5)'   # Warm grey/taupe - negative contributors

    # Groups in stacking order (bottom to top): neg, pos, USA, China
    groups = [
        ('neg', 'Other countries (falling debt)', neg_color, 5),
        ('pos', 'Other countries (rising debt)', pos_color, 4),
        ('usa', 'USA', usa_color, 3),
        ('chn', 'China', chn_color, 2),
    ]

    # Positive bars (stacking upward)
    for grp, name, color, legendrank in groups:
        fig.add_trace(go.Bar(
            x=contrib['year'], y=contrib[f'{grp}_pos'],
            base=contrib[f'base_{grp}_pos'],
            marker_color=color,
            name=name,
            legendrank=legendrank
        ))

    # Negative bars (stacking downward) - same colors, no legend entry
    for grp, name, color, legendrank in groups:
        fig.add_trace(go.Bar(
            x=contrib['year'], y=contrib[f'{grp}_neg'],
            base=contrib[f'base_{grp}_neg'],
            marker_color=color,
            showlegend=False
        ))

    # Line for global debt total
    fig.add_trace(go.Scatter(
        x=contrib['year'], y=contrib['global_debt'],
        mode='lines',
        line=dict(color='#6A1B9A', width=6),
        name='Global',
        legendrank=1
    ))

    # Circle markers for 2025 and 2031
    marker_years = contrib[contrib['year'].isin([2025, 2031])]
    fig.add_trace(go.Scatter(
        x=marker_years['year'], y=marker_years['global_debt'],
        mode='markers',
        marker=dict(symbol='circle-open', size=14, color='#6A1B9A', line=dict(width=3.6, color='#6A1B9A')),
        showlegend=False
    ))

    # Horizontal line at 2015 base level (up to 2025)
    fig.add_trace(go.Scatter(
        x=[2015, 2025],
        y=[base_level_2015, base_level_2015],
        mode='lines',
        line=dict(color='#A0A0A0', width=2),
        showlegend=False
    ))

    # Horizontal line at 2025 base level (from 2025 onwards)
    fig.add_trace(go.Scatter(
        x=[2025, 2031],
        y=[base_level_2025, base_level_2025],
        mode='lines',
        line=dict(color='#A0A0A0', width=2),
        showlegend=False
    ))


    # Forecast horizon shading
    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0)

    _apply_standard_layout(fig, chart_cfg, barmode='overlay')

    return fig


def generate_contribution_report(df, output_dir):
    """Generate a text report of top contributors to Other (positive) and Other (negative)."""
    # Filter to single countries only (ifscode < 9000)
    _, _, _, country_year_contrib = _prepare_other_country_contributions(df)

    # Calculate year-over-year changes and cumulate positive/negative separately
    years = sorted(country_year_contrib.index.tolist())

    # Track cumulative positive/negative contribution for each country
    country_pos_contrib = {iso: 0.0 for iso in country_year_contrib.columns}
    country_neg_contrib = {iso: 0.0 for iso in country_year_contrib.columns}

    for i, year in enumerate(years):
        if year > 2025:
            break
        if i > 0:
            prev_year = years[i-1]
            for iso in country_year_contrib.columns:
                change = country_year_contrib.loc[year, iso] - country_year_contrib.loc[prev_year, iso]
                if change >= 0:
                    country_pos_contrib[iso] += change
                else:
                    country_neg_contrib[iso] += change

    pos_series = pd.Series(country_pos_contrib).sort_values(ascending=False)
    neg_series = pd.Series(country_neg_contrib).sort_values(ascending=True)

    total_pos = pos_series.sum()
    total_neg = neg_series.sum()

    # Build report
    lines = [
        "GROSS DEBT GLOBAL: CONTRIBUTION ANALYSIS",
        "=" * 60,
        "",
        "Countries are classified each year based on whether their",
        "year-over-year contribution change is positive or negative.",
        "Values shown are cumulative sums of these changes (2015-2025).",
        "",
        "=" * 60,
        f"TOTAL OTHER (POSITIVE): {total_pos:.2f} pp",
        "=" * 60,
        "",
        "TOP 10 CONTRIBUTORS TO 'OTHER (POSITIVE)':",
        "-" * 40,
    ]

    top10_pos = pos_series.head(10)
    for iso, val in top10_pos.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_pos.sum():.2f} pp")
    lines.append(f"  Top 10 explains: {top10_pos.sum()/total_pos*100:.1f}% of total")

    lines.append("")
    _append_top10_section(
        lines,
        "TOTAL OTHER (NEGATIVE)",
        {'heading': "TOP 10 CONTRIBUTORS TO 'OTHER (NEGATIVE)':", 'values': neg_series},
        total_neg,
        include_total_wrappers=True
    )

    # Add Japan explanation
    lines.append("")
    lines.append("=" * 60)
    lines.append("NOTE: JAPAN IN BOTH LISTS")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Japan appears as top contributor to both positive and negative")
    lines.append("because it has large swings year-over-year. In years when its")
    lines.append("contribution increases, it adds to 'Other countries (rising debt)'; in years")
    lines.append("when it decreases, it adds to 'Other countries (falling debt)'.")
    lines.append("")
    lines.append("Japan year-over-year contribution changes:")
    lines.append("-" * 40)

    # Calculate Japan's year-over-year changes
    jpn_changes = []
    for i, year in enumerate(years):
        if year > 2025:
            break
        if i > 0:
            prev_year = years[i-1]
            if 'JPN' in country_year_contrib.columns:
                change = country_year_contrib.loc[year, 'JPN'] - country_year_contrib.loc[prev_year, 'JPN']
                group = "positive" if change >= 0 else "negative"
                jpn_changes.append((year, change, group))
                lines.append(f"  {int(year)}: {change:+.4f} ({group})")

    if 'JPN' in country_year_contrib.columns:
        jpn_pos = country_pos_contrib.get('JPN', 0)
        jpn_neg = country_neg_contrib.get('JPN', 0)
        lines.append("")
        lines.append(f"  Japan total positive contributions: {jpn_pos:+.4f}")
        lines.append(f"  Japan total negative contributions: {jpn_neg:+.4f}")
        lines.append(f"  Japan net contribution change:      {jpn_pos + jpn_neg:+.4f}")

    # Write report
    report_path = output_dir / 'gross_debt_global_ver1.txt'
    with open(report_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"  Saved gross_debt_global_ver1.txt")


def generate_contribution_report_ver2(df, output_dir):
    """Generate a text report for ver2 (hybrid: ver3 for period 1, ver1 for period 2)."""
    # Filter to single countries only (ifscode < 9000)
    _, _, _, country_year_contrib = _prepare_other_country_contributions(df)

    years = sorted(country_year_contrib.index.tolist())

    # === PERIOD 1 (2015-2025): Period-based classification ===
    contrib_2015 = country_year_contrib.loc[2015]
    contrib_2025 = country_year_contrib.loc[2025]
    change_p1 = contrib_2025 - contrib_2015

    pos_countries_p1 = change_p1[change_p1 >= 0].sort_values(ascending=False)
    neg_countries_p1 = change_p1[change_p1 < 0].sort_values(ascending=True)

    # === PERIOD 2 (2026-2031): Year-over-year classification ===
    country_pos_contrib_p2 = {iso: 0.0 for iso in country_year_contrib.columns}
    country_neg_contrib_p2 = {iso: 0.0 for iso in country_year_contrib.columns}

    p2_years = [y for y in years if y >= 2025]
    for i, year in enumerate(p2_years):
        if year == 2025:
            continue
        prev_year = p2_years[i-1]
        for iso in country_year_contrib.columns:
            change = country_year_contrib.loc[year, iso] - country_year_contrib.loc[prev_year, iso]
            if change >= 0:
                country_pos_contrib_p2[iso] += change
            else:
                country_neg_contrib_p2[iso] += change

    pos_series_p2 = pd.Series(country_pos_contrib_p2).sort_values(ascending=False)
    neg_series_p2 = pd.Series(country_neg_contrib_p2).sort_values(ascending=True)
    total_pos_p2 = pos_series_p2.sum()
    total_neg_p2 = neg_series_p2.sum()

    # Build report
    lines = [
        "GROSS DEBT GLOBAL (VER2): CONTRIBUTION ANALYSIS",
        "=" * 60,
        "",
        "Hybrid classification approach:",
        "- Period 1 (2015-2025): period-based by 2025-2015 change (like ver3)",
        "- Period 2 (2026-2031): year-over-year classification (like ver1)",
        "",
        "=" * 60,
        "PERIOD 1: 2015-2025 (Period-Based Classification)",
        "=" * 60,
        "",
        f"TOTAL POSITIVE CHANGE (Other positive): {pos_countries_p1.sum():.2f} pp",
        "",
        "TOP 10 CONTRIBUTORS (2025-2015 change):",
        "-" * 40,
    ]

    top10_pos_p1 = pos_countries_p1.head(10)
    for iso, val in top10_pos_p1.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_pos_p1.sum():.2f} pp")
    if pos_countries_p1.sum() != 0:
        lines.append(f"  Top 10 explains: {top10_pos_p1.sum()/pos_countries_p1.sum()*100:.1f}% of total")

    lines.append("")
    lines.append(f"TOTAL NEGATIVE CHANGE (Other negative): {neg_countries_p1.sum():.2f} pp")
    lines.append("")
    lines.append("TOP 10 CONTRIBUTORS (2025-2015 change):")
    lines.append("-" * 40)

    top10_neg_p1 = neg_countries_p1.head(10)
    for iso, val in top10_neg_p1.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_neg_p1.sum():.2f} pp")
    if neg_countries_p1.sum() != 0:
        lines.append(f"  Top 10 explains: {top10_neg_p1.sum()/neg_countries_p1.sum()*100:.1f}% of total")

    lines.append("")
    lines.append("=" * 60)
    lines.append("PERIOD 2: 2026-2031 (Year-over-Year Classification)")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"TOTAL OTHER (POSITIVE): {total_pos_p2:.2f} pp")
    lines.append("")
    lines.append("TOP 10 CONTRIBUTORS (cumulated positive YoY changes):")
    lines.append("-" * 40)

    top10_pos_p2 = pos_series_p2.head(10)
    for iso, val in top10_pos_p2.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_pos_p2.sum():.2f} pp")
    if total_pos_p2 != 0:
        lines.append(f"  Top 10 explains: {top10_pos_p2.sum()/total_pos_p2*100:.1f}% of total")

    lines.append("")
    lines.append(f"TOTAL OTHER (NEGATIVE): {total_neg_p2:.2f} pp")
    lines.append("")
    lines.append("TOP 10 CONTRIBUTORS (cumulated negative YoY changes):")
    lines.append("-" * 40)

    top10_neg_p2 = neg_series_p2.head(10)
    for iso, val in top10_neg_p2.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_neg_p2.sum():.2f} pp")
    if total_neg_p2 != 0:
        lines.append(f"  Top 10 explains: {top10_neg_p2.sum()/total_neg_p2*100:.1f}% of total")

    # Write report
    report_path = output_dir / 'gross_debt_global_ver2.txt'
    with open(report_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"  Saved gross_debt_global_ver2.txt")


def generate_contribution_report_ver3(df, output_dir):
    """Generate a text report of top contributors for ver3 (period-based classification)."""
    # Filter to single countries only (ifscode < 9000)
    _, _, _, country_year_contrib = _prepare_other_country_contributions(df)

    # Calculate contributions at key years
    contrib_2015 = country_year_contrib.loc[2015]
    contrib_2025 = country_year_contrib.loc[2025]
    contrib_2031 = country_year_contrib.loc[2031]

    # Period 1 (2015-2025): classify by 2025-2015 change
    change_p1 = contrib_2025 - contrib_2015
    pos_countries_p1 = change_p1[change_p1 >= 0].sort_values(ascending=False)
    neg_countries_p1 = change_p1[change_p1 < 0].sort_values(ascending=True)

    # Period 2 (2026-2031): classify by 2031-2025 change
    change_p2 = contrib_2031 - contrib_2025
    pos_countries_p2 = change_p2[change_p2 >= 0].sort_values(ascending=False)
    neg_countries_p2 = change_p2[change_p2 < 0].sort_values(ascending=True)

    # Build report
    lines = [
        "GROSS DEBT GLOBAL (VER3): CONTRIBUTION ANALYSIS",
        "=" * 60,
        "",
        "Countries are classified based on TOTAL PERIOD CHANGE:",
        "- Period 1 (2015-2025): classification by 2025-2015 change",
        "- Period 2 (2026-2031): classification by 2031-2025 change",
        "",
        "=" * 60,
        "PERIOD 1: 2015-2025",
        "=" * 60,
        "",
        f"TOTAL POSITIVE CHANGE (Other positive): {pos_countries_p1.sum():.2f} pp",
        "",
        "TOP 10 CONTRIBUTORS (2025-2015 change):",
        "-" * 40,
    ]

    top10_pos_p1 = pos_countries_p1.head(10)
    for iso, val in top10_pos_p1.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_pos_p1.sum():.2f} pp")
    if pos_countries_p1.sum() != 0:
        lines.append(f"  Top 10 explains: {top10_pos_p1.sum()/pos_countries_p1.sum()*100:.1f}% of total")

    lines.append("")
    lines.append(f"TOTAL NEGATIVE CHANGE (Other negative): {neg_countries_p1.sum():.2f} pp")
    lines.append("")
    lines.append("TOP 10 CONTRIBUTORS (2025-2015 change):")
    lines.append("-" * 40)

    top10_neg_p1 = neg_countries_p1.head(10)
    for iso, val in top10_neg_p1.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_neg_p1.sum():.2f} pp")
    if neg_countries_p1.sum() != 0:
        lines.append(f"  Top 10 explains: {top10_neg_p1.sum()/neg_countries_p1.sum()*100:.1f}% of total")

    lines.append("")
    lines.append("=" * 60)
    lines.append("PERIOD 2: 2026-2031")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"TOTAL POSITIVE CHANGE (Other positive): {pos_countries_p2.sum():.2f} pp")
    lines.append("")
    lines.append("TOP 10 CONTRIBUTORS (2031-2025 change):")
    lines.append("-" * 40)

    top10_pos_p2 = pos_countries_p2.head(10)
    for iso, val in top10_pos_p2.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_pos_p2.sum():.2f} pp")
    if pos_countries_p2.sum() != 0:
        lines.append(f"  Top 10 explains: {top10_pos_p2.sum()/pos_countries_p2.sum()*100:.1f}% of total")

    lines.append("")
    lines.append(f"TOTAL NEGATIVE CHANGE (Other negative): {neg_countries_p2.sum():.2f} pp")
    lines.append("")
    lines.append("TOP 10 CONTRIBUTORS (2031-2025 change):")
    lines.append("-" * 40)

    top10_neg_p2 = neg_countries_p2.head(10)
    for iso, val in top10_neg_p2.items():
        lines.append(f"  {iso}: {val:+.4f}")

    lines.append("")
    lines.append(f"  Top 10 sum: {top10_neg_p2.sum():.2f} pp")
    if neg_countries_p2.sum() != 0:
        lines.append(f"  Top 10 explains: {top10_neg_p2.sum()/neg_countries_p2.sum()*100:.1f}% of total")

    # Write report
    report_path = output_dir / 'gross_debt_global_ver3.txt'
    with open(report_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"  Saved gross_debt_global_ver3.txt")


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)

    df = load_data()

    # Filter to global aggregate for second chart
    global_data = df[df['ifscode'] == 9999].copy()
    global_data = global_data[global_data['year'].between(2015, 2031)].sort_values('year')

    # Calculate regional aggregates
    regional_data = calculate_regional_aggregates(df, 'ggxwdg_gdp')

    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    print("Generating Gross Debt charts...")

    # Calculate regional aggregates
    print(f"  Regional aggregates: {len(regional_data)} rows calculated")

    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    # Chart 1: Global with contributions (ver3 - period-based classification)
    contrib_v3, base_level_2015_v3, base_level_2025_v3 = calculate_debt_contributions_ver3(df, base_year=2015)
    fig_v3 = create_contributions_chart(contrib_v3, base_level_2015_v3, base_level_2025_v3, chart_cfg)
    save_path_v3 = output_dir / 'gross_debt_global_ver3'
    pio.write_image(fig_v3, f"{save_path_v3}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig_v3, f"{save_path_v3}.svg", format='svg', engine='kaleido', scale=2)
    fig_v3.write_html(f"{save_path_v3}.html", auto_open=auto_open, include_plotlyjs='cdn')
    csv_v3 = contrib_v3[['year', 'global_debt', 'base_level', 'chn_diff', 'usa_diff', 'pos_diff', 'neg_diff']].copy()
    csv_v3['year'] = csv_v3['year'].astype(int)
    csv_v3.round(2).to_csv(output_dir / 'gross_debt_global_ver3.csv', index=False)
    print(f"  Saved gross_debt_global_ver3.png")

    # Generate contribution report for ver3
    generate_contribution_report_ver3(df, output_dir)

    # Chart 2: By income group (overall balance)
    fig_grp = create_multi_series_chart(df, 'ggxcnl_gdp', DEBT_SERIES_INCOME, chart_cfg)
    save_path_grp = output_dir / 'overall_balance_by_group'
    pio.write_image(fig_grp, f"{save_path_grp}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig_grp, f"{save_path_grp}.svg", format='svg', engine='kaleido', scale=2)
    fig_grp.write_html(f"{save_path_grp}.html", auto_open=auto_open, include_plotlyjs='cdn')
    print(f"  Saved overall_balance_by_group.png")

    print("Gross Debt charts complete.")


if __name__ == "__main__":
    main()
