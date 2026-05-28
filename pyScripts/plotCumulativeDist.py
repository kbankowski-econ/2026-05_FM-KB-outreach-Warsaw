import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from fiscal_common import (
    load_config, resolve_from_config, ensure_output_dir,
    load_chart_config, get_chart_dims_px,
)


def get_cdf_data(df_full, var, start_yr, end_yr):
    mask = (df_full['year'] >= start_yr) & (df_full['year'] <= end_yr)
    agg_codes = [9991, 9992, 9993, 9999]
    subset = df_full[mask & (~df_full['ifscode'].isin(agg_codes))]
    avg_vals = subset.groupby('isocode')[var].mean().dropna().sort_values()
    if avg_vals.empty:
        return None, None
    n = len(avg_vals)
    y = np.linspace(1 / n, 1, n) * 100
    return avg_vals.values, y


def get_global_aggregate(df_full, var, start_yr, end_yr):
    mask = (df_full['year'] >= start_yr) & (df_full['year'] <= end_yr)
    g = df_full[mask & (df_full['ifscode'] == 9999)]
    return None if g.empty else g[var].mean()


def get_country_value(df_full, var, ifscode, start_yr, end_yr):
    mask = (df_full['year'] >= start_yr) & (df_full['year'] <= end_yr)
    c = df_full[mask & (df_full['ifscode'] == ifscode)]
    return None if c.empty else c[var].mean()


POLAND_IFSCODE = 964
POLAND_COLOR = '#4DB6AC'        # teal - 2024-29 (current), consistent with other slides
POLAND_COLOR_LIGHT = '#80CBC4'  # lighter teal - 2014-19 (historical)
POLAND_COLOR_DARK = '#00796B'
POLAND_BG = 'rgba(178, 223, 219, 0.5)'
POLAND_BG_LIGHT = 'rgba(178, 223, 219, 0.32)'


def find_y_at_x(x_arr, y_arr, target_x):
    if target_x is None:
        return None
    idx = np.searchsorted(x_arr, target_x)
    if idx == 0:
        return y_arr[0]
    if idx >= len(x_arr):
        return y_arr[-1]
    return y_arr[idx - 1]


HIST_COLOR = '#757575'       # neutral gray for 2014-19
FC_COLOR = '#6A1B9A'         # purple primary for 2024-29


def build_chart(df, var, label, png_name, chart_cfg, x_range=None):
    x24, y24 = get_cdf_data(df, var, 2024, 2029)
    x14, y14 = get_cdf_data(df, var, 2014, 2019)
    if x24 is None or x14 is None:
        return None, None

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x14, y=y14, mode='lines', name='2014–19 average',
        line=dict(color=HIST_COLOR, width=chart_cfg['line_widths']['standard']),
    ))
    fig.add_trace(go.Scatter(
        x=x24, y=y24, mode='lines', name='2024–29 average',
        line=dict(color=FC_COLOR, width=chart_cfg['line_widths']['thick']),
    ))

    if x24.min() < 0 < x24.max():
        fig.add_vline(x=0, line_dash='dash', line_color='gray', opacity=0.8)

    median_24 = float(np.median(x24))
    median_14 = float(np.median(x14))
    global_24 = get_global_aggregate(df, var, 2024, 2029)
    global_14 = get_global_aggregate(df, var, 2014, 2019)
    y_global_24 = find_y_at_x(x24, y24, global_24)
    y_global_14 = find_y_at_x(x14, y14, global_14)

    fig.add_trace(go.Scatter(
        x=[median_14], y=[50], mode='markers',
        marker=dict(symbol='circle-open', size=10, color=HIST_COLOR, line=dict(width=2)),
        showlegend=False, hoverinfo='skip',
    ))
    fig.add_trace(go.Scatter(
        x=[median_24], y=[50], mode='markers',
        marker=dict(symbol='circle-open', size=12, color=FC_COLOR, line=dict(width=2.5)),
        showlegend=False, hoverinfo='skip',
    ))
    if global_14 is not None:
        fig.add_trace(go.Scatter(
            x=[global_14], y=[y_global_14], mode='markers',
            marker=dict(symbol='diamond-open', size=10, color=HIST_COLOR, line=dict(width=2)),
            showlegend=False, hoverinfo='skip',
        ))
    if global_24 is not None:
        fig.add_trace(go.Scatter(
            x=[global_24], y=[y_global_24], mode='markers',
            marker=dict(symbol='diamond-open', size=12, color=FC_COLOR, line=dict(width=2.5)),
            showlegend=False, hoverinfo='skip',
        ))

    ann_font = chart_cfg['legend']['font_size']
    right = dict(xanchor='left', xshift=10, yanchor='middle')
    left = dict(xanchor='right', xshift=-10, yanchor='middle')
    if var == 'primary_balance':
        mdn_24, mdn_14 = left, right
        wtd_24, wtd_14 = right, right
    else:
        mdn_24, mdn_14 = right, left
        wtd_24, wtd_14 = right, left

    FC_BG = 'rgba(206, 147, 216, 0.28)'   # pale purple tint
    HIST_BG = 'rgba(200, 200, 200, 0.35)'  # pale gray tint
    fig.add_annotation(x=median_24, y=50, text=f"Median:<br>{median_24:.1f}%", showarrow=False,
                       font=dict(size=ann_font, color=FC_COLOR),
                       bgcolor=FC_BG, borderwidth=0, **mdn_24)
    fig.add_annotation(x=median_14, y=50, text=f"Median:<br>{median_14:.1f}%", showarrow=False,
                       font=dict(size=ann_font, color=HIST_COLOR),
                       bgcolor=HIST_BG, borderwidth=0, **mdn_14)
    if global_24 is not None:
        fig.add_annotation(x=global_24, y=y_global_24, text=f"Weighted:<br>{global_24:.1f}%", showarrow=False,
                           font=dict(size=ann_font, color=FC_COLOR),
                           bgcolor=FC_BG, borderwidth=0, **wtd_24)
    if global_14 is not None:
        fig.add_annotation(x=global_14, y=y_global_14, text=f"Weighted:<br>{global_14:.1f}%", showarrow=False,
                           font=dict(size=ann_font, color=HIST_COLOR),
                           bgcolor=HIST_BG, borderwidth=0,
                           **{**wtd_14, 'yshift': -15})

    w_px, h_px = get_chart_dims_px(png_name)
    legend_cfg = {
        **{k: v for k, v in chart_cfg['legend'].items() if k != 'font_size'},
        'y': 1.08, 'x': 0.5,
        'font': {'size': chart_cfg['legend']['font_size']},
        'bgcolor': 'rgba(255,255,255,0)',
    }
    fig.update_layout(
        template=chart_cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=50, b=35, l=50, r=30),
        font=dict(size=chart_cfg['font_size']),
        legend=legend_cfg,
    )
    fig.update_xaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        title=dict(text="(Percent of GDP)", font=dict(size=chart_cfg['axes']['tickfont_size'])),
        range=x_range if x_range else [
            float(np.percentile(x24, 10) - (np.percentile(x24, 90) - np.percentile(x24, 10)) * 0.1),
            float(np.percentile(x24, 90) + (np.percentile(x24, 90) - np.percentile(x24, 10)) * 0.1),
        ],
    )
    fig.update_yaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        range=[0, 105],
    )

    summary_df = pd.DataFrame({
        f'{label} 2014–19 (value)': pd.Series(x14),
        f'{label} 2014–19 (cumulative share)': pd.Series(y14),
        f'{label} 2024–29 (value)': pd.Series(x24),
        f'{label} 2024–29 (cumulative share)': pd.Series(y24),
    }).round(2)
    return fig, summary_df


def add_panel(fig, df_full, var, label, chart_cfg, col_idx, x_range=None):
    """Add CDF traces to a subplot column."""
    x24, y24 = get_cdf_data(df_full, var, 2024, 2029)
    x14, y14 = get_cdf_data(df_full, var, 2014, 2019)
    if x24 is None or x14 is None:
        return

    fig.add_trace(go.Scatter(
        x=x14, y=y14, mode='lines', name='2014–19 average',
        line=dict(color=HIST_COLOR, width=chart_cfg['line_widths']['standard']),
        legendgroup='hist', showlegend=(col_idx == 1),
    ), row=1, col=col_idx)
    fig.add_trace(go.Scatter(
        x=x24, y=y24, mode='lines', name='2024–29 average',
        line=dict(color=FC_COLOR, width=chart_cfg['line_widths']['thick']),
        legendgroup='fc', showlegend=(col_idx == 1),
    ), row=1, col=col_idx)

    if x24.min() < 0 < x24.max():
        fig.add_vline(x=0, line_dash='dash', line_color='gray', opacity=0.8, row=1, col=col_idx)

    median_24 = float(np.median(x24))
    median_14 = float(np.median(x14))
    global_24 = get_global_aggregate(df_full, var, 2024, 2029)
    global_14 = get_global_aggregate(df_full, var, 2014, 2019)

    fig.add_trace(go.Scatter(
        x=[median_14], y=[50], mode='markers',
        marker=dict(symbol='circle-open', size=10, color=HIST_COLOR, line=dict(width=2)),
        showlegend=False, hoverinfo='skip',
    ), row=1, col=col_idx)
    fig.add_trace(go.Scatter(
        x=[median_24], y=[50], mode='markers',
        marker=dict(symbol='circle-open', size=12, color=FC_COLOR, line=dict(width=2.5)),
        showlegend=False, hoverinfo='skip',
    ), row=1, col=col_idx)

    y_g14 = find_y_at_x(x14, y14, global_14) if global_14 is not None else None
    y_g24 = find_y_at_x(x24, y24, global_24) if global_24 is not None else None

    if global_14 is not None:
        fig.add_trace(go.Scatter(
            x=[global_14], y=[y_g14], mode='markers',
            marker=dict(symbol='diamond-open', size=10, color=HIST_COLOR, line=dict(width=2)),
            showlegend=False, hoverinfo='skip',
        ), row=1, col=col_idx)
    if global_24 is not None:
        fig.add_trace(go.Scatter(
            x=[global_24], y=[y_g24], mode='markers',
            marker=dict(symbol='diamond-open', size=12, color=FC_COLOR, line=dict(width=2.5)),
            showlegend=False, hoverinfo='skip',
        ), row=1, col=col_idx)

    # Annotations
    ann_font = 10
    FC_BG = 'rgba(206, 147, 216, 0.28)'
    HIST_BG = 'rgba(200, 200, 200, 0.35)'
    right = dict(xanchor='left', xshift=10, yanchor='middle')
    left = dict(xanchor='right', xshift=-10, yanchor='middle')
    if var == 'primary_balance':
        mdn_24, mdn_14 = left, right
        wtd_24, wtd_14 = right, right
    else:
        mdn_24, mdn_14 = right, left
        wtd_24, wtd_14 = right, left

    xref = f"x{col_idx}" if col_idx > 1 else "x"
    yref = f"y{col_idx}" if col_idx > 1 else "y"
    fig.add_annotation(x=median_24, y=50, text=f"Median:<br>{median_24:.1f}%", showarrow=False,
                       xref=xref, yref=yref,
                       font=dict(size=ann_font, color=FC_COLOR),
                       bgcolor=FC_BG, borderwidth=0, **mdn_24)
    fig.add_annotation(x=median_14, y=50, text=f"Median:<br>{median_14:.1f}%", showarrow=False,
                       xref=xref, yref=yref,
                       font=dict(size=ann_font, color=HIST_COLOR),
                       bgcolor=HIST_BG, borderwidth=0, **mdn_14)
    if global_24 is not None:
        fig.add_annotation(x=global_24, y=y_g24, text=f"Weighted:<br>{global_24:.1f}%", showarrow=False,
                           xref=xref, yref=yref,
                           font=dict(size=ann_font, color=FC_COLOR),
                           bgcolor=FC_BG, borderwidth=0, yshift=-15, **wtd_24)
    wtd14_yshift = 15 if var != 'primary_balance' else -15
    if global_14 is not None:
        fig.add_annotation(x=global_14, y=y_g14, text=f"Weighted:<br>{global_14:.1f}%", showarrow=False,
                           xref=xref, yref=yref,
                           font=dict(size=ann_font, color=HIST_COLOR),
                           bgcolor=HIST_BG, borderwidth=0,
                           **{**wtd_14, 'yshift': wtd14_yshift})

    # Poland - shown alongside median/weighted for both periods.
    # For primary balance, place both Poland labels above their markers.
    if var == 'primary_balance':
        pol_above = dict(xanchor='center', xshift=0, yanchor='bottom')
        pol_kw_14 = {**pol_above, 'yshift': 24}
        pol_kw_24 = {**pol_above, 'yshift': 10}
    elif var in ('ggei_gdp', 'ggxwdg_gdp'):
        # Interest payments & government debt: 2014-19 top-left, 2024-29 bottom-right
        pol_kw_14 = dict(xanchor='right', xshift=-8, yanchor='bottom', yshift=8)
        pol_kw_24 = dict(xanchor='left', xshift=8, yanchor='top', yshift=-8)
    else:
        pol_kw_14 = {**right, 'yshift': -22}
        pol_kw_24 = {**right, 'yshift': 22}

    poland_14 = get_country_value(df_full, var, POLAND_IFSCODE, 2014, 2019)
    if poland_14 is not None:
        y_pol14 = find_y_at_x(x14, y14, poland_14)
        fig.add_trace(go.Scatter(
            x=[poland_14], y=[y_pol14], mode='markers',
            marker=dict(symbol='star', size=11, color=POLAND_COLOR_LIGHT,
                        line=dict(width=1, color=POLAND_COLOR_DARK)),
            name='Poland (2014–19)', legendgroup='pol14', showlegend=False,
            hoverinfo='skip',
        ), row=1, col=col_idx)
        fig.add_annotation(x=poland_14, y=y_pol14, text=f"Poland:<br>{poland_14:.1f}%", showarrow=False,
                           xref=xref, yref=yref,
                           font=dict(size=ann_font, color=POLAND_COLOR_DARK),
                           bgcolor=POLAND_BG_LIGHT, borderwidth=0,
                           **pol_kw_14)

    poland_24 = get_country_value(df_full, var, POLAND_IFSCODE, 2024, 2029)
    if poland_24 is not None:
        y_pol = find_y_at_x(x24, y24, poland_24)
        fig.add_trace(go.Scatter(
            x=[poland_24], y=[y_pol], mode='markers',
            marker=dict(symbol='star', size=14, color=POLAND_COLOR,
                        line=dict(width=1.2, color=POLAND_COLOR_DARK)),
            name='Poland (2024–29)', legendgroup='pol', showlegend=False,
            hoverinfo='skip',
        ), row=1, col=col_idx)
        fig.add_annotation(x=poland_24, y=y_pol, text=f"Poland:<br>{poland_24:.1f}%", showarrow=False,
                           xref=xref, yref=yref,
                           font=dict(size=ann_font, color=POLAND_COLOR_DARK),
                           bgcolor=POLAND_BG, borderwidth=0,
                           **pol_kw_24)

    if x_range is None:
        p10, p90 = np.percentile(x24, 10), np.percentile(x24, 90)
        pad = (p90 - p10) * 0.1
        x_range = [float(p10 - pad), float(p90 + pad)]
    fig.update_xaxes(range=x_range, row=1, col=col_idx)


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    output_dir = ensure_output_dir(config)
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    df = pd.read_stata(data_path)

    panels = [
        ('primary_balance', 'Primary Balance'),
        ('ggei_gdp', 'Interest Payments'),
        ('ggxwdg_gdp', 'Government Debt'),
    ]

    fig = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.08,
        subplot_titles=[label for _, label in panels],
    )

    for col_idx, (var, label) in enumerate(panels, start=1):
        add_panel(fig, df, var, label, chart_cfg, col_idx)

    w_px, h_px = get_chart_dims_px("cumulative_dist_panel.png")
    fig.update_layout(
        template=chart_cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=60, b=50, l=50, r=20),
        font=dict(size=chart_cfg['font_size']),
        legend=dict(
            **{k: v for k, v in chart_cfg['legend'].items() if k not in ('font_size', 'y')},
            y=1.15,
            font=dict(size=chart_cfg['legend']['font_size']),
        ),
    )
    # Only resize subplot titles (first 3 annotations), not the data annotations
    for a in list(fig.layout.annotations)[:3]:
        a.font.size = chart_cfg['axes']['tickfont_size']

    fig.update_xaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        title=dict(text="(Percent of GDP)", font=dict(size=chart_cfg['axes']['tickfont_size'])),
    )
    fig.update_yaxes(
        showgrid=chart_cfg['axes']['showgrid'],
        gridcolor=chart_cfg['axes']['gridcolor'],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes']['linewidth'],
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
        range=[0, 105],
        title=dict(text="(Cumulative share, percent)", font=dict(size=chart_cfg['axes']['tickfont_size'])),
    )

    base = "cumulative_dist_panel"
    pio.write_image(fig, output_dir / f"{base}.png", format='png', engine='kaleido', scale=2)
    pio.write_image(fig, output_dir / f"{base}.svg", format='svg', engine='kaleido', scale=2)
    fig.write_html(output_dir / f"{base}.html", auto_open=auto_open, include_plotlyjs='cdn')
    print(f"Saved {base}.png")


if __name__ == "__main__":
    main()
