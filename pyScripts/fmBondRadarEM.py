import pandas as pd
import pyreadr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
import warnings
import webbrowser
import json

# Silence aggregation warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Constants & Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_PATH = os.path.join(PROJECT_ROOT, "data/fmData/Bond_radar_db_small_2026-02-09.rds")
DICT_PATH = os.path.join(PROJECT_ROOT, "+environment/csvFiles/countryTable.csv")
OUT_DIR = os.path.join(PROJECT_ROOT, "docu")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "chartConfig.json")

os.makedirs(OUT_DIR, exist_ok=True)

with open(CONFIG_PATH, "r") as f:
    cfg = json.load(f)["styling"]

RATING_ORDER = ['AA-A', 'BBB', 'BB', 'B', 'NR']
RATING_COLORS = {"AA-A": "#4A148C", "BBB": "#00897B", "BB": "#E65100", "B": "#AD1457", "NR": "#757575"}
REGION_MAP = {"AFR": "Africa", "SSA": "Africa", "LAC": "Latin America", "APD": "Asia", "MENA": "Middle East", "EUR": "Europe", "CIS": "Europe", "NA": "North America", "WHD": "Latin America"}

# 1. Data Loading & Cleaning
def clean_data():
    df = pyreadr.read_r(DATA_PATH)[None]
    df = df.sort_values(by=['ifscode', 'maturity']).reset_index(drop=True)
    
    # 1.1 Classification from Dictionary
    df_dict = pd.read_csv(DICT_PATH)
    iso_to_class = dict(zip(df_dict['iso3c'], df_dict['devClass']))
    
    # Replace/Remove old classification columns
    df['Group'] = df['iso'].map(iso_to_class)
    df = df.drop(columns=['ae', 'em', 'lic'], errors='ignore')
    
    # Keep only Emerging Market economies (exclude Advanced and Low-Income)
    df = df[df['Group'] == 'Emerging'].reset_index(drop=True)
    
    # Numeric conversions
    df['yield_num'] = pd.to_numeric(df['yield'].astype(str).str.replace("%", "", regex=False), errors='coerce') / 100.0
    df['coupon_num'] = pd.to_numeric(df['coupon'], errors='coerce') / 100.0
    df['yield2_num'] = df['yield_num'].fillna(df['coupon_num'])
    
    # Categorical cleaning
    df['Region_clean'] = df['Region'].map(REGION_MAP).fillna("Other")
    df['s_p_clean'] = df['s_p'].str.replace(r'[+-]', '', regex=True).replace('AAA', 'AA').fillna('NR')
    df['s_p_clean'] = df['s_p_clean'].replace(['AA', 'A'], 'AA-A')
    
    for col in ['issuance_year', 'maturity_year']:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
        
    df.to_csv(os.path.join(PROJECT_ROOT, "data/fmBondradar/Bond_radar_db_processed.csv"), index=False, float_format='%.4f')
    return df

df = clean_data()

# 2. Stats & Plotting Helpers
def get_weighted_stats(data, group_col, val_col, weight_col='usd_equivalent'):
    def wm(x):
        w = data.loc[x.index, weight_col]
        mask = x.notna() & w.notna()
        return np.average(x[mask], weights=w[mask]) if mask.any() else np.nan

    return data.groupby(group_col)[val_col].agg([
        ('p25', lambda x: x.quantile(0.25)),
        ('median', 'median'),
        ('p75', lambda x: x.quantile(0.75)),
        ('wmean', wm)
    ]).reset_index()

def add_stats_traces(fig, stats, x_col, color, name, is_global=False):
    # IQR Band
    fig.add_trace(go.Scatter(
        x=pd.concat([stats[x_col], stats[x_col][::-1]]),
        y=pd.concat([stats['p75'], stats['p25'][::-1]]),
        fill='toself', fillcolor=color, line=dict(color='rgba(255,255,255,0)'),
        opacity=0.3 if is_global else cfg['combined_charts']['iqr_opacity'],
        name=f'IQR {name}', showlegend=not is_global
    ))
    # Median
    fig.add_trace(go.Scatter(
        x=stats[x_col], y=stats['median'], mode='lines',
        line=dict(color='black' if is_global else color, width=2, dash='dot'),
        name=f'Median {name}'
    ))
    # Weighted mean
    fig.add_trace(go.Scatter(
        x=stats[x_col], y=stats['wmean'], mode='lines+markers',
        line=dict(color='black' if is_global else color, width=4),
        marker=dict(size=12 if is_global else 10, symbol='diamond'),
        name=f'W-Avg {name}'
    ))

def apply_common_layout(fig, y_range=None, x_range=None, target_years=None):
    layout = {
        "template": cfg['template'], "width": cfg['width'], "height": cfg['height'],
        "margin": cfg['margins'], "font": {"size": cfg['font_size']},
        "legend": {**{k: v for k, v in cfg['legend'].items() if k != 'font_size'}, "font": {"size": cfg['legend']['font_size']}, "title": None, "traceorder": 'normal'},
        "xaxis": {
            "showgrid": cfg['axes']['showgrid'], "gridcolor": cfg['axes'].get('gridcolor'), "gridwidth": cfg['axes'].get('gridwidth'),
            "linecolor": cfg['axes']['linecolor'], "linewidth": cfg['axes'].get('linewidth'), "mirror": cfg['axes']['mirror'], 
            "ticks": cfg['axes']['ticks'], "tickfont": {"size": cfg['axes']['tickfont_size']}, "range": x_range or cfg['combined_charts']['x_range']
        },
        "yaxis": {
            "showgrid": cfg['axes']['showgrid'], "gridcolor": cfg['axes'].get('gridcolor'), "gridwidth": cfg['axes'].get('gridwidth'),
            "linecolor": cfg['axes']['linecolor'], "linewidth": cfg['axes'].get('linewidth'), "mirror": cfg['axes']['mirror'], 
            "ticks": cfg['axes']['ticks'], "tickfont": {"size": cfg['axes']['tickfont_size']}, "range": y_range,
            "zeroline": cfg['axes'].get('zeroline', True), "zerolinecolor": cfg['axes']['linecolor'], "zerolinewidth": cfg['axes'].get('zerolinewidth')
        },
        "title": None, "yaxis_title": None
    }
    
    years = target_years or cfg['combined_charts']['target_years']
    layout["xaxis"].update({"tickmode": 'array', "tickvals": years, "ticktext": [str(y) if i == 0 else str(y % 100) for i, y in enumerate(years)]})
    fig.update_layout(**layout)

def save_fig(fig, filename):
    try:
        from fiscal_common import get_chart_dims_px
        _w, _h = get_chart_dims_px(f"{filename}.png")
        fig.update_layout(width=_w, height=_h)
    except KeyError:
        pass
    fig.write_image(os.path.join(OUT_DIR, f"{filename}.png"), scale=2)
    fig.write_image(os.path.join(OUT_DIR, f"{filename}.svg"), scale=2)
    html_path = os.path.join(OUT_DIR, f"{filename}.html")
    fig.write_html(html_path, include_plotlyjs='cdn')
    webbrowser.open(f"file://{os.path.abspath(html_path)}")

def create_metadata(filename, title, units, sources, notes):
    """Create a text file with chart metadata"""
    content = [
        f"CHART METADATA: {filename.upper()}",
        "=" * 50,
        f"TITLE: {title}",
        f"UNITS: {units}",
        f"SOURCES: {sources}",
        "",
        f"NOTE: {notes}",
        "=" * 50
    ]
    with open(os.path.join(OUT_DIR, f"{filename}.txt"), "w") as f:
        f.write("\n".join(content))

# 3. Main Plotting Logic
def plot_combined_volumes(configs, filename, y_range=None):
    fig = make_subplots(
        rows=2, cols=1, 
        vertical_spacing=0.12,
        subplot_titles=("Issuance", "Redemptions")
    )
    
    csv_panels = []
    for row, (df_agg, year_col, val_col) in enumerate(configs, 1):
        pivot = df_agg.pivot(index=year_col, columns='s_p_clean', values=val_col).fillna(0) / 1e3
        for rating in [r for r in RATING_ORDER if r in pivot.columns]:
            fig.add_trace(go.Bar(
                x=pivot.index, y=pivot[rating], name=rating,
                marker_color=RATING_COLORS.get(rating),
                showlegend=(row == 1)
            ), row=row, col=1)

        # Collect pivot for combined CSV
        panel_label = "Issuance" if "issu" in year_col else "Redemptions"
        pivot_csv = pivot.copy()
        pivot_csv.index.name = 'year'
        pivot_csv = pivot_csv.add_prefix(f"{panel_label}: ")
        csv_panels.append(pivot_csv)

    # Export combined CSV (one file for both panels, only charted years 2015-2030)
    csv_combined = csv_panels[0].reset_index().merge(csv_panels[1].reset_index(), on='year', how='outer').sort_values('year')
    csv_combined = csv_combined[(csv_combined['year'] >= 2015) & (csv_combined['year'] <= 2030)]

    # Poland total issuance (right-axis line on the 10x10 chart)
    pol_csv = (df_em[df_em['iso'] == 'POL'].groupby('issuance_year')['usd_equivalent'].sum() / 1e3).rename('Poland total issuance')
    csv_combined = csv_combined.merge(pol_csv, left_on='year', right_index=True, how='left')
    csv_combined.to_csv(os.path.join(OUT_DIR, f"{filename}_10x10.csv"), index=False, float_format='%.2f')

    fig.update_layout(barmode='stack')
    apply_common_layout(fig, y_range=y_range)
    
    # Customize subplot titles (annotations)
    fig.update_annotations(
        font=dict(size=cfg['font_size'] * 1.1),
        yshift=-20 # Shift titles lower
    )

    # Ensure subplot axes share configuration
    fig.update_xaxes(
        showgrid=cfg['axes']['showgrid'], linecolor=cfg['axes']['linecolor'], 
        ticks=cfg['axes']['ticks'], tickfont={"size": cfg['font_size']},
        tickmode='array', tickvals=cfg['combined_charts']['target_years'],
        ticktext=[str(y) if i == 0 else str(y % 100) for i, y in enumerate(cfg['combined_charts']['target_years'])],
        range=cfg['combined_charts']['x_range']
    )
    # Hide labels for the top chart
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    
    fig.update_yaxes(
        showgrid=cfg['axes']['showgrid'], linecolor=cfg['axes']['linecolor'], 
        ticks=cfg['axes']['ticks'], tickfont={"size": cfg['font_size']},
        range=y_range
    )
    # Main chart not in chartTable; only _10x10 variant is exported
    if filename == "1_vol_combined_em":
        # Create separate 10x10 chart with just Issuance panel
        fig_small = go.Figure()
        df_agg, year_col, val_col = configs[0]  # First config is Issuance
        pivot = df_agg.pivot(index=year_col, columns='s_p_clean', values=val_col).fillna(0) / 1e3

        # Highlight years 2017 and 2025 with wider bars
        highlight_years = [2017, 2025]
        other_years = [y for y in pivot.index if y not in highlight_years]

        # Add bars for non-highlighted years (narrower)
        for idx, rating in enumerate([r for r in RATING_ORDER if r in pivot.columns]):
            pivot_other = pivot.loc[pivot.index.isin(other_years)]
            fig_small.add_trace(go.Bar(
                x=pivot_other.index, y=pivot_other[rating], name=rating,
                marker_color=RATING_COLORS.get(rating),
                width=0.4,
                showlegend=True,
                legendrank=idx + 1
            ))

        # Add bars for highlighted years (wider)
        for rating in [r for r in RATING_ORDER if r in pivot.columns]:
            pivot_highlight = pivot.loc[pivot.index.isin(highlight_years)]
            fig_small.add_trace(go.Bar(
                x=pivot_highlight.index, y=pivot_highlight[rating], name=rating,
                marker_color=RATING_COLORS.get(rating),
                width=1.0,
                showlegend=False  # Don't duplicate legend entries
            ))

        # Poland total issuance as a line on a secondary (right) axis
        # Reindex to charted years; 2021 has no international issuance -> plot as 0
        pol_years = [y for y in pivot.index if 2015 <= y <= 2025]
        pol_series = (
            df_em[df_em['iso'] == 'POL']
            .groupby('issuance_year')['usd_equivalent'].sum() / 1e3
        ).reindex(pol_years).fillna(0)
        pol_color = "#1E88E5"
        fig_small.add_trace(go.Scatter(
            x=pol_series.index, y=pol_series.values,
            mode='lines+markers', name='Poland (right axis)',
            line=dict(color=pol_color, width=cfg['line_widths']['thick']),
            marker=dict(size=7, symbol='circle', color=pol_color),
            connectgaps=True, yaxis='y2'
        ))
        pol_max = float(pol_series.max())

        fig_small.update_layout(
            template=cfg['template'],
            barmode='stack',
            width=378, height=378,
            margin=dict(t=40, b=40, l=50, r=20),
            font=dict(size=cfg['axes']['tickfont_size']),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="center", x=0.5,
                font=dict(size=cfg['legend']['font_size']),
                traceorder='normal'
            ),
            xaxis=dict(
                showgrid=cfg['axes']['showgrid'],
                linecolor=cfg['axes']['linecolor'],
                ticks=cfg['axes']['ticks'],
                tickfont=dict(size=cfg['axes']['tickfont_size']),
                tickmode='array',
                tickvals=[2015, 2017, 2019, 2021, 2023, 2025],
                ticktext=["<span style='font-size:9px'>2015</span>", '2017', "<span style='font-size:9px'>2019</span>", "<span style='font-size:9px'>2021</span>", "<span style='font-size:9px'>2023</span>", '2025'],
                range=[2014.5, 2025.5]
            ),
            yaxis=dict(
                showgrid=cfg['axes']['showgrid'],
                linecolor=cfg['axes']['linecolor'],
                ticks=cfg['axes']['ticks'],
                tickfont=dict(size=cfg['axes']['tickfont_size']),
                range=y_range
            ),
            yaxis2=dict(
                overlaying='y', side='right',
                showgrid=False,
                linecolor=pol_color,
                tickcolor=pol_color,
                tickfont=dict(size=cfg['axes']['tickfont_size'], color=pol_color),
                ticks=cfg['axes']['ticks'],
                range=[0, pol_max * 1.15]
            )
        )

        save_fig(fig_small, f"{filename}_10x10")

def plot_combined_yields(df, filename):
    fig = go.Figure()
    all_y = []
    x_min, x_max = cfg['combined_charts']['x_range']
    
    for col, color, name in [('issuance_year', 'midnightblue', 'Issued'), ('maturity_year', 'deepskyblue', 'Maturing')]:
        stats = get_weighted_stats(df.dropna(subset=[col, 'yield2_num']), col, 'yield2_num')
        
        # Scale to Percent
        for c in ['p25', 'median', 'p75', 'wmean']: 
            stats[c] *= 100
        
        add_stats_traces(fig, stats, col, color, name)
        all_y.extend(stats.loc[stats[col].between(x_min, x_max), ['p25', 'p75', 'median', 'wmean']].values.flatten())

    y_range = [min(all_y)*0.95, max(all_y)*1.05] if all_y else None
    apply_common_layout(fig, y_range=y_range)
    save_fig(fig, filename)

def plot_maturity_by_rating(df, filename):
    fig = go.Figure()
    all_y = []
    x_range = [2014.5, 2025.5]
    
    # EMDE Traces
    stats_g = get_weighted_stats(df.dropna(subset=['issuance_year', 'maturity_years']), 'issuance_year', 'maturity_years')
    add_stats_traces(fig, stats_g, 'issuance_year', 'lightgrey', 'EMDE', is_global=True)
    all_y.extend(stats_g.loc[stats_g['issuance_year'].between(*x_range), ['p25', 'p75', 'median', 'wmean']].values.flatten())
    
    # Rating Traces (Average Only)
    for r in [r for r in RATING_ORDER if r != 'NR']:
        sub = df[df['s_p_clean'] == r].dropna(subset=['issuance_year', 'maturity_years'])
        if sub.empty: continue
        stats = get_weighted_stats(sub, 'issuance_year', 'maturity_years')
        fig.add_trace(go.Scatter(
            x=stats['issuance_year'], y=stats['wmean'], mode='lines+markers',
            line=dict(color=RATING_COLORS.get(r), width=5), marker=dict(size=6),
            opacity=0.6, name=f'Avg {r}'
        ))
        all_y.extend(stats.loc[stats['issuance_year'].between(*x_range), 'wmean'].values.flatten())

    y_range = [min(all_y)*0.95, max(all_y)*1.05] if all_y else None
    apply_common_layout(fig, y_range=y_range, x_range=x_range, target_years=[2015, 2020, 2025])
    save_fig(fig, filename)

def generate_issuance_summary_table(df):
    """Generate summary statistics for issuance by rating class in 2017 and 2025"""
    target_years = [2017, 2025]
    target_ratings = ['AA-A', 'BBB', 'BB', 'B']
    
    # Filter data
    sub = df[df['issuance_year'].isin(target_years) & df['s_p_clean'].isin(target_ratings)].copy()
    
    # Calculate statistics
    def weighted_avg(group, val_col):
        weights = group['usd_equivalent']
        mask = group[val_col].notna() & weights.notna()
        if not mask.any() or weights[mask].sum() == 0:
            return np.nan
        return np.average(group.loc[mask, val_col], weights=weights[mask])

    summary_list = []
    for (year, rating), group in sub.groupby(['issuance_year', 's_p_clean']):
        summary_list.append({
            'issuance_year': year,
            's_p_clean': rating,
            'avg_size': group['usd_equivalent'].mean(),
            'total_usd': group['usd_equivalent'].sum() / 1e3, # To billions
            'yield2_num': weighted_avg(group, 'yield2_num') * 100,
            'maturity_years': weighted_avg(group, 'maturity_years'),
            'num_countries': group['iso'].nunique()
        })
    summary = pd.DataFrame(summary_list)
    
    # Pivot for table display
    table_data = []
    header = f"{'Rating':<10} | {'Year':<6} | {'Total ($B)':<10} | {'Avg Size ($M)':<15} | {'Avg Yield (%)':<15} | {'Avg Dur (Y)':<12} | {'Num Countries':<13}"
    sep = "-" * len(header)
    table_data.append("SUMMARY STATISTICS: ISSUANCE BY RATING CLASS")
    table_data.append(sep)
    table_data.append(header)
    table_data.append(sep)
    
    for rating in target_ratings:
        r_stats = {}
        for year in target_years:
            row = summary[(summary['issuance_year'] == year) & (summary['s_p_clean'] == rating)]
            if not row.empty:
                r = row.iloc[0]
                r_stats[year] = r
                table_data.append(f"{rating:<10} | {year:<6} | {r['total_usd']:>10.1f} | {r['avg_size']:>15.2f} | {r['yield2_num']:>15.2f} | {r['maturity_years']:>12.2f} | {r['num_countries']:>13}")
            else:
                table_data.append(f"{rating:<10} | {year:<6} | {'N/A':>10} | {'N/A':>15} | {'N/A':>15} | {'N/A':>12} | {'N/A':>13}")
        
        # Add Difference row
        if 2017 in r_stats and 2025 in r_stats:
            diff_total = r_stats[2025]['total_usd'] - r_stats[2017]['total_usd']
            diff_size = r_stats[2025]['avg_size'] - r_stats[2017]['avg_size']
            diff_yield = r_stats[2025]['yield2_num'] - r_stats[2017]['yield2_num']
            diff_dur = r_stats[2025]['maturity_years'] - r_stats[2017]['maturity_years']
            diff_countries = r_stats[2025]['num_countries'] - r_stats[2017]['num_countries']
            table_data.append(f"{'':<10} | {'Diff':<6} | {diff_total:>10.1f} | {diff_size:>15.2f} | {diff_yield:>15.2f} | {diff_dur:>12.2f} | {diff_countries:>13}")
        
        table_data.append(sep)
        
    # Save to file
    out_path = os.path.join(OUT_DIR, "issuance_summary_stats.txt")
    with open(out_path, "w") as f:
        f.write("\n".join(table_data))
    print(f"Summary statistics saved to {out_path}")
    return summary

def plot_stats_comparison(summary_df):
    """Create a 4-panel comparison chart matching standard project dimensions"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Total Issuance (Billions of dollars)", "Weighted Average Yield (Percent)",
                        "Weighted Average Duration (Years)", "Number of Countries"),
        vertical_spacing=0.18,
        horizontal_spacing=0.12
    )
    
    metrics = [
        ('total_usd', 1, 1),
        ('yield2_num', 1, 2),
        ('maturity_years', 2, 1),
        ('num_countries', 2, 2)
    ]
    
    rating_classes = ['AA-A', 'BBB', 'BB', 'B']
    line_w = cfg['line_widths']['thick'] * 1.5
    
    for rating in rating_classes:
        sub = summary_df[summary_df['s_p_clean'] == rating].sort_values('issuance_year')
        if sub.empty: continue
        
        color = RATING_COLORS.get(rating, 'black')
        opacity = 1.0 if rating == 'B' else 0.35
        
        # Convert hex to rgba for opacity
        h = color.lstrip('#')
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        rgba_color = f'rgba({rgb[0]},{rgb[1]},{rgb[2]},{opacity})'
        
        for metric, row, col in metrics:
            fig.add_trace(go.Scatter(
                x=sub['issuance_year'],
                y=sub[metric],
                name=rating,
                mode='lines+markers',
                line=dict(color=rgba_color, width=line_w),
                marker=dict(size=12, symbol='circle', color=rgba_color),
                showlegend=(row == 1 and col == 1)
            ), row=row, col=1 if col == 1 else 2)

    # Apply styling
    fig.update_layout(
        template=cfg['template'],
        width=cfg['width'], height=cfg['height'],
        margin={**cfg['margins'], "t": 60}, # Extra top margin for legend
        font={"size": cfg['font_size'] - 4}
    )
    
    # Customize subplot titles
    fig.update_annotations(font_size=cfg['font_size'] - 4)
    
    # Global axis formatting
    fig.update_xaxes(
        showline=True, linecolor='black', ticks='inside',
        tickmode='array', tickvals=[2017, 2025], ticktext=['2017', '2025'],
        range=[2016.3, 2025.7], tickfont_size=cfg['axes']['tickfont_size']
    )
    fig.update_yaxes(
        showline=True, linecolor='black', ticks='inside', 
        showgrid=True, gridcolor='rgba(0,0,0,0.1)',
        tickfont_size=cfg['axes']['tickfont_size']
    )
    
    # Legend further up
    fig.update_layout(legend=dict(
        orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5,
        font=dict(size=cfg['font_size'] - 6)
    ))
    
    save_fig(fig, "4_issuance_comp_stats")

    # CSV export: plotted comparison stats
    csv_rows = []
    for rating in rating_classes:
        sub = summary_df[summary_df['s_p_clean'] == rating].sort_values('issuance_year')
        for _, row in sub.iterrows():
            csv_rows.append({
                'Rating': rating,
                'Year': int(row['issuance_year']),
                'Total Issuance (Billions of dollars)': round(row['total_usd'], 2),
                'Weighted Average Yield (Percent)': round(row['yield2_num'], 2),
                'Weighted Average Duration (Years)': round(row['maturity_years'], 2),
                'Number of Countries': int(row['num_countries'])
            })
    pd.DataFrame(csv_rows).to_csv(os.path.join(OUT_DIR, "4_issuance_comp_stats.csv"), index=False)

    # Metadata for Comparison Stats
    create_metadata(
        "4_issuance_comp_stats",
        "Emerging Market and Developing Economies: Sovereign Bond Issuance Characteristics (2017 vs 2025)",
        "Billions of U.S. dollars (Total); Percent (Yield); Years (Duration); Number (Countries)",
        "Bond Radar; and IMF staff calculations.",
        "Lines connect 2017 and 2025 observations. B-rated category (Frontier/Developing) is highlighted. Yields and durations are weighted by issuance size. Excludes advanced and low-income economies."
    )

# 4. Execution
df_em = df.copy() # Now contains only Emerging and Low-Income countries

# Calculate common Y-axis for volume charts
vols = []
configs = []
for yc, fname, rr in [('issuance_year', "1_issue_em", (2005, 2025)), ('maturity_year', "1_maturity_em", (2005, 2040))]:
    raw_sub = df_em[df_em[yc].between(*rr)]
    agg = raw_sub.groupby([yc, 's_p_clean'])['usd_equivalent'].sum().reset_index()
    vols.append(agg.groupby(yc)['usd_equivalent'].sum().max())
    configs.append((agg, yc, 'usd_equivalent'))

common_y_range = [0, max(vols) * 1.1 / 1e3]
plot_combined_volumes(configs, "1_vol_combined_em", y_range=common_y_range)

print(f"Processing complete. Files saved to {OUT_DIR}")
