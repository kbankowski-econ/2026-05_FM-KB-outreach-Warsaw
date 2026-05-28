import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
from pathlib import Path
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config, smart_save_image, get_chart_dims_px

_LABEL_FONT_SIZE = load_chart_config()['styling']['legend']['font_size']

def get_data(file_path, start_year, end_year=None, target_isocodes=None):
    """Load and filter data for a specific year or period average."""
    if end_year is None:
        end_year = start_year
        
    df = pd.read_stata(file_path)
    
    # Filter by year range
    mask = (df['year'] >= start_year) & (df['year'] <= end_year)
    df = df[mask].copy()
    
    # Filter by entities (Global + Target Countries)
    global_code = 9999
    if target_isocodes:
        # Get ifscodes for target isocodes
        # We need to filter by isocode OR ifscode 9999
        mask_entity = (df['ifscode'] == global_code) | (df['isocode'].isin(target_isocodes))
        df = df[mask_entity].copy()
    else:
        # Default to just Global if no targets specified
        df = df[df['ifscode'] == global_code].copy()
    
    # Average if period
    if start_year != end_year:
        cols = ['adjustment_needed', 'snow_ball', 'primary_balance', 'gov_revenue', 'primary_exp', 'snow_ball_r', 'snow_ball_g', 'snow_ball_g_real', 'snow_ball_g_deflator', 'sfa_gdp', 'ngdpd']
        group_cols = ['ifscode', 'country', 'isocode']
        
        df = df.groupby(group_cols)[cols].mean().reset_index()
        
    if not df.empty:
        df = df.dropna(subset=['adjustment_needed'])
        
    return df

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
            "autorange": "reversed" # Standard waterfall look: start from top
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

def create_waterfall_chart(p1_agg, p2_agg):
    """Create a waterfall chart decomposing the change in adjustment needed."""
    
    # adjustment_needed is pre-calculated as (PB - Snowball) 
    # Positive values mean primary balance is higher than snowball.
    adj_p1 = p1_agg['adjustment_needed'].iloc[0]
    adj_p2 = p2_agg['adjustment_needed'].iloc[0]
    
    val_p1 = adj_p1
    val_p2 = adj_p2
    
    # Explanatory Factors
    
    # 1. Difference in Revenue and Primary Expenditure
    rev_p1 = p1_agg['gov_revenue'].iloc[0]
    rev_p2 = p2_agg['gov_revenue'].iloc[0]
    diff_rev = rev_p2 - rev_p1
    
    exp_p1 = p1_agg['primary_exp'].iloc[0]
    exp_p2 = p2_agg['primary_exp'].iloc[0]
    # Primary expenditure contribution is negative of the change in expenditure
    # If expenditure increases, fiscal space decreases
    contrib_exp = -(exp_p2 - exp_p1)
    
    # 2. Difference in Snowball Components
    # We want to subtract the change in snowball, so we subtract the change in each component.
    # Snowball = snow_r - snow_g_real - snow_g_deflator (Wait, let's check the formula)
    # Formula: snow_ball = snow_ball_r - snow_ball_g
    # And snow_ball_g = snow_ball_g_real + snow_ball_g_deflator (approx)
    # So Snowball = snow_ball_r - (snow_ball_g_real + snow_ball_g_deflator)
    # Change in Snowball = Δr - Δg_real - Δg_deflator
    # We want -(Change in Snowball) = -Δr + Δg_real + Δg_deflator
    
    # Let's calculate the differences directly
    r_p1 = p1_agg['snow_ball_r'].iloc[0]
    r_p2 = p2_agg['snow_ball_r'].iloc[0]
    diff_r = r_p2 - r_p1
    
    g_real_p1 = p1_agg['snow_ball_g_real'].iloc[0]
    g_real_p2 = p2_agg['snow_ball_g_real'].iloc[0]
    diff_g_real = g_real_p2 - g_real_p1
    
    g_defl_p1 = p1_agg['snow_ball_g_deflator'].iloc[0]
    g_defl_p2 = p2_agg['snow_ball_g_deflator'].iloc[0]
    diff_g_defl = g_defl_p2 - g_defl_p1
    
    contrib_r = -(r_p2 - r_p1)
    contrib_g_real = -(g_real_p2 - g_real_p1)
    contrib_g_defl = -(g_defl_p2 - g_defl_p1)
    
    fig = go.Figure(go.Waterfall(
        name = "20", orientation = "h",
        measure = ["absolute", "relative", "relative", "relative", "relative", "relative", "total"],
        y = ["2014–19 fiscal gap", "Government<br>revenue", "Government<br>primary spending",
             "Snowball: <i>r</i>", "Snowball: <i>g</i> (real)", "Snowball: π (price)",
             "2024–29 fiscal gap"],
        textposition = "outside",
        textfont = {"size": _LABEL_FONT_SIZE},
        text = [f"{val_p1:.2f}", f"{diff_rev:+.2f}", f"{contrib_exp:+.2f}",
                f"{contrib_r:+.2f}", f"{contrib_g_real:+.2f}", f"{contrib_g_defl:+.2f}",
                f"{val_p2:.2f}"],
        x = [val_p1, diff_rev, contrib_exp, contrib_r, contrib_g_real, contrib_g_defl, val_p2],
        width = 0.5,  # Narrower bars for more spacing
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#E65100"}},
        increasing = {"marker":{"color":"#00897B"}},
        totals = {"marker":{"color":"#6A1B9A"}}
    ))

    # Track cumulative sum for range calculation
    cumulative = [val_p1]
    cumulative.append(cumulative[-1] + diff_rev)
    cumulative.append(cumulative[-1] + contrib_exp)
    cumulative.append(cumulative[-1] + contrib_r)
    cumulative.append(cumulative[-1] + contrib_g_real)
    cumulative.append(cumulative[-1] + contrib_g_defl)
    
    x_min = min(cumulative + [val_p1, val_p2])
    x_max = max(cumulative + [val_p1, val_p2])
    padding = (x_max - x_min) * 0.65

    return fig, [x_min - padding, x_max + padding]

def create_waterfall_chart_with_sfa(p1_agg, p2_agg):
    """Create a waterfall chart decomposing the change in adjustment needed, including SFA."""

    # Fiscal gap including SFA: adjustment_needed - sfa_gdp (positive SFA worsens gap)
    adj_p1 = p1_agg['adjustment_needed'].iloc[0] - p1_agg['sfa_gdp'].iloc[0]
    adj_p2 = p2_agg['adjustment_needed'].iloc[0] - p2_agg['sfa_gdp'].iloc[0]

    val_p1 = adj_p1
    val_p2 = adj_p2

    # Revenue
    diff_rev = p2_agg['gov_revenue'].iloc[0] - p1_agg['gov_revenue'].iloc[0]
    # Primary expenditure (inverted)
    contrib_exp = -(p2_agg['primary_exp'].iloc[0] - p1_agg['primary_exp'].iloc[0])
    # Snowball components
    contrib_r = -(p2_agg['snow_ball_r'].iloc[0] - p1_agg['snow_ball_r'].iloc[0])
    contrib_g_real = -(p2_agg['snow_ball_g_real'].iloc[0] - p1_agg['snow_ball_g_real'].iloc[0])
    contrib_g_defl = -(p2_agg['snow_ball_g_deflator'].iloc[0] - p1_agg['snow_ball_g_deflator'].iloc[0])
    # SFA change (inverted: higher SFA worsens fiscal gap)
    contrib_sfa = -(p2_agg['sfa_gdp'].iloc[0] - p1_agg['sfa_gdp'].iloc[0])

    fig = go.Figure(go.Waterfall(
        name = "20", orientation = "h",
        measure = ["absolute", "relative", "relative", "relative", "relative", "relative", "relative", "total"],
        y = ["2014–19 fiscal gap<br>(incl. SFA)", "Government<br>revenue", "Government<br>primary spending",
             "Snowball: <i>r</i>", "Snowball: <i>g</i> (real)", "Snowball: π (price)",
             "Stock-flow<br>adjustment",
             "2024–29 fiscal gap<br>(incl. SFA)"],
        textposition = "outside",
        textfont = {"size": _LABEL_FONT_SIZE},
        text = [f"{val_p1:.2f}", f"{diff_rev:+.2f}", f"{contrib_exp:+.2f}",
                f"{contrib_r:+.2f}", f"{contrib_g_real:+.2f}", f"{contrib_g_defl:+.2f}",
                f"{contrib_sfa:+.2f}", f"{val_p2:.2f}"],
        x = [val_p1, diff_rev, contrib_exp, contrib_r, contrib_g_real, contrib_g_defl, contrib_sfa, val_p2],
        width = 0.5,
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#E65100"}},
        increasing = {"marker":{"color":"#00897B"}},
        totals = {"marker":{"color":"#6A1B9A"}}
    ))

    cumulative = [val_p1]
    for v in [diff_rev, contrib_exp, contrib_r, contrib_g_real, contrib_g_defl, contrib_sfa]:
        cumulative.append(cumulative[-1] + v)

    x_min = min(cumulative + [val_p1, val_p2])
    x_max = max(cumulative + [val_p1, val_p2])
    padding = (x_max - x_min) * 0.65

    return fig, [x_min - padding, x_max + padding]

def create_chart_instance(p1_agg, p2_agg, chart_cfg):
    fig, x_range = create_waterfall_chart(p1_agg, p2_agg)
    apply_common_layout(fig, chart_cfg, x_range=x_range)
    return fig

def create_chart_instance_with_sfa(p1_agg, p2_agg, chart_cfg):
    fig, x_range = create_waterfall_chart_with_sfa(p1_agg, p2_agg)
    apply_common_layout(fig, chart_cfg, x_range=x_range)
    return fig

def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)
    
    p1_def = {'start': 2014, 'end': 2019, 'label': '2014–2019'}
    p2_def = {'start': 2024, 'end': 2029, 'label': '2024–2029'}
    
    # Germany/Japan now live in the multi-country panel (plotAdjustmentWaterfallMultCountry);
    # this task only emits the global chart (chartTable slide_11_left).
    target_isocodes = []

    print(f"Generating waterfall charts in {output_dir}...")

    print(f"Loading data for {p1_def['label']}...")
    agg_p1 = get_data(data_path, p1_def['start'], p1_def['end'], target_isocodes or None)
    
    print(f"Loading data for {p2_def['label']}...")
    agg_p2 = get_data(data_path, p2_def['start'], p2_def['end'], target_isocodes or None)
    
    if agg_p1.empty or agg_p2.empty:
        print("Error: Could not find data for one or both periods.")
        return

    # Get list of unique entities present in both periods
    common_ifscodes = set(agg_p1['ifscode']).intersection(set(agg_p2['ifscode']))
    
    for ifscode in common_ifscodes:
        # Get data for this entity
        d1 = agg_p1[agg_p1['ifscode'] == ifscode]
        d2 = agg_p2[agg_p2['ifscode'] == ifscode]
        
        if d1.empty or d2.empty:
            continue
            
        # Get Name
        if ifscode == 9999:
            name = "global"
        else:
            name = d1['country'].iloc[0]
            
        print(f"Processing {name}...")
        
        # Create Chart
        fig = create_chart_instance(d1, d2, chart_cfg)
        
        safe_name = name.replace(" ", "_").replace("(", "").replace(")", "")
        base_name = f"adjustmentNeeded_waterfall_{safe_name}_2014-19_vs_2024-29"

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
        
        # Save CSV (Label/Value matching waterfall bars)
        csv_labels = [
            "2014–19 fiscal gap", "Government revenue", "Government primary spending",
            "Snowball: r", "Snowball: g (real)", "Snowball: price",
            "2024–29 fiscal gap"
        ]
        rev = d2['gov_revenue'].iloc[0] - d1['gov_revenue'].iloc[0]
        exp = -(d2['primary_exp'].iloc[0] - d1['primary_exp'].iloc[0])
        r = -(d2['snow_ball_r'].iloc[0] - d1['snow_ball_r'].iloc[0])
        g_real = -(d2['snow_ball_g_real'].iloc[0] - d1['snow_ball_g_real'].iloc[0])
        g_defl = -(d2['snow_ball_g_deflator'].iloc[0] - d1['snow_ball_g_deflator'].iloc[0])
        csv_values = [d1['adjustment_needed'].iloc[0], rev, exp, r, g_real, g_defl, d2['adjustment_needed'].iloc[0]]
        pd.DataFrame({'Label': csv_labels, 'Value': [round(v, 2) for v in csv_values]}).to_csv(
            output_dir / f"{base_name}.csv", index=False)

    print("All waterfall charts created successfully.")

if __name__ == "__main__":
    main()
