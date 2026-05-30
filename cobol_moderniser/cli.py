"""
COBOL Moderniser CLI — Production-quality command-line interface.

Provides three sub-commands:
    migrate  — Run the full 5-agent pipeline (parse → extract → test → write → validate).
    parse    — Run only Agent 1 (COBOL parser) and emit JSON.
    validate — Run only Agent 5 (validator) against existing test cases.

Agent modules are loaded dynamically from the repository-root ``agents/``
directory so that the stand-alone agent scripts (which live *outside* the
``cobol_moderniser`` package) can be invoked without being on ``PYTHONPATH``.

Entry-point
-----------
Registered as ``cobol-moderniser`` via setuptools/console_scripts.

Examples
--------
    cobol-moderniser migrate sample_cobol/mortgage_calc.cbl --output ./output
    cobol-moderniser parse sample_cobol/mortgage_calc.cbl --output parse.json
    cobol-moderniser validate --test-cases tests.json --migrated-module output.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, NoReturn, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Package metadata
# ---------------------------------------------------------------------------

try:
    from cobol_moderniser import __version__
except ImportError:  # pragma: no cover — during editable install
    __version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("cobol-moderniser")

_FMT_VERBOSE = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_FMT_SIMPLE = logging.Formatter(fmt="%(message)s")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class CLIError(Exception):
    """Base exception for CLI-level errors with a user-friendly message."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class AgentNotFoundError(CLIError):
    """Raised when a required agent module cannot be located on disk."""

    def __init__(self, agent_name: str, searched_paths: List[Path]) -> None:
        paths_str = "\n  ".join(str(p) for p in searched_paths)
        msg = (
            f"Cannot find agent '{agent_name}'.py.\n"
            f"Searched:\n  {paths_str}\n\n"
            "Make sure you run the CLI from inside the cobol-moderniser repository."
        )
        super().__init__(msg, exit_code=2)
        self.agent_name = agent_name
        self.searched_paths = searched_paths


class PipelineStepError(CLIError):
    """Raised when a single pipeline step (agent) fails."""

    def __init__(self, step: int, agent_name: str, cause: Exception) -> None:
        super().__init__(
            f"Pipeline step {step} ({agent_name}) failed: {cause}",
            exit_code=1,
        )
        self.step = step
        self.agent_name = agent_name
        self.cause = cause


# ---------------------------------------------------------------------------
# Agent discovery & dynamic loading
# ---------------------------------------------------------------------------

_AGENT_NAMES: Tuple[str, ...] = (
    "parser",
    "logic_extractor",
    "test_generator",
    "code_writer",
    "validator",
)


def _find_repo_root() -> Optional[Path]:
    """
    Walk upward from *cwd* looking for the repository root.

    Heuristic: a directory that contains an ``agents/`` sub-directory and a
    ``README.md`` file is considered the repo root.

    Returns
    -------
    Path or None
        Absolute path to the repository root, or *None* if not found.
    """
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        agents_dir = parent / "agents"
        readme = parent / "README.md"
        if agents_dir.is_dir() and readme.is_file():
            return parent
    # Fallback: accept repo root if ``agents/`` exists even without README.md
    for parent in [cwd, *cwd.parents]:
        if (parent / "agents").is_dir():
            return parent
    return None


def _locate_agent_module(agent_name: str) -> Path:
    """
    Return the absolute path to ``agents/<agent_name>.py``.

    Raises
    ------
    AgentNotFoundError
        If the file cannot be found after searching the repo root and cwd.
    """
    searched: List[Path] = []
    candidates: List[Path] = []

    repo_root = _find_repo_root()
    if repo_root is not None:
        candidates.append(repo_root / "agents" / f"{agent_name}.py")

    # Also allow agents/ in cwd as a last resort
    candidates.append(Path.cwd() / "agents" / f"{agent_name}.py")

    for candidate in candidates:
        searched.append(candidate)
        if candidate.is_file():
            return candidate.resolve()

    raise AgentNotFoundError(agent_name, searched)


def _load_agent(agent_name: str) -> ModuleType:
    """
    Dynamically import an agent module from the repo-root ``agents/`` dir.

    The module is loaded via :pyfunc:`importlib.util.spec_from_file_location`
    so that ``agents/`` does **not** need to be on ``PYTHONPATH``.

    Parameters
    ----------
    agent_name : str
        Stem of the agent file, e.g. ``"parser"``.

    Returns
    -------
    ModuleType
        The loaded module.

    Raises
    ------
    AgentNotFoundError
        If the source file cannot be located.
    ImportError
        If the file exists but fails to import.
    """
    module_path = _locate_agent_module(agent_name)
    spec = importlib.util.spec_from_file_location(
        f"agents.{agent_name}", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Failed to create module spec for {module_path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    logger.debug("Loaded agent '%s' from %s", agent_name, module_path)
    return module


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

_AGENT_EMOJI = {
    "parser": "\U0001f50d",          # 🔍
    "logic_extractor": "\U0001f9e0",  # 🧠
    "test_generator": "\U0001f9ea",   # 🧪
    "code_writer": "\U0001f4dd",      # 📝
    "validator": "\U0001f680",        # 🚀
}

_STEP_LABELS = {
    1: "Parse COBOL",
    2: "Extract Business Logic",
    3: "Generate Tests",
    4: "Write Python",
    5: "Validate",
}


def _banner(text: str, width: int = 60) -> str:
    """Return an ASCII banner line."""
    pad = max(2, width - len(text) - 4)
    return f"\n{'=' * width}\n  {text}{' ' * pad}\n{'=' * width}"


def _print_step(step: int, agent_name: str) -> None:
    """Print a formatted pipeline-step header."""
    emoji = _AGENT_EMOJI.get(agent_name, "\u25b6")
    label = _STEP_LABELS.get(step, agent_name.replace("_", " ").title())
    print(f"\n{emoji}  Step {step}/5 — {label}")
    print("-" * 50)


def _print_success(message: str) -> None:
    """Print a green-ish success indicator (works on any terminal)."""
    print(f"\n\u2714  {message}")


def _print_error(message: str) -> None:
    """Print a red-ish error indicator."""
    print(f"\n\u2718  {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _ensure_output_dir(output_dir: Path) -> None:
    """Create *output_dir* (and parents) if they do not exist."""
    output_dir.mkdir(parents=True, exist_ok=True)


def _write_json(data: Any, path: Path) -> None:
    """Serialise *data* as formatted JSON to *path*."""
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _do_migrate(args: argparse.Namespace) -> int:
    """
    Execute the full 5-agent migration pipeline.

    Steps
    -----
    1. Parse the COBOL source into an AST / intermediate representation.
    2. Extract business rules (inputs, outputs, calculations, conditions).
    3. Generate a comprehensive test suite from the extracted rules.
    4. Write idiomatic Python code using templates.
    5. Validate behavioural equivalence (pass/fail report).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.  Expected attributes:
        - ``input`` (Path)
        - ``output`` (Path)
        - ``target`` (str)
        - ``no_ai`` (bool)
        - ``copybook_path`` (Optional[str])
        - ``verbose`` (bool)

    Returns
    -------
    int
        Exit code — 0 on success, 1 on failure.
    """
    source_file: Path = args.input.resolve()
    output_dir: Path = args.output.resolve()
    _ensure_output_dir(output_dir)

    if not source_file.is_file():
        _print_error(f"Input file not found: {source_file}")
        return 1

    print(_banner(f"COBOL Moderniser v{__version__}"))
    print(f"Source : {source_file}")
    print(f"Output : {output_dir}")
    print(f"Target : {args.target}")
    print(f"AI     : {'disabled' if args.no_ai else 'enabled (Claude)'}")

    overall_start = time.perf_counter()

    # ------------------------------------------------------------------
    # Step 1 — Parser
    # ------------------------------------------------------------------
    _print_step(1, "parser")
    try:
        parser_mod = _load_agent("parser")
        parser_instance = parser_mod.COBOLParser(str(source_file))
        parse_result = parser_instance.parse()

        parse_json_path = output_dir / "parse_result.json"
        _write_json(parse_result, parse_json_path)
        _print_success(f"Parse result written to {parse_json_path}")
    except Exception as exc:
        raise PipelineStepError(1, "parser", exc) from exc

    # ------------------------------------------------------------------
    # Step 2 — Logic Extractor
    # ------------------------------------------------------------------
    _print_step(2, "logic_extractor")
    try:
        extractor_mod = _load_agent("logic_extractor")

        # If the user requested --no-ai, we still call the functions but
        # the module may short-circuit the Claude API call internally.
        inputs = extractor_mod.extract_inputs(parse_result)
        outputs = extractor_mod.extract_outputs(parse_result)
        constants = extractor_mod.extract_constants(parse_result)
        validations = extractor_mod.extract_validation_rules(parse_result)
        calculations = extractor_mod.extract_calculation_steps(parse_result)
        conditions = extractor_mod.extract_conditions(parse_result)

        if not args.no_ai:
            ai_interpretation = extractor_mod.interpret_with_ai(parse_result)
        else:
            ai_interpretation = {"skipped": True, "reason": "--no-ai"}

        report = extractor_mod.build_report(
            inputs=inputs,
            outputs=outputs,
            constants=constants,
            validations=validations,
            calculations=calculations,
            conditions=conditions,
            ai_interpretation=ai_interpretation,
        )

        report_path = output_dir / "logic_report.json"
        _write_json(report, report_path)
        _print_success(f"Logic report written to {report_path}")
    except Exception as exc:
        raise PipelineStepError(2, "logic_extractor", exc) from exc

    # ------------------------------------------------------------------
    # Step 3 — Test Generator
    # ------------------------------------------------------------------
    _print_step(3, "test_generator")
    try:
        test_mod = _load_agent("test_generator")
        test_cases = test_mod.build_test_cases(report)
        test_results = test_mod.run_test_suite(test_cases)

        tests_path = output_dir / "test_cases.json"
        _write_json(test_cases, tests_path)
        results_path = output_dir / "test_results.json"
        _write_json(test_results, results_path)
        _print_success(f"Generated {len(test_cases)} test case(s)")
        _print_success(f"Test artefacts written to {output_dir}")
    except Exception as exc:
        raise PipelineStepError(3, "test_generator", exc) from exc

    # ------------------------------------------------------------------
    # Step 4 — Code Writer
    # ------------------------------------------------------------------
    _print_step(4, "code_writer")
    try:
        writer_mod = _load_agent("code_writer")
        # The code_writer module writes Python to its own --output path.
        # We point it at our output directory.
        migrated_py_path = output_dir / "migrated_module.py"

        # The module may accept CLI-style arguments or direct function calls.
        # We attempt the most common patterns.
        if hasattr(writer_mod, "write_code"):
            writer_mod.write_code(
                parse_result=parse_result,
                logic_report=report,
                output_path=str(migrated_py_path),
                target=args.target,
            )
        elif hasattr(writer_mod, "main"):
            # Fall back to invoking its CLI main with patched sys.argv
            original_argv = sys.argv
            try:
                sys.argv = [
                    "code_writer.py",
                    "--input", str(source_file),
                    "--output", str(migrated_py_path),
                ]
                writer_mod.main()
            finally:
                sys.argv = original_argv
        else:
            # Ultimate fallback: write the template constant if present
            migrated_py_path.write_text(
                getattr(writer_mod, "MIGRATED_CODE", "# Migration placeholder"),
                encoding="utf-8",
            )

        if migrated_py_path.is_file():
            _print_success(f"Migrated Python written to {migrated_py_path}")
        else:
            _print_error("Code writer did not produce an output file.")
            return 1
    except Exception as exc:
        raise PipelineStepError(4, "code_writer", exc) from exc

    # ------------------------------------------------------------------
    # Step 5 — Validator
    # ------------------------------------------------------------------
    _print_step(5, "validator")
    try:
        validator_mod = _load_agent("validator")
        validation_summary: List[Dict[str, Any]] = []
        passed = 0
        failed = 0

        for case in test_cases:
            result = validator_mod.run_test(case, str(migrated_py_path))
            validation_summary.append(result)
            if result.get("passed", False):
                passed += 1
            else:
                failed += 1

        summary = {
            "total": len(test_cases),
            "passed": passed,
            "failed": failed,
            "details": validation_summary,
        }

        summary_json = output_dir / "validation_summary.json"
        _write_json(summary, summary_json)

        # Markdown report (optional, if the validator module supports it)
        if hasattr(validator_mod, "generate_markdown_report"):
            md_report = validator_mod.generate_markdown_report(summary)
            summary_md = output_dir / "validation_report.md"
            summary_md.write_text(md_report, encoding="utf-8")
            _print_success(f"Markdown report written to {summary_md}")

        status_emoji = "\u2705" if failed == 0 else "\u274c"
        print(
            f"\n{status_emoji}  Validation: {passed}/{len(test_cases)} passed"
        )
        if failed:
            _print_error(f"{failed} test(s) failed — see {summary_json}")
    except Exception as exc:
        raise PipelineStepError(5, "validator", exc) from exc

    elapsed = time.perf_counter() - overall_start
    print(_banner("Pipeline Complete"))
    print(f"Duration : {elapsed:.2f}s")
    print(f"Output   : {output_dir}")
    return 0 if failed == 0 else 1


def _do_parse(args: argparse.Namespace) -> int:
    """
    Run only Agent 1 (COBOL parser) and emit JSON.

    Parameters
    ----------
    args : argparse.Namespace
        Expected attributes:
        - ``input`` (Path)
        - ``output`` (Optional[Path])
        - ``verbose`` (bool)

    Returns
    -------
    int
        Exit code — 0 on success, 1 on failure.
    """
    source_file: Path = args.input.resolve()
    if not source_file.is_file():
        _print_error(f"Input file not found: {source_file}")
        return 1

    parser_mod = _load_agent("parser")
    parser_instance = parser_mod.COBOLParser(str(source_file))
    parse_result = parser_instance.parse()

    json_text = json.dumps(parse_result, indent=2, default=str)

    if args.output:
        out_path: Path = args.output.resolve()
        _ensure_output_dir(out_path.parent)
        out_path.write_text(json_text, encoding="utf-8")
        _print_success(f"Parse JSON written to {out_path}")
    else:
        print(json_text)

    return 0


def _do_validate(args: argparse.Namespace) -> int:
    """
    Run only Agent 5 (validator) against existing test cases.

    Parameters
    ----------
    args : argparse.Namespace
        Expected attributes:
        - ``test_cases`` (Path)
        - ``migrated_module`` (Path)
        - ``output_md`` (Optional[Path])
        - ``output_json`` (Optional[Path])
        - ``verbose`` (bool)

    Returns
    -------
    int
        Exit code — 0 if all tests pass, 1 otherwise.
    """
    test_cases_path: Path = args.test_cases.resolve()
    migrated_module_path: Path = args.migrated_module.resolve()

    if not test_cases_path.is_file():
        _print_error(f"Test cases file not found: {test_cases_path}")
        return 1
    if not migrated_module_path.is_file():
        _print_error(f"Migrated module not found: {migrated_module_path}")
        return 1

    raw = test_cases_path.read_text(encoding="utf-8")
    test_cases: List[Dict[str, Any]] = json.loads(raw)

    validator_mod = _load_agent("validator")

    results: List[Dict[str, Any]] = []
    passed = 0
    failed = 0

    for case in test_cases:
        result = validator_mod.run_test(case, str(migrated_module_path))
        results.append(result)
        if result.get("passed", False):
            passed += 1
        else:
            failed += 1

    summary = {
        "total": len(test_cases),
        "passed": passed,
        "failed": failed,
        "details": results,
    }

    # Emit requested reports
    if args.output_json:
        json_path: Path = args.output_json.resolve()
        _ensure_output_dir(json_path.parent)
        _write_json(summary, json_path)
        _print_success(f"JSON summary written to {json_path}")

    if args.output_md:
        md_path: Path = args.output_md.resolve()
        _ensure_output_dir(md_path.parent)
        md_lines = [
            "# Validation Report",
            "",
            f"- **Total**: {len(test_cases)}",
            f"- **Passed**: {passed} \u2705",
            f"- **Failed**: {failed} {'\u274c' if failed else ''}",
            "",
            "## Details",
            "",
            "| # | Name | Status |",
            "|---|------|--------|",
        ]
        for idx, res in enumerate(results, 1):
            name = res.get("name", f"case_{idx}")
            status = "PASS" if res.get("passed") else "FAIL"
            md_lines.append(f"| {idx} | {name} | {status} |")
        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        _print_success(f"Markdown report written to {md_path}")

    # Always print summary to stdout
    status_emoji = "\u2705" if failed == 0 else "\u274c"
    print(f"\n{status_emoji}  {passed}/{len(test_cases)} tests passed")
    if failed:
        print(f"\u274c  {failed} test(s) failed")

    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Argument parser factory
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """
    Construct the top-level argument parser with sub-commands.

    Returns
    -------
    argparse.ArgumentParser
        Fully configured parser ready for :pyfunc:`parse_args`.
    """
    parser = argparse.ArgumentParser(
        prog="cobol-moderniser",
        description=(
            "Autonomous migration of legacy COBOL to modern Python "
            "using a 5-agent AI pipeline."
        ),
        epilog=(
            "Example:\n"
            "  cobol-moderniser migrate sample_cobol/mortgage_calc.cbl "
            "--output ./output\n"
            "  cobol-moderniser parse sample_cobol/mortgage_calc.cbl\n"
            "  cobol-moderniser validate --test-cases tests.json "
            "--migrated-module output.py"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable detailed (DEBUG) logging output.",
    )

    # ---- Global options (applied to all sub-commands) ----------------
    # We attach these to the sub-parsers as well so they appear in help.

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # =================================================================
    # migrate
    # =================================================================
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Run the full 5-agent migration pipeline.",
        description="Parse, extract, test, write, and validate in one shot.",
    )
    migrate_parser.add_argument(
        "input",
        type=Path,
        metavar="INPUT.cbl",
        help="Path to the legacy COBOL source file.",
    )
    migrate_parser.add_argument(
        "--target",
        choices=["python"],
        default="python",
        help="Target language for migration (default: python).",
    )
    migrate_parser.add_argument(
        "--no-ai",
        action="store_true",
        default=False,
        dest="no_ai",
        help="Skip the Claude API call in Agent 2 (logic extraction).",
    )
    migrate_parser.add_argument(
        "--copybook-path",
        default=None,
        dest="copybook_path",
        help="Directory containing copybook files referenced by the COBOL source.",
    )
    migrate_parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output"),
        help="Output directory for all generated artefacts (default: ./output).",
    )
    migrate_parser.set_defaults(func=_do_migrate)

    # =================================================================
    # parse
    # =================================================================
    parse_parser = subparsers.add_parser(
        "parse",
        help="Run only Agent 1 (COBOL parser) and emit JSON.",
        description="Parse a COBOL file and output the intermediate representation.",
    )
    parse_parser.add_argument(
        "input",
        type=Path,
        metavar="INPUT.cbl",
        help="Path to the legacy COBOL source file.",
    )
    parse_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output file. If omitted, prints to stdout.",
    )
    parse_parser.set_defaults(func=_do_parse)

    # =================================================================
    # validate
    # =================================================================
    validate_parser = subparsers.add_parser(
        "validate",
        help="Run only Agent 5 (validator) against existing test cases.",
        description="Validate a migrated Python module against a JSON test suite.",
    )
    validate_parser.add_argument(
        "--test-cases",
        type=Path,
        required=True,
        dest="test_cases",
        help="Path to a JSON file containing the test case definitions.",
    )
    validate_parser.add_argument(
        "--migrated-module",
        type=Path,
        required=True,
        dest="migrated_module",
        help="Path to the migrated Python module to validate.",
    )
    validate_parser.add_argument(
        "--output-md",
        type=Path,
        default=None,
        dest="output_md",
        help="Optional path to write a Markdown validation report.",
    )
    validate_parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        dest="output_json",
        help="Optional path to write a JSON validation summary.",
    )
    validate_parser.set_defaults(func=_do_validate)

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def configure_logging(verbose: bool) -> None:
    """
    Set up logging handlers and level.

    Parameters
    ----------
    verbose : bool
        When *True*, emit DEBUG-level messages with timestamps.
        Otherwise emit INFO+ messages with a simple format.
    """
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(_FMT_VERBOSE if verbose else _FMT_SIMPLE)
    logger.setLevel(level)
    logger.addHandler(handler)
    # Quieten noisy third-party libraries unless in verbose mode
    if not verbose:
        logging.getLogger("anthropic").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    CLI entry point.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments.  Defaults to :data:`sys.argv[1:]`.

    Returns
    -------
    int
        Process exit code — 0 on success, non-zero on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # If no sub-command was given, print help and exit
    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    configure_logging(getattr(args, "verbose", False))
    logger.debug("Arguments: %s", vars(args))

    try:
        return args.func(args)
    except AgentNotFoundError as exc:
        _print_error(exc.message)
        if getattr(args, "verbose", False):
            traceback.print_exc()
        return exc.exit_code
    except PipelineStepError as exc:
        _print_error(exc.message)
        if getattr(args, "verbose", False):
            traceback.print_exc()
        return exc.exit_code
    except CLIError as exc:
        _print_error(exc.message)
        return exc.exit_code
    except KeyboardInterrupt:
        _print_error("Interrupted by user.")
        return 130
    except Exception as exc:
        _print_error(f"Unexpected error: {exc}")
        if getattr(args, "verbose", False):
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
