#!/usr/bin/env python3
"""
Standalone script to generate extended test cases for the COBOL Moderniser project.

Usage:
    python generate_extended_tests.py

This imports from agents/test_generator.py and writes:
    tests/generated/extended_test_cases.json
    tests/generated/extended_test_cases.md
"""

from __future__ import annotations

import json
import os
import sys

# Ensure project root is on path so we can import test_generator
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from agents.test_generator import (
    build_all_extended_test_cases,
    build_test_cases,
    build_markdown_summary,
    run_test_suite,
)


def main() -> None:
    """Generate all extended test cases and write JSON + Markdown outputs."""
    print("=" * 60)
    print("COBOL Moderniser – Extended Test Case Generator")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Build extended test cases
    # ------------------------------------------------------------------
    print("\n[1/4] Building 200 extended test cases ...")
    extended_cases = build_all_extended_test_cases()
    print(f"      Generated {len(extended_cases)} extended test cases.")

    # ------------------------------------------------------------------
    # 2. Build original 26 test cases as well (for reference)
    # ------------------------------------------------------------------
    print("\n[2/4] Building 26 original test cases ...")
    original_cases = build_test_cases()
    print(f"      Generated {len(original_cases)} original test cases.")

    all_cases = original_cases + extended_cases

    # ------------------------------------------------------------------
    # 3. Run test suite
    # ------------------------------------------------------------------
    print("\n[3/4] Running test suite ...")
    results = run_test_suite(all_cases)
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print(f"      Passed: {passed}/{len(results)}")
    if failed:
        print(f"      FAILED: {failed} – review output below")
        for r in results:
            if not r["passed"]:
                print(f"        - {r['id']}: {r['description']}")
    else:
        print("      All test cases passed!")

    # ------------------------------------------------------------------
    # 4. Write output files
    # ------------------------------------------------------------------
    print("\n[4/4] Writing output files ...")

    generated_dir = os.path.join(PROJECT_ROOT, "tests", "generated")
    os.makedirs(generated_dir, exist_ok=True)

    # Extended test cases JSON
    json_path = os.path.join(generated_dir, "extended_test_cases.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(extended_cases, fh, indent=2, default=str)
    print(f"      JSON  -> {json_path}  ({os.path.getsize(json_path):,} bytes)")

    # Markdown summary
    md_path = os.path.join(generated_dir, "extended_test_cases.md")
    # Build summary from extended cases only
    extended_results = [r for r in results if r["id"].startswith(("STR", "AMO", "PEN", "ROU", "BOU", "RAT", "VAL"))]
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown_summary(extended_results))
    print(f"      MD    -> {md_path}  ({os.path.getsize(md_path):,} bytes)")

    # Also write original test cases as separate JSON for reference
    original_json_path = os.path.join(generated_dir, "original_test_cases.json")
    with open(original_json_path, "w", encoding="utf-8") as fh:
        json.dump(original_cases, fh, indent=2, default=str)
    print(f"      JSON  -> {original_json_path}  ({os.path.getsize(original_json_path):,} bytes)")

    # Full combined test cases
    full_json_path = os.path.join(generated_dir, "all_test_cases.json")
    with open(full_json_path, "w", encoding="utf-8") as fh:
        json.dump(all_cases, fh, indent=2, default=str)
    print(f"      JSON  -> {full_json_path}  ({os.path.getsize(full_json_path):,} bytes)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Original test cases : {len(original_cases)}")
    print(f"  Extended test cases : {len(extended_cases)}")
    print(f"  Total test cases    : {len(all_cases)}")
    print(f"  Passed              : {passed}/{len(results)}")
    print(f"  Failed              : {failed}")
    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
