"""
=============================================================================
AGENT 5 — VALIDATOR
=============================================================================
Purpose:
    Runs every test case from Agent 3 through the migrated Python module
    from Agent 4 and verifies the outputs match the expected values.
 
    This is the migration proof. A 100% pass rate means the migrated Python
    is behaviourally identical to the original COBOL — to the penny.
 
    For each test case it checks:
      - return_code       (exact match)
      - monthly_payment   (to 2 decimal places)
      - total_repayable   (to 2 decimal places)
      - total_interest    (to 2 decimal places)
      - month_interest    (to 2 decimal places)
      - month_principal   (to 2 decimal places)
      - closing_balance   (to 2 decimal places)
      - penalty           (to 2 decimal places)
 
Output:
    - validation_report.md   — human-readable pass/fail report
    - validation_report.json — machine-readable results
 
    Exit code 0 = all tests passed
    Exit code 1 = one or more tests failed
 
Usage:
    python validator.py
    python validator.py --test-cases tests/generated/test_cases.json
                        --migrated-module output/mortgage_calc.py
=============================================================================
"""
 
import json
import sys
import argparse
import importlib.util
from datetime import datetime
from decimal import Decimal
 
 
# ---------------------------------------------------------------------------
# FIELD TOLERANCE
# All financial outputs must match to exactly 2 decimal places (the penny).
# ---------------------------------------------------------------------------
 
TOLERANCE = Decimal("0.01")
 
CHECKED_FIELDS = [
    "return_code",
    "monthly_payment",
    "total_repayable",
    "total_interest",
    "month_interest",
    "month_principal",
    "closing_balance",
    "penalty",
]
 
 
# ---------------------------------------------------------------------------
# MODULE LOADER
# Dynamically loads the migrated Python module from its file path
# ---------------------------------------------------------------------------
 
def load_migrated_module(module_path: str):
    """Dynamically import the migrated mortgage_calc.py module."""
    spec   = importlib.util.spec_from_file_location("mortgage_calc", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
 
 
# ---------------------------------------------------------------------------
# SINGLE TEST RUNNER
# ---------------------------------------------------------------------------
 
def run_test(case: dict, module) -> dict:
    """
    Run a single test case through the migrated module.
    Returns a result dict with pass/fail status and field-level diffs.
    """
    inputs   = case["inputs"]
    expected = case["expected"]
 
    # Call the migrated module
    actual_result = module.calculate(
        principal       = inputs["principal"],
        annual_rate     = inputs["annual_rate"],
        term_years      = inputs["term_years"],
        repayment_month = inputs["repayment_month"],
        rate_type       = inputs["rate_type"]
    )
 
    # Convert result to dict for comparison
    actual = {
        "return_code":     int(actual_result.return_code),
        "monthly_payment": actual_result.monthly_payment,
        "total_repayable": actual_result.total_repayable,
        "total_interest":  actual_result.total_interest,
        "month_interest":  actual_result.month_interest,
        "month_principal": actual_result.month_principal,
        "closing_balance": actual_result.closing_balance,
        "penalty":         actual_result.penalty,
    }
 
    # Compare field by field
    field_results = {}
    all_passed    = True
 
    for field in CHECKED_FIELDS:
        exp_val = expected.get(field, 0)
        act_val = actual.get(field, 0)
 
        if field == "return_code":
            passed = int(exp_val) == int(act_val)
        else:
            diff   = abs(Decimal(str(exp_val)) - Decimal(str(act_val)))
            passed = diff <= TOLERANCE
 
        if not passed:
            all_passed = False
 
        field_results[field] = {
            "expected": exp_val,
            "actual":   act_val,
            "passed":   passed,
            "diff":     float(abs(Decimal(str(exp_val)) - Decimal(str(act_val))))
        }
 
    return {
        "id":           case["id"],
        "description":  case["description"],
        "category":     case["category"],
        "inputs":       inputs,
        "fields":       field_results,
        "passed":       all_passed,
    }
 
 
# ---------------------------------------------------------------------------
# FULL SUITE RUNNER
# ---------------------------------------------------------------------------
 
def run_all_tests(test_cases: list, module) -> list:
    """Run every test case and collect results."""
    results = []
    passed  = 0
    failed  = 0
 
    for case in test_cases:
        result = run_test(case, module)
        results.append(result)
 
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"  [{status}] {result['id']} — {result['description']}")
 
        if result["passed"]:
            passed += 1
        else:
            failed += 1
            # Print field-level failures immediately
            for field, fr in result["fields"].items():
                if not fr["passed"]:
                    print(f"           ↳ {field}: expected {fr['expected']}, "
                          f"got {fr['actual']} (diff: {fr['diff']})")
 
    print(f"\n  Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    return results
 
 
# ---------------------------------------------------------------------------
# REPORT GENERATION
# ---------------------------------------------------------------------------
 
def build_markdown_report(results: list, module_path: str) -> str:
    """Build a human-readable validation report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 
    total    = len(results)
    passed   = sum(1 for r in results if r["passed"])
    failed   = total - passed
    pct      = (passed / total * 100) if total > 0 else 0
    verdict  = "✅ ALL TESTS PASSED" if failed == 0 else f"❌ {failed} TEST(S) FAILED"
 
    # Category breakdown
    cats = {}
    for r in results:
        cat = r["category"]
        cats.setdefault(cat, {"passed": 0, "failed": 0})
        if r["passed"]:
            cats[cat]["passed"] += 1
        else:
            cats[cat]["failed"] += 1
 
    report = f"""# Validation Report — MORTGAGE-CALC Migration
*Generated by COBOL Moderniser — Agent 5 (Validator)*
*Date: {timestamp}*
*Migrated module: {module_path}*
 
---
 
## Verdict: {verdict}
 
| Metric | Value |
|---|---|
| Total test cases | {total} |
| Passed | {passed} |
| Failed | {failed} |
| Pass rate | {pct:.1f}% |
| Tolerance | £0.01 (to the penny) |
 
---
 
## Results by Category
 
| Category | Passed | Failed | Status |
|---|---|---|---|
"""
    for cat, counts in cats.items():
        status = "✅" if counts["failed"] == 0 else "❌"
        report += (f"| {cat} | {counts['passed']} | "
                   f"{counts['failed']} | {status} |\n")
 
    report += "\n---\n\n## Full Test Results\n\n"
 
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        report += f"### {icon} {r['id']} — {r['description']}\n\n"
 
        inp = r["inputs"]
        report += (f"**Inputs:** "
                   f"£{inp['principal']:,.2f} principal, "
                   f"{inp['annual_rate']*100:.3f}% rate, "
                   f"{inp['term_years']}yr term, "
                   f"month {inp['repayment_month']}, "
                   f"{'fixed' if inp['rate_type']=='F' else 'variable'} rate\n\n")
 
        report += "| Field | Expected | Actual | Result |\n|---|---|---|---|\n"
        for field, fr in r["fields"].items():
            result_icon = "✅" if fr["passed"] else "❌"
            if field == "return_code":
                report += (f"| {field} | {fr['expected']} | "
                           f"{fr['actual']} | {result_icon} |\n")
            else:
                report += (f"| {field} | £{fr['expected']:,.2f} | "
                           f"£{fr['actual']:,.2f} | {result_icon} |\n")
        report += "\n"
 
    report += "---\n\n"
    if failed == 0:
        report += (
            "## Migration Certification\n\n"
            "The migrated Python module `mortgage_calc.py` has passed all "
            f"{total} test cases with zero failures.\n\n"
            "Behavioural equivalence with the original COBOL program "
            "`MORTGAGE-CALC` is confirmed to £0.01 precision across:\n\n"
            "- Standard mortgage scenarios\n"
            "- Early repayment penalty boundary conditions\n"
            "- Interest rate edge cases\n"
            "- Term and principal extremes\n"
            "- Invalid input rejection\n\n"
            "*This report constitutes the migration validation evidence.*\n"
        )
    else:
        report += (
            "## Failures Require Investigation\n\n"
            f"{failed} test case(s) failed. The migrated module does NOT yet "
            "have confirmed behavioural equivalence with the original COBOL.\n\n"
            "Review the failed cases above and correct the migrated code "
            "before proceeding.\n"
        )
 
    return report
 
 
# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
 
def main():
    arg_parser = argparse.ArgumentParser(
        description="COBOL Moderniser — Agent 5: Validator"
    )
    arg_parser.add_argument(
        "--test-cases",
        default="tests/generated/test_cases.json",
        help="Path to test cases JSON from Agent 3"
    )
    arg_parser.add_argument(
        "--migrated-module",
        default="output/mortgage_calc.py",
        help="Path to migrated Python module from Agent 4"
    )
    arg_parser.add_argument(
        "--output-md",
        default="output/validation_report.md",
        help="Path to write the Markdown validation report"
    )
    arg_parser.add_argument(
        "--output-json",
        default="output/validation_report.json",
        help="Path to write the JSON validation results"
    )
    args = arg_parser.parse_args()
 
    print("=" * 60)
    print("  COBOL MODERNISER — Agent 5: Validator")
    print("=" * 60)
    print(f"\n  Test cases   : {args.test_cases}")
    print(f"  Module       : {args.migrated_module}")
    print()
 
    # Load test cases
    print("[VALIDATOR] Loading test cases...")
    with open(args.test_cases, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    print(f"[VALIDATOR] {len(test_cases)} test cases loaded\n")
 
    # Load migrated module
    print("[VALIDATOR] Loading migrated module...")
    module = load_migrated_module(args.migrated_module)
    print(f"[VALIDATOR] Module loaded: {args.migrated_module}\n")
 
    # Run tests
    print("[VALIDATOR] Running test suite...\n")
    results = run_all_tests(test_cases, module)
 
    # Save JSON results
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[VALIDATOR] JSON results written to: {args.output_json}")
 
    # Build and save Markdown report
    report = build_markdown_report(results, args.migrated_module)
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[VALIDATOR] Report written to: {args.output_md}")
 
    # Final verdict
    failed = sum(1 for r in results if not r["passed"])
    total  = len(results)
    passed = total - failed
 
    print("\n" + "=" * 60)
    if failed == 0:
        print(f"  ✅  ALL {total} TESTS PASSED — MIGRATION VALIDATED")
    else:
        print(f"  ❌  {failed}/{total} TESTS FAILED — REVIEW REQUIRED")
    print("=" * 60)
 
    sys.exit(0 if failed == 0 else 1)
 
 
if __name__ == "__main__":
    main()
