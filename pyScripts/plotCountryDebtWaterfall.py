import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
from plotly.subplots import make_subplots
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, get_chart_dims_px

def load_data():
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    df = pd.read_stata(data_path)
    return df

def apply_common_layout(fig, cfg, x_range=None):
    """Apply common styling from chartConfig.json (Horizontal)."""
    w_px, h_px = get_chart_dims_px("global_debt_country_decomposition_waterfall.png")
    layout = {
        "template": cfg['template'],
        "width": w_px,
        "height": h_px,
        "margin": {**cfg['margins'], "l": 80}, # Reduced significantly for ISO3C labels
        "font": {"size": cfg['font_size']},
        "yaxis": {
            "showgrid": False,
            "linecolor": cfg['axes']['linecolor'], 
            "linewidth": cfg['axes'].get('linewidth'),
            "ticks": cfg['axes']['ticks'], 
            "tickfont": {"size": cfg['axes']['tickfont_size']},
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
        }
    }
    fig.update_layout(**layout)

def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    
    df = load_data()
    
    # 1. Get Global Data for start and end
    glob = df[df['ifscode'] == 9999]
    debt_2025 = glob[glob['year'] == 2025]['ggxwdg_gdp'].iloc[0]
    debt_2031 = glob[glob['year'] == 2031]['ggxwdg_gdp'].iloc[0]
    
    # 2. Calculate contributions by country/group
    # Contribution = Debt_i,t1 * w_i,t1 - Debt_i,t0 * w_i,t0
    # where w_it = NGDPD_it / sum(NGDPD_kt)
    
    # Filter for countries and years
    df_sub = df[(df['year'].isin([2025, 2031])) & (df['ifscode'] < 9000)].copy()
    glob_gdp = df_sub.groupby('year')['ngdpd'].sum()
    df_sub['weight'] = df_sub['ngdpd'] / df_sub['year'].map(glob_gdp)
    df_sub['weighted_debt'] = df_sub['ggxwdg_gdp'] * df_sub['weight']
    
    # Pivot to get start and end values
    pivot = df_sub.pivot(index=['isocode', 'country', 'ifscode'], columns='year', values='weighted_debt').reset_index()
    pivot['contribution'] = pivot[2031] - pivot[2025]
    
    # Load country table for ISO3C codes
    country_table_path = resolve_from_config("../+environment/csvFiles/countryTable.csv")
    ct = pd.read_csv(country_table_path)
    
    # Merge ISO3C codes into pivot
    pivot = pivot.merge(ct[['ifscode', 'iso3c']], on='ifscode', how='left')
    
    # MODIFICATION: Exclude specific countries from being shown individually
    exclude_list = []
    pivot_candidates = pivot[~pivot['iso3c'].isin(exclude_list)].copy()
    
    # Identify top countries by absolute contribution
    pivot_candidates = pivot_candidates.sort_values(by='contribution', key=abs, ascending=False)
    
    # Take top 10 countries, group the rest (including excluded ones)
    top_n = 10
    top_countries = pivot_candidates.head(top_n).copy()
    
    # Re-calculate "Other" to include excluded countries and non-top countries
    top_isocodes = top_countries['iso3c'].tolist()
    other_countries = pivot[~pivot['iso3c'].isin(top_isocodes)]
    
    other_v = other_countries['contribution'].sum()
    
    # Prepare Waterfall data starting with Global Debt
    labels = ["2025 debt"]
    x_vals = [debt_2025]
    
    # Add individual countries (using ISO3C)
    for _, row in top_countries.iterrows():
        # Fallback to name if iso3c is missing for some reason
        label = row['iso3c'] if pd.notna(row['iso3c']) else row['country']
        labels.append(label)
        x_vals.append(row['contribution'])
        
    # Add "Other" and final "Total"
    labels.append("Other")
    x_vals.append(other_v)
    labels.append("2031 debt")
    x_vals.append(debt_2031)
    
    measures = ["absolute"] + ["relative"] * (len(labels) - 2) + ["total"]
    
    # Text labels
    text_vals = [f"{v:.0f}" if i == 0 or i == len(x_vals)-1 else f"{v:+.1f}" for i, v in enumerate(x_vals)]

    fig = make_subplots(
        rows=1, cols=2, 
        column_widths=[0.4, 0.6],
        shared_yaxes=True,
        horizontal_spacing=0.05,
        subplot_titles=("Global<br>(Percent of global GDP)", "Country-specific<br>(Percent of GDP)")
    )
    
    # Adjust subplot title positions to fit two rows
    for i in range(len(fig.layout.annotations)):
        fig.layout.annotations[i].y += 0.01

    # 1. Waterfall Chart
    fig.add_trace(go.Waterfall(
        orientation="h",
        measure=measures,
        y=labels,
        x=x_vals,
        text=text_vals,
        textposition="outside",
        textfont=dict(size=chart_cfg['legend']['font_size']),
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#00897B"}}, 
        increasing={"marker": {"color": "#E65100"}}, 
        totals={"marker": {"color": "#6A1B9A"}},
        showlegend=False
    ), row=1, col=1)

    # 2. Arrow Plot (Debt Ratio Changes)
    # We need the raw debt ratios and GDP for the top countries and Other aggregate
    df_raw = df[(df['year'].isin([2025, 2031])) & (df['ifscode'] < 9000)].copy()
    raw_pivot = df_raw.pivot(index='ifscode', columns='year', values='ggxwdg_gdp').reset_index()
    
    # Calculate Other category aggregate debt ratios (GDP-weighted)
    top_ifscodes = top_countries['ifscode'].tolist()
    other_raw = df_raw[~df_raw['ifscode'].isin(top_ifscodes)]
    
    def get_other_agg(year):
        yr_data = other_raw[other_raw['year'] == year]
        return (yr_data['ggxwdg_gdp'] * yr_data['ngdpd']).sum() / yr_data['ngdpd'].sum()
        
    other_r25 = get_other_agg(2025)
    other_r30 = get_other_agg(2031)
    
    # Map back to get ratios for our top countries and Other
    for i, label in enumerate(labels):
        if label in ["2025 debt", "2031 debt"]:
            continue
            
        if label == "Other":
            r25, r30 = other_r25, other_r30
        else:
            # Find the raw ratios for this country
            country_row = top_countries[top_countries['iso3c'] == label]
            if country_row.empty:
                continue
                
            ifscode = country_row['ifscode'].iloc[0]
            ratios = raw_pivot[raw_pivot['ifscode'] == ifscode]
            if ratios.empty:
                continue
            r25 = ratios[2025].iloc[0]
            r30 = ratios[2031].iloc[0]
        
        color = "#E65100" if r30 > r25 else "#00897B"
        
        # Add line segment
        fig.add_trace(go.Scatter(
            x=[r25, r30],
            y=[label, label],
            mode='lines+markers',
            marker=dict(
                symbol=['circle', 'arrow-right' if r30 > r25 else 'arrow-left'],
                size=[5, 9],
                color=color
            ),
            line=dict(color=color, width=3),
            showlegend=False
        ), row=1, col=2)
        
        # Add values next to start/end (conditional on direction)
        # Start Value (2025)
        fig.add_annotation(
            x=r25, y=label, text=f"{r25:.0f}",
            showarrow=False, 
            xanchor='right' if r30 > r25 else 'left',
            xshift=-10 if r30 > r25 else 10,
            font=dict(size=chart_cfg['font_size'] - 5),
            row=1, col=2
        )
        # End Value (2031)
        fig.add_annotation(
            x=r30, y=label, text=f"{r30:.0f}",
            showarrow=False, 
            xanchor='left' if r30 > r25 else 'right',
            xshift=10 if r30 > r25 else -10,
            font=dict(size=chart_cfg['font_size'] - 5),
            row=1, col=2
        )

    # Calculate range for waterfall
    cumulative = [debt_2025]
    for val in x_vals[1:-1]:
        cumulative.append(cumulative[-1] + val)
    
    x_min_wf = min(cumulative + [debt_2025, debt_2031])
    x_max_wf = max(cumulative + [debt_2025, debt_2031])
    padding_wf = (x_max_wf - x_min_wf) * 1.0
    
    # Calculate range for arrow plot
    all_ratios = []
    # Map back to get ratios for our top countries and Other
    for i, label in enumerate(labels):
        if label in ["2025 debt", "2031 debt"]: continue
        if label == "Other":
            all_ratios.extend([other_r25, other_r30])
        else:
            country_row = top_countries[top_countries['iso3c'] == label]
            if not country_row.empty:
                ifscode = country_row['ifscode'].iloc[0]
                ratios = raw_pivot[raw_pivot['ifscode'] == ifscode]
                if not ratios.empty:
                    all_ratios.extend([ratios[2025].iloc[0], ratios[2031].iloc[0]])
    
    x_min_arr = min(all_ratios)
    x_max_arr = max(all_ratios)
    span_arr = x_max_arr - x_min_arr
    padding_arr = span_arr * 0.35
    
    # Synchronize Layout with Globe chart
    fig.update_layout(
        template=chart_cfg['template'],
        width=get_chart_dims_px("global_debt_country_decomposition_waterfall.png")[0],
        height=get_chart_dims_px("global_debt_country_decomposition_waterfall.png")[1],
        margin={**chart_cfg['margins'], "l": 80, "t": 55}, # Tightened top margin
        font=dict(size=chart_cfg['font_size'])
    )
    
    # Synchronize Axes with Globe chart standards
    fig.update_xaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes'].get('gridcolor'),
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth'),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )
    
    fig.update_yaxes(
        showgrid=False,
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth'),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        autorange="reversed"
    )
    
    # Specific ranges for subplots
    fig.update_xaxes(range=[90, 115], row=1, col=1)
    fig.update_xaxes(range=[x_min_arr - padding_arr, x_max_arr + padding_arr], row=1, col=2)
    
    # Save CSV - Panel 1: Waterfall contributions; Panel 2: Debt ratios
    base_name = "global_debt_country_decomposition_waterfall"
    csv_rows = []
    for i, label in enumerate(labels):
        row = {"Label": label, "Contribution (pp of global GDP)": round(x_vals[i], 2)}
        if label in ["2025 debt", "2031 debt"]:
            row["Debt 2025 (% of GDP)"] = None
            row["Debt 2031 (% of GDP)"] = None
        elif label == "Other":
            row["Debt 2025 (% of GDP)"] = round(other_r25, 2)
            row["Debt 2031 (% of GDP)"] = round(other_r30, 2)
        else:
            country_row = top_countries[top_countries['iso3c'] == label]
            if not country_row.empty:
                ifscode = country_row['ifscode'].iloc[0]
                ratios = raw_pivot[raw_pivot['ifscode'] == ifscode]
                if not ratios.empty:
                    row["Debt 2025 (% of GDP)"] = round(ratios[2025].iloc[0], 2)
                    row["Debt 2031 (% of GDP)"] = round(ratios[2031].iloc[0], 2)
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(output_dir / f"{base_name}.csv", index=False)

    # Save outputs
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)
    pio.write_image(fig, output_dir / f"{base_name}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base_name}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base_name}.html", auto_open=auto_open, include_plotlyjs='cdn')
    
    # Save Metadata
    create_metadata(output_dir / f"{base_name}.txt")
    print(f"Country decomposition waterfall complete. Saved {base_name}.png")

def create_metadata(output_path):
    content = [
        "CHART METADATA: GLOBAL DEBT COUNTRY DECOMPOSITION (2025-30)",
        "=" * 50,
        "TITLE: Contribution of Major Economies to the Change in Global Public Debt, 2025–30",
        "UNITS: Percentage points of global GDP",
        "SOURCES: IMF, World Economic Outlook database; and IMF staff calculations.",
        "",
        "NOTE: The chart decomposes the projected change in the global-debt-to-GDP ratio between 2025 and 2031 into contributions from individual countries and groups. The contribution of each entity depends on its projected change in debt and its economic weight (GDP in USD). Positive values indicate contributions that increase the global debt ratio. Note: A country may show a positive contribution even with a falling domestic debt ratio if its weight in global GDP is projected to increase significantly (compositional effect).",
        "=" * 50
    ]
    with open(output_path, 'w') as f:
        f.write('\n'.join(content))

if __name__ == "__main__":
    main()
