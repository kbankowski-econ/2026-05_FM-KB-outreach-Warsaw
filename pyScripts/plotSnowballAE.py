import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config

def load_data():
    # Load WEO data
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    df = pd.read_stata(data_path)
    
    # Load country classification
    ct_path = resolve_from_config("../+environment/csvFiles/countryTable.csv")
    ct = pd.read_csv(ct_path)
    
    return df, ct

def calculate_ae_stats(df, ct, var_name):
    ae_ifscodes = ct[ct['devClass'] == "Advanced"]['ifscode'].tolist()
    ae_df = df[df['ifscode'].isin(ae_ifscodes)].copy()
    
    stats = ae_df.groupby('year')[var_name].agg([
        ('p10', lambda x: x.quantile(0.10)),
        ('p25', lambda x: x.quantile(0.25)),
        ('p75', lambda x: x.quantile(0.75)),
        ('p90', lambda x: x.quantile(0.90)),
        ('median', 'median')
    ]).reset_index()
    
    return stats

def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    
    df, ct = load_data()
    
    # Range: 1995 to 2031 (Longest reliable horizon)
    start_year, end_year = 1995, 2031
    
    # AE Stats for Snowball (Left)
    ae_snowball_stats = calculate_ae_stats(df, ct, 'snow_ball')
    ae_snowball_stats = ae_snowball_stats[ae_snowball_stats['year'].between(start_year, end_year)]
    
    # Japan data
    japan = df[df['isocode'] == 'JPN'].sort_values('year')
    japan = japan[japan['year'].between(start_year, end_year)]
    
    # Project-wide standard colors
    ae_line_color = '#6A1B9A'
    ae_fill_color_iqr = 'rgba(106, 27, 154, 0.25)'
    ae_fill_color_90 = 'rgba(106, 27, 154, 0.10)'
    japan_line_color = '#00897B'
    
    # Create 2x1 Subplots - Stacked like trade_measures_plot
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.12, # Tighter vertical gap
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
    )
    
    # --- SUBPLOT 1: SNOWBALL (TOP) ---
    # 1.1 AE 10th-90th Range
    fig.add_trace(go.Scatter(
        x=pd.concat([ae_snowball_stats['year'], ae_snowball_stats['year'][::-1]]),
        y=pd.concat([ae_snowball_stats['p90'], ae_snowball_stats['p10'][::-1]]),
        fill='toself', fillcolor=ae_fill_color_90,
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip", name="AE 10th-90th<br>percentile",
        showlegend=True, legend='legend'
    ), row=1, col=1)

    # 1.2 AE Interquartile Range
    fig.add_trace(go.Scatter(
        x=pd.concat([ae_snowball_stats['year'], ae_snowball_stats['year'][::-1]]),
        y=pd.concat([ae_snowball_stats['p75'], ae_snowball_stats['p25'][::-1]]),
        fill='toself', fillcolor=ae_fill_color_iqr,
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip", name="AE 25th-75th<br>percentile",
        showlegend=True, legend='legend'
    ), row=1, col=1)

    # 1.3 Japan Snowball
    fig.add_trace(go.Scatter(
        x=japan['year'], y=japan['snow_ball'],
        mode='lines',
        line=dict(color=japan_line_color, width=chart_cfg['line_widths']['thick']),
        name="Japan (<i>r</i>–<i>g</i>)",
        showlegend=True, legend='legend'
    ), row=1, col=1)
    
    # --- SUBPLOT 2: r AND g (BOTTOM) ---
    # 2.1 Japan Implicit Interest Rate (r) -> Orange
    fig.add_trace(go.Scatter(
        x=japan['year'], y=japan['implicit_rate'],
        mode='lines',
        line=dict(color='#F57F17', width=chart_cfg['line_widths']['thick']),
        name="Effective interest<br>rate (<i>r</i>)",
        showlegend=True, legend='legend2'
    ), row=2, col=1)

    # 2.2 Trace for Green Fill (where g > r)
    fig.add_trace(go.Scatter(
        x=japan['year'], y=japan['g'].clip(lower=japan['implicit_rate']),
        mode='lines', line=dict(width=0),
        fill='tonexty', fillcolor='rgba(46, 125, 50, 0.25)',
        showlegend=False, hoverinfo='skip'
    ), row=2, col=1)

    # 2.3 Reset Reference for Red Fill (invisible r)
    fig.add_trace(go.Scatter(
        x=japan['year'], y=japan['implicit_rate'],
        mode='lines', line=dict(color='rgba(0,0,0,0)', width=0),
        showlegend=False, hoverinfo='skip'
    ), row=2, col=1)

    # 2.4 Trace for Red Fill (where r > g)
    fig.add_trace(go.Scatter(
        x=japan['year'], y=japan['g'].clip(upper=japan['implicit_rate']),
        mode='lines', line=dict(width=0),
        fill='tonexty', fillcolor='rgba(198, 40, 40, 0.25)',
        showlegend=False, hoverinfo='skip'
    ), row=2, col=1)
    
    # 2.5 Japan Nominal Growth (g) -> Midnight Blue
    fig.add_trace(go.Scatter(
        x=japan['year'], y=japan['g'],
        mode='lines',
        line=dict(color='#1A237E', width=chart_cfg['line_widths']['thick']),
        name="Nominal<br>growth (<i>g</i>)",
        showlegend=True, legend='legend2'
    ), row=2, col=1)
    
    # 2.3 Japan Real Growth (g_real) -> Bright Indigo
    fig.add_trace(go.Scatter(
        x=japan['year'], y=japan['g_real'],
        mode='lines',
        line=dict(color='#5C6BC0', width=chart_cfg['line_widths']['thick']),
        name="Real growth",
        showlegend=True, legend='legend2'
    ), row=2, col=1)

    # Layout adjustment - Maximum breathing room for sidebar legends
    fig.update_layout(
        template=chart_cfg['template'],
        width=chart_cfg['width'],
        height=chart_cfg['height'], 
        margin=dict(t=40, b=30, l=220, r=25), 
        font=dict(size=chart_cfg['font_size']),
        legend=dict(
            orientation="v",
            yanchor="middle", y=0.78,
            xanchor="left", x=-0.65, # Pushed even further left
            bgcolor='rgba(255,255,255,0)',
            font=dict(size=chart_cfg['font_size'] - 6)
        ),
        legend2=dict(
            orientation="v",
            yanchor="middle", y=0.22,
            xanchor="left", x=-0.65,
            bgcolor='rgba(255,255,255,0)',
            font=dict(size=chart_cfg['font_size'] - 6)
        )
    )
    
    # Common Axis Properties
    fig.update_xaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        tickmode='array',
        tickvals=[2000, 2010, 2020, 2030],
        ticktext=['2000', '10', '20', '30'],
        range=[start_year - 0.5, end_year + 0.5]
    )

    fig.update_yaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        zeroline=True,
        zerolinecolor='black'
    )
    
    # Subplot Titles as Annotations - Font consistency with trade_measures_plot
    fig.layout.annotations = [] 
    fig.add_annotation(
        text="Snowball Effect (Percent of GDP)", 
        xref="paper", yref="paper", 
        x=0.5, y=1.08, 
        showarrow=False, 
        font=dict(size=chart_cfg['font_size'] - 5)
    )
    fig.add_annotation(
        text="<i>r</i> minus <i>g</i> (Percent)", 
        xref="paper", yref="paper", 
        x=0.5, y=0.46, 
        showarrow=False, 
        font=dict(size=chart_cfg['font_size'] - 5)
    )

    # Projection Highlight (2026-2031)
    fig.add_vrect(
        x0=2025.5, x1=end_year + 0.5,
        fillcolor="rgba(128, 128, 128, 0.2)",
        layer="below", line_width=0
    )

    # Export CSV of plotted data (both panels)
    # Panel 1: Snowball effect
    csv_snowball = ae_snowball_stats[['year', 'p10', 'p25', 'median', 'p75', 'p90']].copy()
    csv_snowball = csv_snowball.rename(columns={
        'p10': 'AE Snowball 10th percentile',
        'p25': 'AE Snowball 25th percentile',
        'median': 'AE Snowball median',
        'p75': 'AE Snowball 75th percentile',
        'p90': 'AE Snowball 90th percentile'
    })
    japan_snow = japan[['year', 'snow_ball']].copy().rename(columns={'snow_ball': 'Japan Snowball (r-g)'})
    csv_panel1 = pd.merge(csv_snowball, japan_snow, on='year', how='outer')
    # Panel 2: r and g
    japan_rg = japan[['year', 'implicit_rate', 'g', 'g_real']].copy().rename(columns={
        'implicit_rate': 'Japan Effective interest rate (r)',
        'g': 'Japan Nominal growth (g)',
        'g_real': 'Japan Real growth'
    })
    csv_data = pd.merge(csv_panel1, japan_rg, on='year', how='outer')
    csv_data = csv_data.sort_values('year').round(2)
    base_name = "ae_snowball_japan_panel"
    output_csv = output_dir / f"{base_name}.csv"
    csv_data.to_csv(output_csv, index=False)
    print(f"CSV saved as {output_csv}")

    # Main chart not in chartTable; only the _10x10 variant below is exported.

    # 10x10cm version (378x378 at 96 DPI) - Single panel with just Snowball effect
    fig_small = go.Figure()

    # AE 10th-90th Range
    fig_small.add_trace(go.Scatter(
        x=pd.concat([ae_snowball_stats['year'], ae_snowball_stats['year'][::-1]]),
        y=pd.concat([ae_snowball_stats['p90'], ae_snowball_stats['p10'][::-1]]),
        fill='toself', fillcolor=ae_fill_color_90,
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip", name="AE 10th-90th<br>percentile",
        showlegend=True,
        legendrank=4
    ))

    # AE Interquartile Range
    fig_small.add_trace(go.Scatter(
        x=pd.concat([ae_snowball_stats['year'], ae_snowball_stats['year'][::-1]]),
        y=pd.concat([ae_snowball_stats['p75'], ae_snowball_stats['p25'][::-1]]),
        fill='toself', fillcolor=ae_fill_color_iqr,
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip", name="AE 25th-75th<br>percentile",
        showlegend=True,
        legendrank=3
    ))

    # AE Median
    fig_small.add_trace(go.Scatter(
        x=ae_snowball_stats['year'], y=ae_snowball_stats['median'],
        mode='lines',
        line=dict(color=ae_line_color, width=chart_cfg['line_widths']['thick']),
        name="AE Median",
        showlegend=True,
        legendrank=2
    ))

    # Japan Snowball
    fig_small.add_trace(go.Scatter(
        x=japan['year'], y=japan['snow_ball'],
        mode='lines',
        line=dict(color=japan_line_color, width=chart_cfg['line_widths']['thick']),
        name="Japan",
        showlegend=True,
        legendrank=1
    ))

    # Layout for 10x10cm
    from fiscal_common import get_chart_dims_px
    _w, _h = get_chart_dims_px("ae_snowball_japan_panel_10x10.png")
    fig_small.update_layout(
        template=chart_cfg['template'],
        width=_w, height=_h,
        margin=dict(t=30, b=40, l=35, r=20),
        font=dict(size=13),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            bgcolor='rgba(255,255,255,0)',
            font=dict(size=chart_cfg['legend']['font_size'])
        )
    )

    fig_small.update_xaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        tickmode='array',
        tickvals=[2000, 2010, 2020, 2030],
        ticktext=['2000', '10', '20', '30'],
        range=[start_year - 0.5, end_year + 0.5]
    )

    fig_small.update_yaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        zeroline=True,
        zerolinecolor='black'
    )

    # Projection Highlight (2026-2031)
    fig_small.add_vrect(
        x0=2025.5, x1=end_year + 0.5,
        fillcolor="rgba(128, 128, 128, 0.2)",
        layer="below", line_width=0
    )

    # Japan annotation for 2026-2031 sum
    japan_proj = japan[japan['year'].between(2026, 2031)]
    japan_sum = japan_proj['snow_ball'].sum()
    japan_2028_val = japan[japan['year'] == 2028]['snow_ball'].values[0] if len(japan[japan['year'] == 2028]) > 0 else japan_proj['snow_ball'].mean()
    fig_small.add_annotation(
        x=2028,
        y=japan_2028_val,
        text=f"Σ 2026-31: {japan_sum:.1f}",
        font=dict(size=11, color=japan_line_color),
        showarrow=True,
        arrowhead=0,
        arrowcolor=japan_line_color,
        ax=-25,
        ay=80,
        bgcolor='rgba(255,255,200,0.9)'
    )

    # AE Median annotation for 2026-2031 sum
    ae_proj = ae_snowball_stats[ae_snowball_stats['year'].between(2026, 2031)]
    ae_sum = ae_proj['median'].sum()
    ae_2028_val = ae_snowball_stats[ae_snowball_stats['year'] == 2028]['median'].values[0] if len(ae_snowball_stats[ae_snowball_stats['year'] == 2028]) > 0 else ae_proj['median'].mean()
    fig_small.add_annotation(
        x=2028,
        y=ae_2028_val,
        text=f"Σ 2026-31: {ae_sum:.1f}",
        font=dict(size=11, color=ae_line_color),
        showarrow=True,
        arrowhead=0,
        arrowcolor=ae_line_color,
        ax=-25,
        ay=-80,
        bgcolor='rgba(255,255,200,0.9)'
    )

    pio.write_image(fig_small, output_dir / f"{base_name}_10x10.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig_small, output_dir / f"{base_name}_10x10.svg", format='svg', engine='kaleido', scale=2)
    fig_small.write_html(output_dir / f"{base_name}_10x10.html", auto_open=True, include_plotlyjs='cdn')

    print(f"Snowball AE panel chart complete. Saved {base_name}.png")

if __name__ == "__main__":
    main()
