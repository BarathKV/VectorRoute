import math

def calculate_loan_emi(principal: float, annual_interest_rate: float, tenure_years: int):
    """
    Calculate monthly EMI for a loan.
    Formula:
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = monthly interest rate, n = number of months
    """
    monthly_rate = (annual_interest_rate / 100) / 12
    months = tenure_years * 12

    if monthly_rate == 0:
        emi = principal / months
    else:
        emi = principal * monthly_rate * (1 + monthly_rate) ** months / ((1 + monthly_rate) ** months - 1)

    total_payment = emi * months
    total_interest = total_payment - principal

    return {
        "principal": principal,
        "annual_interest_rate": annual_interest_rate,
        "tenure_years": tenure_years,
        "monthly_emi": round(emi, 2),
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2)
    }
