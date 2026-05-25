"""
MORTGAGE-CALC — Migrated Python Module
Original: COBOL program MORTGAGE-CALC (mortgage_calc.cbl)
Migrated by: COBOL Moderniser — Agent 4 (Code Writer)
"""
 
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from enum import IntEnum
 
class ReturnCode(IntEnum):
    SUCCESS           = 0
    INVALID_PRINCIPAL = 1
    INVALID_RATE      = 2
    INVALID_TERM      = 3
    INVALID_MONTH     = 4
 
MONTHS_IN_YEAR    = 12
PENALTY_THRESHOLD = 36
EARLY_PENALTY_PCT = Decimal("0.030000")
MAX_PRINCIPAL     = Decimal("9999999.99")
MAX_ANNUAL_RATE   = Decimal("99.999999")
MAX_TERM_YEARS    = 40
FIXED_RATE        = "F"
VARIABLE_RATE     = "V"
 
@dataclass
class MortgageInput:
    principal:       float
    annual_rate:     float
    term_years:      int
    repayment_month: int
    rate_type:       str = FIXED_RATE
 
@dataclass
class MortgageResult:
    return_code:     ReturnCode
    monthly_payment: float = 0.0
    total_repayable: float = 0.0
    total_interest:  float = 0.0
    month_interest:  float = 0.0
    month_principal: float = 0.0
    closing_balance: float = 0.0
    penalty:         float = 0.0
 
    @property
    def success(self):
        return self.return_code == ReturnCode.SUCCESS
 
    def summary(self):
        if not self.success:
            return f"Calculation failed: {self.return_code.name}"
        return (
            f"Monthly payment:  £{self.monthly_payment:>12,.2f}\n"
            f"Month interest:   £{self.month_interest:>12,.2f}\n"
            f"Month principal:  £{self.month_principal:>12,.2f}\n"
            f"Closing balance:  £{self.closing_balance:>12,.2f}\n"
            f"Total repayable:  £{self.total_repayable:>12,.2f}\n"
            f"Total interest:   £{self.total_interest:>12,.2f}\n"
            f"Penalty:          £{self.penalty:>12,.2f}"
        )
 
def _validate_inputs(inputs):
    p = Decimal(str(inputs.principal))
    r = Decimal(str(inputs.annual_rate))
    if p <= 0 or p > MAX_PRINCIPAL:      return ReturnCode.INVALID_PRINCIPAL
    if r <= 0 or r > MAX_ANNUAL_RATE:    return ReturnCode.INVALID_RATE
    if inputs.term_years <= 0 or inputs.term_years > MAX_TERM_YEARS: return ReturnCode.INVALID_TERM
    max_month = inputs.term_years * MONTHS_IN_YEAR
    if inputs.repayment_month <= 0 or inputs.repayment_month > max_month: return ReturnCode.INVALID_MONTH
    return ReturnCode.SUCCESS
 
def calculate_mortgage(inputs):
    rc = _validate_inputs(inputs)
    if rc != ReturnCode.SUCCESS:
        return MortgageResult(return_code=rc)
 
    p  = Decimal(str(inputs.principal))
    r  = Decimal(str(inputs.annual_rate))
    n  = inputs.term_years * MONTHS_IN_YEAR
    mo = inputs.repayment_month
 
    monthly_rate    = (r / MONTHS_IN_YEAR).quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)
    rate_plus_one   = Decimal("1") + monthly_rate
    compound_factor = rate_plus_one ** n
    numerator       = p * monthly_rate * compound_factor
    denominator     = compound_factor - Decimal("1")
    monthly_payment = (numerator / denominator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
 
    balance = p
    for _ in range(mo - 1):
        interest_portion  = (balance * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        principal_portion = monthly_payment - interest_portion
        balance           = balance - principal_portion
 
    interest_portion  = (balance * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    principal_portion = monthly_payment - interest_portion
    closing_balance   = balance - principal_portion
 
    total_repayable = (monthly_payment * n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_interest  = total_repayable - p
 
    penalty = Decimal("0.00")
    if inputs.rate_type == FIXED_RATE and mo <= PENALTY_THRESHOLD:
        penalty = (closing_balance * EARLY_PENALTY_PCT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
 
    return MortgageResult(
        return_code     = ReturnCode.SUCCESS,
        monthly_payment = float(monthly_payment),
        total_repayable = float(total_repayable),
        total_interest  = float(total_interest),
        month_interest  = float(interest_portion),
        month_principal = float(principal_portion),
        closing_balance = float(closing_balance),
        penalty         = float(penalty),
    )
 
def calculate(principal, annual_rate, term_years, repayment_month, rate_type=FIXED_RATE):
    return calculate_mortgage(MortgageInput(principal, annual_rate, term_years, repayment_month, rate_type))
 
if __name__ == "__main__":
    print("MORTGAGE-CALC — Migrated Python Module")
    print("=" * 50)
 
    r1 = calculate(200000.00, 0.0525, 25, 1)
    print("\nDemo: £200,000 at 5.25% over 25 years (month 1)")
    print("-" * 50)
    print(r1.summary())
 
    r2 = calculate(200000.00, 0.0525, 25, 12)
    print("\nEarly repayment month 12 — penalty applies (fixed rate)")
    print("-" * 50)
    print(r2.summary())
 
    r3 = calculate(200000.00, 0.0525, 25, 37)
    print("\nEarly repayment month 37 — no penalty")
    print("-" * 50)
    print(r3.summary())
 
    r4 = calculate(0, 0.0525, 25, 1)
    print("\nInvalid input — zero principal")
    print("-" * 50)
    print(r4.summary())
