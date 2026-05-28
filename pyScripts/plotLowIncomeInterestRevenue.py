import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config

def load_data():
    # Load WEO data from the enhanced .dta file
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    df = pd.read_stata(data_path)
    
    # Load country classification for groupings
    ct_path = resolve_from_config("../+environment/csvFiles/countryTable.csv")
    ct = pd.read_csv(ct_path)
    
    return df, ct

def calculate_stats(df, ct, dev_class):
    # Filter countries in the requested development class (Low-Income)
    group_ifscodes = ct[ct['devClass'] == dev_class]['ifscode'].tolist()
    sub_df = df[df['ifscode'].isin(group_ifscodes)].copy()

    # Calculate interest payments to total revenue ratio for individual countries
    sub_df = sub_df[sub_df['ggr_gdp'] > 0].copy()
    sub_df['int_rev_ratio'] = (sub_df['ggei_gdp'] / sub_df['ggr_gdp']) * 100

    # Distribution Statistics (IQ Range) - from individual countries
    stats = sub_df.groupby('year')['int_rev_ratio'].agg([
        ('p25', lambda x: x.quantile(0.25)),
        ('p75', lambda x: x.quantile(0.75))
    ]).reset_index()

    # Use LOW_GRP aggregate ratio (ratio of weighted averages)
    # This is consistent with the country tables
    low_grp = df[df['isocode'] == 'LOW_GRP'][['year', 'ggei_gdp', 'ggr_gdp']].copy()
    low_grp['w_avg'] = low_grp['ggei_gdp'] / low_grp['ggr_gdp'] * 100
    w_avg = low_grp[['year', 'w_avg']]

    return stats, w_avg

def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    
    df, ct = load_data()
    
    # Calculate stats for low-income countries
    stats, w_avg = calculate_stats(df, ct, "Low-Income")
    
    # Focus on 2005-2031 time horizon
    stats = stats[stats['year'].between(2005, 2031)]
    w_avg = w_avg[w_avg['year'].between(2005, 2031)]
    
    fig = go.Figure()
    
    # Calculate stats for individual driver countries
    individual_countries = ['Bangladesh', 'Kenya', 'Nigeria']
    country_data = {}
    for country in individual_countries:
        c_df = df[df['country'] == country].copy()
        c_df = c_df[c_df['ggr_gdp'] > 0]
        c_df['ratio'] = (c_df['ggei_gdp'] / c_df['ggr_gdp']) * 100
        country_data[country] = c_df[c_df['year'].between(2005, 2031)]

    # LIDC Color Scheme
    lidc_color = '#6A1B9A'
    lidc_fill = 'rgba(106, 27, 154, 0.2)'
    country_colors = {'Kenya': '#E65100', 'Bangladesh': '#00897B', 'Nigeria': '#1E88E5'}
    
    # Trace 1: LIDC Interquartile Range
    fig.add_trace(go.Scatter(
        x=pd.concat([stats['year'], stats['year'][::-1]]),
        y=pd.concat([stats['p75'], stats['p25'][::-1]]),
        fill='toself',
        fillcolor=lidc_fill,
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip",
        name='LIDC interquartile range'
    ))
    
    # Trace 2: LIDC Aggregate (ratio of weighted averages)
    fig.add_trace(go.Scatter(
        x=w_avg['year'], y=w_avg['w_avg'],
        mode='lines',
        line=dict(color=lidc_color, width=4),
        name='LIDC aggregate'
    ))

    # Traces 3-5: Individual Countries
    for country in individual_countries:
        data = country_data[country]
        fig.add_trace(go.Scatter(
            x=data['year'], y=data['ratio'],
            mode='lines',
            line=dict(color=country_colors[country], width=2.5, dash='dot'),
            name=country
        ))
    
    # Apply styling from chartConfig.json
    legend_style = {k: v for k, v in chart_cfg['legend'].items() if k != 'font_size'}
    legend_style.update({
        "font": dict(size=chart_cfg['legend']['font_size']),
        "y": 1.01, "x": 0.5, "xanchor": 'center', "orientation": 'h'
    })

    from fiscal_common import get_chart_dims_px
    _w, _h = get_chart_dims_px("low_income_interest_revenue_ratio.png")
    fig.update_layout(
        template=chart_cfg['template'],
        width=_w,
        height=_h,
        margin=dict(t=110, b=40, l=35, r=8, autoexpand=False),
        font=dict(size=chart_cfg['font_size']),
        legend=legend_style,
        yaxis_title="",
        xaxis_title=""
    )
    
    fig.update_xaxes(
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        tickmode='array', tickvals=[2005, 2010, 2015, 2020, 2025, 2030],
        ticktext=['2005', '10', '15', '20', '25', '30'], range=[2004.5, 2031.5],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )
    
    fig.update_yaxes(
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        zeroline=True, zerolinecolor='black',
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        rangemode='tozero'
    )
    
    # Forecast Horizon Shading
    fig.add_vrect(
        x0=2025.5, x1=2031.5,
        fillcolor="rgba(128, 128, 128, 0.4)",
        layer="below", line_width=0
    )
    
    # Save output
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)
    base_name = "low_income_interest_revenue_ratio"
    save_path = output_dir / base_name
    
    pio.write_image(fig, f"{save_path}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, f"{save_path}.svg", format='svg', engine='kaleido', scale=2)

    fig.write_html(f"{save_path}.html", auto_open=auto_open, include_plotlyjs='cdn')

    # Export CSV with only plotted series
    csv_df = w_avg.rename(columns={'w_avg': 'LIDC aggregate'}).merge(
        stats[['year', 'p25', 'p75']].rename(columns={'p25': 'LIDC interquartile range (p25)', 'p75': 'LIDC interquartile range (p75)'}),
        on='year', how='outer'
    )
    for country in individual_countries:
        c = country_data[country][['year', 'ratio']].rename(columns={'ratio': country})
        csv_df = csv_df.merge(c, on='year', how='outer')

    csv_df = csv_df.sort_values('year')
    csv_df['year'] = csv_df['year'].astype(int)
    csv_path = f"{save_path}.csv"
    csv_df.to_csv(csv_path, index=False, float_format='%.3f')
    print(f"CSV saved to {csv_path}")

    print(f"Updated LIDC Interest Revenue Ratio plot saved to {save_path}.png")

if __name__ == "__main__":
    main()
