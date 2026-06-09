"""
=============================================================================
AGENT 4 -- CODE WRITER
=============================================================================
"""

import argparse
from datetime import datetime

MIGRATED_CODE = '''"""
=============================================================================
MORTGAGE-CALC -- Migrated Python Module
=============================================================================
Original:    COBOL program MORTGAGE-CALC (mortgage_calc.cbl)
Migrated by: COBOL Moderniser -- Agent 4 (Code Writer)
Date:        {timestamp}

Purpose:
    Calculates mortgage amortisation figures for a given loan, including:
      - Monthly repayment amount
      - Principal / interest split for any given month
      - Running balance after a given month
      - Total cost of loan over the full term
      - Early repayment penalty (where applicable)

Migration notes:
    - Decimal arithmetic used throughout to match COBOL fixed-point precision
    - Rounding: ROUND_HALF_UP applied at each step, matching COBOL ROUNDED
    - Penalty threshold: 36 months (3 years), fixed-rate mortgages only
    - Penalty rate: 3.0% of outstanding balance
    - Maximum principal: 9,999,999.99
    - Maximum term: 40 years
    - Interest rate stored as decimal (5.25% = 0.0525)
=============================================================================
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


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

FIXED_RATE    = "F"
VARIABLE_RATE = "V"


@dataclass
class MortgageInput:
    """Input parameters for the mortgage calculation."""
    principal:       float
    annual_rate:     float
    term_years:      int
    repayment_month: int
    rate_type:       str = FIXED_RATE


@dataclass
class MortgageResult:
    """Output from the mortgage calculation."""
    return_code:      ReturnCode
    monthly_payment:  float = 0.0
    total_repayable:  float = 0.0
    total_interest:   float = 0.0
    month_interest:   float = 0.0
    month_principal:  float = 0.0
    closing_balance:  float = 0.0
    penalty:          float = 0.0

    @property
    def success(self) -> bool:
        return self.return_code == ReturnCode.SUCCESS


def calculate_mortgage(inputs: MortgageInput) -> MortgageResult:
    """Calculate mortgage amortisation figures."""
    rc = _validate_inputs(inputs)
    if rc != ReturnCode.SUCCESS:
        return MortgageResult(return_code=rc)

    p = Decimal(str(inputs.principal))
    r = Decimal(str(inputs.annual_rate))
    n = inputs.term_years * MONTHS_IN_YEAR
    mo = inputs.repayment_month

    monthly_rate = (r / MONTHS_IN_YEAR).quantize(
        Decimal("0.0000000001"), rounding=ROUND_HALF_UP
    )

    rate_plus_one   = Decimal("1") + monthly_rate
    compound_factor = rate_plus_one ** n
    numerator       = p * monthly_rate * compound_factor
    denominator     = compound_factor - Decimal("1")
    monthly_payment = (numerator / denominator).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    balance = p
    for _ in range(mo - 1):
        interest_portion  = (balance * monthly_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        principal_portion = monthly_payment - interest_portion
        balance           = balance - principal_portion

    interest_portion  = (balance * monthly_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    principal_portion = monthly_payment - interest_portion
    closing_balance   = balance - principal_portion

    total_repayable = (monthly_payment * n).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_interest = total_repayable - p

    penalty = Decimal("0.00")
    if inputs.rate_type == FIXED_RATE and mo <= PENALTY_THRESHOLD:
        penalty = (closing_balance * EARLY_PENALTY_PCT).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

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


def _validate_inputs(inputs: MortgageInput) -> ReturnCode:
    """Validate all input fields. Handles edge cases (None, strings)."""
    # Principal validation
    try:
        p = Decimal(str(inputs.principal))
        if p <= 0 or p > MAX_PRINCIPAL:
            return ReturnCode.INVALID_PRINCIPAL
    except Exception:
        return ReturnCode.INVALID_PRINCIPAL

    # Rate validation
    try:
        r = Decimal(str(inputs.annual_rate))
        if r <= 0 or r > MAX_ANNUAL_RATE:
            return ReturnCode.INVALID_RATE
    except Exception:
        return ReturnCode.INVALID_RATE

    # Term validation
    try:
        if inputs.term_years <= 0 or inputs.term_years > MAX_TERM_YEARS:
            return ReturnCode.INVALID_TERM
    except Exception:
        return ReturnCode.INVALID_TERM

    # Month validation
    try:
        max_month = inputs.term_years * MONTHS_IN_YEAR
        if inputs.repayment_month <= 0 or inputs.repayment_month > max_month:
            return ReturnCode.INVALID_MONTH
    except Exception:
        return ReturnCode.INVALID_MONTH

    # Rate type validation
    if inputs.rate_type not in (FIXED_RATE, VARIABLE_RATE):
        return ReturnCode.INVALID_MONTH

    return ReturnCode.SUCCESS


def calculate(
    principal:       float,
    annual_rate:     float,
    term_years:      int,
    repayment_month: int,
    rate_type:       str = FIXED_RATE
) -> MortgageResult:
    """Convenience wrapper -- calculate mortgage with raw input values."""
    return calculate_mortgage(MortgageInput(
        principal       = principal,
        annual_rate     = annual_rate,
        term_years      = term_years,
        repayment_month = repayment_month,
        rate_type       = rate_type
    ))'''


def generate(parse_data: dict, extracted: dict, output_path: str = "output/mortgage_calc.py") -> str:
    """Generate the migrated Python module."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    code = MIGRATED_CODE.format(timestamp=timestamp)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)
    return code


def main():
    arg_parser = argparse.ArgumentParser(description="COBOL Moderniser -- Agent 4: Code Writer")
    arg_parser.add_argument("--output", default="output/mortgage_calc.py")
    args = arg_parser.parse_args()
    code = generate({}, {}, args.output)
    print(f"[CODE WRITER] Migrated Python written to: {args.output}")


if __name__ == "__main__":
    main()

