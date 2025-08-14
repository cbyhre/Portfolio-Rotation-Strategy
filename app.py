import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

st.set_page_config(layout="wide", page_title="Roth Conversion Optimizer")

# === User Inputs ===
salary = st.number_input("Current Salary ($)", value=100000, step=1000)
retirement_age = st.number_input("Retirement Age", value=65, step=1)
start_age = st.number_input("Current Age", value=40, step=1)
CAGR = st.number_input("Annual Investment CAGR (decimal)", value=0.1, step=0.01, format="%.2f")
initial_capital = st.number_input("Initial 401k Capital ($)", value=1_000_000, step=10000)

# === Fixed Parameters ===
salary_growth = 0.03
end_age = 100
inflation = 0.025
cap_gains_rate = 0

# === RMD Table ===
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

# === Tax Function ===
def future_tax_rate(income, year_offset):
    factor = (1 + inflation) ** year_offset
    brackets = [
        {"rate": 0.10, "start": 0 * factor, "end": 41300 * factor},
        {"rate": 0.12, "start": 41300 * factor, "end": 167900 * factor},
        {"rate": 0.22, "start": 167900 * factor, "end": 358300 * factor},
        {"rate": 0.24, "start": 358300 * factor, "end": 683300 * factor},
        {"rate": 0.32, "start": 683300 * factor, "end": 867600 * factor},
        {"rate": 0.35, "start": 867600 * factor, "end": 1302800 * factor},
        {"rate": 0.37, "start": 1302800 * factor, "end": float("inf")}
    ]
    tax = 0
    remaining_income = income
    for bracket in brackets:
        if income > bracket["start"]:
            taxable_amount = min(remaining_income, bracket["end"] - bracket["start"])
            tax += taxable_amount * bracket["rate"]
            remaining_income -= taxable_amount
        else:
            break
    return tax / income if income > 0 else 0

# === Simulation ===
def run_sim(conversion_age_start, annual_conversion, return_balances=False):
    ages = list(range(start_age, end_age + 1))
    capital_401k = initial_capital
    capital_roth = 0
    capital_brokerage = 0
    current_salary = salary
    balances = []

    for age in ages:
        if age < conversion_age_start:
            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))
            if start_age < age < retirement_age:
                current_salary *= (1 + salary_growth)

        elif age < 73:
            taxable_income = (current_salary if age < retirement_age else 0) + annual_conversion
            conversion_amount = min(annual_conversion, capital_401k)
            tax_rate = future_tax_rate(taxable_income, age - start_age)
            tax_due = conversion_amount * tax_rate

            capital_401k -= conversion_amount
            capital_roth += conversion_amount

            if capital_brokerage >= tax_due:
                capital_brokerage -= tax_due
            else:
                remaining_tax = tax_due - capital_brokerage
                capital_brokerage = 0
                capital_401k -= remaining_tax

            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))

            if start_age < age < retirement_age:
                current_salary *= (1 + salary_growth)

        else:
            withdraw_pct = Withdrawl_Minimums.loc[Withdrawl_Minimums['Age'] == age, "% of Account You Must Withdraw"]
            if not withdraw_pct.empty and capital_401k > 0:
                withdrawal = capital_401k * (withdraw_pct.values[0] / 100)
                tax_rate = future_tax_rate(withdrawal, age - start_age)
                after_tax_withdrawal = withdrawal * (1 - tax_rate)
                capital_401k -= withdrawal
                capital_brokerage += after_tax_withdrawal

            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))

        if return_balances:
            balances.append(capital_401k + capital_roth + capital_brokerage)

    if return_balances:
        return balances
    else:
        return capital_401k + capital_roth + capital_brokerage

# === Never Convert ===
def run_never():
    ages = list(range(start_age, end_age + 1))
    capital_401k_nc = initial_capital
    capital_brokerage_nc = 0
    balances_nc = []
    for age in ages:
        if age < 73:
            capital_401k_nc *= (1 + CAGR)
            capital_brokerage_nc *= (1 + CAGR * (1 - cap_gains_rate))
        else:
            withdraw_pct = Withdrawl_Minimums.loc[Withdrawl_Minimums['Age'] == age, "% of Account You Must Withdraw"]
            if not withdraw_pct.empty and capital_401k_nc > 0:
                withdrawal = capital_401k_nc * (withdraw_pct.values[0] / 100)
                tax_rate = future_tax_rate(withdrawal, age - start_age)
                after_tax_withdrawal = withdrawal * (1 - tax_rate)
                capital_401k_nc -= withdrawal
                capital_brokerage_nc += after_tax_withdrawal
            capital_401k_nc *= (1 + CAGR)
            capital_brokerage_nc *= (1 + CAGR * (1 - cap_gains_rate))
        balances_nc.append(capital_401k_nc + capital_brokerage_nc)
    return balances_nc

# === Grid Search ===
results = []
for conv_start in range(start_age, 73):
    for conv_amount in range(0, 1_000_000, 10_000):
        final_balance = run_sim(conv_start, conv_amount)
        results.append((conv_start, conv_amount, final_balance))

results_df = pd.DataFrame(results, columns=["Conversion Start Age", "Annual Conversion", "Final Balance"])
results_df = results_df.sort_values(by="Final Balance", ascending=False).reset_index(drop=True)

best_conv_start, best_conv_amount, best_final_balance = results_df.iloc[0]

# === Balances for Plot ===
ages = list(range(start_age, end_age + 1))
best_balances = run_sim(best_conv_start, best_conv_amount, return_balances=True)
never_balances = run_never()
spread_pct = [(b - n) / n * 100 if n != 0 else 0 for b, n in zip(best_balances, never_balances)]

# === Display Results ===
st.subheader("Optimal Strategy")
st.markdown(f"**At age {best_conv_start}, start converting ${best_conv_amount:,.0f} per year into a Roth IRA.**")
st.markdown(f"Final Balance (Best): **${best_final_balance:,.0f}**")
st.markdown(f"Final Balance (Never Convert): **${never_balances[-1]:,.0f}**")
st.markdown(f"Difference: **${best_final_balance - never_balances[-1]:,.0f} ({spread_pct[-1]:.2f}%)**")

# === Plot ===
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
ax1.plot(ages, best_balances, label=f"Best Conversion (Start {best_conv_start}, ${best_conv_amount:,}/yr)")
ax1.plot(ages, never_balances, label="Never Convert")
ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
ax1.set_ylabel("Total Capital ($)")
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
