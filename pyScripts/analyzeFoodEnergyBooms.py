import sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import resolve_from_config, ensure_output_dir, load_config, load_chart_config, get_chart_dims_px

# Load country classification from data dictionary
ct_path = resolve_from_config("../+environment/csvFiles/countryTable.csv")
ct = pd.read_csv(ct_path)

# Build country group lists from countryTable
ae_list = ct[ct['devClass'] == 'Advanced']['ifscode'].tolist()
em_list = ct[ct['devClass'] == 'Emerging']['ifscode'].tolist()
lic_list = ct[ct['devClass'] == 'Low-Income']['ifscode'].tolist()

# Build cgroup mapping (ifscode -> group code)
devclass_to_code = {'Advanced': 'AE', 'Emerging': 'EM', 'Low-Income': 'LIC'}
cgroup = ct.set_index('ifscode')['devClass'].map(devclass_to_code).to_dict()

# Build iso_to_ifs mapping
iso_to_ifs = ct.set_index('iso3c')['ifscode'].to_dict()
ifs_to_country = ct.set_index('ifscode')['country'].to_dict()

# Oil exporters from data dictionary
oil_exporter_list = ct[ct['oilExporter'] == 'Yes']['ifscode'].tolist()


def compute_boom_change(df, boom_periods, value_col='adj_deficit'):
    """
    Calculate deficit change from year after boom start to boom end.

    For each country and each boom period:
        deficit_change = deficit_end - deficit_(start+1)
    Using start+1 to avoid pandemic effects in 2020 (abnormal deficits).
    Then average across all boom periods for each country.
    """
    d = df.sort_values(['ifscode', 'year']).copy()

    results = []
    for ifscode in d['ifscode'].unique():
        country_data = d[d['ifscode'] == ifscode].set_index('year')[value_col]

        changes = []
        for start_year, end_year in boom_periods:
            # Use start+1 to avoid pandemic-year effects
            baseline_year = start_year + 1
            if baseline_year in country_data.index and end_year in country_data.index:
                def_baseline = country_data.loc[baseline_year]
                def_end = country_data.loc[end_year]
                if pd.notna(def_baseline) and pd.notna(def_end):
                    changes.append(def_end - def_baseline)

        if changes:
            avg_change = np.mean(changes)
            results.append({
                'ifscode': ifscode,
                'def_change': avg_change,
                'n_booms': len(changes)
            })

    out = pd.DataFrame(results)
    out['country_group'] = out['ifscode'].map(cgroup)
    # deficit increased if change > 0 (deficit = negative balance, so increase is bad)
    out['def_incr'] = (out['def_change'] > 0).astype(int)

    return out

def gen_summary(df):
    """Generate summary statistics by country group."""
    summary = df.groupby('country_group').agg(
        share_increasing_deficit=('def_incr', 'mean'),
        count_increasing_deficit=('def_incr', 'sum'),
        count_total=('def_incr', 'count')
    )
    # Count of countries with improving deficit
    summary['count_improving_deficit'] = summary['count_total'] - summary['count_increasing_deficit']
    # Use median instead of mean to be robust to outliers
    summary['median_deficit_change_if_increase'] = (
        df[df['def_incr'] == 1]
        .groupby('country_group')['def_change']
        .median()
    )
    # For exporters: median improvement (positive value) for those who improved
    summary['median_deficit_change_if_improve'] = (
        df[df['def_incr'] == 0]
        .groupby('country_group')['def_change']
        .median()
        .abs()  # Make positive (improvement magnitude)
    )
    summary = summary.reset_index()
    summary['share_increasing_deficit'] *= 100

    return summary


##### Download / Load Data #####
## WEO - Load from WEO_enhanced.dta
weo_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
fiscal_df = pd.read_stata(weo_path)
fiscal_df = fiscal_df[['ifscode', 'year', 'ggxcnl_gdp', 'ggxonlb_gdp']].copy()
fiscal_df['adj_deficit'] = -fiscal_df['ggxcnl_gdp']
fiscal_df = fiscal_df.query('year >= 1991 & year <= 2025')

## Primary Commodity Price System (PCPS)
pcps_path = resolve_from_config("../data/fmData/food_energy_index_v2.xlsx")
pcps = pd.read_excel(pcps_path)
pcps = pcps.sort_values('year')

# Define boom periods based on economic history (not statistical algorithm)
# Energy booms:
#   1. 2002-2008: Commodity Supercycle (China industrialization, oil to $147)
#   2. 2009-2014: Post-crisis recovery plateau (oil $80-110)
#   3. 2020-2022: COVID recovery + Ukraine war
# Food booms:
#   1. 2006-2008: Global Food Crisis (biofuels, export bans, riots)
#   2. 2009-2011: Second food spike (La Niña, Russia export ban, Arab Spring)
#   3. 2020-2022: COVID + Ukraine (supply chains, grain/fertilizer shock)

energy_boom_periods = [(2002, 2008), (2009, 2014), (2020, 2022)]
food_boom_periods = [(2006, 2008), (2009, 2011), (2020, 2022)]

def year_in_boom(year, boom_periods):
    return any(start <= year <= end for start, end in boom_periods)

pcps['energy_index_boom'] = pcps['year'].apply(lambda y: 1 if year_in_boom(y, energy_boom_periods) else 0)
pcps['food_index_boom'] = pcps['year'].apply(lambda y: 1 if year_in_boom(y, food_boom_periods) else 0)


##### Post-cleaning #####
df = fiscal_df.merge(pcps, on='year', how='left')
df = df[['ifscode', 'year', 'adj_deficit', 'food_index', 'energy_index', 'food_index_point', 'energy_index_point', 'food_index_boom', 'energy_index_boom']].sort_values(['ifscode', 'year'])
df = df.sort_values(['ifscode','year'])

# Exclude outlier economies (COVID-driven fiscal swings unrelated to commodity prices)
exclude_list = [532, 546]  # Hong Kong SAR, Macao SAR
df = df[~df['ifscode'].isin(exclude_list)]

## food index boom - deficit change from boom start to boom end
food = compute_boom_change(df, food_boom_periods)
food_summary = gen_summary(food)

## energy index boom (non-exporters) - deficit change from boom start to boom end
energy = compute_boom_change(df[~df['ifscode'].isin(oil_exporter_list)], energy_boom_periods)
energy_summary = gen_summary(energy)

## energy index boom (oil exporters only - keep AE/EM/LIC grouping)
energy_exp = compute_boom_change(df[df['ifscode'].isin(oil_exporter_list)], energy_boom_periods)
energy_exp_summary = gen_summary(energy_exp)


##### Export #####
config = load_config()
output_dir = ensure_output_dir(config)

# output_excel = output_dir / 'fiscal_performance_food_energy_boom.xlsx'
# print(f"Exporting results to {output_excel}...")
# with pd.ExcelWriter(output_excel, engine="xlsxwriter") as writer:
#
#     df.to_excel(writer, sheet_name='data_all', index=False)
#     food.to_excel(writer, sheet_name='food_clean', index=False)
#     energy.to_excel(writer, sheet_name='energy_clean', index=False)
#
#     workbook  = writer.book
#     worksheet = workbook.add_worksheet('chart')
#     writer.sheets['chart'] = worksheet
#
#     worksheet.write('B2', 'Food')
#     food_summary.to_excel(
#         writer,
#         sheet_name='chart',
#         startrow=2,   # B3
#         startcol=1,
#         index=False
#     )
#
#     worksheet.write('B9', 'Energy')
#     energy_summary.to_excel(
#         writer,
#         sheet_name='chart',
#         startrow=9,   # B10
#         startcol=1,
#         index=False
#     )

##### Generate Bar Charts #####
from plotly.subplots import make_subplots

chart_cfg = load_chart_config()['styling']
auto_open = config.get("output_settings", {}).get("auto_open_html", False)

# Get data for each group - handle missing groups gracefully
def get_group_values(summary, groups, col):
    idx = summary.set_index('country_group')
    values = []
    for g in groups:
        if g in idx.index:
            values.append(idx.loc[g, col])
        else:
            values.append(np.nan)
    return values

groups = ['AE', 'EM', 'LIC']

# Get both shares and counts
energy_share = get_group_values(energy_summary, groups, 'share_increasing_deficit')
energy_exp_share_raw = get_group_values(energy_exp_summary, groups, 'share_increasing_deficit')
energy_exp_share = [100 - x if not np.isnan(x) else np.nan for x in energy_exp_share_raw]

energy_count = get_group_values(energy_summary, groups, 'count_increasing_deficit')
energy_exp_count = get_group_values(energy_exp_summary, groups, 'count_improving_deficit')

energy_avg_chg = get_group_values(energy_summary, groups, 'median_deficit_change_if_increase')
energy_exp_avg_chg = get_group_values(energy_exp_summary, groups, 'median_deficit_change_if_improve')

# Colors for country groups
ae_color = '#1E88E5'      # Blue for Advanced
em_color = '#E65100'      # Deep orange for Emerging
lic_color = '#00897B'     # Teal for Low-Income
ae_color_light = '#90CAF9'
em_color_light = '#FFAB91'
lic_color_light = '#80CBC4'
ae_label_color = '#B3E5FC'
em_label_color = '#FFE082'
lic_label_color = '#FFCDD2'

def create_deficit_bar_chart(importer_values, exporter_values, y_axis_title, y_range=None):
    """Create a grouped bar chart for deficit changes during energy booms."""
    categories = [
        'Energy<br>(importers)<br>Deficit <b><span style="color:#E65100">deterioration</span></b>',
        'Energy<br>(exporters)<br>Deficit <b><span style="color:#00897B">improvement</span></b>'
    ]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Main bars (left axis)
    for i, (name, color, group) in enumerate([
        ('Advanced economies', ae_color, 'AE'),
        ('Emerging markets', em_color, 'EM'),
        ('Low-income developing countries', lic_color, 'LIC')
    ]):
        fig.add_trace(go.Bar(
            name=name,
            x=categories,
            y=[importer_values[i], exporter_values[i]],
            marker_color=color,
            legendgroup=group,
            offsetgroup=group
        ), secondary_y=False)

    # Thin bars for median deficit change (right axis)
    for i, (color_light, group) in enumerate([
        (ae_color_light, 'AE'),
        (em_color_light, 'EM'),
        (lic_color_light, 'LIC')
    ]):
        fig.add_trace(go.Bar(
            x=categories,
            y=[energy_avg_chg[i], energy_exp_avg_chg[i]],
            marker_color=color_light,
            width=0.06,
            offsetgroup=group,
            showlegend=False
        ), secondary_y=True)

    # Annotations for thin bar labels
    avg_data = {
        'AE': {'values': [energy_avg_chg[0], energy_exp_avg_chg[0]], 'color': ae_label_color, 'xshift': -58},
        'EM': {'values': [energy_avg_chg[1], energy_exp_avg_chg[1]], 'color': em_label_color, 'xshift': 0},
        'LIC': {'values': [energy_avg_chg[2], energy_exp_avg_chg[2]], 'color': lic_label_color, 'xshift': 58}
    }
    for group, data in avg_data.items():
        for j, cat in enumerate(categories):
            if not np.isnan(data['values'][j]):
                fig.add_annotation(
                    x=cat, y=data['values'][j],
                    text=f"{data['values'][j]:.1f}",
                    font=dict(size=chart_cfg['legend']['font_size'], color=data['color']),
                    showarrow=False, xshift=data['xshift'], yshift=12, yref='y2'
                )

    # Layout
    legend_style = {k: v for k, v in chart_cfg['legend'].items() if k != 'font_size'}
    legend_style.update({
        "font": dict(size=chart_cfg['legend']['font_size']),
        "y": 1.01, "x": 0.5, "xanchor": 'center', "orientation": 'h',
        "tracegroupgap": 0, "itemwidth": 30
    })

    _fe_w, _fe_h = get_chart_dims_px("food_energy_boom_deficit_count.png")
    fig.update_layout(
        template=chart_cfg['template'],
        width=_fe_w,
        height=_fe_h,
        margin=dict(t=40, b=0, l=50, r=60),
        font=dict(size=chart_cfg['axes']['tickfont_size']),
        legend=legend_style,
        barmode='group',
        bargap=0.2,
        bargroupgap=0.1,
        xaxis_title=""
    )

    fig.update_xaxes(
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )

    # Left y-axis
    left_yaxis_kwargs = dict(
        title_text=y_axis_title,
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )
    if y_range:
        left_yaxis_kwargs['range'] = y_range
    fig.update_yaxes(**left_yaxis_kwargs, secondary_y=False)

    # Right y-axis (median change)
    fig.update_yaxes(
        title_text="Median deficit change<br>(percentage points of GDP)",
        showgrid=False,
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        range=[0, 6],
        secondary_y=True
    )

    return fig

# Generate SHARE chart
fig_share = create_deficit_bar_chart(
    energy_share, energy_exp_share,
    y_axis_title="Share of countries (percent)",
    y_range=[0, 100]
)
# Share chart disabled for outreach project (not in chartTable)

# Generate COUNT chart
fig_count = create_deficit_bar_chart(
    energy_count, energy_exp_count,
    y_axis_title="Number of countries"
)
count_path = output_dir / "food_energy_boom_deficit_count"
pio.write_image(fig_count, f"{count_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_count, f"{count_path}.svg", format='svg', engine='kaleido', scale=2)
fig_count.write_html(f"{count_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Count chart saved to {count_path}.png")

# Export CSV with chart data
csv_df = pd.DataFrame({
    'income_group': ['Advanced', 'Emerging', 'Low-Income'],
    'importers_deficit_deterioration_count': energy_count,
    'importers_median_deficit_change_pct_gdp': [round(x, 2) for x in energy_avg_chg],
    'exporters_deficit_improvement_count': energy_exp_count,
    'exporters_median_deficit_change_pct_gdp': [round(x, 2) for x in energy_exp_avg_chg]
})
csv_df.to_csv(f"{count_path}.csv", index=False)
print(f"CSV data saved to {count_path}.csv")

# Outreach project: only the count chart is listed in chartTable; skip the rest
sys.exit(0)

# Export txt with underlying numbers
group_labels = {'AE': 'Advanced', 'EM': 'Emerging', 'LIC': 'Low-Income'}
txt_path = output_dir / "food_energy_boom_deficit_data.txt"
with open(txt_path, 'w') as f:
    f.write("FOOD/ENERGY BOOM DEFICIT ANALYSIS\n")
    f.write("=" * 70 + "\n\n")

    f.write("SHARE OF COUNTRIES WITH DEFICIT DETERIORATION/IMPROVEMENT (%)\n")
    f.write("-" * 70 + "\n")
    f.write(f"{'Group':<15} {'Importers (deterioration)':>28} {'Exporters (improvement)':>28}\n")
    for i, g in enumerate(groups):
        f.write(f"{group_labels[g]:<15} {energy_share[i]:>28.2f} {energy_exp_share[i]:>28.2f}\n")

    f.write(f"\nCOUNT OF COUNTRIES WITH DEFICIT DETERIORATION/IMPROVEMENT\n")
    f.write("-" * 70 + "\n")
    f.write(f"{'Group':<15} {'Importers (deterioration)':>28} {'Exporters (improvement)':>28}\n")
    for i, g in enumerate(groups):
        f.write(f"{group_labels[g]:<15} {energy_count[i]:>28.2f} {energy_exp_count[i]:>28.2f}\n")

    f.write(f"\nMEDIAN DEFICIT CHANGE (pp of GDP)\n")
    f.write("-" * 70 + "\n")
    f.write(f"{'Group':<15} {'Importers (if deterioration)':>28} {'Exporters (if improvement)':>28}\n")
    for i, g in enumerate(groups):
        f.write(f"{group_labels[g]:<15} {energy_avg_chg[i]:>28.2f} {energy_exp_avg_chg[i]:>28.2f}\n")

print(f"Data txt saved to {txt_path}")

##### Aggregate versions (no income group split) #####
# Importers aggregate
imp_share_agg = energy['def_incr'].mean() * 100
imp_count_agg = int(energy['def_incr'].sum())
imp_total_agg = len(energy)
imp_median_chg = energy.loc[energy['def_incr'] == 1, 'def_change'].median()

# Exporters aggregate (improvement = 1 - def_incr)
exp_share_agg = (1 - energy_exp['def_incr'].mean()) * 100
exp_count_agg = int((1 - energy_exp['def_incr']).sum())
exp_total_agg = len(energy_exp)
exp_median_chg = energy_exp.loc[energy_exp['def_incr'] == 0, 'def_change'].abs().median()

def create_aggregate_bar_chart(imp_val, exp_val, y_axis_title, imp_median, exp_median, y_range=None):
    """Create a simple 2-bar chart (importers vs exporters), no income group split."""
    categories = [
        'Energy<br>(importers)<br>Deficit <b><span style="color:#E65100">deterioration</span></b>',
        'Energy<br>(exporters)<br>Deficit <b><span style="color:#00897B">improvement</span></b>'
    ]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Distinct colors (unrelated to income group palette)
    imp_bar_color = '#00897B'      # Teal
    exp_bar_color = '#7B1FA2'      # Purple
    imp_thin_color = '#80CBC4'     # Light teal
    exp_thin_color = '#CE93D8'     # Light purple

    # Main bars
    fig.add_trace(go.Bar(
        x=categories,
        y=[imp_val, exp_val],
        marker_color=[imp_bar_color, exp_bar_color],
        showlegend=False,
        width=0.5
    ), secondary_y=False)

    # Thin bars for median deficit change (right axis)
    fig.add_trace(go.Bar(
        x=categories,
        y=[imp_median if pd.notna(imp_median) else 0,
           exp_median if pd.notna(exp_median) else 0],
        marker_color=[imp_thin_color, exp_thin_color],
        width=0.08,
        showlegend=False
    ), secondary_y=True)

    # Annotations for median values
    for j, (cat, val) in enumerate(zip(categories, [imp_median, exp_median])):
        if pd.notna(val):
            fig.add_annotation(
                x=cat, y=val,
                text=f"{val:.1f}",
                font=dict(size=11, color=[imp_thin_color, exp_thin_color][j]),
                showarrow=False, yshift=12, yref='y2'
            )

    legend_style = chart_cfg['legend'].copy()
    legend_style.update({
        "font": dict(size=chart_cfg['font_size'] - 7),
        "y": 1.01, "x": 0.5, "xanchor": 'center', "orientation": 'h',
    })

    fig.update_layout(
        template=chart_cfg['template'],
        width=chart_cfg['width'],
        height=chart_cfg['height'],
        margin=dict(t=80, b=50, l=50, r=60),
        font=dict(size=chart_cfg['font_size'] - 6),
        legend=legend_style,
        barmode='group',
        bargap=0.2,
        xaxis_title=""
    )

    fig.update_xaxes(
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )

    left_yaxis_kwargs = dict(
        title_text=y_axis_title,
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )
    if y_range:
        left_yaxis_kwargs['range'] = y_range
    fig.update_yaxes(**left_yaxis_kwargs, secondary_y=False)

    fig.update_yaxes(
        title_text="Median deficit change<br>(percentage points of GDP)",
        showgrid=False,
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        range=[0, 6],
        secondary_y=True
    )

    return fig

# Aggregate SHARE chart
fig_share_agg = create_aggregate_bar_chart(
    imp_share_agg, exp_share_agg,
    y_axis_title="Share of countries (percent)",
    imp_median=imp_median_chg, exp_median=exp_median_chg,
    y_range=[0, 100]
)
share_agg_path = output_dir / "food_energy_boom_deficit_share_agg"
pio.write_image(fig_share_agg, f"{share_agg_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_share_agg, f"{share_agg_path}.svg", format='svg', engine='kaleido', scale=2)
fig_share_agg.write_html(f"{share_agg_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Aggregate share chart saved to {share_agg_path}.png")

# Aggregate COUNT chart
fig_count_agg = create_aggregate_bar_chart(
    imp_count_agg, exp_count_agg,
    y_axis_title="Number of countries",
    imp_median=imp_median_chg, exp_median=exp_median_chg,
)
count_agg_path = output_dir / "food_energy_boom_deficit_count_agg"
pio.write_image(fig_count_agg, f"{count_agg_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_count_agg, f"{count_agg_path}.svg", format='svg', engine='kaleido', scale=2)
fig_count_agg.write_html(f"{count_agg_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Aggregate count chart saved to {count_agg_path}.png")

# Export txt for aggregate charts
agg_txt_path = output_dir / "food_energy_boom_deficit_data_agg.txt"
with open(agg_txt_path, 'w') as f:
    f.write("FOOD/ENERGY BOOM DEFICIT ANALYSIS (AGGREGATE)\n")
    f.write("=" * 70 + "\n\n")

    f.write(f"{'':30} {'Importers':>18} {'Exporters':>18}\n")
    f.write("-" * 66 + "\n")
    f.write(f"{'Share deterioration/improvement (%)':30} {imp_share_agg:>18.2f} {exp_share_agg:>18.2f}\n")
    f.write(f"{'Count':30} {imp_count_agg:>18} {exp_count_agg:>18}\n")
    f.write(f"{'Total countries':30} {imp_total_agg:>18} {exp_total_agg:>18}\n")
    f.write(f"{'Median deficit change (pp GDP)':30} {imp_median_chg:>18.2f} {exp_median_chg:>18.2f}\n")

print(f"Aggregate data txt saved to {agg_txt_path}")

##### Average Deficit Change Across Energy Booms #####
# Combine energy importers + exporters for energy booms (all countries)
energy_all = pd.concat([energy, energy_exp], ignore_index=True)

# X-axis categories: Importers, Exporters, All countries
# Each dot = one country's average deficit change across all episodes
cat_labels = ['Importers', 'Exporters', 'All countries']
cat_data = [energy, energy_exp, energy_all]
cat_colors = ['#00897B', '#7B1FA2', '#546E7A']  # Teal, Purple, Blue-grey

mean_marker_color = '#D84315'   # Deep orange for mean
median_marker_color = '#6A1B9A' # Strong blue for median

fig_avg = go.Figure()

bar_width = 0.5

for i, (label, dot_df, color) in enumerate(zip(cat_labels, cat_data, cat_colors)):
    avg_val = -dot_df['def_change'].mean()
    med_val = -dot_df['def_change'].median()

    # Jitter dots
    hw = bar_width / 2.5
    jitter = np.random.default_rng(42 + i).uniform(-hw, hw, len(dot_df))
    fig_avg.add_trace(go.Scatter(
        x=i + jitter,
        y=-dot_df['def_change'].values,
        mode='markers',
        marker=dict(size=5, color=color, opacity=0.4),
        showlegend=False,
        customdata=[ifs_to_country.get(ifs, str(int(ifs))) for ifs in dot_df['ifscode'].values],
        hovertemplate='%{customdata}: %{y:.2f} pp<extra></extra>'
    ))

    # Mean horizontal line
    fig_avg.add_trace(go.Scatter(
        x=[i - hw, i + hw], y=[avg_val, avg_val],
        mode='lines',
        line=dict(color=mean_marker_color, width=3),
        name='Mean' if i == 0 else None,
        showlegend=(i == 0),
        legendgroup='mean'
    ))

    # Median horizontal line
    fig_avg.add_trace(go.Scatter(
        x=[i - hw, i + hw], y=[med_val, med_val],
        mode='lines',
        line=dict(color=median_marker_color, width=3, dash='dash'),
        name='Median' if i == 0 else None,
        showlegend=(i == 0),
        legendgroup='median'
    ))

    # Annotations (to the right of the jitter area)
    # Ensure vertical spacing so labels don't overlap
    label_gap = 8  # minimum pixel spacing
    if abs(avg_val - med_val) < 0.8:  # values too close in data space
        avg_yshift = label_gap
        med_yshift = -label_gap
    else:
        avg_yshift = 0
        med_yshift = 0
    fig_avg.add_annotation(
        x=i + hw, y=avg_val,
        text=f"mean: {avg_val:+.2f}",
        font=dict(size=10, color=mean_marker_color),
        bgcolor='rgba(255, 249, 219, 0.85)', borderpad=2,
        showarrow=False, xshift=8, yshift=avg_yshift, xanchor='left'
    )
    fig_avg.add_annotation(
        x=i + hw, y=med_val,
        text=f"median: {med_val:+.2f}",
        font=dict(size=10, color=median_marker_color),
        bgcolor='rgba(255, 249, 219, 0.85)', borderpad=2,
        showarrow=False, xshift=8, yshift=med_yshift, xanchor='left'
    )

# Zero line
fig_avg.add_hline(y=0, line_dash='dot', line_color='black', line_width=1)

fig_avg.update_layout(
    template=chart_cfg['template'],
    width=chart_cfg['width'],
    height=chart_cfg['height'],
    margin=dict(t=60, b=50, l=60, r=30),
    font=dict(size=chart_cfg['font_size'] - 6),
    yaxis_title="Change in overall balance<br>(percentage points of GDP)",
    xaxis_title="",
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="center", x=0.5,
        font=dict(size=chart_cfg['font_size'] - 6)
    ),
    xaxis=dict(
        tickvals=[0, 1, 2],
        ticktext=cat_labels
    )
)

fig_avg.update_xaxes(
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
)

fig_avg.update_yaxes(
    showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
)

avg_path = output_dir / "food_energy_boom_avg_deficit_change"
pio.write_image(fig_avg, f"{avg_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_avg, f"{avg_path}.svg", format='svg', engine='kaleido', scale=2)
fig_avg.write_html(f"{avg_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Average deficit change chart saved to {avg_path}.png")

##### Energy Index Chart #####
import requests
from io import StringIO

# Fetch Brent oil price from FRED
brent_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU&cosd=1991-01-01&coed=2026-12-31&fq=Annual&fam=avg"
try:
    brent_response = requests.get(brent_url, timeout=10)
    brent_df = pd.read_csv(StringIO(brent_response.text))
    brent_df['year'] = pd.to_datetime(brent_df['observation_date']).dt.year
    brent_df = brent_df.rename(columns={'DCOILBRENTEU': 'brent_price'})
    has_brent = True
    print(f"Fetched Brent oil price from FRED ({len(brent_df)} years)")
except Exception as e:
    print(f"Could not fetch Brent price: {e}")
    has_brent = False

fig_energy = make_subplots(specs=[[{"secondary_y": True}]])

# Energy index (left axis)
fig_energy.add_trace(go.Scatter(
    x=pcps['year'],
    y=pcps['energy_index'],
    mode='lines',
    name='IMF energy index',
    line=dict(color=em_color, width=2)
), secondary_y=False)

# Brent oil price (right axis)
if has_brent:
    fig_energy.add_trace(go.Scatter(
        x=brent_df['year'],
        y=brent_df['brent_price'],
        mode='lines',
        name='Brent oil price',
        line=dict(color=lic_color, width=2, dash='dot')
    ), secondary_y=True)

# Shade full boom periods and show price change from start to end
for start_year, end_year in energy_boom_periods:
    # Get index values at start and end
    idx_start = pcps[pcps['year'] == start_year]['energy_index'].values
    idx_end = pcps[pcps['year'] == end_year]['energy_index'].values

    # Shaded rectangle for boom period
    fig_energy.add_vrect(
        x0=start_year, x1=end_year,
        fillcolor="rgba(255, 160, 0, 0.15)",
        line=dict(color="rgba(255, 160, 0, 0.5)", width=1.5, dash="dash")
    )

    # Add annotation with price change
    if len(idx_start) > 0 and len(idx_end) > 0:
        pct_chg = (idx_end[0] - idx_start[0]) / idx_start[0] * 100
        mid_year = (start_year + end_year) / 2
        mid_y = (idx_start[0] + idx_end[0]) / 2
        sign = "+" if pct_chg >= 0 else ""
        fig_energy.add_annotation(
            x=mid_year, y=mid_y,
            text=f"{sign}{pct_chg:.0f}%",
            font=dict(size=10, color="rgba(255, 160, 0, 0.9)"),
            showarrow=False,
            bgcolor="rgba(255,255,255,0.8)"
        )

fig_energy.update_layout(
    template=chart_cfg['template'],
    width=chart_cfg['width'],
    height=chart_cfg['height'],
    margin=dict(t=40, b=50, l=50, r=50),
    font=dict(size=chart_cfg['font_size'] - 6),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="center", x=0.5,
        font=dict(size=chart_cfg['font_size'] - 6)
    )
)

fig_energy.update_xaxes(
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
)

# Left y-axis (energy index)
fig_energy.update_yaxes(
    title_text="Index (2016 = 100)",
    showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    secondary_y=False
)

# Right y-axis (Brent price)
fig_energy.update_yaxes(
    title_text="USD per barrel",
    showgrid=False,
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    secondary_y=True
)

energy_save_path = output_dir / "energy_index"
pio.write_image(fig_energy, f"{energy_save_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_energy, f"{energy_save_path}.svg", format='svg', engine='kaleido', scale=2)
fig_energy.write_html(f"{energy_save_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Energy index chart saved to {energy_save_path}.png")

##### Food Index Chart #####
fig_food = go.Figure()

fig_food.add_trace(go.Scatter(
    x=pcps['year'],
    y=pcps['food_index'],
    mode='lines',
    name='Food price index',
    line=dict(color=ae_color, width=2)
))

# Shade full boom periods and show price change from start to end
for start_year, end_year in food_boom_periods:
    # Get index values at start and end
    idx_start = pcps[pcps['year'] == start_year]['food_index'].values
    idx_end = pcps[pcps['year'] == end_year]['food_index'].values

    # Shaded rectangle for boom period
    fig_food.add_vrect(
        x0=start_year, x1=end_year,
        fillcolor="rgba(70, 130, 180, 0.15)",
        line=dict(color="rgba(70, 130, 180, 0.5)", width=1.5, dash="dash")
    )

    # Add annotation with price change
    if len(idx_start) > 0 and len(idx_end) > 0:
        pct_chg = (idx_end[0] - idx_start[0]) / idx_start[0] * 100
        mid_year = (start_year + end_year) / 2
        mid_y = (idx_start[0] + idx_end[0]) / 2
        sign = "+" if pct_chg >= 0 else ""
        fig_food.add_annotation(
            x=mid_year, y=mid_y,
            text=f"{sign}{pct_chg:.0f}%",
            font=dict(size=10, color="rgba(70, 130, 180, 0.9)"),
            showarrow=False,
            bgcolor="rgba(255,255,255,0.8)"
        )

fig_food.update_layout(
    template=chart_cfg['template'],
    width=chart_cfg['width'],
    height=chart_cfg['height'],
    margin=dict(t=40, b=50, l=50, r=30),
    font=dict(size=chart_cfg['font_size'] - 6),
    showlegend=False,
    yaxis_title="Index (2016 = 100)"
)

fig_food.update_xaxes(
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
)

fig_food.update_yaxes(
    showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
)

food_save_path = output_dir / "food_index"
pio.write_image(fig_food, f"{food_save_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_food, f"{food_save_path}.svg", format='svg', engine='kaleido', scale=2)
fig_food.write_html(f"{food_save_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Food index chart saved to {food_save_path}.png")

##### Oil-Dependent Countries Fiscal Balance vs Energy Index #####
# Countries: Saudi Arabia, Kuwait, Iraq, Angola, Nigeria
oil_dependent_countries = {
    'SAU': {'name': 'Saudi Arabia', 'color': '#1A237E'},  # Dark blue
    'KWT': {'name': 'Kuwait', 'color': '#4682B4'},        # Steel blue
    'IRQ': {'name': 'Iraq', 'color': '#E65100'},          # Crimson
    'AGO': {'name': 'Angola', 'color': '#F57F17'},        # Amber
    'NGA': {'name': 'Nigeria', 'color': '#00897B'}        # Green
}

# Load full WEO data for these countries
weo_full = pd.read_stata(weo_path)
oil_dep_isocodes = list(oil_dependent_countries.keys())
oil_dep_fiscal = weo_full[weo_full['isocode'].isin(oil_dep_isocodes)][['isocode', 'year', 'ggxcnl_gdp']].copy()
oil_dep_fiscal = oil_dep_fiscal[oil_dep_fiscal['year'].between(1991, 2025)]
# Remove Iraq 2004 outlier
oil_dep_fiscal = oil_dep_fiscal[~((oil_dep_fiscal['isocode'] == 'IRQ') & (oil_dep_fiscal['year'] == 2004))]
# Remove Kuwait 1991-1992 outliers (Gulf War)
oil_dep_fiscal = oil_dep_fiscal[~((oil_dep_fiscal['isocode'] == 'KWT') & (oil_dep_fiscal['year'].isin([1991, 1992])))]

fig_oil_dep = make_subplots(specs=[[{"secondary_y": True}]])

# Energy index on left axis
fig_oil_dep.add_trace(go.Scatter(
    x=pcps['year'],
    y=pcps['energy_index'],
    mode='lines',
    name='Energy index',
    line=dict(color='#9E9E9E', width=2, dash='dot')
), secondary_y=False)

# Plot overall balance for each country (right axis)
for iso, props in oil_dependent_countries.items():
    country_data = oil_dep_fiscal[oil_dep_fiscal['isocode'] == iso].sort_values('year')
    fig_oil_dep.add_trace(go.Scatter(
        x=country_data['year'],
        y=country_data['ggxcnl_gdp'],
        mode='lines',
        name=props['name'],
        line=dict(color=props['color'], width=2)
    ), secondary_y=True)

# Shade full boom periods
for start_year, end_year in energy_boom_periods:
    fig_oil_dep.add_vrect(
        x0=start_year, x1=end_year,
        fillcolor="rgba(255, 160, 0, 0.15)",
        line=dict(color="rgba(255, 160, 0, 0.5)", width=1.5, dash="dash")
    )

fig_oil_dep.update_layout(
    template=chart_cfg['template'],
    width=chart_cfg['width'],
    height=chart_cfg['height'],
    margin=dict(t=40, b=50, l=50, r=50),
    font=dict(size=chart_cfg['font_size'] - 6),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="center", x=0.5,
        font=dict(size=chart_cfg['font_size'] - 6)
    )
)

fig_oil_dep.update_xaxes(
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
)

# Left y-axis (energy index)
fig_oil_dep.update_yaxes(
    title_text="Energy index<br>(2016 = 100)",
    showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    secondary_y=False
)

# Right y-axis (overall balance)
fig_oil_dep.update_yaxes(
    title_text="Overall balance<br>(percent of GDP)",
    showgrid=False,
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    zeroline=True, zerolinecolor='black', zerolinewidth=1,
    secondary_y=True
)

oil_dep_save_path = output_dir / "energy_oil_dependent_balance"
pio.write_image(fig_oil_dep, f"{oil_dep_save_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_oil_dep, f"{oil_dep_save_path}.svg", format='svg', engine='kaleido', scale=2)
fig_oil_dep.write_html(f"{oil_dep_save_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Oil-dependent countries chart saved to {oil_dep_save_path}.png")

##### Energy Importers Fiscal Balance vs Energy Index #####
# Countries: Pakistan, Egypt, Jordan, Lebanon, Sri Lanka
energy_importer_countries = {
    'PAK': {'name': 'Pakistan', 'color': '#1A237E'},    # Dark blue
    'EGY': {'name': 'Egypt', 'color': '#4682B4'},       # Steel blue
    'JOR': {'name': 'Jordan', 'color': '#E65100'},      # Crimson
    'LKA': {'name': 'Sri Lanka', 'color': '#00897B'}    # Green
}

energy_imp_isocodes = list(energy_importer_countries.keys())
energy_imp_fiscal = weo_full[weo_full['isocode'].isin(energy_imp_isocodes)][['isocode', 'year', 'ggxcnl_gdp']].copy()
energy_imp_fiscal = energy_imp_fiscal[energy_imp_fiscal['year'].between(1991, 2025)]

fig_energy_imp = make_subplots(specs=[[{"secondary_y": True}]])

# Energy index on left axis
fig_energy_imp.add_trace(go.Scatter(
    x=pcps['year'],
    y=pcps['energy_index'],
    mode='lines',
    name='Energy index',
    line=dict(color='#9E9E9E', width=2, dash='dot')
), secondary_y=False)

# Plot overall balance for each country (right axis)
for iso, props in energy_importer_countries.items():
    country_data = energy_imp_fiscal[energy_imp_fiscal['isocode'] == iso].sort_values('year')
    fig_energy_imp.add_trace(go.Scatter(
        x=country_data['year'],
        y=country_data['ggxcnl_gdp'],
        mode='lines',
        name=props['name'],
        line=dict(color=props['color'], width=2)
    ), secondary_y=True)

# Shade full boom periods
for start_year, end_year in energy_boom_periods:
    fig_energy_imp.add_vrect(
        x0=start_year, x1=end_year,
        fillcolor="rgba(255, 160, 0, 0.15)",
        line=dict(color="rgba(255, 160, 0, 0.5)", width=1.5, dash="dash")
    )

fig_energy_imp.update_layout(
    template=chart_cfg['template'],
    width=chart_cfg['width'],
    height=chart_cfg['height'],
    margin=dict(t=40, b=50, l=50, r=50),
    font=dict(size=chart_cfg['font_size'] - 6),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="center", x=0.5,
        font=dict(size=chart_cfg['font_size'] - 6)
    )
)

fig_energy_imp.update_xaxes(
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
)

# Left y-axis (energy index)
fig_energy_imp.update_yaxes(
    title_text="Energy index<br>(2016 = 100)",
    showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    secondary_y=False
)

# Right y-axis (overall balance)
fig_energy_imp.update_yaxes(
    title_text="Overall balance<br>(percent of GDP)",
    showgrid=False,
    linecolor=chart_cfg['axes']['linecolor'],
    linewidth=chart_cfg['axes'].get('linewidth', 1.5),
    ticks=chart_cfg['axes']['ticks'],
    tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    zeroline=True, zerolinecolor='black', zerolinewidth=1,
    secondary_y=True
)

energy_imp_save_path = output_dir / "energy_importer_balance"
pio.write_image(fig_energy_imp, f"{energy_imp_save_path}.png", format='png', engine='kaleido', scale=2)
pio.write_image(fig_energy_imp, f"{energy_imp_save_path}.svg", format='svg', engine='kaleido', scale=2)
fig_energy_imp.write_html(f"{energy_imp_save_path}.html", auto_open=auto_open, include_plotlyjs='cdn')
print(f"Energy importer countries chart saved to {energy_imp_save_path}.png")

print("Food/Energy Boom Analysis complete.")