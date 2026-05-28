"""
FM-KB Outreach Warsaw May 2026 - Task Runner
================================================================================
This script manages the workflow for generating charts for the
FM-KB Outreach Warsaw May 2026 materials.

Tasks are ordered to match the slide/chart sequence in chartTable.csv.

CHART TASKS (in chartTable.csv order):
--------------------------------------------------------------------------------
- plotUncertainty:              Global Policy Uncertainty Indices (slide 2 left)
                                In: WPUI-global.xlsx, GFPU_Data_60countries_C1.xlsx | Out: uncertainty_plot.png/html/svg
- analyzeFoodEnergyBooms:       Deficit effects during energy price booms (slide 2 right)
                                In: WEO_enhanced.dta | Out: food_energy_boom_deficit_count.png (and others)
- plotGlobalOutlook:            Global Macroeconomic and Fiscal Outlook (slide 3)
                                In: WEO_enhanced.dta | Out: global_outlook_panel.png/html/svg
- plotGlobalInterestRates:      Cost of Government Debt Financing (slide 4)
                                In: WEO_enhanced.dta | Out: global_interest_rates_panel.png/html/svg
- plotInterestRates:            Long-Term Bond Yields in AEs (slide 5 left)
                                In: 10-30y-bond-yields_cache.csv | Out: interest_rates_plot.png/html/svg
- plotTermPremia:               Term Spreads in Selected AEs (slide 5 right)
                                In: term_premia_cache.csv | Out: term_premia_plot.png/html/svg
- plotChinaUSDominance:         Overall Balance + Global Debt Evolution (slide 7)
                                In: WEO_enhanced.dta | Out: overall_balance_by_group.png, gross_debt_global_ver3.png
- plotGlobeDebtWaterfall:       Drivers of Increase in Global Debt (slide 6 left)
                                In: WEO_enhanced.dta | Out: globe_debt_decomposition_waterfall_2025-31.png
- plotCountryDebtWaterfall:     Country Decomposition of Global Debt (slide 6 right)
                                In: WEO_enhanced.dta | Out: global_debt_country_decomposition_waterfall.png
- plotDebtOwnership:            Evolution of Ownership of Global Debt (slide 8 left)
                                In: debt-ownership-Michael-desc.xlsx | Out: debt_ownership_plot.png
- summarizeBloombergCountryDebt: Short-Term Debt in AEs (slide 8 right)
                                In: Multiple .xlsx | Out: sovereign_tenure_dist_panel.png/csv
- plotCumulativeDist:           Cumulative Distribution of Fiscal Indicators (slide 10)
                                In: WEO_enhanced.dta | Out: cumulative_dist_panel.png
- plotAdjustmentWaterfall:      Change in Global Fiscal Gap, factor decomp (slides 11-12)
                                In: WEO_enhanced.dta | Out: adjustmentNeeded_waterfall_global_2014-19_vs_2024-29.png
- plotCountryDecomposition:     Change in Global Fiscal Gap, country decomp (slide 11 right)
                                In: WEO_enhanced.dta | Out: fiscalSpace_change_by_country_2014-19_vs_2024-29.png
- plotMutliVarPoland:           Poland Fiscal Variables and Debt Dynamics panel (slide 13)
                                In: WEO_enhanced.dta | Out: poland_fiscal_variables_panel.png
- plotGlobalOverallBalance:     Fiscal Overview by group (slide 15 left)
                                In: WEO_enhanced.dta | Out: global_overall_balance_*.png
- customDutiesUS:               Evolution of US Customs Revenue (slide 14 middle)
                                In: US Treasury API (MTS), WEO_enhanced.dta | Out: customs_duties_plot.png
- plotOBBBFiscalEffects:        OBBB Act impact on US deficit (slide 14 right)
                                In: OBBB-deficit-impact.xlsx | Out: obbb_fiscal_effects.png
- plotChinaDebtSwap:            China Debt Swap analysis
                                In: chn_debt_swap_cache.csv | Out: chn_debt_swap.png
- plotFiscalStance:             Fiscal Stance scatter (PB vs output gap)
                                In: WEO_enhanced.dta | Out: fiscal_stance_usa_chn.png
- plotSnowballAE:               Snowball Factor analysis for AE
                                In: WEO_enhanced.dta | Out: ae_snowball_japan_panel_10x10.png
- plotDefenseSpendingAutocorr:  Defense Spending autocorrelation bars
                                In: WEO_enhanced.dta | Out: defense_spending_autocorr.png
- plotBondRadar:                Emerging Market Bond Radar
                                In: Bond_radar_db_small_2026-02-09.rds | Out: 1_vol_combined_em_10x10.png
- plotEMSpreadsWaterfall:       EM Spreads waterfall
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: em_spreads_waterfall.png
- plotLowIncomeInterestRev:     LIC Interest Revenue ratio
                                In: WEO_enhanced.dta | Out: low_income_interest_revenue_ratio.png
- plotODAflows:                 ODA Flow analysis
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: oda_flows_grouped.png
- plotDaR:                      Debt-at-Risk charts (density + scenario bars)
                                In: global_dar.xlsx, density_scenario3_WLD_h3.xlsx | Out: debt_at_risk_density.png, debt_at_risk_adverse.png, debt_at_risk_ai.png
- plotSocialUnrest:             Social Unrest / political instability (Figure 1.27)
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: social_unrest_events.png, social_unrest_irf.png
- plotConvenienceYield:         Convenience Yield charts (daily + medians, Figure 1.29)
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: convenience_yield_daily.png, convenience_yield_medians.png
- plotDebtRollover:             Debt Rollover simulation bars (Figure 1.30)
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: debt_rollover_simulation.png
- plotTreasurySpillovers:       Treasury Spillovers bars (Figure 1.31.2, 1.32.1)
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: treasury_spillovers.png
- plotEMDEFiscalRisks:          EMDE Fiscal Risks horizontal bars (Figure 1.34.1)
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: emde_fiscal_risks.png
- plotAEFiscalRisks:            AE Fiscal Risks horizontal bars (Figure 1.35)
                                In: 2026AprFiscalMonitorDatabase.xlsx | Out: ae_fiscal_risks.png

EXTRAS (not in chartTable.csv):
--------------------------------------------------------------------------------
- globalPrimBalanceForGap:      Global Primary Balance by Income Group
                                Out: global_primary_balance_by_group.png
- buildSpeakingHandout:         Build speaker-notes handout PDF (slide image + notes)

- run-all:                      Execution of full workflow

Main entry point: invoke run-all
"""

from invoke import task
import os
import sys

# Configuration: Path to your scripts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APR26_SCRIPT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "2025-12_FM-Apr26")

# =============================================================================
# CHART TASKS (ordered to match chartTable.csv)
# =============================================================================

@task
def plotUncertainty(c):
    """
    Generate Uncertainty Indexes Plot.
    Out: uncertainty_plot.png
    """
    path = os.path.join(SCRIPT_DIR, "plotUncertainty.py")
    print(f"--- Generating Uncertainty Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def analyzeFoodEnergyBooms(c):
    """
    Analyze fiscal performance during food/energy price booms.
    Out: food_energy_boom_deficit_count.png (and others)
    """
    path = os.path.join(SCRIPT_DIR, "analyzeFoodEnergyBooms.py")
    print(f"--- Analyzing Food/Energy Booms ---")
    c.run(f"{sys.executable} {path}")

@task
def plotGlobalOutlook(c):
    """
    Generate Global Fiscal Outlook Line Charts (3x1 Panel).
    In: WEO_enhanced.dta | Out: global_outlook_panel.png/html/svg
    """
    path = os.path.join(SCRIPT_DIR, "plotGlobalOutlook.py")
    print(f"--- Generating Global Fiscal Outlook Panel ---")
    c.run(f"{sys.executable} {path}")

@task
def plotGlobalInterestRates(c):
    """
    Generate Global Interest Rates Panel Chart.
    In: WEO_enhanced.dta | Out: global_interest_rates_panel.png/html/svg
    """
    path = os.path.join(SCRIPT_DIR, "plotGlobalInterestRates.py")
    print(f"--- Generating Global Interest Rates Panel ---")
    c.run(f"{sys.executable} {path}")

@task
def plotInterestRates(c):
    """
    Generate 10Y and 30Y Bond Yield Plots.
    Out: interest_rates_plot.png
    """
    path = os.path.join(SCRIPT_DIR, "plotInterestRates.py")
    print(f"--- Generating Interest Rate Plots ---")
    c.run(f"{sys.executable} {path}")

@task
def plotTermPremia(c):
    """
    Generate Term Premia Plots.
    Out: term_premia_plot.png
    """
    path = os.path.join(SCRIPT_DIR, "plotTermPremia.py")
    print(f"--- Generating Term Premia Plots ---")
    c.run(f"{sys.executable} {path}")

@task
def plotChinaUSDominance(c):
    """
    Generate China/US Dominance Analysis Panel.
    In: WEO_enhanced.dta | Out: gross_debt_global_ver*.png, china_us_dominance_panel.png
    """
    path = os.path.join(SCRIPT_DIR, "plotChinaUSDominance.py")
    print(f"--- Generating China/US Dominance Charts ---")
    c.run(f"{sys.executable} {path}")

@task
def plotGlobeDebtWaterfall(c):
    """
    Generate Global Debt Decomposition Waterfall.
    Out: globe_debt_decomposition_waterfall_2025-31.png
    """
    path = os.path.join(SCRIPT_DIR, "plotGlobeDebtWaterfall.py")
    print(f"--- Generating Global Debt Waterfall ---")
    c.run(f"{sys.executable} {path}")

@task
def plotCountryDebtWaterfall(c):
    """
    Generate Country Debt Contribution Waterfall.
    Out: global_debt_country_decomposition_waterfall.png
    """
    path = os.path.join(SCRIPT_DIR, "plotCountryDebtWaterfall.py")
    print(f"--- Generating Country Debt Waterfall ---")
    c.run(f"{sys.executable} {path}")

@task
def plotDebtOwnership(c):
    """
    Generate Debt Ownership Decomposition.
    In: debt-ownership-Michael-desc.xlsx | Out: debt_ownership_plot.png
    """
    path = os.path.join(SCRIPT_DIR, "plotDebtOwnership.py")
    print(f"--- Generating Debt Ownership Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def summarizeBloombergCountryDebt(c):
    """
    Generate Sovereign Tenure Distribution Panel (US, UK, Japan, Germany).
    In: Multiple .xlsx | Out: sovereign_tenure_dist_panel.png/csv
    """
    path = os.path.join(SCRIPT_DIR, "summarizeBloombergCountryDebt.py")
    print(f"--- Generating Sovereign Tenure Distribution Panel ---")
    c.run(f"{sys.executable} {path}")

@task
def plotCumulativeDist(c):
    """
    Generate Cumulative Distribution Charts (Overall Balance + Government Debt).
    Out: cumulative_dist_overall_balance.png, cumulative_dist_government_debt.png
    """
    path = os.path.join(SCRIPT_DIR, "plotCumulativeDist.py")
    print(f"--- Generating Cumulative Distribution Charts ---")
    c.run(f"{sys.executable} {path}")

@task
def plotAdjustmentWaterfall(c):
    """
    Generate Global Adjustment Waterfall Plot.
    In: WEO_enhanced.dta | Out: adjustmentNeeded_waterfall_global_2014-19_vs_2024-29.png
    """
    path = os.path.join(SCRIPT_DIR, "plotAdjustmentWaterfall.py")
    print(f"--- Generating Global Adjustment Waterfall ---")
    c.run(f"{sys.executable} {path}")

@task
def plotAdjustmentWaterfallMultCountry(c):
    """
    Generate 1x3 fiscal-gap waterfall panel (Germany, Japan, Poland).
    In: WEO_enhanced.dta | Out: adjustmentNeeded_waterfall_multi_2014-19_vs_2024-29.png
    """
    path = os.path.join(SCRIPT_DIR, "plotAdjustmentWaterfallMultCountry.py")
    print(f"--- Generating Multi-Country Adjustment Waterfall (DEU/JPN/POL) ---")
    c.run(f"{sys.executable} {path}")

@task
def plotMutliVarPoland(c):
    """
    Generate 32x12 cm panel of Poland's fiscal variables (AE Europe + CESEE bands) (slide 13).
    In: WEO_enhanced.dta | Out: poland_fiscal_variables_panel.png
    """
    path = os.path.join(SCRIPT_DIR, "plotMutliVarPoland.py")
    print(f"--- Generating Poland Fiscal Variables Panel (32x12) ---")
    c.run(f"{sys.executable} {path}")

@task
def plotCountryDecomposition(c):
    """
    Generate Country-specific Waterfall Decompositions.
    In: WEO_enhanced.dta | Out: fiscalSpace_change_by_country_2014-19_vs_2024-29.png
    """
    path = os.path.join(SCRIPT_DIR, "plotCountryDecompositionWaterfall.py")
    print(f"--- Generating Country Decomposition Waterfall ---")
    c.run(f"{sys.executable} {path}")

@task
def plotGlobalOverallBalance(c):
    """
    Generate highlighted 2x1 panels (Overall Balance + Gross Debt) by income group.
    """
    path = os.path.join(SCRIPT_DIR, "plotGlobalOverallBalance.py")
    print(f"--- Generating Global Overall Balance / Gross Debt Highlights ---")
    c.run(f"{sys.executable} {path}")

@task
def customDutiesUS(c):
    """Generate US Customs Duties Analysis."""
    path = os.path.join(SCRIPT_DIR, "customDutiesUS.py")
    print("--- Generating US Customs Duties Plots ---")
    c.run(f"{sys.executable} {path}")

@task
def plotOBBBFiscalEffects(c):
    """Generate OBBB Fiscal Impact Bars."""
    path = os.path.join(SCRIPT_DIR, "plotOBBBFiscalEffects.py")
    print("--- Generating OBBB Fiscal Impact Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def plotChinaDebtSwap(c):
    """Generate China Debt Swap Analysis."""
    path = os.path.join(SCRIPT_DIR, "plotChinaDebtSwap.py")
    print("--- Generating China Debt Swap Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def plotFiscalStance(c):
    """Generate Fiscal Stance Scatter (PB vs Output Gap)."""
    path = os.path.join(SCRIPT_DIR, "plotFiscalStance.py")
    print("--- Generating Fiscal Stance Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def plotSnowballAE(c):
    """Generate Snowball Factor Analysis for AE."""
    path = os.path.join(SCRIPT_DIR, "plotSnowballAE.py")
    print("--- Generating Snowball AE Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def plotDefenseSpendingAutocorr(c):
    """Generate Defense Spending Autocorrelation Bars."""
    path = os.path.join(SCRIPT_DIR, "plotDefenseSpendingAutocorr.py")
    print("--- Generating Defense Spending Autocorrelation Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def plotBondRadar(c):
    """Generate Emerging Market Bond Radar Analysis."""
    path = os.path.join(SCRIPT_DIR, "fmBondRadarEM.py")
    print("--- Generating Bond Radar Plots ---")
    c.run(f"{sys.executable} {path}")

@task
def plotEMSpreadsWaterfall(c):
    """Generate EM Spreads Waterfall Chart."""
    path = os.path.join(SCRIPT_DIR, "plotEMSpreadsWaterfall.py")
    print("--- Generating EM Spreads Waterfall Plot ---")
    c.run(f"{sys.executable} {path}")

@task
def plotLowIncomeInterestRev(c):
    """Generate LIC Interest Revenue Ratio Plots."""
    path = os.path.join(SCRIPT_DIR, "plotLowIncomeInterestRevenue.py")
    print("--- Generating LIC Interest Revenue Ratio Plots ---")
    c.run(f"{sys.executable} {path}")

@task
def plotODAflows(c):
    """Generate ODA Flow Analysis Charts."""
    path = os.path.join(SCRIPT_DIR, "plotODAflows.py")
    print("--- Generating ODA Flows Plots ---")
    c.run(f"{sys.executable} {path}")

@task
def plotDaR(c):
    """
    Generate Debt-at-Risk Density Chart.
    In: global_dar.xlsx, density_scenario3_WLD_h3.xlsx | Out: debt_at_risk_density.png
    """
    path = os.path.join(SCRIPT_DIR, "plotDaR.py")
    print(f"--- Generating Debt-at-Risk Density Chart ---")
    c.run(f"{sys.executable} {path}")

@task
def plotSocialUnrest(c):
    """
    Generate Social Unrest / Political Instability Charts.
    In: 2026AprFiscalMonitorDatabase.xlsx (Figure 1.27) | Out: social_unrest_events.png, social_unrest_irf.png
    """
    path = os.path.join(SCRIPT_DIR, "plotSocialUnrest.py")
    print(f"--- Generating Social Unrest Charts ---")
    c.run(f"{sys.executable} {path}")

@task
def plotConvenienceYield(c):
    """
    Generate Convenience Yield Charts (daily + medians).
    In: 2026AprFiscalMonitorDatabase.xlsx (Figure 1.29) | Out: convenience_yield_daily.png, convenience_yield_medians.png
    """
    path = os.path.join(SCRIPT_DIR, "plotConvenienceYield.py")
    print(f"--- Generating Convenience Yield Charts ---")
    c.run(f"{sys.executable} {path}")

@task
def plotDebtRollover(c):
    """
    Generate Debt Rollover Simulation Bar Charts (2x1 panel).
    In: 2026AprFiscalMonitorDatabase.xlsx (Figure 1.30) | Out: debt_rollover_simulation.png
    """
    path = os.path.join(SCRIPT_DIR, "plotDebtRollover.py")
    print(f"--- Generating Debt Rollover Simulation Charts ---")
    c.run(f"{sys.executable} {path}")

@task
def plotTreasurySpillovers(c):
    """
    Generate Treasury Spillovers Bar Charts (2x1 panel).
    In: 2026AprFiscalMonitorDatabase.xlsx (Figure 1.31.2, 1.32.1) | Out: treasury_spillovers.png
    """
    path = os.path.join(SCRIPT_DIR, "plotTreasurySpillovers.py")
    print(f"--- Generating Treasury Spillovers Charts ---")
    c.run(f"{sys.executable} {path}")

@task
def plotEMDEFiscalRisks(c):
    """
    Generate EMDE Fiscal Risks Horizontal Bar Chart.
    In: 2026AprFiscalMonitorDatabase.xlsx (Figure 1.34.1) | Out: emde_fiscal_risks.png
    """
    path = os.path.join(SCRIPT_DIR, "plotEMDEFiscalRisks.py")
    print(f"--- Generating EMDE Fiscal Risks Chart ---")
    c.run(f"{sys.executable} {path}")

@task
def plotAEFiscalRisks(c):
    """
    Generate AE Fiscal Risks Horizontal Bar Chart.
    In: 2026AprFiscalMonitorDatabase.xlsx (Figure 1.35) | Out: ae_fiscal_risks.png
    """
    path = os.path.join(SCRIPT_DIR, "plotAEFiscalRisks.py")
    print(f"--- Generating AE Fiscal Risks Chart ---")
    c.run(f"{sys.executable} {path}")

# =============================================================================
# EXTRAS (not part of chartTable.csv slide sequence)
# =============================================================================

@task
def globalPrimBalanceForGap(c):
    """
    Generate Global Primary Balance by Income Group.
    In: WEO_enhanced.dta | Out: global_primary_balance_by_group.png
    """
    path = os.path.join(SCRIPT_DIR, "plotGlobalPrimBalanceForGap.py")
    print(f"--- Generating Global Primary Balance for Gap ---")
    c.run(f"{sys.executable} {path}")

@task
def buildSpeakingHandout(c):
    """
    Build a speaker-notes handout PDF: each page = slide image + parsed notes.
    In: 2026-05_FM-outreach_PL-fiscal-council.pdf, 2026-05_FM-outreach_PL-fiscal-council_speaking.md
    Out: 2026-05_FM-outreach_PL-fiscal-council_speaking.pdf
    """
    path = os.path.join(SCRIPT_DIR, "buildSpeakingHandout.py")
    print(f"--- Building speaker-notes handout ---")
    c.run(f"{sys.executable} {path}")

# =============================================================================
# FULL WORKFLOW (chartTable.csv order, data prep first)
# =============================================================================

@task(pre=[globalPrimBalanceForGap,
           plotUncertainty, analyzeFoodEnergyBooms, plotGlobalOutlook,
           plotGlobalInterestRates, plotInterestRates, plotTermPremia,
           plotGlobeDebtWaterfall, plotCountryDebtWaterfall, plotChinaUSDominance,
           plotDebtOwnership, summarizeBloombergCountryDebt, plotCumulativeDist,
           plotAdjustmentWaterfall, plotCountryDecomposition, plotAdjustmentWaterfallMultCountry, plotMutliVarPoland, plotGlobalOverallBalance,
           customDutiesUS, plotOBBBFiscalEffects, plotChinaDebtSwap, plotFiscalStance,
           plotSnowballAE, plotDefenseSpendingAutocorr, plotBondRadar,
           plotEMSpreadsWaterfall, plotLowIncomeInterestRev, plotODAflows, plotDaR,
           plotSocialUnrest, plotConvenienceYield, plotDebtRollover, plotTreasurySpillovers,
           plotEMDEFiscalRisks, plotAEFiscalRisks])
def run_all(c):
    """Run all tasks."""
    print("All tasks completed.")
