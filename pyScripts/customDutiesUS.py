import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime

from fiscal_common import ensure_output_dir, load_config, load_chart_config, resolve_project_path


def get_customs_data():
    """Fetch customs duties data from Treasury API"""
    url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_4"
    params = {'limit': 10000, 'sort': '-record_date'}
    
    response = requests.get(url, params=params)
    data = response.json()['data']
    
    df = pd.DataFrame(data)
    df['record_date'] = pd.to_datetime(df['record_date'])
    df['current_month_net_rcpt_amt'] = pd.to_numeric(df['current_month_net_rcpt_amt'], errors='coerce')
    
    # Filter for Customs Duties only
    df = df[df['classification_desc'] == 'Customs Duties'].copy()

    # If value for Dec 2025 is missing, assume it is equal to Nov 2025
    dec_2025 = pd.Timestamp('2025-12-31')
    nov_2025 = pd.Timestamp('2025-11-30')
    
    if dec_2025 not in df['record_date'].values:
        nov_data = df[df['record_date'] == nov_2025]
        if not nov_data.empty:
            imputed_row = nov_data.iloc[0].copy()
            imputed_row['record_date'] = dec_2025
            df = pd.concat([df, pd.DataFrame([imputed_row])], ignore_index=True)
            print(f"INFO: Dec 2025 data missing. Imputed from Nov 2025: ${imputed_row['current_month_net_rcpt_amt']/1e9:.2f}B")
            
    return df

def load_gdp_data():
    """Load US GDP data from WEO_enhanced.dta"""
    data_path = resolve_project_path('data', 'fmData', 'WEO_enhanced.dta')
    gdp_df = pd.read_stata(data_path)
    us_data = gdp_df[gdp_df['isocode'] == 'USA']

    gdp_dict = {}
    for _, row in us_data.iterrows():
        year = int(row['year'])
        gdp_dict[year] = row['ngdpd'] / 1e12  # Convert USD to trillions

    return gdp_dict

def create_ytd_data(df, gdp_data):
    """Create year-to-date cumulative data as percentage of GDP"""
    df['year'] = df['record_date'].dt.year
    df['month'] = df['record_date'].dt.month
    df['month_name'] = df['record_date'].dt.strftime('%b')
    df['net_receipts_billions'] = df['current_month_net_rcpt_amt'] / 1e9
    
    # Create pivot and calculate cumulative sums
    monthly_data = df.pivot_table(
        index=['month', 'month_name'], 
        columns='year', 
        values='net_receipts_billions', 
        aggfunc='sum'
    ).reset_index()
    
    # Calculate cumulative sums and convert to % of GDP
    for year in monthly_data.columns:
        if isinstance(year, int) and year in gdp_data:
            monthly_data[year] = monthly_data[year].cumsum()
            annual_gdp_trillions = gdp_data[year]
            monthly_data[year] = (monthly_data[year] / 1000.0) / annual_gdp_trillions * 100
    
    monthly_data.set_index('month_name', inplace=True)
    monthly_data.drop('month', axis=1, inplace=True)
    
    return monthly_data


def apply_common_layout(fig, cfg, y_range=None, x_range=None, tickvals=None, ticktext=None):
    """Apply common styling from chartConfig.json, matching fmBondRadarEM.py logic"""
    layout = {
        "template": cfg['template'],
        "width": cfg['width'],
        "height": cfg['height'],
        "margin": cfg['margins'],
        "font": {"size": cfg['font_size']},
        "legend": {
            **cfg['legend'], 
            "y": 1.01, # Move legend closer to plot
            "font": {"size": cfg['legend']['font_size']},
            "title": None, 
            "traceorder": 'normal'
        },
        "xaxis": {
            "showgrid": cfg['axes']['showgrid'],
            "gridcolor": cfg['axes'].get('gridcolor'),
            "gridwidth": cfg['axes'].get('gridwidth'),
            "linecolor": cfg['axes']['linecolor'],
            "linewidth": cfg['axes'].get('linewidth'),
            "mirror": cfg['axes']['mirror'],
            "ticks": cfg['axes']['ticks'],
            "tickfont": {"size": cfg['axes']['tickfont_size']},
            "range": x_range
        },
        "yaxis": {
            "showgrid": cfg['axes']['showgrid'],
            "gridcolor": cfg['axes'].get('gridcolor'),
            "gridwidth": cfg['axes'].get('gridwidth'),
            "linecolor": cfg['axes']['linecolor'],
            "linewidth": cfg['axes'].get('linewidth'),
            "mirror": cfg['axes']['mirror'],
            "ticks": cfg['axes']['ticks'],
            "tickfont": {"size": cfg['axes']['tickfont_size']},
            "range": y_range,
            "zeroline": cfg['axes'].get('zeroline', True),
            "zerolinecolor": cfg['axes']['linecolor'],
            "zerolinewidth": cfg['axes'].get('zerolinewidth')
        },
        "title": None,
        "yaxis_title": None
    }
    
    if tickvals and ticktext:
        layout["xaxis"].update({"tickmode": 'array', "tickvals": tickvals, "ticktext": ticktext})
    
    fig.update_layout(**layout)


def create_monthly_plot(df, chart_cfg, fiscal_cfg, gdp_data):
    """Create monthly customs duties plot with annual series on secondary axis"""
    df_sorted = df.sort_values('record_date')
    net_receipts_billions = df_sorted['current_month_net_rcpt_amt'] / 1e9
    
    # Calculate annual series
    df['year'] = df['record_date'].dt.year
    counts = df.groupby('year')['record_date'].count()
    annual_duties = df.groupby('year')['current_month_net_rcpt_amt'].sum() / 1e9 # in billions
    
    annual_steps_x = []
    annual_steps_y = []
    
    for year in sorted(annual_duties.index):
        if year in gdp_data and counts[year] == 12:
            # GDP is in trillions in gdp_data
            gdp_billions = gdp_data[year] * 1000
            val_pct = (annual_duties[year] / gdp_billions) * 100
            
            # Break the line between years to hide vertical parts
            if annual_steps_x:
                annual_steps_x.append(None)
                annual_steps_y.append(None)
            
            # Create horizontal segments for the year
            annual_steps_x.extend([pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")])
            annual_steps_y.extend([val_pct, val_pct])
    
    # Calculate y-axis range for left axis
    y_max = net_receipts_billions.max()
    y_range = [0, y_max * 1.05] # Tighter top padding
    
    from plotly.subplots import make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Left axis: Monthly series
    fig.add_trace(go.Scatter(
        x=df_sorted['record_date'],
        y=net_receipts_billions,
        mode='lines',
        name='Monthly (billions of dollars, left scale)',
        line=dict(color=chart_cfg['colors']['primary'], width=chart_cfg['line_widths']['thick'])
    ), secondary_y=False)
    
    # Right axis: Annual series (stepwise, horizontal only)
    fig.add_trace(go.Scatter(
        x=annual_steps_x,
        y=annual_steps_y,
        mode='lines',
        name='Annual (percent of GDP, right scale)',
        line=dict(color='rgba(0,0,0,0.4)', width=chart_cfg['line_widths']['thick']),
        connectgaps=False
    ), secondary_y=True)
    
    # Apply common layout and then customize
    apply_common_layout(
        fig, chart_cfg, 
        y_range=y_range,
        x_range=['2015-01-01', df_sorted['record_date'].max()], # Removed extra month padding
        tickvals=['2015-01-01', '2020-01-01', '2025-01-01'],
        ticktext=['2015', '20', '25']
    )
    
    # Customize right axis
    fig.update_yaxes(
        title_text="",
        showgrid=False,
        ticks='inside',
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        secondary_y=True,
        zeroline=False,
        range=[0, 1.2]
    )
    
    fig.update_layout(
        legend=dict(
            **{k: v for k, v in chart_cfg['legend'].items() if k != 'font_size'},
            font=dict(size=chart_cfg['legend']['font_size'])
        )
    )
    
    return fig


def create_ytd_plot(ytd_df, chart_cfg):
    """Create year-to-date cumulative plot"""
    # Define colors (purple gradient: lightest → darkest)
    colors = ['#F3E5F5', '#E1BEE7', '#CE93D8', '#BA68C8', '#AB47BC',
             '#9C27B0', '#8E24AA', '#7B1FA2', '#6A1B9A', '#4A148C']
    
    fig = go.Figure()
    months = list(range(1, 13))
    
    # Add traces for each year (excluding 2015)
    year_columns = [col for col in ytd_df.columns if isinstance(col, int) and col != 2015]
    
    all_y = []
    for i, year in enumerate(sorted(year_columns)):
        if ytd_df[year].notna().any():
            y_values = ytd_df[year]
            all_y.extend(y_values.dropna().tolist())
            
            # Create legend name
            if year == 2025:
                legend_name = str(year)
                width = chart_cfg['line_widths']['thick']
            else:
                dec_value = y_values.get('Dec', None)
                legend_name = f"{year} ({dec_value:.2f})" if pd.notna(dec_value) else str(year)
                width = chart_cfg['line_widths']['standard']
            
            fig.add_trace(go.Scatter(
                x=list(range(1, len(y_values) + 1)), 
                y=y_values,
                mode='lines+markers',
                name=legend_name,
                line=dict(color=colors[i % len(colors)], width=width),
                marker=dict(size=4)
            ))
            
            # Add September 2025 annotation
            if year == 2025:
                sep_value = y_values.get('Sep', None)
                if pd.notna(sep_value):
                    fig.add_annotation(
                        x=9, y=sep_value, text=f'{sep_value:.2f}',
                        showarrow=False, xanchor='left', yanchor='middle',
                        font=dict(size=chart_cfg['font_size'], color=colors[i % len(colors)]),
                        bgcolor='rgba(255,255,255,0.7)', borderwidth=0, xshift=10
                    )
    
    y_range = [min(all_y)*0.95, max(all_y)*1.05] if all_y else None
    
    apply_common_layout(
        fig, chart_cfg,
        y_range=y_range,
        x_range=[1, 12],
        tickvals=[2, 4, 6, 8, 10, 12],
        ticktext=['Feb', 'Apr', 'Jun', 'Aug', 'Oct', 'Dec']
    )
    
    return fig

def create_report(ytd_df, gdp_data, output_path):
    """Create dynamic text report for customs duties"""
    report_lines = [
        "US CUSTOMS DUTIES ANALYSIS REPORT",
        "=" * 50,
        f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ""
    ]
    
    # Latest Data Analysis
    if 2025 in ytd_df.columns:
        # Find the latest available month in 2025
        ytd_2025 = ytd_df[2025].dropna()
        if not ytd_2025.empty:
            latest_month_idx = ytd_2025.index[-1]
            latest_pct = ytd_2025.iloc[-1]
            
            if 2025 in gdp_data:
                gdp_2025_trillions = gdp_data[2025]
                gdp_billions = gdp_2025_trillions * 1000
                nominal_billions = (latest_pct / 100) * gdp_billions
                
                report_lines.extend([
                    f"LATEST DATA SUMMARY (YTD through {latest_month_idx} 2025)",
                    "-" * 50,
                    f"YTD Percentage of GDP: {latest_pct:.4f}%",
                    f"US GDP 2025 (nominal): ${gdp_2025_trillions:.2f} trillion",
                    f"YTD Total Customs Duties: ${nominal_billions:.2f} billion",
                    ""
                ])

    # Historical Full-Year Comparison
    report_lines.extend([
        "HISTORICAL COMPARISON (Annual Totals / Dec YTD)",
        "-" * 50
    ])
    
    # Sort all years including 2025
    all_years = sorted([col for col in ytd_df.columns if isinstance(col, int) and col != 2015])
    
    for year in all_years:
        dec_value = ytd_df.loc['Dec', year] if 'Dec' in ytd_df.index else None
        if pd.notna(dec_value) and year in gdp_data:
            gdp_year = gdp_data[year] * 1000
            nominal_year = (dec_value / 100) * gdp_year
            label = f"{year} (Est.)" if year == 2025 else str(year)
            report_lines.append(f"{label:12}: {dec_value:.4f}% of GDP (${nominal_year:.2f}B)")

    # Add 2024 to 2025 comparison summary
    if 2024 in all_years and 2025 in all_years:
        val_2024 = (ytd_df.loc['Dec', 2024] / 100) * (gdp_data[2024] * 1000)
        val_2025 = (ytd_df.loc['Dec', 2025] / 100) * (gdp_data[2025] * 1000)
        
        factor = val_2025 / val_2024
        pct_increase = (factor - 1) * 100
        
        report_lines.extend([
            "",
            "FISCAL YEAR 2025 VS 2024 SUMMARY",
            "-" * 50,
            f"2024 Total Customs Duties: ${val_2024:.2f}B",
            f"2025 Estimated Total     : ${val_2025:.2f}B",
            f"Growth Factor            : {factor:.1f}x ({(factor-1):.1f}-fold increase)",
            f"Nominal Percentage Change: +{pct_increase:.1f}%"
        ])
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(report_lines))

def main():
    """Main function to generate customs duties charts"""
    chart_config = load_chart_config()['styling']
    fiscal_config = load_config()
    base_path = ensure_output_dir(fiscal_config)
    
    # Get data
    df = get_customs_data()
    gdp_data = load_gdp_data()
    ytd_df = create_ytd_data(df, gdp_data)
    
    # Create plots
    monthly_fig = create_monthly_plot(df, chart_config, fiscal_config, gdp_data)
    ytd_fig = create_ytd_plot(ytd_df, chart_config)
    
    # Save outputs
    auto_open = fiscal_config['output_settings']['auto_open_html']
    
    # Monthly plot CSV
    df_sorted = df.sort_values('record_date').copy()
    monthly_csv = pd.DataFrame({
        'Date': df_sorted['record_date'].values,
        'Monthly (billions of dollars, left scale)': (df_sorted['current_month_net_rcpt_amt'] / 1e9).round(2).values
    })
    # Build annual % of GDP series aligned to monthly dates
    annual_gdp_map = {}
    counts = df.groupby('year')['record_date'].count()
    annual_duties = df.groupby('year')['current_month_net_rcpt_amt'].sum() / 1e9
    for year in sorted(annual_duties.index):
        if year in gdp_data and counts[year] == 12:
            gdp_billions = gdp_data[year] * 1000
            annual_gdp_map[year] = round((annual_duties[year] / gdp_billions) * 100, 2)
    monthly_csv['Annual (percent of GDP, right scale)'] = monthly_csv['Date'].apply(
        lambda d: annual_gdp_map.get(pd.Timestamp(d).year, None)
    )
    monthly_csv.to_csv(base_path / "customs_duties_plot.csv", index=False)

    # YTD plot CSV
    ytd_csv = ytd_df.copy().round(2)
    ytd_csv.index.name = 'Month'
    ytd_csv.columns = [str(c) for c in ytd_csv.columns]
    ytd_csv.to_csv(base_path / "customs_duties_ytd_plot.csv")

    # Apply CSV-driven dimensions
    from fiscal_common import get_chart_dims_px
    mw, mh = get_chart_dims_px("customs_duties_plot.png")
    monthly_fig.update_layout(width=mw, height=mh)
    pio.write_image(monthly_fig, base_path / "customs_duties_plot.png", format='png', engine='kaleido', scale=2)
    pio.write_image(monthly_fig, base_path / "customs_duties_plot.svg", format='svg', engine='kaleido', scale=2)
    monthly_fig.write_html(base_path / "customs_duties_plot.html", auto_open=auto_open, include_plotlyjs='cdn')

    print("Custom duties chart completed.")

if __name__ == "__main__":
    main()
