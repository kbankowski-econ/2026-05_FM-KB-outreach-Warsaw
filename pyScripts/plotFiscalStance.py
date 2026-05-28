import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
import numpy as np
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config

def apply_common_layout(fig, cfg):
    """Apply common styling from chartConfig.json."""
    layout = {
        "template": cfg['template'],
        "width": cfg['width'], 
        "height": cfg['height'],
        "margin": cfg['margins'],
        "font": {"size": cfg['font_size']},
        "legend": {
            **cfg['legend'], 
            "y": 1.05, 
            "font": {"size": cfg['legend']['font_size']},
            "title": None
        },
        "xaxis": {
            "title": {"text": "Primary balance (percent of GDP)", "font": {"size": cfg['font_size'] - 4}},
            "showgrid": cfg['axes']['showgrid'], 
            "gridcolor": cfg['axes'].get('gridcolor'), 
            "linecolor": cfg['axes']['linecolor'], 
            "linewidth": cfg['axes'].get('linewidth'),
            "ticks": cfg['axes']['ticks'], 
            "tickfont": {"size": cfg['axes']['tickfont_size']},
            "zeroline": True,
            "zerolinecolor": "black",
            "zerolinewidth": 1
        },
        "yaxis": {
            "title": {"text": "Output gap (percent of potential GDP)", "font": {"size": cfg['font_size'] - 4}},
            "showgrid": cfg['axes']['showgrid'], 
            "gridcolor": cfg['axes'].get('gridcolor'),
            "linecolor": cfg['axes']['linecolor'], 
            "linewidth": cfg['axes'].get('linewidth'),
            "ticks": cfg['axes']['ticks'], 
            "tickfont": {"size": cfg['axes']['tickfont_size']},
            "zeroline": True, 
            "zerolinecolor": "black",
            "zerolinewidth": 1
        }
    }
    fig.update_layout(**layout)

def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    
    # Path to enhanced WEO data
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    
    if not data_path.exists():
        print(f"Error: {data_path} missing.")
        return

    print(f"Loading data from {data_path}...")
    df = pd.read_stata(data_path)
    
    # Filter for US, China, and global aggregate
    # Order: aggregate first, then countries to ensure countries are on top
    target_isos = ['GLB_X_USA_CHN', 'USA', 'CHN']
    df_plot = df[df['isocode'].isin(target_isos)].copy()
    df_plot = df_plot[(df_plot['year'] >= 2015) & (df_plot['year'] <= 2031)]
    
    # Drop rows with missing values in either axis
    df_plot = df_plot.dropna(subset=['ngap_r', 'primary_balance'])
    
    # Calculate data bounds to prevent shapes from expanding the axis limits
    x_min, x_max = df_plot['primary_balance'].min(), df_plot['primary_balance'].max()
    y_min, y_max = df_plot['ngap_r'].min(), df_plot['ngap_r'].max()
    
    # Add small padding for shapes
    x_range = [x_min - 0.5, x_max + 0.5]
    y_range = [y_min - 0.5, y_max + 0.5]

    fig = go.Figure()
    
    # Force axes to stay within data range
    fig.update_xaxes(range=x_range)
    fig.update_yaxes(range=y_range)
    
    # Define series properties (Aligned colors with other charts)
    # USA (AE): #4682B4, China (EM): #FFA000, Global: Charcoal
    series_map = {
        'USA': {'name': 'United States', 'color': 'rgba(0, 137, 123, 1.0)', 'symbol': 'circle'},
        'CHN': {'name': 'China', 'color': 'rgba(230, 81, 0, 1.0)', 'symbol': 'circle'},
        'GLB_X_USA_CHN': {'name': 'Global (excluding China and United States)', 'color': 'rgba(117, 117, 117, 0.4)', 'symbol': 'circle'}
    }
    
    for iso in target_isos:
        info = series_map[iso]
        subset = df_plot[df_plot['isocode'] == iso].sort_values('year')
        if subset.empty:
            continue
            
        # Add continuous trail line (rounded with splines)
        # Use legendrank to order legend (China, US, Global) while keeping Global on bottom layer
        l_rank = {'CHN': 1, 'USA': 2, 'GLB_X_USA_CHN': 3}.get(iso, 10)
        
        fig.add_trace(go.Scatter(
            x=subset['primary_balance'],
            y=subset['ngap_r'],
            mode='lines',
            name=info['name'],
            legendrank=l_rank,
            line=dict(
                color=info['color'],
                width=3.5,
                shape='spline',
                smoothing=1.3,
                dash='solid'
            ),
            showlegend=True,
            hoverinfo='skip'
        ))

        # Sizes list: 18 for 2025, 10 otherwise
        sizes = [18 if y == 2025 else 10 for y in subset['year']]
        
        # Color list: Darker for projections (2025+), white fill for 2015
        # USA base: 70, 130, 180 | CHN base: 255, 160, 0 | Global base: 55, 71, 79
        dark_color = {'USA': 'rgba(35, 65, 90, 1.0)', 'CHN': 'rgba(128, 80, 0, 1.0)', 'GLB_X_USA_CHN': 'rgba(30, 40, 45, 1.0)'}

        def get_marker_style(year):
            if year == 2015:
                return 'white', info['color']  # white fill, colored border
            elif year >= 2025:
                return dark_color[iso], 'white'  # dark fill, white border
            else:
                return info['color'], 'white'  # base color fill, white border

        fill_colors = [get_marker_style(y)[0] for y in subset['year']]
        border_colors = [get_marker_style(y)[1] for y in subset['year']]

        # Add points
        fig.add_trace(go.Scatter(
            x=subset['primary_balance'],
            y=subset['ngap_r'],
            mode='markers',
            name=info['name'],
            marker=dict(
                size=sizes,
                color=fill_colors,
                symbol='circle',
                line=dict(width=2, color=border_colors)
            ),
            showlegend=False,
            text=subset['year'].astype(int),
            hovertemplate="<b>" + info['name'] + " (%{text})</b><br>Primary Balance: %{x:.1f}%<br>Output Gap: %{y:.1f}%<extra></extra>"
        ))
        
        # Add label ONLY for 2025 - always above
        subset_2025 = subset[subset['year'] == 2025]
        for _, row in subset_2025.iterrows():
            fig.add_annotation(
                x=row['primary_balance'],
                y=row['ngap_r'],
                text="<b>2025</b>",
                showarrow=False,
                yshift=28,
                font=dict(size=12, color=info['color'], family='Arial Black'),
                bgcolor="rgba(255,255,255,0.7)"
            )
        
        

    apply_common_layout(fig, chart_cfg)
    
    # Projection area (usually 2025-2030)
    # Since this is a scatter, we can't easily use vrect if we want to show it only for the future
    # But we can add a subtle note or style the lines differently for projections
    
    # Export CSV of plotted data
    csv_frames = []
    for iso in target_isos:
        info = series_map[iso]
        subset = df_plot[df_plot['isocode'] == iso].sort_values('year')
        if subset.empty:
            continue
        frame = pd.DataFrame({
            'year': subset['year'].values,
            f"{info['name']}: Primary balance": subset['primary_balance'].values,
            f"{info['name']}: Output gap": subset['ngap_r'].values
        })
        csv_frames.append(frame)
    csv_data = csv_frames[0]
    for frame in csv_frames[1:]:
        csv_data = pd.merge(csv_data, frame, on='year', how='outer')
    csv_data = csv_data.sort_values('year').round(2)
    base_name = "fiscal_stance_usa_chn"
    output_csv = output_dir / f"{base_name}.csv"
    csv_data.to_csv(output_csv, index=False)
    print(f"CSV saved as {output_csv}")

    # Save outputs at CSV-driven dimensions
    from fiscal_common import get_chart_dims_px
    _w, _h = get_chart_dims_px(f"{base_name}.png")
    fig.update_layout(width=_w, height=_h)
    pio.write_image(fig, output_dir / f"{base_name}.png", scale=2)
    pio.write_image(fig, output_dir / f"{base_name}.svg", scale=2)
    fig.write_html(output_dir / f"{base_name}.html", auto_open=True, include_plotlyjs='cdn')
    
    # Metadata
    metadata_path = output_dir / f"{base_name}.txt"
    with open(metadata_path, 'w') as f:
        f.write("CHART METADATA: FISCAL STANCE EVOLUTION - USA vs CHINA\n")
        f.write("=" * 50 + "\n")
        f.write("TITLE: Fiscal Stance Evolution (2015-2031)\n")
        f.write("X-AXIS: Primary Balance (Percent of GDP)\n")
        f.write("Y-AXIS: Output Gap (Percent of potential GDP)\n")
        f.write("SOURCES: IMF, World Economic Outlook database; and IMF staff calculations.\n")
        f.write("NOTE: Each dot represents a year. Lines indicate the temporal trajectory from 2015 to 2031.\n")
        f.write("=" * 50 + "\n")

    print(f"Chart and metadata generated in {output_dir}")

if __name__ == "__main__":
    main()
