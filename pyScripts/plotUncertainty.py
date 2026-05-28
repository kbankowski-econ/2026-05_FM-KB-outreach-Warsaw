import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import os
import json
import webbrowser

def plot_uncertainty():
    # Paths and configuration
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(script_dir, "../"))
    output_png = os.path.join(root, 'docu/uncertainty_plot.png')
    output_html = os.path.join(root, 'docu/uncertainty_plot.html')
    config_path = os.path.join(script_dir, "chartConfig.json")

    with open(config_path, "r") as f:
        cfg = json.load(f)["styling"]

    from fiscal_common import get_chart_dims_px
    w_px, h_px = get_chart_dims_px("uncertainty_plot.png")

    # Data loading
    excel_wpui = os.path.join(root, 'data/fmData/WPUI-global.xlsx')
    excel_gfpu = os.path.join(root, 'data/fmData/GFPU_Data_60countries_C1.xlsx')

    # 1. Load WPUI (Sheet 'visualizer1974', skip header row with "string"/"number")
    df_wpui = pd.read_excel(excel_wpui, sheet_name='visualizer1974', skiprows=1, usecols=[0, 1])
    df_wpui.columns = ['date_str', 'wpui_raw']
    # Parse dates like "Jan-08" to datetime
    df_wpui['date'] = pd.to_datetime(df_wpui['date_str'], format='%b-%y', errors='coerce')
    df_wpui = df_wpui.dropna(subset=['date'])

    # Re-index so Jan 2015 = 100
    wpui_base = df_wpui.loc[df_wpui['date'] == '2015-01-01', 'wpui_raw'].iloc[0]
    df_wpui['policy_uncertainty'] = (df_wpui['wpui_raw'] / wpui_base) * 100

    df_wpui = df_wpui[['date', 'policy_uncertainty']]

    # 2. Load Global Fiscal Policy Uncertainty (Sheet '60Countries_normalized_LATEST', 'global' column)
    df_fpu = pd.read_excel(excel_gfpu, sheet_name='60Countries_normalized_LATEST', usecols=['publication_datetime', 'global'])
    df_fpu.columns = ['date', 'fiscal_uncertainty_raw']

    # Re-index so Jan 2015 = 100
    fpu_base = df_fpu.loc[df_fpu['date'] == '2015-01-01', 'fiscal_uncertainty_raw'].iloc[0]
    df_fpu['fiscal_uncertainty'] = (df_fpu['fiscal_uncertainty_raw'] / fpu_base) * 100

    df_fpu = df_fpu[['date', 'fiscal_uncertainty']]
    
    # Merge and filter (using outer join to keep more recent dates)
    df = pd.merge(df_wpui, df_fpu, on='date', how='outer').sort_values('date')
    df = df[df['date'] >= '2015-01-01'].copy()
    
    # Setup subplots with dual Y axes
    cutoff = pd.Timestamp('2025-05-01')
    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.1, specs=[[{"secondary_y": True}, {"secondary_y": True}]])
    
    series_config = {
        'policy_uncertainty': ('World Policy Uncertainty Index', '#6A1B9A', False),
        'fiscal_uncertainty': ('Global Fiscal Policy Uncertainty Index (right scale)', '#E65100', True)
    }
    
    for key, (name, color, sec) in series_config.items():
        hovertemplate = f"<b>{name}</b><br>Date: %{{x|%Y-%m-%d}}<br>Value: %{{y:.2f}}<extra></extra>"
        fig.add_trace(go.Scatter(x=df['date'], y=df[key], name=name, mode='lines', line=dict(color=color, width=cfg['line_widths']['standard']), hovertemplate=hovertemplate), row=1, col=1, secondary_y=sec)
        recent = df[df['date'] >= cutoff]
        fig.add_trace(go.Scatter(x=recent['date'], y=recent[key], mode='lines', line=dict(color=color, width=cfg['line_widths']['thick']), showlegend=False, hovertemplate=hovertemplate), row=1, col=2, secondary_y=sec)

    # Calculate padded ranges
    def get_range(data, include_zero=True):
        data = data[~pd.isna(data)]
        if len(data) == 0: return [0, 1]
        d_min, d_max = min(data), max(data)
        padding = (d_max - d_min) * 0.05 if d_max > d_min else 0.1
        lower = min(0, d_min - padding) if include_zero else d_min - padding
        return [lower, d_max + padding]

    pri_range = get_range(df['policy_uncertainty'].values, include_zero=True)
    sec_range = get_range(df['fiscal_uncertainty'].values, include_zero=False)

    # Layout and styling from config
    fig.update_layout(
        template=cfg['template'],
        width=w_px,
        height=h_px,
        margin=cfg['margins'],
        font=dict(size=cfg['font_size']),
        legend=dict(**{**{k: v for k, v in cfg['legend'].items() if k != 'font_size'}, 'y': 1.08}, font=dict(size=cfg['legend']['font_size']))
    )
    
    # Common axis styling
    fig.update_xaxes(
        showgrid=cfg['axes']['showgrid'], 
        gridcolor=cfg['axes'].get('gridcolor'),
        gridwidth=cfg['axes'].get('gridwidth'),
        linecolor=cfg['axes']['linecolor'], 
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'], 
        tickfont=dict(size=cfg['axes']['tickfont_size'])
    )
    fig.update_yaxes(
        showgrid=cfg['axes']['showgrid'],
        gridcolor=cfg['axes'].get('gridcolor'),
        gridwidth=cfg['axes'].get('gridwidth'),
        linecolor=cfg['axes']['linecolor'],
        linewidth=cfg['axes'].get('linewidth'),
        ticks=cfg['axes']['ticks'],
        tickfont=dict(size=cfg['axes']['tickfont_size']),
        zeroline=False
    )

    # Specific ranges and visibility
    fig.update_yaxes(range=pri_range, secondary_y=False, tickformat=",")
    fig.update_yaxes(range=sec_range, secondary_y=True)

    # X-axis specific formats – full year for first tick, abbreviated for rest
    x_ticks = pd.date_range(start=df['date'].min().replace(month=1, day=1), end=df['date'].max(), freq='5YS')
    fig.update_xaxes(
        tickvals=x_ticks,
        ticktext=[d.strftime("%Y") if i == 0 else str(d.year % 100) for i, d in enumerate(x_ticks)],
        row=1, col=1
    )
    fig.update_xaxes(dtick="M3", tick0="2025-05-01", tickformat="%b<br>%y", tickangle=0, range=[recent['date'].min(), recent['date'].max()], row=1, col=2)
    
    # Hide cross-labels
    fig.update_yaxes(showticklabels=False, secondary_y=True, row=1, col=1)
    fig.update_yaxes(showticklabels=False, secondary_y=False, row=1, col=2)
    
    # Recent period highlight
    bg = dict(type="rect", y0=0, y1=1, fillcolor='rgba(0,0,0,0.15)', layer="below", line_width=0)
    fig.add_shape(**bg, x0=cutoff, x1=df['date'].max(), xref="x", yref="y domain")
    fig.add_shape(**bg, x0=recent['date'].min(), x1=recent['date'].max(), xref="x2", yref="y2 domain")

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    
    # Save PNG and SVG
    pio.write_image(fig, output_png, format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_png.replace('.png', '.svg'), format='svg', engine='kaleido', scale=2)
    print(f"Plot saved as {output_png}")
    
    # Save CSV
    output_csv = output_png.replace('.png', '.csv')
    df_export = df[['date', 'policy_uncertainty', 'fiscal_uncertainty']].copy()
    df_export = df_export.rename(columns={
        'policy_uncertainty': 'World Policy Uncertainty Index',
        'fiscal_uncertainty': 'Global Fiscal Policy Uncertainty Index'
    })
    df_export['date'] = df_export['date'].dt.strftime('%Y-%m-%d')
    df_export['World Policy Uncertainty Index'] = df_export['World Policy Uncertainty Index'].round(2)
    df_export['Global Fiscal Policy Uncertainty Index'] = df_export['Global Fiscal Policy Uncertainty Index'].round(2)
    df_export.to_csv(output_csv, index=False)
    print(f"CSV data saved as {output_csv}")

    # Save HTML
    fig.write_html(output_html, include_plotlyjs='cdn')
    print(f"Interactive plot saved as {output_html}")
    
    # Auto-open HTML
    webbrowser.open('file://' + os.path.realpath(output_html))

if __name__ == "__main__":
    plot_uncertainty()