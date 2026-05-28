"""
Generate highlighted panel charts for 2x1 (overall balance + gross debt)
by income group. For each group, the corresponding line is full-opacity
while the others fade to a light backdrop.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from fiscal_common import (
    load_config, resolve_from_config, ensure_output_dir,
    load_chart_config, get_chart_dims_px,
)


# Series: (name, filter_type, filter_value, color, width, legendrank)
SERIES_INCOME = [
    ('China', 'isocode', 'CHN', '#E53935', 3, 2),
    ('USA', 'isocode', 'USA', '#00897B', 3, 3),
    ('Advanced Economies excl. USA', 'ifscode', 9994, '#1E88E5', 2.5, 4),
    ('Emerging Markets excl. China', 'ifscode', 9995, '#FF9800', 2.5, 5),
    ('Low-Income Developing Countries', 'ifscode', 9993, '#795548', 2.5, 6),
    ('Global', 'ifscode', 9999, '#6A1B9A', 6, 1),
]


def hex_to_rgba(hex_color, opacity=1.0):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {opacity})'


def add_series(fig, data, var_name, show_legend, name, color, width, legendrank, opacity, row, col):
    plot_data = data[data[var_name].notna()]
    if plot_data.empty:
        return
    line_color = hex_to_rgba(color, opacity) if opacity < 1.0 else color
    fig.add_trace(go.Scatter(
        x=plot_data['year'], y=plot_data[var_name],
        mode='lines', name=name,
        line=dict(color=line_color, width=width),
        showlegend=show_legend, legendgroup=name, legendrank=legendrank,
    ), row=row, col=col)
    marker_data = plot_data[plot_data['year'].isin([2025, 2031])]
    if not marker_data.empty:
        ms = 8 + width
        mw = width * 0.6
        fig.add_trace(go.Scatter(
            x=marker_data['year'], y=marker_data[var_name],
            mode='markers',
            marker=dict(symbol='circle-open', size=ms, color=line_color, line=dict(width=mw, color=line_color)),
            showlegend=False, legendgroup=name,
        ), row=row, col=col)


def create_panel_chart(df, chart_cfg, png_name, highlight_name):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        subplot_titles=("Overall Balance", "Gross Debt"),
    )

    for name, filter_type, filter_value, color, width, legendrank in SERIES_INCOME:
        if filter_type == 'ifscode':
            data = df[df['ifscode'] == filter_value].copy()
        else:
            data = df[df['isocode'] == filter_value].copy()
        data = data[data['year'].between(2015, 2031)].sort_values('year')
        opacity = 1.0 if (highlight_name is None or name == highlight_name) else 0.15
        add_series(fig, data, 'ggxcnl_gdp', True, name, color, width, legendrank, opacity, 1, 1)
        add_series(fig, data, 'ggxwdg_gdp', False, name, color, width, legendrank, opacity, 2, 1)

    fig.add_vrect(x0=2025.5, x1=2031.5, fillcolor="rgba(128, 128, 128, 0.3)", layer="below", line_width=0)

    w_px, h_px = get_chart_dims_px(png_name)
    fig.update_layout(
        template=chart_cfg['template'],
        width=w_px, height=h_px,
        margin=dict(t=85, b=30, l=40, r=15),
        font=dict(size=chart_cfg['axes']['tickfont_size']),
        showlegend=True,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.10, xanchor='center', x=0.5,
            font=dict(size=chart_cfg['legend']['font_size']), tracegroupgap=0,
        ),
    )
    for a in fig.layout.annotations:
        a.font.size = chart_cfg['axes']['tickfont_size']

    fig.update_xaxes(
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        tickmode='array',
        tickvals=[2015, 2020, 2025, 2030],
        ticktext=['2015', '20', '25', '30'],
        range=[2014.5, 2031.5],
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    )
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_yaxes(
        showgrid=True, gridcolor=chart_cfg['axes'].get('gridcolor', '#E0E0E0'),
        zeroline=True, zerolinecolor='black',
        linecolor=chart_cfg['axes']['linecolor'],
        linewidth=chart_cfg['axes'].get('linewidth', 1.5),
        ticks=chart_cfg['axes']['ticks'],
        tickfont=dict(size=chart_cfg['axes']['tickfont_size']),
    )
    return fig


def main():
    config = load_config()
    chart_cfg = load_chart_config()['styling']
    output_dir = ensure_output_dir(config)
    data_path = resolve_from_config("../data/fmData/WEO_enhanced.dta")
    auto_open = config.get("output_settings", {}).get("auto_open_html", False)

    df = pd.read_stata(data_path)

    for name, *_ in SERIES_INCOME:
        if name == 'Global':
            continue
        safe_name = name.replace(' ', '_').replace('.', '')
        base = f'global_overall_balance_{safe_name}'
        fig = create_panel_chart(df, chart_cfg, f"{base}.png", highlight_name=name)
        pio.write_image(fig, output_dir / f'{base}.png', format='png', engine='kaleido', scale=2)
        pio.write_image(fig, output_dir / f'{base}.svg', format='svg', engine='kaleido', scale=2)
        fig.write_html(output_dir / f'{base}.html', auto_open=auto_open, include_plotlyjs='cdn')
        print(f"Saved {base}.png")


if __name__ == "__main__":
    main()
