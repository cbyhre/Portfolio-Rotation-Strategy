import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

st.set_page_config(layout="wide", page_title="Roth Conversion Optimizer")

# === User Inputs ===
salary = st.number_input("Current Salary ($)", value=100000, step=1000)
retirement_age = st.number_input("Expected Retirement Age", value=65, step=1)
start_age = st.number_input("Current Age", value=40, step=1)
CAGR = st.number_input("Annual Return or CAGR (%)", value=0.1, step=0.01, format="%.2f")
initial_capital = st.number_input("Current 401k Capital ($)", value=1_000_000, step=10000)
annual_withdrawal_pct = st.number_input("Annual Living Expense Withdrawal (% of Retirement Balance)", value=0.03, step=0.01, format="%.2f")

# === Fixed Parameters ===
salary_growth = 0.03
end_age = 100
inflation = 0.025
cap_gains_rate = 0
federal_tax_brackets = [
    (0, 0.10), (11000, 0.12), (44725, 0.22), (95375, 0.24),
    (182100, 0.32), (231250, 0.35), (578125, 0.37)
]
rmd_table = pd.DataFrame({
    "Age": [73,74,75,76,77,78,79,80,81,82,83,84,85],
    "Divisor": [26.5,25.5,24.6,23.7,22.9,22.0,21.1,20.2,19.4,18.5,17.7,16.8,16.0]
})

annual_contribution_pct = 0.05  # % of salary
employer_match_pct = 0.03

# === Helper Functions ===
def get_federal_tax_rate(income, age):
    # Adjust brackets for inflation
    years_since_start = age - start_age
    inflation_factor = (1 + inflation) ** years_since_start
    adj_brackets = [(b[0] * inflation_factor, b[1]) for b in federal_tax_brackets]

    tax = 0
    for i, (bracket, rate) in enumerate(adj_brackets):
        if i == len(adj_brackets) - 1 or income <= adj_brackets[i + 1][0]:
            tax += (income - bracket) * rate
            break
        else:
            next_bracket = adj_brackets[i + 1][0]
            tax += (next_bracket - bracket) * rate
    return max(tax, 0)

def get_rmd_divisor(age):
    if age in rmd_table["Age"].values:
        return rmd_table.loc[rmd_table["Age"] == age, "Divisor"].values[0]
    elif age > rmd_table["Age"].max():
        return max(rmd_table["Divisor"].iloc[-1] - (age - rmd_table["Age"].max()) * 0.9, 1)
    return None

# === Simulation Function ===
def run_sim(conversion_start_age):
    capital_401k = initial_capital
    capital_roth = 0
    capital_brokerage = 0
    current_salary = salary

    results = []
    
    for age in range(start_age, end_age + 1):
        # === 1. Salary growth ===
        if age > start_age:
            current_salary *= (1 + salary_growth)

        # === 2. Contributions (before retirement only) ===
        if age < retirement_age:
            contribution_limit = 23500 * (1 + inflation) ** (age - start_age)
            raw_employee_contribution = current_salary * annual_contribution_pct
            employee_contribution = min(raw_employee_contribution, contribution_limit)
            employer_match = current_salary * employer_match_pct
            capital_401k += employee_contribution + employer_match
        else:
            employee_contribution = 0

        # === 3. Living Expense Withdrawals ===
        living_expense_withdrawal = 0
        if age >= retirement_age:
            living_expense_withdrawal = capital_401k * annual_withdrawal_pct
            capital_401k -= living_expense_withdrawal  # before taxes
            tax_due = get_federal_tax_rate(living_expense_withdrawal, age)
            capital_401k -= tax_due
            capital_brokerage += (living_expense_withdrawal - tax_due)

        # === 4. Roth Conversions ===
        if conversion_start_age <= age < 73 and capital_401k > 0:
            conversion_amount = capital_401k * 0.20
            tax_due = get_federal_tax_rate(conversion_amount, age)
            capital_401k -= conversion_amount
            capital_roth += conversion_amount - tax_due
            capital_brokerage -= tax_due

        # === 5. RMDs ===
        if age >= 73:
            divisor = get_rmd_divisor(age)
            if divisor and capital_401k > 0:
                rmd_amount = capital_401k / divisor
                tax_due = get_federal_tax_rate(rmd_amount, age)
                capital_401k -= rmd_amount
                capital_brokerage += (rmd_amount - tax_due)

        # === 6. Growth ===
        capital_401k *= (1 + CAGR)
        capital_roth *= (1 + CAGR)
        capital_brokerage *= (1 + CAGR)

        # === Save results ===
        results.append({
            "Age": age,
            "401k Balance": capital_401k,
            "Roth Balance": capital_roth,
            "Brokerage Balance": capital_brokerage,
            "Living Expense Withdrawals ($)": living_expense_withdrawal,
            "Personal Contributions ($)": employee_contribution
        })
    
    return pd.DataFrame(results)

# === Run and Display ===
conversion_start_age = st.slider("Conversion Start Age", min_value=start_age, max_value=73, value=start_age)
df = run_sim(conversion_start_age)

# Format currency
for col in ["401k Balance", "Roth Balance", "Brokerage Balance", "Living Expense Withdrawals ($)", "Personal Contributions ($)"]:
    df[col] = df[col].apply(lambda x: f"${x:,.0f}")

st.dataframe(df)

# === Plot ===
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(df["Age"], df["401k Balance"], label="401k")
ax.plot(df["Age"], df["Roth Balance"], label="Roth")
ax.plot(df["Age"], df["Brokerage Balance"], label="Brokerage")
ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
ax.set_xlabel("Age")
ax.set_ylabel("Balance ($)")
ax.legend()
st.pyplot(fig)
