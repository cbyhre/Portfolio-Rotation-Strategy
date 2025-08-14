import pandas as pd
import streamlit as st

# === Streamlit UI ===
st.title("Optimal 401k to Roth Conversion Finder")

current_age = st.number_input("Current Age", min_value=18, max_value=72, value=49, step=1)
retirement_age = st.number_input("Retirement Age", min_value=current_age, max_value=72, value=65, step=1)
initial_capital = st.number_input("Current 401k Balance ($)", min_value=0, value=1_000_000, step=10_000, format="%d")
CAGR = st.number_input("Portfolio CAGR (as decimal)", min_value=0.0, max_value=0.5, value=0.10, step=0.01)

# === Fixed parameters ===
salary = 250_000
salary_growth = 0.03
end_age = 100
inflation = 0.025
cap_gains_rate = 0

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

def run_sim(conversion_age_start, annual_conversion):
    ages = list(range(current_age, end_age + 1))
    capital_401k = initial_capital
    capital_roth = 0
    capital_brokerage = 0
    current_salary = salary

    for age in ages:
        if age < conversion_age_start:
            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))
            if current_age < age < retirement_age:
                current_salary *= (1 + salary_growth)

        elif age < 73:
            taxable_income = (current_salary if age < retirement_age else 0) + annual_conversion
            conversion_amount = min(annual_conversion, capital_401k)
            tax_rate = future_tax_rate(taxable_income, age - current_age)
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

            if current_age < age < retirement_age:
                current_salary *= (1 + salary_growth)

        else:
            withdraw_pct = Withdrawl_Minimums.loc[Withdrawl_Minimums['Age'] == age, "% of Account You Must Withdraw"]
            if not withdraw_pct.empty and capital_401k > 0:
                withdrawal = capital_401k * (withdraw_pct.values[0] / 100)
                tax_rate = future_tax_rate(withdrawal, age - current_age)
                after_tax_withdrawal = withdrawal * (1 - tax_rate)
                capital_401k -= withdrawal
                capital_brokerage += after_tax_withdrawal

            capital_401k *= (1 + CAGR)
            capital_roth *= (1 + CAGR)
            capital_brokerage *= (1 + CAGR * (1 - cap_gains_rate))

    return capital_401k + capital_roth + capital_brokerage

if st.button("Run Optimization"):
    results = []
    for conv_start in range(current_age, 73):
        for conv_amount in range(1_000, int(initial_capital) + 1, 5_000):
            final_balance = run_sim(conv_start, conv_amount)
            results.append((conv_start, conv_amount, final_balance))

    results_df = pd.DataFrame(results, columns=["Conversion Start Age", "Annual Conversion", "Final Balance"])
    results_df = results_df.sort_values(by="Final Balance", ascending=False).reset_index(drop=True)

    st.subheader("Top 10 Strategies by Ending Balance")
    st.dataframe(results_df.head(10))
