# FM-KB Outreach — Warsaw (May 2026)

Chart-production pipeline for the IMF **Fiscal Monitor** outreach presentation
delivered in Warsaw (Polish fiscal council), May 2026. The repository turns raw
source data (WEO / Fiscal Monitor database, Bloomberg, Haver, US Treasury, and a
handful of bespoke spreadsheets) into the figures that populate the slide deck,
plus the supporting CSVs and interactive HTML versions of each chart.

Everything that defines *what charts exist* — which slide each one belongs to,
its title and footnotes, which script produces it, and the exact size it must be
rendered at — lives in a single manifest:

> ### 📌 [`pyScripts/chartTable.csv`](pyScripts/chartTable.csv) is the source of truth.

Read that file (or the catalog below) and you know the entire deck. The Python
scripts are just the machinery that fills it in.

---

## `chartTable.csv` — the chart manifest

One row per slide element. Chart slides point at a `.png`; text/recommendation
slides point at a `.md` or carry no output. Columns:

| Column | Meaning |
| --- | --- |
| `id` | Slide identifier and position, e.g. `slide_5_left`, `slide_13`. |
| `SlideHeading` | The headline shown on the slide (shared across left/middle/right panels of the same slide). |
| `pngFile` | Output image path for the chart (the file the generating script writes). |
| `task` | The `invoke` task that produces this chart (see [`pyScripts/tasks.py`](pyScripts/tasks.py)). Blank for text slides and the two diagram slides. |
| `Title` | Chart title (panel title within the figure). |
| `Subtitle` | Units line, e.g. `(Percent of GDP)`. |
| `Sources` | Source attribution printed under the chart. |
| `Notes` | Footnote / methodology note. |
| `Width`, `Height` | Rendered chart size **in centimetres**. |

### Why the manifest is central

The `Width`/`Height` columns are not documentation — they are consumed at render
time. Each chart script calls `get_chart_dims_px(<png filename>)` in
[`pyScripts/fiscal_common.py`](pyScripts/fiscal_common.py), which looks the file
up in `chartTable.csv` (by basename), reads its `Width`/`Height` in cm, and
converts to pixels at 96 DPI. So the manifest drives the actual canvas geometry of
the produced figures. (A malformed value here renders a broken chart — keep the
dimensions clean.)

`tasks.py` is ordered to match the slide sequence in this file, and `run-all`
executes the chart tasks in that order.

---

## Chart catalog

Generated charts, in slide order. Output files land in [`docu/`](docu/) as
`.png` + `.svg` + interactive `.html` + a data `.csv`.

| Slide | Chart | Task | Output (`docu/…`) | Size (cm) |
| --- | --- | --- | --- | --- |
| `slide_2_left` | Global Policy Uncertainty Indices | `plotUncertainty` | `uncertainty_plot.png` | 15×10 |
| `slide_2_right` | Government Deficit Effects during Energy Price Booms | `analyzeFoodEnergyBooms` | `food_energy_boom_deficit_count.png` | 15×10 |
| `slide_3` | Global Macroeconomic and Fiscal Outlook | `plotGlobalOutlook` | `global_outlook_panel.png` | 32×10 |
| `slide_4` | Cost of Government Debt Financing and Primary Balance | `plotGlobalInterestRates` | `global_interest_rates_panel.png` | 32×10 |
| `slide_5_left` | Long-Term Bond Yields in Advanced Economies | `plotInterestRates` | `interest_rates_plot.png` | 15×10 |
| `slide_5_right` | Term Spreads in Selected Advanced Economies | `plotTermPremia` | `term_premia_plot.png` | 15×10 |
| `slide_6_left` | Drivers of the Increase in Government Debt: Global and Poland | `plotGlobeDebtWaterfall` | `globe_debt_decomposition_waterfall_2025-31.png` | 15×10 |
| `slide_6_right` | Country Decomposition of the Increase in Global Government Debt | `plotCountryDebtWaterfall` | `global_debt_country_decomposition_waterfall.png` | 15×10 |
| `slide_7_left` | Overall Balance Across Selected Economies and Country Groups | `plotChinaUSDominance` | `overall_balance_by_group.png` | 15×10 |
| `slide_7_right` | Global Government Debt Evolution | `plotChinaUSDominance` | `gross_debt_global_ver3.png` | 15×10 |
| `slide_8_left` | Evolution of Ownership of Global Debt | `plotDebtOwnership` | `debt_ownership_plot.png` | 15×10 |
| `slide_8_right` | Short-Term Debt in Advanced Economies | `summarizeBloombergCountryDebt` | `sovereign_tenure_dist_panel.png` | 15×10 |
| `slide_10` | Global Cumulative Distribution of Main Fiscal Indicators | `plotCumulativeDist` | `cumulative_dist_panel.png` | 32×10 |
| `slide_11_left` | Change in Global Fiscal Gap, Factor Decomposition | `plotAdjustmentWaterfall` | `adjustmentNeeded_waterfall_global_2014-19_vs_2024-29.png` | 15×10 |
| `slide_11_right` | Change in Global Fiscal Gap, Country Decomposition | `plotCountryDecomposition` | `fiscalSpace_change_by_country_2014-19_vs_2024-29.png` | 15×10 |
| `slide_12` | Change in Fiscal Gap in Selected Countries | `plotAdjustmentWaterfallMultCountry` | `adjustmentNeeded_waterfall_multi_2014-19_vs_2024-29.png` | 32×10 |
| `slide_13` | Poland: Fiscal Variables and Debt Dynamics | `plotMutliVarPoland` | `poland_fiscal_variables_panel.png` | 32×12 |
| `slide_15_left` | Fiscal Overview: US | `plotGlobalOverallBalance` | `global_overall_balance_USA.png` | 10×10 |
| `slide_15_middle` | Evolution of US Customs Revenue | `customDutiesUS` | `customs_duties_plot.png` | 10×10 |
| `slide_15_right` | Impact of the One Big Beautiful Bill Act on the US Fiscal Deficit | `plotOBBBFiscalEffects` | `obbb_fiscal_effects.png` | 10×10 |
| `slide_16_left` | Fiscal Overview: China | `plotGlobalOverallBalance` | `global_overall_balance_China.png` | 10×10 |
| `slide_16_middle` | Issuance and Redemptions of Government Debt in China | `plotChinaDebtSwap` | `chn_debt_swap.png` | 10×10 |
| `slide_16_right` | Evolution of the Fiscal Balance, 2015–31 | `plotFiscalStance` | `fiscal_stance_usa_chn.png` | 10×10 |
| `slide_17_left` | Fiscal Overview: Advanced Economies excl. US | `plotGlobalOverallBalance` | `global_overall_balance_Advanced_Economies_excl_USA.png` | 10×10 |
| `slide_17_middle` | Japan Debt Dynamics: Snowball Decomposition | `plotSnowballAE` | `ae_snowball_japan_panel_10x10.png` | 10×10 |
| `slide_17_right` | Rigidity of Functional Spending Categories in Europe | `plotDefenseSpendingAutocorr` | `defense_spending_autocorr.png` | 10×10 |
| `slide_18_left` | Fiscal Overview: Emerging Markets excl. China | `plotGlobalOverallBalance` | `global_overall_balance_Emerging_Markets_excl_China.png` | 10×10 |
| `slide_18_middle` | Issuance of Sovereign Bonds by Emerging Markets | `plotBondRadar` | `1_vol_combined_em_10x10.png` | 10×10 |
| `slide_18_right` | Compression in Emerging Market Bond Index Spreads | `plotEMSpreadsWaterfall` | `em_spreads_waterfall.png` | 10×10 |
| `slide_19_left` | Fiscal Overview: Low-Income Developing Countries | `plotGlobalOverallBalance` | `global_overall_balance_Low-Income_Developing_Countries.png` | 10×10 |
| `slide_19_middle` | Interest Payments in Low-Income Developing Countries | `plotLowIncomeInterestRev` | `low_income_interest_revenue_ratio.png` | 10×10 |
| `slide_19_right` | Official Development Assistance Flows | `plotODAflows` | `oda_flows_grouped.png` | 10×10 |
| `slide_21_left` | Global Public Debt-at-Risk | `plotDaR` | `debt_at_risk_density.png` | 10×10 |
| `slide_21_middle` | Change in Debt-at-Risk: Severe Middle East War Scenario | `plotDaR` | `debt_at_risk_adverse.png` | 10×10 |
| `slide_21_right` | Change in Debt-at-Risk: AI Investment Shock Scenario | `plotDaR` | `debt_at_risk_ai.png` | 10×10 |
| `slide_22_left` | Convenience Yield of US Treasuries | `plotConvenienceYield` | `convenience_yield_daily.png` | 15×10 |
| `slide_22_right` | International Convenience Yield versus G10 Sovereign Bonds | `plotConvenienceYield` | `convenience_yield_medians.png` | 15×10 |
| `slide_23` | Simulated Debt-to-GDP Change after a Short-Term Borrowing Cost Increase | `plotDebtRollover` | `debt_rollover_simulation.png` | 32×10 |
| `slide_24` | International Spillovers from Shocks to US Treasury Supply | `plotTreasurySpillovers` | `treasury_spillovers.png` | 32×10 |
| `slide_25_left` | Top Fiscal Risks in IMF Staff Reports — Advanced Economies | `plotAEFiscalRisks` | `ae_fiscal_risks.png` | 15×10 |
| `slide_25_right` | Top Fiscal Risks in IMF Staff Reports — EMDEs | `plotEMDEFiscalRisks` | `emde_fiscal_risks.png` | 15×10 |

**Non-task slides** also listed in the manifest:
- `slide_27`, `slide_28` — text/recommendation slides backed by Markdown
  (`docu/slide_27_policy_recommendations.md`, `docu/slide_28_country_recommendations.md`).
- `slide_31`, `slide_32` — fiscal-rules and fiscal-council diagrams produced by
  `buildFiscalRulesDiagram.py` / `buildFiscalCouncilDiagram.py` (run directly, not
  via `invoke`).

---

## How it works

Charts are produced through the [Invoke](https://www.pyinvoke.org/) task runner.
`tasks.py` defines one task per chart; each task shells out to the corresponding
`plot*.py` script.

```bash
# from the pyScripts/ directory (where tasks.py lives)
cd pyScripts

invoke --list              # show every available chart task
invoke plotUncertainty     # produce a single chart
invoke run-all             # produce the whole deck, in chartTable.csv order
```

`run-all` runs all 33 chart tasks. Outputs are written to `docu/` and the
`.html` versions auto-open in a browser (controlled by `auto_open_html` in
`fiscal_config.json`).

> **Note:** `customDutiesUS` fetches live data from the US Treasury MTS API, so it
> needs network access. Several Bloomberg/Haver-sourced charts (`plotInterestRates`,
> `plotTermPremia`, `plotChinaDebtSwap`, …) try a live download first and fall back
> to a cached CSV in `data/fmData/` when `imf_datatools` is unavailable.

---

## Repository layout

```
.
├── pyScripts/                 # all chart code + the manifest
│   ├── chartTable.csv         # ← the chart manifest (source of truth)
│   ├── tasks.py               # invoke task definitions + run-all
│   ├── fiscal_common.py       # shared helpers (config, dims, smart-save)
│   ├── fiscal_config.json     # output dir + auto-open setting
│   ├── chartConfig.json       # shared chart styling (template, fonts, colors)
│   └── plot*.py / *.py        # one script per chart (+ diagram/handout builders)
├── data/
│   ├── fmData/                # WEO, Fiscal Monitor DB, Bloomberg, caches, …
│   └── fmBondradar/           # bond-radar processed cache
├── docu/                      # generated charts (png/svg/html/csv) + the deck PDF/PPTX
└── +environment/
    └── csvFiles/countryTable.csv   # country/group reference table
```

## Data & Git LFS

Large binary inputs and the deck files are stored with **Git LFS** (see
`.gitattributes`): `*.xlsx`, `*.dta`, `*.pdf`, `*.pptx`. After cloning, materialize
them with:

```bash
git lfs pull          # or: git lfs checkout   (if objects are already local)
```

If these show up as small (~130-byte) text pointer files, the chart scripts will
fail to read them — run the command above first.

## Configuration

- **`fiscal_config.json`** — `output_settings.base_path` (where charts are written,
  resolved relative to `pyScripts/`; currently `../docu`) and `auto_open_html`.
- **`chartConfig.json`** — shared styling: Plotly template, fonts, margins, legend,
  axis styling, line widths.
- **`fiscal_common.py`** — config loading, `get_chart_dims_px()` (the cm→px lookup
  against `chartTable.csv`), output-path resolution, and a content-aware image saver.

## Requirements

Python 3.11+ with `pandas`, `plotly` (+ `kaleido` for PNG/SVG export), `openpyxl`,
`pyreadr` (for the bond-radar `.rds`), and `invoke`. Optional `imf_datatools` enables
live Bloomberg/Haver pulls; without it, scripts use the bundled caches.
