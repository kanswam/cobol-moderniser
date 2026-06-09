#!/usr/bin/env python3
"""
=============================================================================
COBOL MODERNISER — AGENT 7 (Externaliser)
=============================================================================
Purpose:
    Extract business rules from the simplified Python mortgage calculator
    and express them as standalone YAML, JSON, and Markdown files —
    completely separate from the code.

    A business analyst, compliance officer, or regulator can read,
    understand, and propose changes to business rules WITHOUT opening
    a Python file.

Output files (written to the specified output directory):
    - business_rules.yaml    : Machine-readable rules (PyYAML-compatible)
    - business_rules.json    : Same data as JSON for API consumers
    - business_rules.md      : Narrative version for non-technical audiences

Usage:
    python agents/externaliser.py
    python agents/externaliser.py --output-dir output

Author:  COBOL Moderniser Team
Version: 1.0.0
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# BUSINESS RULES DATA
# Hardcoded for now — fully schema-specified and self-contained.
# These rules were extracted from the original COBOL MORTGAGE-CALC program
# (mortgage_calc.cbl, dated 1987-03-14) and the migrated Python module.
# ---------------------------------------------------------------------------

_BUSINESS_RULES: Dict[str, Any] = {
    "program": {
        "name": "MORTGAGE-CALC",
        "description": "UK Mortgage Amortisation Calculator",
        "original_language": "COBOL",
        "original_date": "1987-03-14",
        "migrated_to": "Python",
        "migration_date": "2026-05-25",
        "version": "1.0.0",
    },
    "calculation_rules": {
        "interest": {
            "name": "Monthly Interest Rate Calculation",
            "description": (
                "The annual interest rate is divided by 12 to produce the monthly "
                "rate used in all payment calculations."
            ),
            "formula": "monthly_rate = annual_rate / 12",
            "precision": 10,
            "rounding": "ROUND_HALF_UP",
            "regulatory_basis": "Standard UK mortgage convention",
        },
        "monthly_payment": {
            "name": "Monthly Repayment Calculation",
            "description": (
                "Uses the standard amortisation formula to calculate a fixed monthly "
                "payment that will repay both principal and interest over the full term."
            ),
            "formula": "M = P x r(1+r)^n / ((1+r)^n - 1)",
            "variables": {
                "M": "Monthly repayment amount",
                "P": "Principal loan amount",
                "r": "Monthly interest rate",
                "n": "Total number of monthly payments",
            },
            "precision": 2,
            "rounding": "ROUND_HALF_UP",
        },
        "rounding": {
            "name": "Financial Rounding Rule",
            "description": (
                "All financial calculations are rounded to 2 decimal places using "
                "ROUND_HALF_UP -- matching the original COBOL ROUNDED behaviour. "
                "This ensures penny-level accuracy and regulatory compliance."
            ),
            "method": "ROUND_HALF_UP",
            "decimal_places": 2,
            "regulatory_basis": "FSA mortgage conduct rules 1998",
        },
    },
    "validation_rules": {
        "principal": {
            "name": "Loan Amount Validation",
            "description": (
                "The principal must be a positive amount within system limits"
            ),
            "minimum": Decimal("0.01"),
            "maximum": Decimal("9999999.99"),
            "currency": "GBP",
            "error_code": 1,
            "error_name": "INVALID_PRINCIPAL",
        },
        "annual_rate": {
            "name": "Interest Rate Validation",
            "description": (
                "The annual interest rate must be positive and within limits"
            ),
            "minimum": Decimal("0.000001"),
            "maximum": Decimal("99.999999"),
            "unit": "decimal",
            "error_code": 2,
            "error_name": "INVALID_RATE",
        },
        "term": {
            "name": "Loan Term Validation",
            "description": "The loan term must be between 1 and 40 years",
            "minimum_years": 1,
            "maximum_years": 40,
            "error_code": 3,
            "error_name": "INVALID_TERM",
        },
        "repayment_month": {
            "name": "Repayment Month Validation",
            "description": (
                "The requested repayment month must fall within the loan term. "
                "Month 1 is the first payment, month N is the final payment."
            ),
            "minimum": 1,
            "maximum": "term_years x 12",
            "error_code": 4,
            "error_name": "INVALID_MONTH",
        },
    },
    "penalty_rules": {
        "early_repayment": {
            "name": "Early Repayment Penalty",
            "description": (
                "A penalty is charged when a borrower repays a fixed-rate mortgage "
                "early within the first 3 years (36 months). This compensates the "
                "lender for lost interest income during the fixed-rate period. "
                "Variable-rate mortgages are exempt because the lender's risk "
                "profile differs -- rate changes already absorb some of this risk."
            ),
            "penalty_rate": Decimal("0.03"),
            "penalty_rate_pct": "3%",
            "applies_when": {
                "rate_type": "FIXED",
                "repayment_month_max": 36,
            },
            "exempt_when": {
                "rate_type": "VARIABLE",
            },
            "calculation": "penalty = outstanding_balance x 0.03",
            "regulatory_basis": "FSA mortgage conduct rules 1992",
            "last_reviewed": "2003-09-30",
        },
    },
    "rate_types": {
        "FIXED": {
            "code": "F",
            "description": (
                "Fixed interest rate -- rate does not change during the term. "
                "Early repayment penalty applies within first 36 months."
            ),
        },
        "VARIABLE": {
            "code": "V",
            "description": (
                "Variable interest rate -- rate may change during the term. "
                "No early repayment penalty applies."
            ),
        },
    },
    "change_log": [
        {
            "date": "1987-03-14",
            "change": "Initial implementation",
            "author": "Systems Development Team",
        },
        {
            "date": "1992-11-02",
            "change": "Added early repayment penalty logic",
            "regulatory_driver": "FSA mortgage conduct rules",
        },
        {
            "date": "1998-06-15",
            "change": "Updated rounding to comply with FSA rules",
            "regulatory_driver": "FSA rounding standards",
        },
        {
            "date": "2003-09-30",
            "change": "Added variable rate support",
        },
        {
            "date": "2026-05-25",
            "change": "Migrated from COBOL to Python by COBOL Moderniser",
        },
    ],
}


# ---------------------------------------------------------------------------
# SERIALISATION HELPERS
# ---------------------------------------------------------------------------

def _decimal_handler(obj: Any) -> Any:
    """Convert Decimal objects to float for JSON serialisation."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


def _ensure_dir(path: str) -> None:
    """Create parent directories for *path* if they do not exist."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# YAML GENERATOR
# ---------------------------------------------------------------------------

def _generate_yaml(rules: Dict[str, Any]) -> str:
    """Generate the business_rules.yaml file content as a string."""
    # Build YAML manually for precise control over formatting and comments.
    lines: list[str] = [
        "# ============================================================",
        "# MORTGAGE-CALC BUSINESS RULES",
        "# Generated by COBOL Moderniser -- Agent 7 (Externaliser)",
        "# Source: MORTGAGE-CALC (mortgage_calc.cbl, 1987)",
        "# ============================================================",
        "",
        "program:",
        f'  name: {rules["program"]["name"]}',
        f'  description: {rules["program"]["description"]}',
        f'  original_language: {rules["program"]["original_language"]}',
        f'  original_date: "{rules["program"]["original_date"]}"',
        f'  migrated_to: {rules["program"]["migrated_to"]}',
        f'  migration_date: "{rules["program"]["migration_date"]}"',
        f'  version: "{rules["program"]["version"]}"',
        "",
        "calculation_rules:",
        "  interest:",
        f'    name: {rules["calculation_rules"]["interest"]["name"]}',
        "    description: >",
        "      The annual interest rate is divided by 12 to produce the monthly",
        "      rate used in all payment calculations.",
        f'    formula: "{rules["calculation_rules"]["interest"]["formula"]}"',
        f'    precision: {rules["calculation_rules"]["interest"]["precision"]}',
        f'    rounding: {rules["calculation_rules"]["interest"]["rounding"]}',
        f'    regulatory_basis: "{rules["calculation_rules"]["interest"]["regulatory_basis"]}"',
        "",
        "  monthly_payment:",
        f'    name: {rules["calculation_rules"]["monthly_payment"]["name"]}',
        "    description: >",
        "      Uses the standard amortisation formula to calculate a fixed monthly",
        "      payment that will repay both principal and interest over the full term.",
        f'    formula: "{rules["calculation_rules"]["monthly_payment"]["formula"]}"',
        "    variables:",
    ]

    variables = rules["calculation_rules"]["monthly_payment"]["variables"]
    for var_key, var_desc in variables.items():
        lines.append(f"      {var_key}: {var_desc}")

    lines.extend([
        f'    precision: {rules["calculation_rules"]["monthly_payment"]["precision"]}',
        f'    rounding: {rules["calculation_rules"]["monthly_payment"]["rounding"]}',
        "",
        "  rounding:",
        f'    name: {rules["calculation_rules"]["rounding"]["name"]}',
        "    description: >",
        "      All financial calculations are rounded to 2 decimal places using",
        "      ROUND_HALF_UP -- matching the original COBOL ROUNDED behaviour.",
        "      This ensures penny-level accuracy and regulatory compliance.",
        f'    method: {rules["calculation_rules"]["rounding"]["method"]}',
        f'    decimal_places: {rules["calculation_rules"]["rounding"]["decimal_places"]}',
        f'    regulatory_basis: "{rules["calculation_rules"]["rounding"]["regulatory_basis"]}"',
        "",
        "validation_rules:",
        "  principal:",
        f'    name: {rules["validation_rules"]["principal"]["name"]}',
        f'    description: {rules["validation_rules"]["principal"]["description"]}',
        f'    minimum: {float(rules["validation_rules"]["principal"]["minimum"])}',
        f'    maximum: {float(rules["validation_rules"]["principal"]["maximum"])}',
        f'    currency: {rules["validation_rules"]["principal"]["currency"]}',
        f'    error_code: {rules["validation_rules"]["principal"]["error_code"]}',
        f'    error_name: {rules["validation_rules"]["principal"]["error_name"]}',
        "",
        "  annual_rate:",
        f'    name: {rules["validation_rules"]["annual_rate"]["name"]}',
        f'    description: {rules["validation_rules"]["annual_rate"]["description"]}',
        f'    minimum: {float(rules["validation_rules"]["annual_rate"]["minimum"])}',
        f'    maximum: {float(rules["validation_rules"]["annual_rate"]["maximum"])}',
        f'    unit: {rules["validation_rules"]["annual_rate"]["unit"]}',
        f'    error_code: {rules["validation_rules"]["annual_rate"]["error_code"]}',
        f'    error_name: {rules["validation_rules"]["annual_rate"]["error_name"]}',
        "",
        "  term:",
        f'    name: {rules["validation_rules"]["term"]["name"]}',
        f'    description: {rules["validation_rules"]["term"]["description"]}',
        f'    minimum_years: {rules["validation_rules"]["term"]["minimum_years"]}',
        f'    maximum_years: {rules["validation_rules"]["term"]["maximum_years"]}',
        f'    error_code: {rules["validation_rules"]["term"]["error_code"]}',
        f'    error_name: {rules["validation_rules"]["term"]["error_name"]}',
        "",
        "  repayment_month:",
        f'    name: {rules["validation_rules"]["repayment_month"]["name"]}',
        "    description: >",
        "      The requested repayment month must fall within the loan term.",
        "      Month 1 is the first payment, month N is the final payment.",
        f'    minimum: {rules["validation_rules"]["repayment_month"]["minimum"]}',
        f'    maximum: "{rules["validation_rules"]["repayment_month"]["maximum"]}"',
        f'    error_code: {rules["validation_rules"]["repayment_month"]["error_code"]}',
        f'    error_name: {rules["validation_rules"]["repayment_month"]["error_name"]}',
        "",
        "penalty_rules:",
        "  early_repayment:",
        f'    name: {rules["penalty_rules"]["early_repayment"]["name"]}',
        "    description: >",
        "      A penalty is charged when a borrower repays a fixed-rate mortgage",
        "      early within the first 3 years (36 months). This compensates the",
        "      lender for lost interest income during the fixed-rate period.",
        "      Variable-rate mortgages are exempt because the lender's risk",
        "      profile differs -- rate changes already absorb some of this risk.",
        f'    penalty_rate: {float(rules["penalty_rules"]["early_repayment"]["penalty_rate"])}',
        f'    penalty_rate_pct: "{rules["penalty_rules"]["early_repayment"]["penalty_rate_pct"]}"',
        "    applies_when:",
        f'      rate_type: {rules["penalty_rules"]["early_repayment"]["applies_when"]["rate_type"]}',
        f'      repayment_month_max: '
        f'{rules["penalty_rules"]["early_repayment"]["applies_when"]["repayment_month_max"]}',
        "    exempt_when:",
        f'      rate_type: {rules["penalty_rules"]["early_repayment"]["exempt_when"]["rate_type"]}',
        f'    calculation: "{rules["penalty_rules"]["early_repayment"]["calculation"]}"',
        f'    regulatory_basis: '
        f'"{rules["penalty_rules"]["early_repayment"]["regulatory_basis"]}"',
        f'    last_reviewed: "{rules["penalty_rules"]["early_repayment"]["last_reviewed"]}"',
        "",
        "rate_types:",
        "  FIXED:",
        f'    code: "{rules["rate_types"]["FIXED"]["code"]}"',
        "    description: >",
        "      Fixed interest rate -- rate does not change during the term.",
        "      Early repayment penalty applies within first 36 months.",
        "  VARIABLE:",
        f'    code: "{rules["rate_types"]["VARIABLE"]["code"]}"',
        "    description: >",
        "      Variable interest rate -- rate may change during the term.",
        "      No early repayment penalty applies.",
        "",
        "change_log:",
    ])

    for entry in rules["change_log"]:
        lines.append(f'  - date: "{entry["date"]}"')
        lines.append(f'    change: {entry["change"]}')
        if "author" in entry:
            lines.append(f'    author: {entry["author"]}')
        if "regulatory_driver" in entry:
            lines.append(f'    regulatory_driver: {entry["regulatory_driver"]}')

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MARKDOWN GENERATOR
# ---------------------------------------------------------------------------

def _generate_markdown(rules: Dict[str, Any]) -> str:
    """Generate the business_rules.md file content as a string."""
    lines: list[str] = [
        "# MORTGAGE-CALC Business Rules Document",
        "",
        "| | |",
        "|---|---|",
        f'| **Program** | {rules["program"]["name"]} |',
        f'| **Description** | {rules["program"]["description"]} |',
        f'| **Original language** | {rules["program"]["original_language"]} ({rules["program"]["original_date"]}) |',
        f'| **Migrated to** | {rules["program"]["migrated_to"]} ({rules["program"]["migration_date"]}) |',
        f'| **Version** | {rules["program"]["version"]} |',
        "",
        "---",
        "",
        "## 1. Who Should Read This Document",
        "",
        "This document is written for **non-technical readers** who need to",
        "understand or influence how the mortgage calculator works.",
        "",
        "**Intended audience:**",
        "- **Business Analysts** -- who need to verify the calculator behaves",
        "  correctly for different mortgage products",
        "- **Compliance Officers** -- who need to confirm regulatory rules are",
        "  correctly encoded (e.g. early repayment penalties, rounding rules)",
        "- **Regulators** -- who may audit the logic against published",
        "  conduct rules",
        "- **Product Managers** -- who want to propose changes (e.g. new",
        "  penalty rates, additional rate types)",
        "",
        "You do **not** need to read Python code to understand this document.",
        "Every rule is explained in plain English.",
        "",
        "---",
        "",
        "## 2. What This Program Does",
        "",
        "The Mortgage Amortisation Calculator works out:",
        "",
        "1. **Your fixed monthly payment** -- the amount you pay every month",
        "   for the life of the mortgage",
        "2. **How much of each payment is interest vs. principal** -- in the",
        "   early years, most of your payment is interest; in later years,",
        "   most goes toward paying off the loan",
        "3. **Your remaining balance** -- how much you still owe after any",
        "   given month",
        "4. **Total cost over the full term** -- the sum of all payments",
        "   you will make",
        "5. **Early repayment penalty** -- a charge that may apply if you",
        "   pay off a fixed-rate mortgage early",
        "",
        "---",
        "",
        "## 3. How Your Monthly Payment Is Calculated",
        "",
        "The calculator uses the **standard amortisation formula** -- the same",
        "method used by virtually all UK mortgage lenders since the 1980s.",
        "",
        "### The Formula (in plain English)",
        "",
        "Your monthly payment is calculated so that, if you make every payment",
        "on time, the loan is fully repaid at the end of the term. The formula",
        "takes into account:",
        "",
        "- How much you borrowed (the **principal**)",
        "- The annual interest rate (e.g. 5.25% per year)",
        "- How long the mortgage runs (the **term**, in years)",
        "",
        "The annual rate is first divided by 12 to get a **monthly interest",
        "rate**. Then the formula works out the fixed payment that will clear",
        "the debt over all those months.",
        "",
        "### Mathematical Formula",
        "",
        "```",
        "M = P x r(1+r)^n / ((1+r)^n - 1)",
        "```",
        "",
        "Where:",
        "",
        "| Symbol | Meaning |",
        "|--------|---------|",
        "| **M** | Monthly repayment amount |",
        "| **P** | Principal (amount borrowed) |",
        "| **r** | Monthly interest rate (annual rate / 12) |",
        "| **n** | Total number of monthly payments (term in years x 12) |",
        "",
        "### Rounding",
        "",
        "All calculations are rounded to **2 decimal places** (penny accuracy).",
        "The rounding method is **ROUND_HALF_UP** -- this means 0.005 rounds",
        "up to 0.01. This matches the rounding behaviour of the original COBOL",
        "system and complies with **FSA mortgage conduct rules (1998)**.",
        "",
        "---",
        "",
        "## 4. How Interest and Principal Are Split Each Month",
        "",
        "Every monthly payment is split into two parts:",
        "",
        "1. **Interest portion** -- the lender's charge for lending you money.",
        "   This is calculated as: `balance x monthly interest rate`, rounded",
        "   to the nearest penny.",
        "2. **Principal portion** -- the rest of your payment goes toward",
        "   reducing the amount you owe. This is: `monthly payment - interest",
        "   portion`.",
        "",
        "### How the Split Changes Over Time",
        "",
        "Early in the mortgage, your balance is high, so the interest portion",
        "is large and the principal portion is small. As you gradually pay down",
        "the loan, the balance decreases, so the interest portion gets smaller",
        "and more of each payment goes toward the principal.",
        "",
        "For example, on a 200,000 GBP mortgage at 5.25% over 25 years:",
        "",
        "| Month | Interest | Principal | Balance Remaining |",
        "|-------|----------|-----------|-------------------|",
        "| 1 | ~875.00 | ~324.62 | ~199,675.38 |",
        "| 12 | ~866.54 | ~333.08 | ~196,813.08 |",
        "| 180 (mid-term) | ~524.44 | ~675.18 | ~129,536.82 |",
        "| 300 (final) | ~7.06 | ~1,192.56 | 0.00 |",
        "",
        "These figures are illustrative -- actual values are calculated to the",
        "exact penny.",
        "",
        "---",
        "",
        "## 5. Early Repayment Penalty",
        "",
        "### What Is It?",
        "",
        "An **early repayment penalty** (also called an early redemption charge)",
        "is a fee you may have to pay if you repay your mortgage before the end",
        "of the term. This exists because the lender expected to receive a",
        "certain amount of interest income over the fixed-rate period.",
        "",
        "### When Does It Apply?",
        "",
        "The penalty **only applies** when **all three** conditions are true:",
        "",
        "1. You have a **fixed-rate** mortgage (not a variable-rate one)",
        "2. You repay early within the **first 36 months** (3 years) of the",
        "   mortgage",
        "3. There is still an outstanding balance to penalise",
        "",
        "### When Is There NO Penalty?",
        "",
        "No penalty is charged if:",
        "",
        "- You have a **variable-rate** mortgage (rate type = VARIABLE)",
        "- You repay **after month 36** (even on a fixed-rate mortgage)",
        "- You reach the natural end of the mortgage term",
        "",
        "### How Much Is the Penalty?",
        "",
        "The penalty is **3% of the outstanding balance** at the time of",
        "repayment. For example:",
        "",
        "| Outstanding Balance | Penalty (3%) |",
        "|---------------------|--------------|",
        "| 200,000.00 | 6,000.00 |",
        "| 150,000.00 | 4,500.00 |",
        "| 50,000.00 | 1,500.00 |",
        "",
        "The penalty is calculated after the normal monthly payment and",
        "interest have been applied for that month.",
        "",
        "### Why the Difference Between Fixed and Variable Rates?",
        "",
        "**Fixed-rate mortgages:** The lender locks in an interest rate for",
        "the full term. If you repay early, the lender loses the expected",
        "interest income. The penalty compensates for this loss.",
        "",
        "**Variable-rate mortgages:** The interest rate can change over time.",
        "The lender's risk profile is different -- rate changes already",
        "absorb some of the risk of early repayment. Therefore, no penalty",
        "is charged.",
        "",
        "### Regulatory Basis",
        "",
        "This penalty structure is based on the **FSA mortgage conduct rules",
        "(1992)**. The penalty rate was last reviewed on **30 September 2003**.",
        "",
        "---",
        "",
        "## 6. Input Constraints (Validation Rules)",
        "",
        "The calculator checks all inputs before performing any calculations.",
        "If an input is invalid, an error code is returned and no calculation",
        "is performed.",
        "",
        "| Input | Minimum | Maximum | Unit | Error Code | Error Name |",
        "|-------|---------|---------|------|------------|------------|",
        f'| Principal (loan amount) | 0.01 | 9,999,999.99 | GBP | '
        f'{rules["validation_rules"]["principal"]["error_code"]} | '
        f'{rules["validation_rules"]["principal"]["error_name"]} |',
        f'| Annual interest rate | 0.000001 | 99.999999 | decimal | '
        f'{rules["validation_rules"]["annual_rate"]["error_code"]} | '
        f'{rules["validation_rules"]["annual_rate"]["error_name"]} |',
        f'| Loan term | 1 year | 40 years | years | '
        f'{rules["validation_rules"]["term"]["error_code"]} | '
        f'{rules["validation_rules"]["term"]["error_name"]} |',
        f'| Repayment month | 1 | term x 12 | months | '
        f'{rules["validation_rules"]["repayment_month"]["error_code"]} | '
        f'{rules["validation_rules"]["repayment_month"]["error_name"]} |',
        "",
        "**Error codes** follow the original COBOL convention:",
        "0 = Success, 1 = Invalid Principal, 2 = Invalid Rate,",
        "3 = Invalid Term, 4 = Invalid Month.",
        "",
        "---",
        "",
        "## 7. Rate Types",
        "",
        "The calculator supports two types of interest rate:",
        "",
        "### Fixed Rate (code: F)",
        "",
        "- The interest rate stays the same for the entire mortgage term",
        "- Early repayment penalty applies if you repay within the first 36 months",
        "- Suitable for borrowers who want payment certainty",
        "",
        "### Variable Rate (code: V)",
        "",
        "- The interest rate may change during the mortgage term",
        "- No early repayment penalty applies",
        "- Suitable for borrowers willing to accept rate fluctuation",
        "",
        "The rate type is set when the mortgage is created and does not change",
        "during the life of the loan.",
        "",
        "---",
        "",
        "## 8. Change Log",
        "",
        "| Date | Change | Author / Driver |",
        "|------|--------|-----------------|",
    ]

    for entry in rules["change_log"]:
        author = entry.get("author", entry.get("regulatory_driver", "-"))
        lines.append(f'| {entry["date"]} | {entry["change"]} | {author} |')

    lines.extend([
        "",
        "---",
        "",
        "## 9. How to Propose a Rule Change",
        "",
        "Business rules are stored in three separate files (all containing the",
        "same information in different formats):",
        "",
        "| File | Format | Best For |",
        "|------|--------|----------|",
        "| `business_rules.yaml` | YAML | Technical systems, CI/CD pipelines |",
        "| `business_rules.json` | JSON | API integrations, web front-ends |",
        "| `business_rules.md` | Markdown | Human reading, compliance reviews |",
        "",
        "### To propose a change:",
        "",
        "1. **Open `business_rules.md`** to understand the current rules",
        "2. **Edit `business_rules.yaml`** -- this is the master file that",
        "   the Python calculator reads",
        "3. **Submit the changed YAML file** to the development team with a",
        "   brief explanation of why the change is needed",
        "4. **The development team** will review the change, update the",
        "   corresponding `.md` and `.json` files, run the full test suite",
        "   (226 test cases), and deploy the updated rules",
        "",
        "### Common change examples:",
        "",
        "- **Penalty rate change**: Edit `penalty_rate` under",
        "  `penalty_rules.early_repayment` (e.g. change 0.03 to 0.02 for 2%)",
        "- **Penalty-free period change**: Edit `repayment_month_max` under",
        "  `penalty_rules.early_repayment.applies_when` (e.g. change 36 to 24)",
        "- **New rate type**: Add a new entry under `rate_types`",
        "- **Maximum term change**: Edit `maximum_years` under",
        "  `validation_rules.term`",
        "",
        "### Important notes:",
        "",
        "- All monetary values are in **GBP (British Pounds)**",
        "- All interest rates are expressed as **decimals** (5.25% = 0.0525)",
        "- Changes to validation limits may require updating test cases",
        "- Any penalty rule change requires compliance sign-off before deployment",
        "",
        "---",
        "",
        "*Document generated by COBOL Moderniser -- Agent 7 (Externaliser).*",
        f'*Version: {rules["program"]["version"]}*',
        "",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON GENERATOR
# ---------------------------------------------------------------------------

def _generate_json(rules: Dict[str, Any]) -> str:
    """Generate the business_rules.json file content as a string (2-space indent)."""
    # Convert Decimals to floats for JSON compatibility
    serialisable = json.loads(json.dumps(rules, default=_decimal_handler))
    return json.dumps(serialisable, indent=2)


# ---------------------------------------------------------------------------
# MAIN EXTERNALISE FUNCTION
# ---------------------------------------------------------------------------

def externalise(input_py: str, output_dir: str) -> None:
    """
    Write business rules to YAML, JSON, and Markdown in *output_dir*.

    Parameters
    ----------
    input_py:
        Path to the simplified Python module (used for provenance only).
    output_dir:
        Directory where business_rules.yaml, business_rules.json, and
        business_rules.md will be written.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # --- YAML ---
    yaml_path = out_path / "business_rules.yaml"
    yaml_content = _generate_yaml(_BUSINESS_RULES)
    with open(yaml_path, "w", encoding="utf-8") as fh:
        fh.write(yaml_content)
    print(f"[OK]  YAML written:  {yaml_path}")

    # --- JSON ---
    json_path = out_path / "business_rules.json"
    json_content = _generate_json(_BUSINESS_RULES)
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(json_content)
    print(f"[OK]  JSON written:  {json_path}")

    # --- Markdown ---
    md_path = out_path / "business_rules.md"
    md_content = _generate_markdown(_BUSINESS_RULES)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_content)
    print(f"[OK]  Markdown written: {md_path}")

    print(f"[OK]  All 3 business rule files written to {out_path}")


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------

def main() -> None:  # pragma: no cover
    """Parse CLI arguments and run the externaliser."""
    arg_parser = argparse.ArgumentParser(
        description=(
            "COBOL Moderniser -- Agent 7 (Externaliser): "
            "Extract business rules to YAML, JSON, and Markdown"
        ),
    )
    arg_parser.add_argument(
        "--input-py",
        default="output/mortgage_calc_simplified.py",
        help="Path to the simplified Python module (for provenance)",
    )
    arg_parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for the generated business rule files",
    )
    args = arg_parser.parse_args()

    externalise(args.input_py, args.output_dir)


if __name__ == "__main__":  # pragma: no cover
    main()
