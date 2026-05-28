import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, smart_save_image, get_chart_dims_px

_LABEL_FONT_SIZE = load_chart_config()['styling']['legend']['font_size']

def get_data(file_path, start_year, end_year=None):
    """Load and filter data for a specific year or period average."""
    if end_year is None:
        end_year = start_year
        
    df = pd.read_stata(file_path)
    
    # Filter by year range
    mask = (df['year'] >= start_year) & (df['year'] <= end_year)
    df = df[mask].copy()
    
    # Separate aggregates and countries
    # Use ifscode < 9000 to get only individual countries (aggregates have ifscode >= 9000)
    countries = df[df['ifscode'] < 9000]
    global_agg = df[df['ifscode'] == 9999]
    
    # Average if period
    if start_year != end_year:
        # We need adjustment_needed_global_gdp
        cols = ['adjustment_needed_global_gdp', 'sfa_gdp', 'ngdpd']
        group_cols = ['ifscode', 'country', 'isocode']
        
        # Calculate mean for countries
        countries = countries.groupby(group_cols)[cols].mean().reset_index()
        
        # Calculate mean for global aggregate
        global_agg = global_agg.groupby(['ifscode'])[cols].mean().reset_index()
        
    return countries, global_agg

def apply_common_layout(fig, cfg, x_range=None):
    """Apply common styling from chartConfig.json to maintain project-wide consistency (Horizontal)."""
    layout = {
        "template": cfg['template'],
        "width": cfg['width'], 
        "height": cfg['height'],
        "margin": {**cfg['margins'], "l": 150, "r": 15}, # Space for horizontal labels
        "font": {"size": cfg['font_size']},
        "legend": {
            **{k: v for k, v in cfg['legend'].items() if k != 'font_size'},
            "y": 1.01,
            "font": {"size": cfg['legend']['font_size']},
            "title": None
        },
        "yaxis": {
            "showgrid": False,
            "linecolor": cfg['axes']['linecolor'], 
            "linewidth": cfg['axes'].get('linewidth'),
            "ticks": cfg['axes']['ticks'], 
            "tickfont": {"size": cfg['axes']['tickfont_size']},
            "mirror": cfg['axes']['mirror'],
            "autorange": "reversed"
        },
        "xaxis": {
            "showgrid": cfg['axes']['showgrid'], 
            "gridcolor": cfg['axes'].get('gridcolor'),
            "linecolor": cfg['axes']['linecolor'], 
            "linewidth": cfg['axes'].get('linewidth'),
            "ticks": cfg['axes']['ticks'], 
            "tickfont": {"size": cfg['axes']['tickfont_size']},
            "range": x_range, 
            "zeroline": True, 
            "zerolinecolor": cfg['axes']['linecolor']
        },
        "title": None,
        "xaxis_title": None,
        "yaxis_title": None
    }
    fig.update_layout(**layout)

def create_country_decomposition_chart(countries_p1, countries_p2, global_p1, global_p2):
    """Create a waterfall chart decomposing global change by country contributions."""
    
    # 1. Global Start and End Points (Fiscal Space = -Adjustment Needed)
    # We use adjustment_needed_global_gdp directly.
    # Note: The global aggregate row in the data contains the sum of country adjustment_needed_usd / global_gdp.
    # So its value should match the sum of countries.
    
    global_adj_p1 = global_p1['adjustment_needed_global_gdp'].iloc[0]
    global_adj_p2 = global_p2['adjustment_needed_global_gdp'].iloc[0]
    
    gap_p1 = global_adj_p1
    gap_p2 = global_adj_p2
    
    # 2. Calculate Change per Country
    # Merge P1 and P2
    merged = pd.merge(
        countries_p2[['ifscode', 'country', 'isocode', 'adjustment_needed_global_gdp']],
        countries_p1[['ifscode', 'adjustment_needed_global_gdp']],
        on='ifscode',
        suffixes=('_p2', '_p1'),
        how='inner'
    )
    
    # Calculate Change in Adjustment Needed (% Global GDP)
    # Contribution to Fiscal Gap = Change in Adjustment Needed
    merged['contribution'] = merged['adjustment_needed_global_gdp_p2'] - merged['adjustment_needed_global_gdp_p1']
    
    # 3. Identify Top Contributors
    # Sort by absolute contribution to find the biggest movers
    merged['abs_contribution'] = merged['contribution'].abs()
    merged = merged.sort_values('abs_contribution', ascending=False)
    
    # Select Top N countries
    top_n = 10
    top_contributors = merged.head(top_n).copy()
    
    # Calculate "Others"
    total_change = gap_p2 - gap_p1
    top_sum = top_contributors['contribution'].sum()
    others_contribution = total_change - top_sum
    
    # Prepare Waterfall Data
    # Start
    y_labels = ["2014–19 fiscal gap"]
    x_values = [gap_p1]
    measure = ["absolute"]
    text = [f"{gap_p1:.2f}"]
    
    # Countries
    for _, row in top_contributors.iterrows():
        y_labels.append(row['isocode'])
        x_values.append(row['contribution'])
        measure.append("relative")
        text.append(f"{row['contribution']:+.2f}")
        
    # Others
    y_labels.append("Others")
    x_values.append(others_contribution)
    measure.append("relative")
    text.append(f"{others_contribution:+.2f}")
    
    # End
    y_labels.append("2024–29 fiscal gap")
    x_values.append(gap_p2)
    measure.append("total")
    text.append(f"{gap_p2:.2f}")
    
    # Create Chart
    fig = go.Figure(go.Waterfall(
        name = "20", orientation = "h",
        measure = measure,
        y = y_labels,
        textposition = "outside",
        textfont = {"size": _LABEL_FONT_SIZE},
        text = text,
        x = x_values,
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#E65100"}}, 
        increasing = {"marker":{"color":"#00897B"}}, 
        totals = {"marker":{"color":"#6A1B9A"}}
    ))

    # Calculate x-axis range
    cumulative = [gap_p1]
    current = gap_p1
    for val in x_values[1:-1]:
        current += val
        cumulative.append(current)
    cumulative.append(gap_p2)
    
    x_min = min(cumulative)
    x_max = max(cumulative)
    padding = (x_max - x_min) * 0.65
    
    return fig, [x_min - padding, x_max + padding]

def create_country_decomposition_chart_with_sfa(countries_p1, countries_p2, global_p1, global_p2):
    """Create a country decomposition waterfall including SFA in the fiscal gap."""

    # Fiscal gap incl. SFA at global level (SFA subtracted: positive SFA worsens gap)
    gap_sfa_p1 = (global_p1['adjustment_needed_global_gdp'].iloc[0]
                  - global_p1['sfa_gdp'].iloc[0])
    gap_sfa_p2 = (global_p2['adjustment_needed_global_gdp'].iloc[0]
                  - global_p2['sfa_gdp'].iloc[0])

    # Compute SFA contribution to global GDP for each country
    global_gdp_p1 = countries_p1['ngdpd'].sum()
    global_gdp_p2 = countries_p2['ngdpd'].sum()
    countries_p1 = countries_p1.copy()
    countries_p2 = countries_p2.copy()
    countries_p1['sfa_global_gdp'] = countries_p1['sfa_gdp'] / 100 * countries_p1['ngdpd'] / global_gdp_p1 * 100
    countries_p2['sfa_global_gdp'] = countries_p2['sfa_gdp'] / 100 * countries_p2['ngdpd'] / global_gdp_p2 * 100

    # Fiscal gap incl. SFA per country (as % of global GDP, SFA subtracted)
    countries_p1['gap_incl_sfa'] = countries_p1['adjustment_needed_global_gdp'] - countries_p1['sfa_global_gdp']
    countries_p2['gap_incl_sfa'] = countries_p2['adjustment_needed_global_gdp'] - countries_p2['sfa_global_gdp']

    # Country contributions
    merged = pd.merge(
        countries_p2[['ifscode', 'country', 'isocode', 'gap_incl_sfa']],
        countries_p1[['ifscode', 'gap_incl_sfa']],
        on='ifscode', suffixes=('_p2', '_p1'), how='inner'
    )
    merged['contribution'] = merged['gap_incl_sfa_p2'] - merged['gap_incl_sfa_p1']
    merged['abs_contribution'] = merged['contribution'].abs()
    merged = merged.sort_values('abs_contribution', ascending=False)

    top_n = 10
    top_contributors = merged.head(top_n).copy()
    total_change = gap_sfa_p2 - gap_sfa_p1
    others_contribution = total_change - top_contributors['contribution'].sum()

    # Build waterfall
    y_labels = ["2014–19 fiscal gap<br>(incl. SFA)"]
    x_values = [gap_sfa_p1]
    measure = ["absolute"]
    text = [f"{gap_sfa_p1:.2f}"]

    for _, row in top_contributors.iterrows():
        y_labels.append(row['isocode'])
        x_values.append(row['contribution'])
        measure.append("relative")
        text.append(f"{row['contribution']:+.2f}")

    y_labels.append("Others")
    x_values.append(others_contribution)
    measure.append("relative")
    text.append(f"{others_contribution:+.2f}")

    y_labels.append("2024–29 fiscal gap<br>(incl. SFA)")
    x_values.append(gap_sfa_p2)
    measure.append("total")
    text.append(f"{gap_sfa_p2:.2f}")

    fig = go.Figure(go.Waterfall(
        name="20", orientation="h",
        measure=measure, y=y_labels, textposition="outside",
        text=text, x=x_values,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#E65100"}},
        increasing={"marker": {"color": "#00897B"}},
        totals={"marker": {"color": "#6A1B9A"}}
    ))

    cumulative = [gap_sfa_p1]
    current = gap_sfa_p1
    for val in x_values[1:-1]:
        current += val
        cumulative.append(current)
    cumulative.append(gap_sfa_p2)

    x_min = min(cumulative)
    x_max = max(cumulative)
    padding = (x_max - x_min) * 0.65

    return fig, [x_min - padding, x_max + padding]

def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)
    
    p1_def = {'start': 2014, 'end': 2019, 'label': '2014–2019'}
    p2_def = {'start': 2024, 'end': 2029, 'label': '2024–2029'}
    
    print(f"Generating country decomposition waterfall chart in {output_dir}...")
    
    # Load Data
    c_p1, g_p1 = get_data(data_path, p1_def['start'], p1_def['end'])
    c_p2, g_p2 = get_data(data_path, p2_def['start'], p2_def['end'])
    
    if g_p1.empty or g_p2.empty:
        print("Error: Global data missing.")
        return

    # Create Chart
    fig, x_range = create_country_decomposition_chart(c_p1, c_p2, g_p1, g_p2)
    apply_common_layout(fig, chart_cfg, x_range=x_range)
    base_name = "fiscalSpace_change_by_country_2014-19_vs_2024-29"

    # Apply CSV-driven dimensions (cm → px) with smaller fonts to match
    w_px, h_px = get_chart_dims_px(f"{base_name}.png")
    fig.update_layout(
        showlegend=False,
        width=w_px, height=h_px,
        margin=dict(l=120, r=10),
        font=dict(size=13),
        xaxis=dict(tickfont=dict(size=chart_cfg['axes']['tickfont_size'])),
        yaxis=dict(tickfont=dict(size=chart_cfg['axes']['tickfont_size']))
    )

    smart_save_image(fig, output_dir / f"{base_name}.png")
    smart_save_image(fig, output_dir / f"{base_name}.svg")

    # Save HTML
    fig.write_html(output_dir / f"{base_name}.html", auto_open=auto_open, include_plotlyjs='cdn')
    
    # Save CSV
    # We can save the top contributors data
    # (Re-calculating logic briefly for CSV export)
    merged = pd.merge(
        c_p2[['ifscode', 'country', 'isocode', 'adjustment_needed_global_gdp']],
        c_p1[['ifscode', 'adjustment_needed_global_gdp']],
        on='ifscode', suffixes=('_p2', '_p1')
    )
    merged['change_adj'] = merged['adjustment_needed_global_gdp_p2'] - merged['adjustment_needed_global_gdp_p1']
    merged['contribution'] = merged['change_adj']
    # Save CSV (Label/Value matching waterfall bars)
    fig_data = create_country_decomposition_chart(c_p1, c_p2, g_p1, g_p2)
    # Re-extract labels and values from the chart function
    wf = fig_data[0].data[0]
    pd.DataFrame({'Label': list(wf.y), 'Value': [round(v, 2) for v in wf.x]}).to_csv(
        output_dir / f"{base_name}.csv", index=False)

    print("Country decomposition chart created successfully.")

if __name__ == "__main__":
    main()
