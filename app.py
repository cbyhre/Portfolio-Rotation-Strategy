# app.py
# Streamlit app for "Optimal Roth Conversions vs Never Converting"
# Deploy on Streamlit Community Cloud for a free website link.

import io
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import streamlit as st

# -------------------------------
# Streamlit Page Config
# -------------------------------
st.set_page_config(page_title="Roth Conversion Optimizer", layout="wide")

st.title("Roth Conversion Optimizer")
st.caption("Compare optimal annual Roth conversion strategies vs. never converting")

# -------------------------------
# Sidebar Inputs (Global Params)
# -------------------------------
st.sidebar.header("Global Parameters")

salary = st.sidebar.number_input("Starting Salary ($)", value=250_000, step=10_000, min_value=0)
salary_growth = st.sidebar.number_input("Annual Salary Growth (%)", value=3.0, step=0.1, min_value=0.0) / 100.0
retirement_age = st.sidebar.number_input("Retirement Age", value=65, min_value=50, max_value=85, step=1)

start_age = st.sidebar.number_input("Start Age", value=49, min_value=30, max_value=70, step=1)
end_age = st.sidebar.number_input("End Age", value=100, min_value=75, max_value=120, step=1)

CAGR = st.sidebar.number_input("Portfolio CAGR (%)", value=10.0, step=0.1, min_value=0.0, max_value=50.0) / 100.0
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=1_000_000, step=50_000, min_value=0)
inflation = st.sidebar.number_input("Inflation Rate (%)", value=2.5, step=0.1, min_value=0.0, max_value=15.0) / 100.0
cap_gains_rate = st.sidebar.number_input("Capital Gains Tax Rate on Brokerage Growth (%)", value=0.0, step=0.1, min_value=0.0, max_value=40.0) / 100.0

st.sidebar.markdown("---")
mode = st.sidebar.radio("Mode", ["Grid Search (find best)", "Manual Scenario"], index=0)

# -------------------------------
# Static IRS RMD Table
# -------------------------------
Withdrawl_Minimums = pd.DataFrame({
    "Age": [73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90,
            91, 92, 93, 94, 95, 96, 97, 98, 99, 100],
    "IRS Factor": [26.5, 25.5, 24.6, 23.7, 22.9, 22.0, 21.1, 20.2, 19.4, 18.5, 17.7,
                   16.8, 16.0, 15.2, 14.4, 13.7, 12.9, 12.2, 11.5, 10.8, 10.1, 9.5,
                   8.9, 8.4, 7.8, 7.3, 6.8, 6.4],
    "% of Account You Must Withdraw": [3.77, 3.92, 4.07, 4.22, 4.37, 4.55, 4.74,
                                       4.95, 5.15, 5.41, 5.65, 5.95, 6.25, 6.58,
                                       6.94, 7.30, 7.75, 8.20, 8.70, 9.26, 9.90,
                                       10.53, 11.24, 11.90, 12.82, 13.70, 14.71, 15.63]
})

# -------------------------------
# Tax Function
# -------------------------------
def future_tax_rate(income: float, year_offset: int, inflation_rate: float) -> float:
    """Return the effective ordinary income tax rate given inflated brackets."""
    if income <= 0:
        return 0.0
    factor = (1 + inflation_rate) ** year_offset
    brackets = [
        {"rate": 0.10, "start": 0,                 "end": 41_300 * factor},
        {"rate": 0.12, "start": 41_300 * factor,  "end": 167_900 * factor},
        {"rate": 0.22, "start": 167_900 * factor, "end": 358_300 * factor},
        {"rate": 0.24, "start": 358_300 * factor, "end": 683_300 * factor},
        {"rate": 0.32, "start": 683_300 * factor, "end": 867_600 * factor},
        {"rate": 0.35, "start": 867_600 * factor, "end": 1_302_800 * factor},
        {"rate": 0.37, "start": 1_302_800 * factor, "end": float("inf")},
    ]
    tax = 0.0
    remaining = income
    for b in brackets:
        if income > b["start"]:
            taxable = min(remaining, b["end"] - b["start"])
            if taxable > 0:
                tax += taxable * b["rate"]
                remaining -= taxable
        else:
            break
        if remaining <= 0:
            break
    return tax / income

# -------------------------------
# Core Simulation (Single Run)
# -------------------------------
def run_sim(
    conversion_age_start: int,
    annual_conversion: float,
    *,
    salary: float,
    salary_growth: float,
    retirement_age: int,
    start_age: int,
    end_age: int,
    CAGR: float,
    initial_capital: float,
    inflation: float,
    cap_gains_rate: float,
    return_balances: bool = False
):
    ages = list(range(start_age, end_age + 1))
    capital_401k = float(initial_capital)
    capital_roth = 0.0
    capital_brokerage = 0.0
    current_salary = float(salary)
    balances = []

    for age in ages:
        if age < conversion_age_start:
            # Growth only
            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))
            if start_age < age < retirement_age:
                current_salary *= (1 + salary_growth)

        elif age < 73:
            # Conversion years (before RMD)
            conversion_amount = min(annual_conversion, capital_401k)
            taxable_income = (current_salary if age < retirement_age else 0.0) + conversion_amount
            eff_rate = future_tax_rate(taxable_income, age - start_age, inflation)
            tax_due = conversion_amount * eff_rate

            # Move conversion to Roth
            capital_401k -= conversion_amount
            capital_roth += conversion_amount

            # Pay taxes: brokerage first, then 401k if needed
            if capital_brokerage >= tax_due:
                capital_brokerage -= tax_due
            else:
                remaining_tax = tax_due - capital_brokerage
                capital_brokerage = 0.0
                capital_401k -= remaining_tax

            # Apply growth
            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))

            if start_age < age < retirement_age:
                current_salary *= (1 + salary_growth)

        else:
            # RMD phase: withdraw % from 401k, taxed as ordinary income; after-tax -> brokerage
            row = Withdrawl_Minimums.loc[Withdrawl_Minimums["Age"] == age]
            if not row.empty and capital_401k > 0:
                withdraw_pct = float(row["% of Account You Must Withdraw"].values[0]) / 100.0
                withdrawal = capital_401k * withdraw_pct
                eff_rate = future_tax_rate(withdrawal, age - start_age, inflation)
                after_tax_withdrawal = withdrawal * (1 - eff_rate)
                capital_401k -= withdrawal
                capital_brokerage += after_tax_withdrawal

            # Growth
            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))

        if return_balances:
            balances.append(capital_401k + capital_roth + capital_brokerage)

    return (balances if return_balances else (capital_401k + capital_roth + capital_brokerage))

# -------------------------------
# Never Convert Helper (for plot)
# -------------------------------
def run_never(
    *,
    start_age: int,
    end_age: int,
    CAGR: float,
    initial_capital: float,
    inflation: float,
    cap_gains_rate: float
):
    ages = list(range(start_age, end_age + 1))
    capital_401k_nc = float(initial_capital)
    capital_brokerage_nc = 0.0
    balances_nc = []

    for age in ages:
        if age < 73:
            capital_401k_nc *= (1 + CAGR)
            capital_brokerage_nc *= (1 + CAGR * (1 - cap_gains_rate))
        else:
            row = Withdrawl_Minimums.loc[Withdrawl_Minimums["Age"] == age]
            if not row.empty and capital_401k_nc > 0:
                withdraw_pct = float(row["% of Account You Must Withdraw"].values[0]) / 100.0
                withdrawal = capital_401k_nc * withdraw_pct
                eff_rate = future_tax_rate(withdrawal, age - start_age, inflation)
                after_tax_withdrawal = withdrawal * (1 - eff_rate)
                capital_401k_nc -= withdrawal
                capital_brokerage_nc += after_tax_withdrawal

            capital_401k_nc *= (1 + CAGR)
            capital_brokerage_nc *= (1 + CAGR * (1 - cap_gains_rate))

        balances_nc.append(capital_401k_nc + capital_brokerage_nc)

    return balances_nc

# -------------------------------
# Grid Search (Vector of Runs)
# -------------------------------
@st.cache_data(show_spinner=True)
def grid_search(conv_age_min, conv_age_max, conv_amt_min, conv_amt_max, conv_amt_step,
                salary, salary_growth, retirement_age, start_age, end_age, CAGR, initial_capital, inflation, cap_gains_rate):
    results = []
    for conv_start in range(conv_age_min, conv_age_max + 1):
        for conv_amount in range(conv_amt_min, conv_amt_max + 1, conv_amt_step):
            final_balance = run_sim(
                conv_start, conv_amount,
                salary=salary,
                salary_growth=salary_growth,
                retirement_age=retirement_age,
                start_age=start_age,
                end_age=end_age,
                CAGR=CAGR,
                initial_capital=initial_capital,
                inflation=inflation,
                cap_gains_rate=cap_gains_rate,
                return_balances=False
            )
            results.append((conv_start, conv_amount, final_balance))
    df = pd.DataFrame(results, columns=["Conversion Start Age", "Annual Conversion", "Final Balance"])
    df = df.sort_values(by="Final Balance", ascending=False).reset_index(drop=True)
    return df

# -------------------------------
# UI for Mode Selection
# -------------------------------
ages = list(range(start_age, end_age + 1))

if mode == "Grid Search (find best)":
    st.subheader("Find Optimal Combination")

    c1, c2, c3 = st.columns(3)
    with c1:
        conv_age_min = st.number_input("Conversion Start Age (min)", value=max(49, start_age), min_value=start_age, max_value=72, step=1)
    with c2:
        conv_age_max = st.number_input("Conversion Start Age (max)", value=72, min_value=conv_age_min, max_value=72, step=1)
    with c3:
        st.write("")  # spacer

    c4, c5, c6 = st.columns(3)
    with c4:
        conv_amt_min = st.number_input("Annual Conversion ($) min", value=10_000, min_value=0, max_value=10_000_000, step=10_000)
    with c5:
        conv_amt_max = st.number_input("Annual Conversion ($) max", value=500_000, min_value=conv_amt_min, max_value=10_000_000, step=10_000)
    with c6:
        conv_amt_step = st.number_input("Annual Conversion Step ($)", value=10_000, min_value=1_000, max_value=1_000_000, step=1_000)

    run_btn = st.button("Run Grid Search")

    if run_btn:
        results_df = grid_search(
            conv_age_min, conv_age_max,
            conv_amt_min, conv_amt_max, conv_amt_step,
            salary, salary_growth, retirement_age,
            start_age, end_age, CAGR, initial_capital, inflation, cap_gains_rate
        )

        st.write("### Top 10 Strategies")
        st.dataframe(results_df.head(10).style.format({
            "Annual Conversion": "${:,.0f}",
            "Final Balance": "${:,.0f}"
        }), use_container_width=True)

        best_conv_start, best_conv_amount, best_final_balance = results_df.iloc[0]
        st.success(f"Best Strategy → Start Age: {int(best_conv_start)}, Annual Conversion: ${int(best_conv_amount):,}, Final Balance: ${best_final_balance:,.0f}")

        # Run best vs never and plot
        best_balances = run_sim(
            int(best_conv_start), int(best_conv_amount),
            salary=salary,
            salary_growth=salary_growth,
            retirement_age=retirement_age,
            start_age=start_age,
            end_age=end_age,
            CAGR=CAGR,
            initial_capital=initial_capital,
            inflation=inflation,
            cap_gains_rate=cap_gains_rate,
            return_balances=True
        )
        never_balances = run_never(
            start_age=start_age, end_age=end_age,
            CAGR=CAGR, initial_capital=initial_capital,
            inflation=inflation, cap_gains_rate=cap_gains_rate
        )
        spread_pct = [(b - n) / n * 100 if n != 0 else 0 for b, n in zip(best_balances, never_balances)]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        ax1.plot(ages, best_balances, label=f"Best Conversion (Start {int(best_conv_start)}, ${int(best_conv_amount):,}/yr)")
        ax1.plot(ages, never_balances, label="Never Convert")
        ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
        ax1.set_ylabel("Total Capital ($)")
        ax1.set_title(f"Optimal Roth Conversions vs Never Converting  •  Retirement Age {retirement_age}")
        ax1.legend()
        ax1.grid(True)

        ax2.plot(ages, spread_pct, color="green", label="Spread % (Best vs Never)")
        ax2.axhline(0, color="black", linewidth=1, linestyle="--")
        ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax2.set_xlabel("Age")
        ax2.set_ylabel("Spread (%)")
        ax2.legend()
        ax2.grid(True)

        st.pyplot(fig)

else:
    st.subheader("Manual Scenario (compare to Never Convert)")
    c1, c2 = st.columns(2)
    with c1:
        manual_conv_start = st.number_input("Conversion Start Age", value=max(55, start_age), min_value=start_age, max_value=72, step=1)
    with c2:
        manual_conv_amount = st.number_input("Annual Conversion ($)", value=118_000, min_value=0, max_value=10_000_000, step=5_000)

    run_btn = st.button("Run Manual Comparison")

    if run_btn:
        manual_balances = run_sim(
            int(manual_conv_start), float(manual_conv_amount),
            salary=salary,
            salary_growth=salary_growth,
            retirement_age=retirement_age,
            start_age=start_age,
            end_age=end_age,
            CAGR=CAGR,
            initial_capital=initial_capital,
            inflation=inflation,
            cap_gains_rate=cap_gains_rate,
            return_balances=True
        )
        never_balances = run_never(
            start_age=start_age, end_age=end_age,
            CAGR=CAGR, initial_capital=initial_capital,
            inflation=inflation, cap_gains_rate=cap_gains_rate
        )
        spread_pct = [(b - n) / n * 100 if n != 0 else 0 for b, n in zip(manual_balances, never_balances)]

        final_manual = manual_balances[-1]
        final_never = never_balances[-1]
        st.info(f"Final Balance — Manual: ${final_manual:,.0f}  |  Never: ${final_never:,.0f}  |  Δ: ${final_manual - final_never:,.0f}")

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        ax1.plot(ages, manual_balances, label=f"Manual Conversion (Start {int(manual_conv_start)}, ${int(manual_conv_amount):,}/yr)")
        ax1.plot(ages, never_balances, label="Never Convert")
        ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
        ax1.set_ylabel("Total Capital ($)")
        ax1.set_title(f"Manual Roth Conversions vs Never Converting  •  Retirement Age {retirement_age}")
        ax1.legend()
        ax1.grid(True)

        ax2.plot(ages, spread_pct, color="green", label="Spread % (Manual vs Never)")
        ax2.axhline(0, color="black", linewidth=1, linestyle="--")
        ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax2.set_xlabel("Age")
        ax2.set_ylabel("Spread (%)")
        ax2.legend()
        ax2.grid(True)

        st.pyplot(fig)

# -------------------------------
# Footer / How to Deploy
# -------------------------------
st.markdown("""
**How to get a website link:**
1. Put this `app.py` in a GitHub repo.
2. Go to **Streamlit Community Cloud** → **Deploy an app** → select your repo/branch/file.
3. Get your public URL (e.g., `https://your-app-name.streamlit.app`) and share it.
""")
