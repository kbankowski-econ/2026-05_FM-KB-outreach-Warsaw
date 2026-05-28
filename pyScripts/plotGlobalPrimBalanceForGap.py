"""
Generate a chart for global primary balance with IQ band.
Chart is 10cm x 10cm (378 x 378 pixels at 96 DPI)
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from fiscal_common import load_config, resolve_from_config, ensure_output_dir, load_chart_config


# 10cm x 10cm at 96 DPI
CHART_SIZE = 378


def load_data():
    """Load WEO enhanced data."""
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    df = pd.read_stata(data_path)
    return df


def calculate_stats(df, var_name='primary_balance'):
    """Calculate IQ band statistics and GDP-weighted average."""
    # Filter to single countries only (exclude aggregates)
    countries = df[df['ifscode'] < 9000].copy()
    countries = countries[countries['year'].between(2014, 2031)]
    countries = countries[countries[var_name].notna()]

    stats_list = []
    for year in range(2014, 2032):
        year_data = countries[countries['year'] == year]
        if len(year_data) > 0:
            # Percentiles (unweighted)
            p25 = year_data[var_name].quantile(0.25)
            p50 = year_data[var_name].quantile(0.50)
            p75 = year_data[var_name].quantile(0.75)

            # GDP-weighted average
            valid = year_data[year_data['ngdpd'].notna()]
            if len(valid) > 0 and valid['ngdpd'].sum() > 0:
                w_avg = (valid[var_name] * valid['ngdpd']).sum() / valid['ngdpd'].sum()
            else:
                w_avg = year_data[var_name].mean()

            stats_list.append({
                'year': year,
                'p25': p25,
                'p50': p50,
                'p75': p75,
                'w_avg': w_avg
            })

    return pd.DataFrame(stats_list)


def create_iq_band_chart(stats, chart_cfg):
    """Create a chart with IQ band and weighted average."""
    fig = go.Figure()

    # IQ band (25th to 75th percentile)
    fig.add_trace(go.Scatter(
        x=list(stats['year']) + list(stats['year'][::-1]),
        y=list(stats['p75']) + list(stats['p25'][::-1]),
        fill='toself',
        fillcolor='rgba(106, 27, 154, 0.3)',
        line=dict(color='rgba(0,0,0,0)'),
        name='IQ Range (P25-P75)',
        showlegend=True,
        legendrank=2
    ))

    # GDP-weighted average line (slightly transparent)
    fig.add_trace(go.Scatter(
        x=stats['year'],
        y=stats['w_avg'],
        mode='lines',
        name='Global (GDP-weighted)',
        line=dict(color='rgba(106, 27, 154, 0.6)', width=4),
        legendrank=1
    ))


    # Calculate period averages
    avg_2014_19 = stats[(stats['year'] >= 2014) & (stats['year'] <= 2019)]['w_avg'].mean()
    avg_2024_29 = stats[(stats['year'] >= 2024) & (stats['year'] <= 2029)]['w_avg'].mean()

    # Horizontal line for 2014-19 average
    fig.add_trace(go.Scatter(
        x=[2014, 2019],
        y=[avg_2014_19, avg_2014_19],
        mode='lines',
        name=f'2014-19 avg: {avg_2014_19:.1f}',
        line=dict(color='#00897B', width=4),
        showlegend=True,
        legendrank=3
    ))

    # Horizontal line for 2024-29 average
    fig.add_trace(go.Scatter(
        x=[2024, 2029],
        y=[avg_2024_29, avg_2024_29],
        mode='lines',
        name=f'2024-29 avg: {avg_2024_29:.1f}',
        line=dict(color='#E65100', width=4),
        showlegend=True,
        legendrank=4
    ))

    # Forecast horizon shading
    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0)

    # Layout
    fig.update_layout(
        template=chart_cfg['template'],
        width=CHART_SIZE,
        height=CHART_SIZE,
        margin=dict(t=50, b=40, l=50, r=20),
        font=dict(size=chart_cfg['font_size'] - 2),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(size=chart_cfg['legend']['font_size']),
            tracegroupgap=2
        )
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        dtick=5,
        tick0=2015,
        range=[2013.5, 2031.5],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        zeroline=True,
        zerolinecolor='black',
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size'])
    )

    return fig


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)

    df = load_data()

    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    print("Generating Global Primary Balance chart...")

    # Check data availability
    has_prim_bal = df['primary_balance'].notna().any() if 'primary_balance' in df.columns else False
    print(f"  primary_balance: {'available' if has_prim_bal else 'NOT available'}")

    # Calculate statistics
    stats = calculate_stats(df, 'primary_balance')
    print(f"  Stats calculated for {len(stats)} years")

    # Create chart
    fig = create_iq_band_chart(stats, chart_cfg)
    save_path = output_dir / 'global_primary_balance_by_group'
    pio.write_image(fig, f"{save_path}.png", format='png', engine='kaleido', scale=2)
    fig.write_html(f"{save_path}.html", auto_open=auto_open)
    print(f"  Saved global_primary_balance_by_group.png")

    # Export CSV
    csv_data = stats[['year', 'p25', 'p50', 'p75', 'w_avg']].copy()
    csv_data = csv_data.round(2)
    csv_path = output_dir / 'global_primary_balance.csv'
    csv_data.to_csv(csv_path, index=False)
    print(f"  Exported data to {csv_path}")

    print("Global Primary Balance chart complete.")


if __name__ == "__main__":
    main()
