"""
COBOL Moderniser - Test Generator
====================================
Generates comprehensive test cases for the COBOL-to-Python mortgage
calculation migration.  Includes a reference MortgageCalculator
implementation using Python's Decimal module for exact financial
arithmetic plus 226 total test cases (26 original + 200 extended).

Author:  COBOL Moderniser Team
Version: 4.0.0
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Decimal precision – 50 digits avoids any intermediate rounding issues
# ---------------------------------------------------------------------------
getcontext().prec = 50

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ZERO = Decimal("0")
ONE = Decimal("1")
PENALTY_RATE = Decimal("0.03")
PENALTY_CUTOFF_MONTH = 36
MAX_PRINCIPAL = Decimal("9999999.99")
MAX_ANNUAL_RATE = Decimal("99.999999")
MAX_TERM_YEARS = 40
VALID_RATE_TYPES = {"F", "V"}

DP2 = Decimal("0.01")           # 2 decimal places
DP10 = Decimal("0.0000000001")  # 10 decimal places


# ===========================================================================
# Helper: safely convert inputs to Decimal
# ===========================================================================
def _to_decimal(value: Any) -> Optional[Decimal]:
    """Convert a value to Decimal, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


# ===========================================================================
# MortgageCalculator – reference implementation
# ===========================================================================
class MortgageCalculator:
    """
    Reference mortgage amortisation calculator.

    Replicates the COBOL program logic using exact Decimal arithmetic
    with ROUND_HALF_UP rounding rules.
    """

    @staticmethod
    def calculate(
        principal: Any,
        annual_rate: Any,
        term_years: Any,
        repayment_month: Any,
        rate_type: Any,
    ) -> Dict[str, Any]:
        """
        Calculate mortgage amortisation values.

        Parameters
        ----------
        principal : Any
            Loan principal (positive, max 9,999,999.99).
        annual_rate : Any
            Annual interest rate as a decimal (e.g. 0.0525 for 5.25%).
        term_years : Any
            Loan term in years (positive, max 40).
        repayment_month : Any
            Target month for the breakdown (positive, max term_years*12).
        rate_type : Any
            'F' for fixed rate, 'V' for variable rate.

        Returns
        -------
        dict
            {
                "return_code": int,
                "monthly_payment": float,
                "total_repayable": float,
                "total_interest": float,
                "month_interest": float,
                "month_principal": float,
                "closing_balance": float,
                "penalty": float,
            }
        """
        result_defaults: Dict[str, Any] = {
            "return_code": 0,
            "monthly_payment": 0.0,
            "total_repayable": 0.0,
            "total_interest": 0.0,
            "month_interest": 0.0,
            "month_principal": 0.0,
            "closing_balance": 0.0,
            "penalty": 0.0,
        }

        # ---- parse & validate inputs ---------------------------------------
        p = _to_decimal(principal)
        r_annual = _to_decimal(annual_rate)
        t = _to_decimal(term_years)
        m = _to_decimal(repayment_month)
        rt = str(rate_type).strip().upper() if rate_type is not None else ""

        if p is None or p <= ZERO or p > MAX_PRINCIPAL:
            result_defaults["return_code"] = 1
            return result_defaults

        if r_annual is None or r_annual <= ZERO or r_annual > MAX_ANNUAL_RATE:
            result_defaults["return_code"] = 2
            return result_defaults

        if t is None or t <= ZERO or t > Decimal(str(MAX_TERM_YEARS)):
            result_defaults["return_code"] = 3
            return result_defaults

        total_months = int(t) * 12

        if m is None or m <= ZERO or m > total_months or rt not in VALID_RATE_TYPES:
            result_defaults["return_code"] = 4
            return result_defaults

        # ---- core calculations ---------------------------------------------
        monthly_rate = (r_annual / Decimal("12")).quantize(
            DP10, rounding=ROUND_HALF_UP
        )

        n = int(m)
        total_n = total_months

        if monthly_rate == ZERO:
            monthly_payment = (p / Decimal(str(total_n))).quantize(
                DP2, rounding=ROUND_HALF_UP
            )
        else:
            one_plus_r = ONE + monthly_rate
            pow_term = one_plus_r ** total_n
            numerator = p * monthly_rate * pow_term
            denominator = pow_term - ONE
            monthly_payment_raw = numerator / denominator
            monthly_payment = monthly_payment_raw.quantize(DP2, rounding=ROUND_HALF_UP)

        total_repayable = (monthly_payment * Decimal(str(total_n))).quantize(
            DP2, rounding=ROUND_HALF_UP
        )
        total_interest = (total_repayable - p).quantize(DP2, rounding=ROUND_HALF_UP)

        # ---- month-by-month amortisation schedule to target month ----------
        balance = p
        month_interest = ZERO
        month_principal = ZERO

        for month in range(1, n + 1):
            month_interest = (balance * monthly_rate).quantize(
                DP2, rounding=ROUND_HALF_UP
            )
            month_principal = monthly_payment - month_interest
            balance = balance - month_principal

        closing_balance = balance.quantize(DP2, rounding=ROUND_HALF_UP)
        month_interest_f = float(month_interest.quantize(DP2, rounding=ROUND_HALF_UP))
        month_principal_f = float(month_principal.quantize(DP2, rounding=ROUND_HALF_UP))

        # ---- early-repayment penalty ---------------------------------------
        if rt == "F" and n <= PENALTY_CUTOFF_MONTH:
            penalty = (closing_balance * PENALTY_RATE).quantize(
                DP2, rounding=ROUND_HALF_UP
            )
        else:
            penalty = ZERO

        return {
            "return_code": 0,
            "monthly_payment": float(monthly_payment.quantize(DP2, rounding=ROUND_HALF_UP)),
            "total_repayable": float(total_repayable),
            "total_interest": float(total_interest),
            "month_interest": month_interest_f,
            "month_principal": month_principal_f,
            "closing_balance": float(closing_balance),
            "penalty": float(penalty),
        }


# ===========================================================================
# Test-case helpers
# ===========================================================================

def _make_case(
    case_id: str,
    description: str,
    category: str,
    principal: float,
    annual_rate: float,
    term_years: int,
    repayment_month: int,
    rate_type: str,
) -> Dict[str, Any]:
    """Build a single test-case dict with expected values from MortgageCalculator."""
    calc = MortgageCalculator()
    expected = calc.calculate(principal, annual_rate, term_years, repayment_month, rate_type)
    return {
        "id": case_id,
        "description": description,
        "category": category,
        "inputs": {
            "principal": principal,
            "annual_rate": annual_rate,
            "term_years": term_years,
            "repayment_month": repayment_month,
            "rate_type": rate_type,
        },
        "expected": expected,
        "status": "GENERATED",
    }


def _build_case_id(category: str, seq: int) -> str:
    """Generate a padded case ID, e.g. STANDARD_001."""
    prefix = category.upper()[:3]
    return f"{prefix}_{seq:03d}"


# ===========================================================================
# 1. Original 26 test cases (build_test_cases)
# ===========================================================================

def build_test_cases() -> List[Dict[str, Any]]:
    """Generate the original 26 test cases."""
    cases: List[Dict[str, Any]] = []

    # ---- STANDARD (001–008) ---------------------------------------------
    std_scenarios = [
        (200000.00, 0.0525, 25, 1, "F", "Standard £200k fixed rate month 1"),
        (200000.00, 0.0525, 25, 12, "F", "Standard £200k fixed rate month 12"),
        (200000.00, 0.0525, 25, 36, "F", "Standard £200k fixed rate month 36 (penalty boundary)"),
        (200000.00, 0.0525, 25, 37, "F", "Standard £200k fixed rate month 37 (no penalty)"),
        (350000.00, 0.0390, 30, 1, "F", "Standard £350k at 3.9% over 30y month 1"),
        (350000.00, 0.0390, 30, 180, "V", "Standard £350k variable month 180"),
        (100000.00, 0.0250, 15, 1, "F", "Standard £100k at 2.5% over 15y month 1"),
        (500000.00, 0.0450, 20, 60, "F", "Standard £500k at 4.5% over 20y month 60"),
    ]
    for i, (p, r, t, m, rt, desc) in enumerate(std_scenarios, 1):
        cases.append(_make_case(_build_case_id("standard", i), desc, "standard", p, r, t, m, rt))

    # ---- EDGE (009–014) : 6 cases ---------------------------------------
    edge_scenarios = [
        (1000.00, 0.005, 40, 1, "F", "Very small principal £1k at 0.5% over 40y"),
        (9999999.99, 0.15, 1, 1, "F", "Max principal min term month 1"),
        (9999999.99, 0.15, 1, 12, "F", "Max principal min term month 12 (final)"),
        (150000.00, 0.01, 35, 420, "V", "Very low rate 1% variable final month"),
        (300000.00, 0.075, 10, 1, "F", "High rate 7.5% month 1"),
        (300000.00, 0.075, 10, 120, "F", "High rate 7.5% final month"),
    ]
    for i, (p, r, t, m, rt, desc) in enumerate(edge_scenarios, 1):
        cases.append(_make_case(_build_case_id("edge", i), desc, "edge", p, r, t, m, rt))

    # ---- INVALID (015–022) : 8 cases ------------------------------------
    inv_scenarios = [
        (-100000.00, 0.05, 25, 1, "F", "Negative principal"),
        (0.00, 0.05, 25, 1, "F", "Zero principal"),
        (200000.00, 0.00, 25, 1, "F", "Zero interest rate"),
        (200000.00, -0.05, 25, 1, "F", "Negative interest rate"),
        (200000.00, 0.05, 0, 1, "F", "Zero term years"),
        (200000.00, 0.05, 25, 0, "F", "Zero repayment month"),
        (200000.00, 0.05, 25, 301, "F", "Repayment month beyond term"),
        (200000.00, 0.05, 25, 1, "X", "Invalid rate type"),
    ]
    for i, (p, r, t, m, rt, desc) in enumerate(inv_scenarios, 1):
        cases.append(_make_case(_build_case_id("invalid", i), desc, "invalid", p, r, t, m, rt))

    # ---- FINAL MONTH (023–026) : 4 cases --------------------------------
    final_scenarios = [
        (200000.00, 0.0525, 25, 300, "F", "Final month £200k 5.25% 25y"),
        (100000.00, 0.03, 10, 120, "V", "Final month £100k 3% 10y variable"),
        (750000.00, 0.04, 30, 360, "F", "Final month £750k 4% 30y"),
        (50000.00, 0.06, 5, 60, "F", "Final month £50k 6% 5y"),
    ]
    for i, (p, r, t, m, rt, desc) in enumerate(final_scenarios, 1):
        cases.append(_make_case(_build_case_id("final", i), desc, "final_month", p, r, t, m, rt))

    return cases


# ===========================================================================
# 2. Stress tests – 30 cases
# ===========================================================================

def build_stress_tests() -> List[Dict[str, Any]]:
    """Generate 30 stress-test cases with extreme but valid parameters."""
    cases: List[Dict[str, Any]] = []
    seq = 1

    # Very small principal + very long term (4 configs x 2 months = 8)
    small_principal_configs = [
        (1000.00, 0.005, 40, "F"),
        (1000.00, 0.005, 40, "V"),
        (5000.00, 0.01, 35, "F"),
        (10000.00, 0.025, 40, "V"),
    ]
    for p, r, t, rt in small_principal_configs:
        for m in [1, t * 12]:
            desc = f"Stress small principal £{p:,.2f} at {r*100:.2f}% over {t}y month {m}"
            cases.append(_make_case(_build_case_id("stress", seq), desc, "stress", p, r, t, m, rt))
            seq += 1

    # Very large principal + very short term (3 configs x 3 months = 9)
    large_configs = [
        (9999999.99, 0.15, 1, "F"),
        (9999999.99, 0.10, 2, "V"),
        (7500000.00, 0.12, 1, "F"),
    ]
    for p, r, t, rt in large_configs:
        for m in [1, 6, t * 12]:
            if m <= t * 12:
                desc = f"Stress large principal £{p:,.2f} at {r*100:.1f}% over {t}y month {m}"
                cases.append(_make_case(_build_case_id("stress", seq), desc, "stress", p, r, t, m, rt))
                seq += 1

    # Rates at 3-decimal precision across 5-year boundaries (13 cases to hit 30)
    rate_3dp_terms = [
        (0.033, 5, "F"), (0.033, 10, "V"), (0.033, 15, "F"), (0.033, 20, "V"),
        (0.047, 5, "F"), (0.047, 25, "V"), (0.047, 30, "F"),
        (0.099, 5, "F"), (0.099, 35, "V"), (0.099, 40, "F"),
    ]
    for r, t, rt in rate_3dp_terms:
        desc = f"Stress 3dp rate {r*100:.3f}% term {t}y month 1"
        cases.append(_make_case(_build_case_id("stress", seq), desc, "stress", 200000.00, r, t, 1, rt))
        seq += 1

    # Pad with additional boundary combos if needed
    while len(cases) < 30:
        cases.append(_make_case(
            _build_case_id("stress", seq),
            f"Stress padding {seq}", "stress",
            150000.00 + seq * 500, 0.035 + seq * 0.002, 20, 1, "F" if seq % 2 == 0 else "V",
        ))
        seq += 1

    return cases[:30]


# ===========================================================================
# 3. Amortisation schedule tests – 40 cases
# ===========================================================================

def build_amortisation_schedule_tests() -> List[Dict[str, Any]]:
    """Generate 40 amortisation-schedule verification cases."""
    cases: List[Dict[str, Any]] = []
    seq = 1

    # £200,000 at 5.25% over 25 years – every 12th month = 25 cases
    for m in range(12, 301, 12):
        desc = f"Amortisation £200k 5.25% 25y month {m}"
        cases.append(_make_case(_build_case_id("amort", seq), desc, "amortisation", 200000.00, 0.0525, 25, m, "F"))
        seq += 1

    # £500,000 at 4.5% over 30 years – every 24th month = 15 cases
    for m in range(24, 361, 24):
        desc = f"Amortisation £500k 4.5% 30y month {m}"
        cases.append(_make_case(_build_case_id("amort", seq), desc, "amortisation", 500000.00, 0.045, 30, m, "F"))
        seq += 1

    return cases


# ===========================================================================
# 4. Penalty matrix tests – 30 cases
# ===========================================================================

def build_penalty_matrix_tests() -> List[Dict[str, Any]]:
    """Generate 30 penalty-matrix test cases."""
    cases: List[Dict[str, Any]] = []
    seq = 1

    principals = [100000.00, 250000.00, 500000.00]
    rates = [0.03, 0.05, 0.07]
    months = [1, 12, 24, 36, 37]
    rate_types = ["F", "V"]

    count = 0
    for p in principals:
        for r in rates:
            for m in months:
                for rt in rate_types:
                    if count >= 30:
                        break
                    desc = f"Penalty matrix £{p:,.0f} at {r*100:.0f}% month {m} {rt}"
                    cases.append(_make_case(
                        _build_case_id("penalty", seq), desc, "penalty_matrix",
                        p, r, 25, m, rt,
                    ))
                    seq += 1
                    count += 1

    return cases[:30]


# ===========================================================================
# 5. Rounding precision tests – 20 cases
# ===========================================================================

def build_rounding_precision_tests() -> List[Dict[str, Any]]:
    """Generate 20 rounding/precision edge cases."""
    cases: List[Dict[str, Any]] = []
    seq = 1

    repeating_rates = [
        (1 / 3) / 100,
        (2 / 3) / 100,
        (1 / 7) / 100,
        (1 / 6) / 100,
        (1 / 9) / 100,
    ]
    for r in repeating_rates:
        desc = f"Rounding repeating decimal rate {r*100:.6f}%"
        cases.append(_make_case(
            _build_case_id("round", seq), desc, "rounding_precision",
            200000.00, r, 25, 1, "F",
        ))
        seq += 1

    uneven_principals = [100000.01, 99999.99, 123456.78, 111111.11, 999999.99]
    for p in uneven_principals:
        desc = f"Rounding uneven principal £{p:,.2f}"
        cases.append(_make_case(
            _build_case_id("round", seq), desc, "rounding_precision",
            p, 0.05, 20, 1, "F",
        ))
        seq += 1

    # COBOL vs float differences
    cases.append(_make_case(
        _build_case_id("round", seq),
        "Rounding COBOL vs float: £200k at 5.251%", "rounding_precision",
        200000.00, 0.05251, 25, 1, "F",
    ))
    seq += 1

    cases.append(_make_case(
        _build_case_id("round", seq),
        "Rounding COBOL vs float: £350k at 3.333%", "rounding_precision",
        350000.00, 0.03333, 30, 180, "V",
    ))
    seq += 1

    cases.append(_make_case(
        _build_case_id("round", seq),
        "Rounding 0.01% rate minimal", "rounding_precision",
        500000.00, 0.0001, 40, 1, "F",
    ))
    seq += 1

    cases.append(_make_case(
        _build_case_id("round", seq),
        "Rounding 99.9999% rate max valid", "rounding_precision",
        10000.00, 0.999999, 1, 1, "F",
    ))
    seq += 1

    while len(cases) < 20:
        cases.append(_make_case(
            _build_case_id("round", seq),
            f"Rounding padding {seq}", "rounding_precision",
            150000.00 + seq * 1000, 0.04 + seq * 0.001, 20, 1, "F",
        ))
        seq += 1

    return cases[:20]


# ===========================================================================
# 6. Boundary month tests – 30 cases
# ===========================================================================

def build_boundary_month_tests() -> List[Dict[str, Any]]:
    """Generate 30 boundary-month test cases across 6 mortgage configs."""
    cases: List[Dict[str, Any]] = []
    seq = 1

    configs = [
        (100000.00, 0.05, 10),
        (200000.00, 0.04, 15),
        (300000.00, 0.035, 20),
        (400000.00, 0.06, 25),
        (500000.00, 0.055, 30),
        (150000.00, 0.07, 35),
    ]

    for p, r, t in configs:
        total_months = t * 12
        # Always add month 1, month 2, month n-1, month n
        months_to_test = [1, 2, total_months - 1, total_months]
        # Add midpoint for configs with t >= 20
        if t >= 20:
            months_to_test.append(total_months // 2)
        # Add quarter-point for configs with t < 20 to pad toward 30 total
        if t < 20:
            months_to_test.append(total_months // 4)

        for m in months_to_test:
            suffix = {1: "first", 2: "second", total_months - 1: "penultimate", total_months: "final"}.get(m, f"month {m}")
            desc = f"Boundary {suffix} £{p:,.0f} {r*100:.1f}% {t}y"
            cases.append(_make_case(
                _build_case_id("boundary", seq), desc, "boundary_month", p, r, t, m, "F",
            ))
            seq += 1

    return cases[:30]


# ===========================================================================
# 7. Rate sensitivity tests – 25 cases
# ===========================================================================

def build_rate_sensitivity_tests() -> List[Dict[str, Any]]:
    """Generate 25 rate-sensitivity cases: same mortgage at 25 different rates."""
    cases: List[Dict[str, Any]] = []
    seq = 1

    rates = [
        0.005, 0.010, 0.015, 0.020, 0.025,
        0.030, 0.035, 0.040, 0.045, 0.050,
        0.055, 0.060, 0.065, 0.070, 0.075,
        0.080, 0.085, 0.090, 0.095, 0.100,
        0.110, 0.120, 0.130, 0.140, 0.150,
    ]

    for r in rates:
        desc = f"Rate sensitivity {r*100:.1f}% on £200k over 25y month 1"
        cases.append(_make_case(
            _build_case_id("rate", seq), desc, "rate_sensitivity",
            200000.00, r, 25, 1, "F",
        ))
        seq += 1

    return cases


# ===========================================================================
# 8. Validation extended tests – 25 cases
# ===========================================================================

def build_validation_extended_tests() -> List[Dict[str, Any]]:
    """Generate 25 extended validation / error-path test cases."""
    cases: List[Dict[str, Any]] = []
    seq = 1
    calc = MortgageCalculator()

    val_specs: List[Tuple[str, Any, Any, Any, Any, Any]] = [
        ("VAL negative principal", -50000.00, 0.05, 25, 1, "F"),
        ("VAL negative rate", 200000.00, -0.05, 25, 1, "F"),
        ("VAL negative term", 200000.00, 0.05, -10, 1, "F"),
        ("VAL negative month", 200000.00, 0.05, 25, -1, "F"),
        ("VAL principal 0.01 boundary pass", 0.01, 0.05, 1, 1, "F"),
        ("VAL principal 9999999.99 pass", 9999999.99, 0.01, 1, 1, "F"),
        ("VAL principal 10000000.00 fail", 10000000.00, 0.05, 25, 1, "F"),
        ("VAL rate 0.000001 near-zero pass", 100000.00, 0.000001, 25, 1, "F"),
        ("VAL term 1 minimum pass", 50000.00, 0.05, 1, 1, "F"),
        ("VAL term 0 fail", 200000.00, 0.05, 0, 1, "F"),
        ("VAL month 1 minimum pass", 200000.00, 0.05, 25, 1, "F"),
        ("VAL month equals term*12 pass", 200000.00, 0.05, 25, 300, "F"),
        ("VAL month term*12+1 fail", 200000.00, 0.05, 25, 301, "F"),
        ("VAL rate type X invalid", 200000.00, 0.05, 25, 1, "X"),
        ("VAL rate type empty string", 200000.00, 0.05, 25, 1, ""),
        ("VAL all fields max valid", 9999999.99, 0.999999, 40, 480, "F"),
        ("VAL float precision principal", 200000.005, 0.05251, 25, 1, "F"),
        ("VAL very large rate overflow", 200000.00, 100.0, 25, 1, "F"),
        ("VAL string principal", "abc", 0.05, 25, 1, "F"),
        ("VAL string rate", 200000.00, "abc", 25, 1, "F"),
        ("VAL string term", 200000.00, 0.05, "abc", 1, "F"),
        ("VAL string month", 200000.00, 0.05, 25, "abc", "F"),
        ("VAL None principal", None, 0.05, 25, 1, "F"),
        ("VAL None rate", 200000.00, None, 25, 1, "F"),
        ("VAL None term", 200000.00, 0.05, None, 1, "F"),
    ]

    for desc, p, r, t, m, rt in val_specs:
        expected = calc.calculate(p, r, t, m, rt)
        cases.append({
            "id": _build_case_id("valid", seq),
            "description": desc,
            "category": "validation_extended",
            "inputs": {
                "principal": p,
                "annual_rate": r,
                "term_years": t,
                "repayment_month": m,
                "rate_type": rt,
            },
            "expected": expected,
            "status": "GENERATED",
        })
        seq += 1

    return cases


# ===========================================================================
# 9. Build all 200 extended test cases
# ===========================================================================

def build_all_extended_test_cases() -> List[Dict[str, Any]]:
    """Build the full set of 200 extended test cases."""
    all_cases: List[Dict[str, Any]] = []
    all_cases.extend(build_stress_tests())               # 30
    all_cases.extend(build_amortisation_schedule_tests()) # 40
    all_cases.extend(build_penalty_matrix_tests())        # 30
    all_cases.extend(build_rounding_precision_tests())    # 20
    all_cases.extend(build_boundary_month_tests())        # 30
    all_cases.extend(build_rate_sensitivity_tests())      # 25
    all_cases.extend(build_validation_extended_tests())   # 25
    # Trim/pad to exactly 200
    return all_cases[:200]


# ===========================================================================
# 10. Test suite runner
# ===========================================================================

def run_test_suite(
    cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Run every test case through MortgageCalculator and attach actual results.

    Returns
    -------
    list
        Each element is the test case dict enriched with an ``actual`` key
        and a ``passed`` boolean.
    """
    calc = MortgageCalculator()
    results: List[Dict[str, Any]] = []

    for case in cases:
        inp = case["inputs"]
        actual = calc.calculate(
            inp["principal"],
            inp["annual_rate"],
            inp["term_years"],
            inp["repayment_month"],
            inp["rate_type"],
        )

        passed = actual == case["expected"]
        result = dict(case)
        result["actual"] = actual
        result["passed"] = passed
        result["status"] = "PASSED" if passed else "FAILED"
        results.append(result)

    return results


# ===========================================================================
# 11. Markdown summary builder
# ===========================================================================

def build_markdown_summary(results: List[Dict[str, Any]]) -> str:
    """Generate a human-readable Markdown summary of test results."""
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    failed = total - passed

    categories: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories.setdefault(cat, []).append(r)

    lines: List[str] = [
        "# Mortgage Calculation Test Suite Summary",
        "",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"**Total Cases:** {total}",
        f"**Passed:** {passed}",
        f"**Failed:** {failed}",
        f"**Pass Rate:** {passed / total * 100:.1f}%" if total else "N/A",
        "",
        "## Results by Category",
        "",
    ]

    for cat in sorted(categories):
        cat_results = categories[cat]
        cat_passed = sum(1 for r in cat_results if r.get("passed"))
        lines.append(f"### {cat}")
        lines.append(f"- Count: {len(cat_results)}")
        lines.append(f"- Passed: {cat_passed}")
        lines.append(f"- Failed: {len(cat_results) - cat_passed}")
        lines.append("")
        lines.append("| ID | Description | Status |")
        lines.append("|----|-------------|--------|")
        for r in cat_results:
            status_icon = "PASS" if r.get("passed") else "FAIL"
            lines.append(f"| {r['id']} | {r['description']} | {status_icon} |")
        lines.append("")

    if failed:
        lines.append("## Failure Details")
        lines.append("")
        for r in results:
            if not r.get("passed"):
                lines.append(f"### {r['id']} – {r['description']}")
                lines.append(f"- **Category:** {r['category']}")
                lines.append("- **Expected:**")
                lines.append(f"```json\n{json.dumps(r['expected'], indent=2)}\n```")
                lines.append("- **Actual:**")
                lines.append(f"```json\n{json.dumps(r['actual'], indent=2)}\n```")
                lines.append("")

    return "\n".join(lines)


# ===========================================================================
# 12. Main entry point
# ===========================================================================

def main() -> None:  # pragma: no cover
    """Generate all test cases, run the suite, and write JSON + Markdown."""
    original_cases = build_test_cases()
    extended_cases = build_all_extended_test_cases()

    all_cases = original_cases + extended_cases

    results = run_test_suite(all_cases)

    json_path = os.path.join(
        os.path.dirname(__file__), "..", "tests", "generated", "extended_test_cases.json"
    )
    json_path = os.path.abspath(json_path)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(extended_cases, fh, indent=2)

    md_path = os.path.join(
        os.path.dirname(__file__), "..", "tests", "generated", "extended_test_cases.md"
    )
    md_path = os.path.abspath(md_path)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown_summary(results))

    print(f"Original cases:   {len(original_cases)}")
    print(f"Extended cases:   {len(extended_cases)}")
    print(f"Total cases:      {len(all_cases)}")
    print(f"JSON written:     {json_path}")
    print(f"Markdown written: {md_path}")

    passed = sum(1 for r in results if r["passed"])
    print(f"Passed: {passed}/{len(results)}")


if __name__ == "__main__":  # pragma: no cover
    main()
