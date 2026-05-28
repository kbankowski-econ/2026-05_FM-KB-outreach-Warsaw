"""
Summarize Bloomberg Sovereign Debt Dataset - Mega Annual Summary
====================================================================
Generates a consolidated comparison report of the sovereign debt dataset
across multiple historical snapshots stored in an Excel file.

Input:  Excel file with yearly snapshots as sheets
Output: {Country}_mega_summary.txt and several distribution plots
"""

import pandas as pd
import os
import argparse
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from fiscal_common import ensure_output_dir, load_config, resolve_project_path, load_chart_config

# --- Configuration & Metadata ---

COUNTRY_MAP = {
    'US': 'US_-Bloomberg-all.xlsx', 'UK': 'UK_all.xlsx',
    'Japan': 'Japan_all.xlsx', 'Germany': 'Germany_all.xlsx'
}

VARIABLE_DEFINITIONS = [
    ("COUNTRY", "Bloomberg 2-letter country code"), ("CRNCY", "Currency"),
    ("ISSUE_DT", "Issue Date"), ("MATURITY", "Maturity Date"),
    ("AMT_ISSUED", "Total Issued"), ("AMT_OUTSTANDING", "Amount Outstanding"),
    ("SECURITY_TYP", "Security Class"), ("CPN_TYP", "Coupon Structure"),
    ("CPN_FREQ", "Payment Frequency"), ("MTY_TYP", "Maturity Type"),
    ("TYPE_OF_BOND", "Bond Flavor"), ("MARKET_ISSUE", "Target Market"),
    ("CALLABLE", "Callable (Y/N)"), ("PUTABLE", "Putable (Y/N)"),
    ("SINKABLE", "Sinkable (Y/N)"), ("DEFAULTED", "Defaulted (Y/N)"),
    ("LONG_COMP_NAME", "Full Name")
]

PERIOD_BINS = {
    'issue': ([1900, 2000, 2005, 2010, 2015, 2020, 2025, 2030], 
              ['Before 2000', '2001-2005', '2006-2010', '2011-2015', '2016-2020', '2021-2025', '2026+']),
    'maturity': ([2010] + list(range(2011, 2031)) + [2040, 2050, 2060, 2100],
                 [str(y) for y in range(2011, 2031)] + ['2031-2040', '2041-2050', '2051-2060', '2061+']),
    'tenure': ([0, 0.25, 0.5, 1] + list(range(2, 11)) + list(range(15, 41, 5)) + [150],
               ['≤ 3 months', '3-6 months', '6-12 months'] + [f'{i-1}-{i} years' for i in range(2, 11)] + 
               [f'{i-5}-{i} years' for i in range(15, 41, 5)] + ['40+ years']),
    'residual': ([0, 0.25, 0.5, 1] + list(range(2, 11)) + list(range(15, 41, 5)) + [150],
                 ['≤ 3 months', '3-6 months', '6-12 months'] + [f'{i-1}-{i} years' for i in range(2, 11)] + 
                 [f'{i-5}-{i} years' for i in range(15, 41, 5)] + ['40+ years'])
}

# --- Core Data Functions ---

def load_bloomberg_data(filename: str, sheet_name: str, year_val: int):
    """Load and preprocess snapshot data, filtering out matured and noise items."""
    excel_path = resolve_project_path('data', 'fmData', filename)
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    df['ISSUE_DT'], df['MATURITY'] = pd.to_datetime(df['ISSUE_DT'], errors='coerce'), pd.to_datetime(df['MATURITY'], errors='coerce')
    df['original_tenure_years'] = (df['MATURITY'] - df['ISSUE_DT']).dt.days / 365.25
    snap_date = pd.Timestamp(year=year_val, month=12, day=31)
    df['residual_maturity_years'] = (df['MATURITY'] - snap_date).dt.days / 365.25
    
    matured_mask = df['MATURITY'] < snap_date
    clean_df = df[~matured_mask].copy()
    
    # Exclude benchmark-incompatible items
    strips_mask = clean_df['LONG_COMP_NAME'].str.contains('STRIP|When Issued', case=False, na=False)
    final_df = clean_df[~strips_mask].copy()
    
    print(f"Loaded {len(df):,} ({sheet_name}): Excluded {matured_mask.sum()} matured, {strips_mask.sum()} Strips/WI")
    return final_df, df[matured_mask].copy()

def get_binned_series(df: pd.DataFrame, bin_key: str, weight_col: Optional[str] = None):
    """Bin data based on defined periods and return sums (in billions) or counts."""
    bins, labels = PERIOD_BINS[bin_key]
    if bin_key == 'tenure': values = df['original_tenure_years']
    elif bin_key == 'residual': values = df['residual_maturity_years']
    elif bin_key == 'issue': values = df['ISSUE_DT'].dt.year
    else: values = df['MATURITY'].dt.year
    
    cat_series = pd.cut(values, bins=bins, labels=labels)
    if weight_col:
        res = df.groupby(cat_series, observed=False)[weight_col].sum() / 1e9
    else:
        res = cat_series.value_counts(dropna=False)
    
    res.index = res.index.map(lambda x: str(x) if pd.notna(x) else 'N/A')
    return res.groupby(level=0, observed=False).sum()

def calculate_weighted_avg(df: pd.DataFrame, val_col: str, weight_col: str = 'AMT_OUTSTANDING'):
    """Helper for weighted averages."""
    v = df.dropna(subset=[val_col, weight_col])
    return (v[val_col] * v[weight_col]).sum() / v[weight_col].sum() if not v.empty and v[weight_col].sum() > 0 else None

# --- Summary Generation ---

def add_table(output: List[str], title: str, year_dict: Dict[int, pd.Series], years: List[int], 
              top_n: Optional[int] = None, custom_sort: Optional[List[str]] = None):
    """Format a multi-year comparison table."""
    all_cats = set().union(*(s.index.tolist() for s in year_dict.values()))
    sorted_cats = [c for c in (custom_sort or []) if c in all_cats] + \
                  sorted([c for c in all_cats if c not in (custom_sort or [])], 
                         key=lambda x: year_dict.get(max(years), pd.Series()).get(x, 0), reverse=True)
    if top_n: sorted_cats = sorted_cats[:top_n]

    is_val = any(k in title for k in ["USD B", "Amt", "Outstanding"])
    is_pct = "%" in title or "Percent" in title
    cw, cat_w = 10, 35
    total_w = cat_w + (cw * len(years))
    
    output.extend(["-" * total_w, title, "-" * total_w, 
                   f"{'Category':<{cat_w}}" + "".join(f"{y:>{cw}}" for y in years), "-" * total_w])
    for cat in sorted_cats:
        row = f"{str(cat)[:cat_w-1]:<{cat_w}}"
        for y in years:
            v = year_dict[y].get(cat, 0)
            row += f"{f'{v:.1f}%' if is_pct else f'{v:,.0f}' if is_val else f'{v:,}':>{cw}}"
        output.append(row)
    
    total_row = f"{'TOTAL':<{cat_w}}"
    for y in years:
        v = year_dict[y].sum()
        total_row += f"{f'{v:.1f}%' if is_pct else f'{v:,.0f}' if is_val else f'{v:,}':>{cw}}"
    output.extend(["-" * total_w, total_row, ""])

def generate_mega_summary(dfs: Dict[int, pd.DataFrame], country: str):
    """Orchestrate the text summary generation with all original tables."""
    years = sorted(dfs.keys())
    output = ["=" * 100, f"BLOOMBERG {country.upper()} DEBT - MEGA ANNUAL SUMMARY", "=" * 100,
              f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
              f"Years included: {', '.join(map(str, years))}\n",
              "-" * 100, "VARIABLE DEFINITIONS", "-" * 100]
    for var, desc in VARIABLE_DEFINITIONS: output.append(f"  {var:<20} {desc}")
    output.append("")
    
    def process_series(col, mapper):
        res = {}
        for y, df in dfs.items():
            counts = df[col].value_counts(dropna=False)
            res[y] = counts.groupby(counts.index.map(mapper), observed=False).sum()
        return res

    # Categorical Breakdowns
    cats = [("COUNTRY", "BY COUNTRY (Top 30)", 30, lambda x: x if pd.notna(x) else 'N/A'),
            ("CRNCY", "CURRENCY (Top 15)", 15, lambda x: x if pd.notna(x) else 'N/A'),
            ("SECURITY_TYP", "SECURITY TYPE", None, lambda x: x if pd.notna(x) else 'N/A'),
            ("CPN_TYP", "COUPON TYPE", None, lambda x: x if pd.notna(x) else 'N/A'),
            ("MTY_TYP", "MATURITY TYPE", None, lambda x: x if pd.notna(x) else 'N/A'),
            ("TYPE_OF_BOND", "BOND FLAVOR", None, lambda x: x if pd.notna(x) else 'Plain Vanilla'),
            ("MARKET_ISSUE", "MARKET ISSUE", None, lambda x: x if pd.notna(x) else 'N/A')]
    for col, title, n, m in cats: add_table(output, title, process_series(col, m), years, top_n=n)

    # Status columns (Y/N)
    for col in ["CALLABLE", "PUTABLE", "SINKABLE", "DEFAULTED"]:
        m = lambda x: x if pd.notna(x) else ('N' if col != 'DEFAULTED' else 'N/A')
        add_table(output, f"{col} STATUS", process_series(col, m), years)

    # All Binning Breakdowns
    bins = [("issue", "ISSUE YEAR BREAKDOWN", None), ("maturity", "MATURITY YEAR (Count)", None),
            ("maturity", "MATURITY YEAR (USD B Outstanding)", 'AMT_OUTSTANDING'),
            ("tenure", "ORIGINAL TENURE (Count)", None), ("tenure", "ORIGINAL TENURE (USD B)", 'AMT_OUTSTANDING')]
    for key, title, weight in bins:
        add_table(output, title, {y: get_binned_series(df, key, weight) for y, df in dfs.items()}, years, custom_sort=PERIOD_BINS[key][1])

    # Tenure Percent & Average
    pct_ten = {y: (s := get_binned_series(df, 'tenure', 'AMT_OUTSTANDING')) / s.sum() * 100 for y, df in dfs.items()}
    add_table(output, "ORIGINAL TENURE (% Outstanding)", pct_ten, years, custom_sort=PERIOD_BINS['tenure'][1])
    
    total_w = 35 + (10 * len(years))
    output.extend(["-" * total_w, "WEIGHTED AVERAGE ORIGINAL TENURE (Years)", "-" * total_w])
    wa_ten_line = f"{'Avg Value':<35}"
    for y in years:
        wa = calculate_weighted_avg(dfs[y], 'original_tenure_years')
        wa_ten_line += f"{wa:>10.1f}" if wa is not None else f"{'N/A':>10}"
    output.extend([wa_ten_line, ""])

    # Residual Breakdowns
    for res_title, weight in [("RESIDUAL MATURITY (Count)", None), ("RESIDUAL MATURITY (USD B)", 'AMT_OUTSTANDING')]:
        add_table(output, res_title, {y: get_binned_series(df, 'residual', weight) for y, df in dfs.items()}, years, custom_sort=PERIOD_BINS['residual'][1])
    
    pct_res = {y: (s := get_binned_series(df, 'residual', 'AMT_OUTSTANDING')) / s.sum() * 100 for y, df in dfs.items()}
    add_table(output, "RESIDUAL MATURITY (% Outstanding)", pct_res, years, custom_sort=PERIOD_BINS['residual'][1])
    
    output.extend(["-" * total_w, "WEIGHTED AVERAGE RESIDUAL MATURITY (Years)", "-" * total_w])
    wa_res_line = f"{'Avg Value':<35}"
    for y in years:
        wa = calculate_weighted_avg(dfs[y], 'residual_maturity_years')
        wa_res_line += f"{wa:>10.1f}" if wa is not None else f"{'N/A':>10}"
    output.extend([wa_res_line, ""])

    return '\n'.join(output)

# --- Plotting ---

def update_axes(fig, cfg, row=None, col=None, show_y=True, is_uk=False, is_bar=False):
    """Set axis styling for line or bar charts."""
    k = dict(showgrid=cfg['axes']['showgrid'], gridcolor=cfg['axes'].get('gridcolor'),
             linecolor=cfg['axes']['linecolor'], linewidth=cfg['axes'].get('linewidth'),
             tickfont=dict(size=cfg['axes']['tickfont_size']))
    if row: k.update(row=row, col=col)
    
    # X-Axis Range & Ticks
    x_cfg = dict(tickvals=[2020, 2025], ticktext=['2020', '25'], range=[2015.8, 2026.2]) if is_bar else \
            dict(tickvals=[2015, 2020, 2025], ticktext=['2015', '2020', '2025'], range=[2011.8, 2026.2])
    fig.update_xaxes(**x_cfg, **k)
    
    # Y-Axis
    yk = {**k, 'zeroline': True, 'zerolinecolor': cfg['axes']['linecolor'], 'showticklabels': show_y}
    if is_uk:
        yk['showgrid'] = False
        fig.update_yaxes(secondary_y=True, **yk)
    else:
        fig.update_yaxes(**yk)

def save_fig(fig, cfg, path, auto_open, legend_y=1.15, top=80):
    """Apply layout and save."""
    from fiscal_common import get_chart_dims_px
    png_name = f"{Path(path).name}.png"
    try:
        width_px, height_px = get_chart_dims_px(png_name)
    except KeyError:
        width_px, height_px = cfg['width'], cfg['height']
    fig.update_layout(template=cfg['template'], width=width_px, height=height_px, font={"size": cfg['font_size']},
                      legend={**{k: v for k, v in cfg['legend'].items() if k != 'font_size'}, "y": legend_y, "x": 0.5, "xanchor": "center", "orientation": "h", "font": {"size": cfg['legend']['font_size']}},
                      margin=dict(t=top, b=40, l=0, r=0), showlegend=True)
    pio.write_image(fig, f"{path}.png", format='png', scale=2)
    pio.write_image(fig, f"{path}.svg", format='svg')
    fig.write_html(f"{path}.html", auto_open=auto_open, include_plotlyjs='cdn')

def plot_us_benchmark(dfs, out, auto_open):
    """Specific US Line Chart with Haver Bench."""
    years = sorted(dfs.keys())
    vals = [calculate_weighted_avg(dfs[y], 'residual_maturity_years') for y in years]
    cfg = load_chart_config()['styling']
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[y for y,v in zip(years, vals) if v], y=[v for v in vals if v], mode='lines', 
                             line=dict(color='#1a7f7f', width=cfg['line_widths']['thick']), name='Average maturity (US)'))
    
    hp = resolve_project_path('data', 'fmData', 'us_avg_maturity_quarterly.csv')
    if os.path.exists(hp):
        h = pd.read_csv(hp)
        h['dates'] = pd.to_datetime(h['dates'])
        q4 = h[h['dates'].dt.month == 10]
        fig.add_trace(go.Scatter(x=q4['dates'].dt.year, y=q4['PDAVGMQ@GOVFIN']/12, mode='lines',
                                 line=dict(color='#757575', width=cfg['line_widths']['standard'], dash='dash'), name='Haver benchmark'))
    
    update_axes(fig, cfg)
    save_fig(fig, cfg, out / "us_avg_residual_maturity", auto_open, 1.05, 30)

def plot_consolidated(all_dfs, out, val_col, fname, auto_open, is_bar=False):
    """Generate multi-country panels or merged line charts."""
    countries = sorted(['US', 'UK', 'Japan', 'Germany'])
    cfg = load_chart_config()['styling']
    
    if is_bar:
        fig = make_subplots(rows=1, cols=4, subplot_titles=countries, horizontal_spacing=0.02, shared_yaxes=True)
        colors = ['#311B92', '#7B1FA2', '#E1BEE7']
        m = {'≤ 3 months': 'Less than 1 year', '3-6 months': 'Less than 1 year', '6-12 months': 'Less than 1 year', '1-2 years': '1–2 years', '2-3 years': '2–4 years', '3-4 years': '2–4 years'}
        
        for i, c in enumerate(countries):
            rows = []
            for y in sorted(all_dfs[c].keys()):
                if y < 2016: continue
                s = get_binned_series(all_dfs[c][y], val_col, 'AMT_OUTSTANDING')
                row = {'y': y, 'Less than 1 year': 0.0, '1–2 years': 0.0, '2–4 years': 0.0}
                for cat, v in s.items():
                    if m.get(cat): row[m[cat]] += (v / s.sum() * 100)
                rows.append(row)
            if not rows: continue
            df = pd.DataFrame(rows)
            for j, cat in enumerate(['Less than 1 year', '1–2 years', '2–4 years']):
                fig.add_trace(go.Bar(name=cat, x=df['y'], y=df[cat], marker_color=colors[j], 
                                     showlegend=(i==0), legendrank=100-j), row=1, col=i+1)
            update_axes(fig, cfg, 1, i+1, i==0, False, True)
        
        fig.update_layout(barmode='stack')
        for a in fig['layout']['annotations']: a['font'] = dict(size=cfg['axes']['tickfont_size'])
        save_fig(fig, cfg, out / fname, auto_open)

        # CSV export: stacked bar data for each country
        csv_rows = []
        for c_name in countries:
            for y in sorted(all_dfs[c_name].keys()):
                if y < 2016: continue
                s = get_binned_series(all_dfs[c_name][y], val_col, 'AMT_OUTSTANDING')
                row = {'Country': c_name, 'Year': y, 'Less than 1 year': 0.0, '1–2 years': 0.0, '2–4 years': 0.0}
                for cat, v in s.items():
                    if m.get(cat): row[m[cat]] += (v / s.sum() * 100)
                csv_rows.append(row)
        if csv_rows:
            csv_df = pd.DataFrame(csv_rows).round(2)
            csv_df.to_csv(out / f"{fname}.csv", index=False)
    else:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        colors = ['#1a7f7f', '#e6550d', '#31a354', '#756bb1']
        for i, c in enumerate(countries):
            yrs = sorted(all_dfs[c].keys())
            vals = [calculate_weighted_avg(all_dfs[c][y], val_col) for y in yrs]
            fig.add_trace(go.Scatter(x=[y for y,v in zip(yrs, vals) if v], y=[v for v in vals if v], mode='lines', 
                                     line=dict(color=colors[i], width=cfg['line_widths']['thick']), name=f"{c} (rhs)" if c=='UK' else c), secondary_y=(c=='UK'))
        update_axes(fig, cfg)
        update_axes(fig, cfg, is_uk=True)
        save_fig(fig, cfg, out / fname, auto_open)

# --- Execution ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--country')
    args = parser.parse_args()
    out = ensure_output_dir(load_config())
    
    def process(c, f):
        return process_country_data(c, f, out)

    if args.country:
        process(args.country, COUNTRY_MAP[args.country])
    else:
        all_dfs = {c: process(c, f) for c, f in COUNTRY_MAP.items()}
        all_dfs = {k: v for k, v in all_dfs.items() if v}
        plot_consolidated(all_dfs, out, 'tenure', "sovereign_tenure_dist_panel", True, True)

def process_country_data(c, f, out):
    path = resolve_project_path('data', 'fmData', f)
    if not os.path.exists(path): return None
    xl = pd.ExcelFile(path)
    dfs, filts = {}, {}
    for s in xl.sheet_names:
        try:
            y = int(s)
            dfs[y], filts[y] = load_bloomberg_data(f, s, y)
        except: pass
    if not dfs: return None
    
    return dfs

if __name__ == "__main__": main()
