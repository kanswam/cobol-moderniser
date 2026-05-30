"""
=============================================================================
COBOL MODERNISER — FULL PIPELINE RUNNER
=============================================================================
Purpose:
    Orchestrate the 5-agent pipeline that migrates a COBOL program to
    Python.

    Agents (in order):
        1. Parser          — parse COBOL into structured JSON
        2. Logic Extractor — extract business rules (makes API calls)
        3. Code Generator  — produce Python from logic + structure
        4. Test Generator  — generate unit tests
        5. Validator       — verify outputs and flag issues

    This runner:
        - Loads each agent module dynamically
        - Feeds the output of agent N into agent N+1
        - Tracks API costs when Agent 2 uses Claude
        - Prints a tidy summary at the end

Usage:
    python demo/run_pipeline.py --input sample_cobol/mortgage.cbl
    python demo/run_pipeline.py --input sample_cobol/mortgage.cbl --no-ai
=============================================================================
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ensure the repo root is on sys.path so ``import agents.…`` works.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# OPTIONAL COST TRACKING
# ---------------------------------------------------------------------------
try:
    from agents.cost_tracker import CostTracker, PRICING
except Exception:  # pragma: no cover
    CostTracker = None  # type: ignore[misc, assignment]
    PRICING = {}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _load_module(name: str, path: str) -> Any:
    """Load a Python module from an arbitrary file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_dir(path: str) -> None:
    """Create parent directories for *path* if they do not exist."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _box_line(text: str, width: int = 72) -> str:
    """Centre *text* inside a box-drawing line."""
    pad = max(0, width - 2 - len(text))
    left = pad // 2
    right = pad - left
    return "║" + " " * left + text + " " * right + "║"


# ---------------------------------------------------------------------------
# AGENT STEP FUNCTIONS
# ---------------------------------------------------------------------------

def step_parser(cobol_path: str, output_json: str) -> Dict[str, Any]:
    """
    Agent 1 — Parser.

    Parse the raw COBOL source into a structured JSON map.
    """
    print("\n" + "=" * 72)
    print("STEP 1/5 — Parser")
    print("=" * 72)

    parser_path = _REPO_ROOT / "agents" / "parser.py"
    if not parser_path.exists():
        print("[WARN] parser.py not found — using stub.")
        parse_data = {
            "program_id": "UNKNOWN",
            "data_fields": {},
            "paragraphs": {},
            "conditions": {},
        }
    else:
        parser = _load_module("agents.parser", str(parser_path))
        # The parser module is expected to expose a ``main()`` or
        # ``parse_cobol(source_code)`` style API.  We normalise here.
        if hasattr(parser, "parse_cobol"):
            with open(cobol_path, "r", encoding="utf-8") as fh:
                source = fh.read()
            parse_data = parser.parse_cobol(source)
        elif hasattr(parser, "main"):
            # Fallback: call main with --input and capture output file.
            import tempfile
            tmp_out = tempfile.mktemp(suffix=".json")
            old_argv = sys.argv
            try:
                sys.argv = ["parser.py", "--input", cobol_path, "--output", tmp_out]
                parser.main()
            finally:
                sys.argv = old_argv
            with open(tmp_out, "r", encoding="utf-8") as fh:
                parse_data = json.load(fh)
            os.remove(tmp_out)
        else:
            raise RuntimeError("Parser module has no parse_cobol() or main()")

    _ensure_dir(output_json)
    with open(output_json, "w", encoding="utf-8") as fh:
        json.dump(parse_data, fh, indent=2)

    print(f"[OK]  Parser output written to {output_json}")
    return parse_data


def step_logic(
    parse_data: Dict[str, Any],
    output_md: str,
    output_json: str,
    no_ai: bool = False,
    tracker: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Agent 2 — Logic Extractor.

    Extract business rules from the parsed structure.  When *tracker* is
    supplied and AI mode is enabled, token usage is recorded automatically.
    """
    print("\n" + "=" * 72)
    print("STEP 2/5 — Logic Extractor")
    print("=" * 72)

    extractor_path = _REPO_ROOT / "agents" / "logic_extractor.py"
    if not extractor_path.exists():
        print("[WARN] logic_extractor.py not found — skipping.")
        return {}

    extractor = _load_module("agents.logic_extractor", str(extractor_path))

    # Run the structured extractors (no API calls).
    extracted: Dict[str, Any] = {
        "inputs": extractor.extract_inputs(parse_data),
        "outputs": extractor.extract_outputs(parse_data),
        "constants": extractor.extract_constants(parse_data),
        "validation_rules": extractor.extract_validation_rules(parse_data),
        "calculation_steps": extractor.extract_calculation_steps(parse_data),
        "conditions": extractor.extract_conditions(parse_data),
    }

    _ensure_dir(output_json)
    with open(output_json, "w", encoding="utf-8") as fh:
        json.dump(extracted, fh, indent=2)
    print(f"[OK]  Logic JSON written to {output_json}")

    # AI interpretation (optional, costs money).
    if no_ai:
        ai_text = "*AI interpretation skipped (--no-ai flag set)*"
        print("[LOGIC] Skipping AI interpretation.")
    else:
        # Pass the tracker so the extractor can record API costs.
        ai_text = extractor.interpret_with_ai(parse_data, extracted, tracker=tracker)

    # Build Markdown report.
    report = extractor.build_report(parse_data, extracted, ai_text)
    _ensure_dir(output_md)
    with open(output_md, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"[OK]  Business rules written to {output_md}")

    return extracted


def step_codegen(
    parse_data: Dict[str, Any],
    extracted: Dict[str, Any],
    output_py: str,
) -> str:
    """
    Agent 3 — Code Generator.

    Generate Python source from the parse tree + business logic.
    """
    print("\n" + "=" * 72)
    print("STEP 3/5 — Code Generator")
    print("=" * 72)

    # Stub: if a real code generator exists, load and run it.
    codegen_path = _REPO_ROOT / "agents" / "code_generator.py"
    if codegen_path.exists():
        codegen = _load_module("agents.code_generator", str(codegen_path))
        if hasattr(codegen, "generate"):
            python_code = codegen.generate(parse_data, extracted)
        else:
            python_code = _stub_codegen(parse_data, extracted)
    else:
        print("[WARN] code_generator.py not found — using stub.")
        python_code = _stub_codegen(parse_data, extracted)

    _ensure_dir(output_py)
    with open(output_py, "w", encoding="utf-8") as fh:
        fh.write(python_code)
    print(f"[OK]  Python output written to {output_py}")
    return python_code


def step_testgen(parse_data: Dict[str, Any], output_dir: str) -> List[str]:
    """
    Agent 4 — Test Generator.

    Generate unit tests for the migrated Python code.
    """
    print("\n" + "=" * 72)
    print("STEP 4/5 — Test Generator")
    print("=" * 72)

    testgen_path = _REPO_ROOT / "agents" / "test_generator.py"
    if testgen_path.exists():
        testgen = _load_module("agents.test_generator", str(testgen_path))
        if hasattr(testgen, "generate_tests"):
            test_files = testgen.generate_tests(parse_data, output_dir)
        else:
            test_files = _stub_testgen(parse_data, output_dir)
    else:
        print("[WARN] test_generator.py not found — using stub.")
        test_files = _stub_testgen(parse_data, output_dir)

    print(f"[OK]  Test files: {len(test_files)} file(s) written")
    return test_files


def step_validator(
    parse_data: Dict[str, Any],
    extracted: Dict[str, Any],
    python_code: str,
) -> Dict[str, Any]:
    """
    Agent 5 — Validator.

    Cross-check outputs and flag any inconsistencies.
    """
    print("\n" + "=" * 72)
    print("STEP 5/5 — Validator")
    print("=" * 72)

    issues: List[str] = []

    # Basic sanity checks.
    if not parse_data.get("program_id"):
        issues.append("Missing program_id in parser output")
    if not extracted.get("inputs") and not extracted.get("outputs"):
        issues.append("No inputs or outputs extracted")
    if not python_code.strip():
        issues.append("Generated Python code is empty")

    result = {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    }

    if result["status"] == "PASS":
        print("[OK]  Validation passed")
    else:
        print(f"[FAIL] Validation failed with {len(issues)} issue(s):")
        for issue in issues:
            print(f"       - {issue}")

    return result


# ---------------------------------------------------------------------------
# STUBS (used when an agent module is missing)
# ---------------------------------------------------------------------------

def _stub_codegen(parse_data: Dict[str, Any], extracted: Dict[str, Any]) -> str:
    """Generate a minimal Python stub so the pipeline can still finish."""
    lines = [
        '# Generated by COBOL Moderniser (stub)',
        f'# Original: {parse_data.get("program_id", "UNKNOWN")}',
        '',
        'def main():',
        '    """TODO: implement business logic."""',
        '    pass',
        '',
        'if __name__ == "__main__":',
        '    main()',
        '',
    ]
    return "\n".join(lines)


def _stub_testgen(parse_data: Dict[str, Any], output_dir: str) -> List[str]:
    """Generate a minimal test stub so the pipeline can still finish."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "test_generated.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Generated tests (stub)\n")
    return [path]


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="COBOL Moderniser — Full 5-Agent Pipeline",
    )
    arg_parser.add_argument(
        "--input", required=True,
        help="Path to the COBOL source file (.cbl)",
    )
    arg_parser.add_argument(
        "--output-dir", default="output",
        help="Directory for all generated artefacts",
    )
    arg_parser.add_argument(
        "--no-ai", action="store_true",
        help="Skip the AI interpretation step (Agent 2) — free mode",
    )
    arg_parser.add_argument(
        "--no-cost", action="store_true",
        help="Disable cost tracking even when AI is used",
    )
    args = arg_parser.parse_args()

    cobol_path = args.input
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Cost tracker — created once at pipeline start.
    # ------------------------------------------------------------------
    tracker: Optional[Any] = None
    if CostTracker is not None and not args.no_cost:
        tracker = CostTracker()
        print("[INFO] Cost tracking enabled.")
    else:
        print("[INFO] Cost tracking disabled.")

    overall_start = time.perf_counter()

    # ------------------------------------------------------------------
    # Step 1 — Parser
    # ------------------------------------------------------------------
    parser_json = str(out_dir / "parser_output.json")
    parse_data = step_parser(cobol_path, parser_json)

    # ------------------------------------------------------------------
    # Step 2 — Logic Extractor
    # ------------------------------------------------------------------
    logic_md = str(out_dir / "business_rules.md")
    logic_json = str(out_dir / "logic_output.json")
    extracted = step_logic(
        parse_data,
        logic_md,
        logic_json,
        no_ai=args.no_ai,
        tracker=tracker,
    )

    # ------------------------------------------------------------------
    # Step 3 — Code Generator
    # ------------------------------------------------------------------
    python_out = str(out_dir / "generated.py")
    python_code = step_codegen(parse_data, extracted, python_out)

    # ------------------------------------------------------------------
    # Step 4 — Test Generator
    # ------------------------------------------------------------------
    test_dir = str(out_dir / "tests")
    test_files = step_testgen(parse_data, test_dir)

    # ------------------------------------------------------------------
    # Step 5 — Validator
    # ------------------------------------------------------------------
    validation = step_validator(parse_data, extracted, python_code)

    overall_elapsed = time.perf_counter() - overall_start

    # ------------------------------------------------------------------
    # Cost report (before final summary so it appears above the box).
    # ------------------------------------------------------------------
    if tracker is not None and tracker.has_records:
        tracker.print_summary()
        cost_report_path = str(out_dir / "cost_report.json")
        tracker.save(cost_report_path)
        print(f"[OK]  Cost report saved to {cost_report_path}")

    # ------------------------------------------------------------------
    # Final summary box
    # ------------------------------------------------------------------
    print("\n╔══════════════════════════════════════════════════════════════════════════╗")
    print("║               COBOL MODERNISER — PIPELINE COMPLETE                      ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")

    status_text = "PASS" if validation["status"] == "PASS" else "FAIL"
    status_colour_tag = ""  # terminals that support it can add ANSI codes
    print(f"║   Status        : {status_text:<58} ║")
    print(f"║   Input         : {cobol_path:<58} ║")
    print(f"║   Output dir    : {str(out_dir):<58} ║")
    print(f"║   Duration      : {overall_elapsed:.1f}s{'':<54} ║")
    print("║──────────────────────────────────────────────────────────────────────────║")

    # Cost line (only when applicable)
    if tracker is not None and tracker.has_records:
        cost = tracker.total_cost_usd
        tokens = tracker.total_tokens
        cost_line = f"API cost:  ${cost:.4f}  |  {tokens:,} tokens"
        print(f"║   {cost_line:<69} ║")
    elif args.no_ai:
        print(f"║   API cost:  $0.0000  |  0 tokens ( --no-ai mode ){'':<17} ║")
    elif CostTracker is None:
        print(f"║   API cost:  n/a  (cost_tracker module unavailable){'':<19} ║")

    print("╚══════════════════════════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
