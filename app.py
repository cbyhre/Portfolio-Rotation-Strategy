import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

st.set_page_config(layout="wide", page_title="Roth Conversion Optimizer")

# === User Inputs ===
salary = st.number_input("Current Salary ($)", value=100000, step=1000)
retirement_age = st.number_input("Expected Retirement Age", value=65, step=1)
start_age = st.number_input("Current Age", value=40, step=1)
CAGR = st.number_input("Annual Return or CAGR (%)", value=10.0, step=0.1) / 100
initial_capital = st.number_input("Current 401k Capital ($)", value=1_000_000, step=10000)
withdrawal_pct = st.number_input("Annual Living Expense Withdrawal (% in Retirement)", value=4.0, step=0.1) / 100
annual_contribution_pct = st.number_input("Annual 401k Contribution (% of salary)", value=10.0, step=0.1) / 100
employer_match_pct = st.number_input("Employer Match (% of salary)", value=5.0, step=0.1) / 100

# === Fixed Parameters ===
salary_growth = 0.03
end_age = 100
inflation = 0.025
cap_gains_rate = 0
IRS_401k_limit_start = 23500

# === Assumptions Box ===
st.markdown(f"""
### Assumptions Used in This Model:
- **Inflation Rate:** {inflation*100:.2f}% per year
- **Salary Growth Rate:** {salary_growth*100:.2f}% per year until retirement
- **CAGR (Investment Growth):** {CAGR*100:.2f}%
- **Living Expense Withdrawal:** {withdrawal_pct*100:.2f}% of total capital in first retirement year, then grows with inflation
- **Employee 401k Contribution:** {annual_contribution_pct*100:.2f}% of salary (capped at ${IRS_401k_limit_start:,.0f} plus inflation)
- **Employer Match:** {employer_match_pct*100:.2f}% of salary
- **Capital Gains Tax Rate on Brokerage:** {cap_gains_rate*100:.2f}%
- **Rules:** Uses current 401k withdrawal rules and RMD schedule
- **Taxes:** Federal tax brackets are adjusted annually for inflation
- **State Taxes:** Illinois exempts qualified retirement plan distributions and conversions from state tax
""")

# === RMD Table ===
Withdrawl_Minimums = pd.DataFrame({
    "Age": list(range(73, 101)),
    "IRS Factor": [26.5, 25.5, 24.6, 23.7, 22.9, 22.0, 21.1, 20.2, 19.4, 18.5, 17.7, 16.8, 16.0, 15.2, 14.4, 13.7, 12.9, 12.2, 11.5, 10.8, 10.1, 9.5, 8.9, 8.4, 7.8, 7.3, 6.8, 6.4],
    "% of Account You Must Withdraw": [3.77, 3.92, 4.07, 4.22, 4.37, 4.55, 4.74, 4.95, 5.15, 5.41, 5.65, 5.95, 6.25, 6.58, 6.94, 7.30, 7.75, 8.20, 8.70, 9.26, 9.90, 10.53, 11.24, 11.90, 12.82, 13.70, 14.71, 15.63]
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
    balances, withdrawals, employee_contribs = [], [], []
    base_withdraw_amount = None  # first-year retirement withdrawal

    for age in ages:
        # 1. Contributions
        if age < retirement_age:
            years_since_start = age - start_age
            contribution_limit = IRS_401k_limit_start * (1 + inflation) ** years_since_start
            employee_contribution = min(current_salary * annual_contribution_pct, contribution_limit)
            employer_match = current_salary * employer_match_pct
            capital_401k += employee_contribution + employer_match
        else:
            employee_contribution = 0
        employee_contribs.append(employee_contribution)

        # 2. Withdrawals for living expenses (inflation-adjusted)
        if age == retirement_age:
            base_withdraw_amount = (capital_401k + capital_roth + capital_brokerage) * withdrawal_pct
        if age >= retirement_age and base_withdraw_amount:
            years_since_retire = age - retirement_age
            living_expense = base_withdraw_amount * ((1 + inflation) ** years_since_retire)
            if capital_brokerage >= living_expense:
                capital_brokerage -= living_expense
            elif capital_brokerage + capital_roth >= living_expense:
                from_roth = living_expense - capital_brokerage
                capital_brokerage = 0
                capital_roth -= from_roth
            else:
                from_401k = living_expense - (capital_brokerage + capital_roth)
                capital_brokerage = 0
                capital_roth = 0
                tax_rate = future_tax_rate(from_401k, age - start_age)
                capital_401k -= from_401k / (1 - tax_rate)
            withdrawals.append(living_expense)
        else:
            withdrawals.append(0)

        # 3. Conversions
        if conversion_age_start <= age < 73 and annual_conversion > 0:
            conversion_amount = min(annual_conversion, capital_401k)
            tax_rate = future_tax_rate(conversion_amount, age - start_age)
            tax_due = conversion_amount * tax_rate
            capital_401k -= conversion_amount
            capital_roth += conversion_amount
            if capital_brokerage >= tax_due:
                capital_brokerage -= tax_due
            else:
                remaining_tax = tax_due - capital_brokerage
                capital_brokerage = 0
                capital_401k -= remaining_tax

        # 4. RMDs
        withdraw_pct = Withdrawl_Minimums.loc[Withdrawl_Minimums['Age'] == age, "% of Account You Must Withdraw"]
        if not withdraw_pct.empty and capital_401k > 0:
            rmd_withdrawal = capital_401k * (withdraw_pct.values[0] / 100)
            tax_rate = future_tax_rate(rmd_withdrawal, age - start_age)
            after_tax = rmd_withdrawal * (1 - tax_rate)
            capital_401k -= rmd_withdrawal
            capital_brokerage += after_tax

        # 5. Growth
        capital_401k *= (1 + CAGR)
        capital_roth *= (1 + CAGR)
        capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))

        # 6. Salary growth
        if age < retirement_age:
            current_salary *= (1 + salary_growth)

        if return_balances:
            balances.append(capital_401k + capital_roth + capital_brokerage)

    return (balances, withdrawals, employee_contribs) if return_balances else capital_401k + capital_roth + capital_brokerage

# === Never Convert ===
def run_never():
    ages = list(range(start_age, end_age + 1))
    capital_401k = initial_capital
    capital_brokerage = 0
    current_salary = salary
    balances, withdrawals, employee_contribs = [], [], []
    base_withdraw_amount = None

    for age in ages:
        # 1. Contributions
        if age < retirement_age:
            years_since_start = age - start_age
            contribution_limit = IRS_401k_limit_start * (1 + inflation) ** years_since_start
            employee_contribution = min(current_salary * annual_contribution_pct, contribution_limit)
            employer_match = current_salary * employer_match_pct
            capital_401k += employee_contribution + employer_match
        else:
            employee_contribution = 0
        employee_contribs.append(employee_contribution)

        # 2. Withdrawals for living expenses (inflation-adjusted)
        if age == retirement_age:
            base_withdraw_amount = (capital_401k + capital_brokerage) * withdrawal_pct
        if age >= retirement_age and base_withdraw_amount:
            years_since_retire = age - retirement_age
            living_expense = base_withdraw_amount * ((1 + inflation) ** years_since_retire)
            if capital_brokerage >= living_expense:
                capital_brokerage -= living_expense
            else:
                from_401k = living_expense - capital_brokerage
                capital_brokerage = 0
                tax_rate = future_tax_rate(from_401k, age - start_age)
                capital_401k -= from_401k / (1 - tax_rate)
            withdrawals.append(living_expense)
        else:
            withdrawals.append(0)

        # 4. RMDs
        withdraw_pct = Withdrawl_Minimums.loc[Withdrawl_Minimums['Age'] == age, "% of Account You Must Withdraw"]
        if not withdraw_pct.empty and capital_401k > 0:
            rmd_withdrawal = capital_401k * (withdraw_pct.values[0] / 100)
            tax_rate = future_tax_rate(rmd_withdrawal, age - start_age)
            after_tax = rmd_withdrawal * (1 - tax_rate)
            capital_401k -= rmd_withdrawal
            capital_brokerage += after_tax

        # 5. Growth
        capital_401k *= (1 + CAGR)
        capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))

        # 6. Salary growth
        if age < retirement_age:
            current_salary *= (1 + salary_growth)

        balances.append(capital_401k + capital_brokerage)

    return balances, withdrawals, employee_contribs

# === Grid Search ===
results = []
for conv_start in range(start_age, 73):
    for conv_amount in range(0, 1_000_000, 10_000):
        final_balance = run_sim(conv_start, conv_amount)
        results.append((conv_start, conv_amount, final_balance))

results_df = pd.DataFrame(results, columns=["Conversion Start Age", "Annual Conversion", "Final Balance"])
results_df = results_df.sort_values(by="Final Balance", ascending=False).reset_index(drop=True)
best_conv_start, best_conv_amount, best_final_balance = results_df.iloc[0]

# === Balances for Plot & Table ===
ages = list(range(start_age, end_age + 1))
best_balances, best_withdrawals, best_contribs = run_sim(best_conv_start, best_conv_amount, return_balances=True)
never_balances, never_withdrawals, never_contribs = run_never()
spread_pct = [(b - n) / n * 100 if n != 0 else 0 for b, n in zip(best_balances, never_balances)]

# === Display Results ===
st.subheader("Optimal Strategy Instructions")
st.markdown(f"**Start at age {best_conv_start}: Convert ${best_conv_amount:,.0f} per year into a Roth IRA.**")
st.markdown(f"**Final Balance (Optimal Strategy):** ${best_final_balance:,.0f}")
st.markdown(f"**Final Balance (Never Convert):** ${never_balances[-1]:,.0f}")
st.markdown(f"**Advantage:** ${best_final_balance - never_balances[-1]:,.0f} (**{spread_pct[-1]:.2f}% higher**)")

# === Plot ===
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
ax1.plot(ages, best_balances, label=f"Optimal Conversion (Start {best_conv_start}, ${best_conv_amount:,}/yr)")
ax1.plot(ages, never_balances, label="Never Convert")
ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
ax1.set_ylabel("Total Capital ($)")
ax1.legend()
ax1.grid(True)
ax2.plot(ages, spread_pct, color="green", label="Spread % (Optimal vs Never)")
ax2.axhline(0, color="black", linewidth=1, linestyle="--")
ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
ax2.set_xlabel("Age")
ax2.set_ylabel("Spread (%)")
ax2.legend()
ax2.grid(True)
st.pyplot(fig)

# === Table ===
comparison_df = pd.DataFrame({
    "Age": ages,
    "Conversion Total": best_balances,
    "Conversion Living Expense Withdrawal": best_withdrawals,
    "Conversion Employee Contribution": best_contribs,
    "Non-Conversion Total": never_balances,
    "Non-Conversion Living Expense Withdrawal": never_withdrawals,
    "Non-Conversion Employee Contribution": never_contribs
})
for col in ["Conversion Total", "Conversion Living Expense Withdrawal", "Conversion Employee Contribution",
            "Non-Conversion Total", "Non-Conversion Living Expense Withdrawal", "Non-Conversion Employee Contribution"]:
    comparison_df[col] = comparison_df[col].apply(lambda x: f"${x:,.0f}")

st.subheader("Yearly Comparison Table")
st.dataframe(comparison_df)
