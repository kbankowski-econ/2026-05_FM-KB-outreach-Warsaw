import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import ensure_output_dir, load_config, load_chart_config, resolve_project_path, get_chart_dims_px
from pathlib import Path
from plotly.subplots import make_subplots

def load_data():
    excel_path = resolve_project_path('data', 'fmData', 'debt-ownership-Michael-desc.xlsx')
    df = pd.read_excel(excel_path, sheet_name=0)

    # Replace total_WEO with GLB_GRP ggxwdg_gdp from WEO_enhanced (full series incl. 2031)
    weo_path = resolve_project_path('data', 'fmData', 'WEO_enhanced.dta')
    weo = pd.read_stata(str(weo_path))
    glb = weo[(weo['isocode'] == 'GLB_GRP') & (weo['year'] >= 2010)][['year', 'ggxwdg_gdp']].rename(columns={'ggxwdg_gdp': 'total_WEO'})
    df = df.drop(columns=['total_WEO'], errors='ignore')
    df = df.merge(glb, on='year', how='outer').sort_values('year').reset_index(drop=True)
    df['year'] = df['year'].astype(int)

    # Extrapolate 'total' for 2025–2031 based on WEO differences (anchored at 2024)
    anchor_year = 2024
    anchor_total = df.loc[df['year'] == anchor_year, 'total'].iloc[0]
    anchor_weo = df.loc[df['year'] == anchor_year, 'total_WEO'].iloc[0]
    for yr in range(anchor_year + 1, df['year'].max() + 1):
        weo_diff = (df.loc[df['year'] == yr, 'total_WEO'].iloc[0] - anchor_weo)
        df.loc[df['year'] == yr, 'total'] = anchor_total + weo_diff

    return df

def apply_common_layout(fig, cfg, y_range_left=None, y_range_right=None, dtick=10, x_range=None):
    """Apply common styling from chartConfig.json to maintain project-wide consistency."""

    width_px, height_px = get_chart_dims_px("debt_ownership_plot.png")
    fig.update_layout(
        template=cfg['template'],
        width=width_px,
        height=height_px,
        margin=dict(t=30, b=40, l=0, r=0), # Removed left/right margins
        font={"size": cfg['font_size']},
        legend={**{k: v for k, v in cfg['legend'].items() if k != 'font_size'}, "y": 1.01, "font": {"size": cfg['legend']['font_size']}, "title": None},
        barmode="relative"
    )

    # X-axis
    fig.update_xaxes(
        showgrid=cfg['axes']['showgrid'], 
        gridcolor=cfg['axes'].get('gridcolor'), 
        linecolor=cfg['axes']['linecolor'], 
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'], 
        tickfont={"size": cfg['axes']['tickfont_size']},
        range=x_range,
        domain=[0, 1]
    )

    # Primary Y-axis (Bars - Contributions)
    fig.update_yaxes(
        title="",
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont={"size": cfg['axes']['tickfont_size']},
        zeroline=True,
        zerolinecolor=cfg['axes']['linecolor'],
        range=y_range_left,
        dtick=dtick,
        secondary_y=False
    )

    # Secondary Y-axis (Lines - Debt Levels)
    fig.update_yaxes(
        title="",
        showgrid=False,
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont={"size": cfg['axes']['tickfont_size']},
        range=y_range_right,
        dtick=dtick,
        secondary_y=True
    )

def main():
    cfg = load_chart_config()['styling']
    out_dir = ensure_output_dir(load_config())
    df = load_data()
    
    # Identify 2010 total value as the anchor for the secondary Y-axis
    # Zero on the left (contributions) moves to 'total_2010' on the right (levels)
    total_2010 = df.loc[df['year'] == 2010, 'total'].iloc[0]
    
    # Calculate aligned ranges with identical scale
    # Left (contributions): approx -8 to +24 -> [-10, 40]
    # Right (levels): [total_2010 - 10, total_2010 + 40]
    y_range_left = [-10, 40]
    y_range_right = [total_2010 - 10, total_2010 + 40]
    dtick = 10

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Ownership Categories (Stacked Bars)
    # Grouped by type: Official (Oranges), Banks (Blues), Nonbanks (Greens)
    # Domestic = Deep saturated colors, Foreign = Lighter with slight hue shift
    categories = [
        # Official sector: Orange family
        ('Domestic official', '#BF360C'),   # Deep burnt orange
        ('Foreign official', '#FFAB91'),    # Light coral/salmon (shifted towards pink)
        # Banks sector: Blue family  
        ('Domestic banks', '#0D47A1'),      # Deep navy blue
        ('Foreign banks', '#81D4FA'),       # Light sky blue (shifted towards cyan)
        # Nonbanks sector: Green family
        ('Domestic nonbanks', '#1B5E20'),   # Deep forest green
        ('Foreign nonbanks', '#A5D6A7')     # Light mint green (shifted towards lime)
    ]

    for var, color in categories:
        fig.add_trace(go.Bar(
            x=df['year'], 
            y=df[var], 
            name=var, 
            marker_color=color, 
            opacity=0.9
        ), secondary_y=False)
    
    # Total Lines (on secondary Y axis) - ORIGINAL VALUES
    fig.add_trace(go.Scatter(
        x=df['year'], 
        y=df['total'], 
        name='Total (right scale)', 
        mode='lines',
        line=dict(color='black', width=cfg['line_widths']['thick'])
    ), secondary_y=True)

    fig.add_trace(go.Scatter(
        x=df['year'], 
        y=df['total_WEO'], 
        name='Total WEO (right scale)', 
        mode='lines',
        line=dict(color='#FF00FF', width=cfg['line_widths']['standard'], dash='dash')
    ), secondary_y=True)

    apply_common_layout(
        fig, cfg,
        y_range_left=y_range_left,
        y_range_right=y_range_right,
        dtick=dtick,
        x_range=[df['year'].min(), df['year'].max()]
    )

    # Abbreviated x-axis year labels: 2010, 15, 20, ...
    x_ticks = list(range(df['year'].min(), df['year'].max() + 1, 5))
    fig.update_xaxes(
        tickvals=x_ticks,
        ticktext=[str(y) if i == 0 else str(y % 100) for i, y in enumerate(x_ticks)]
    )

    # Save CSV
    csv_cols = ['year'] + [var for var, _ in categories] + ['total', 'total_WEO']
    csv_rename = {var: var for var, _ in categories}
    csv_rename['total'] = 'Total (right scale)'
    csv_rename['total_WEO'] = 'Total WEO (right scale)'
    csv_df = df[csv_cols].copy().rename(columns=csv_rename)
    csv_df = csv_df.round(2)
    csv_df.to_csv(out_dir / "debt_ownership_plot.csv", index=False)

    fpath = out_dir / "debt_ownership_plot"
    pio.write_image(fig, f"{fpath}.png", format='png', scale=2)
    pio.write_image(fig, f"{fpath}.svg", format='svg')
    fig.write_html(f"{fpath}.html", auto_open=True, include_plotlyjs='cdn')
    
    # Save Metadata
    create_metadata(out_dir / "debt_ownership_plot.txt")
    print(f"Chart and metadata saved to: {fpath}.png")

def create_metadata(output_path):
    """Create a text file with chart metadata"""
    content = [
        "CHART METADATA: DEBT OWNERSHIP DECOMPOSITION",
        "=" * 50,
        "TITLE: Decomposition of General Government Debt by Holder",
        "UNITS: Percent of GDP (Relative Change)",
        "SOURCES: IMF staff calculations based on national authorities.",
        "",
        "NOTE: Bars represent the contribution of different holder categories to the change in government debt. 'Total' reflects the sum of these components, while 'Total WEO' provides the comparison against WEO headline debt data.",
        "=" * 50
    ]
    with open(output_path, 'w') as f:
        f.write('\n'.join(f"{line}" for line in content))

if __name__ == "__main__":
    main()
