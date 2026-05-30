"""
=============================================================================
AGENT 2 — LOGIC EXTRACTOR
=============================================================================
Purpose:
    Reads the structured JSON map produced by Agent 1 (Parser) and extracts
    the business logic in plain English.

    This agent answers the question: "What does this COBOL program actually DO
    in business terms?" — independent of how it is technically implemented.

    It uses the Anthropic API (Claude) to reason over the parsed structure
    and produce a business rules document that a non-technical stakeholder
    could read and verify.

Output:
    - A JSON file containing structured business rules
    - A Markdown document containing a human-readable business rules summary

Usage:
    python logic_extractor.py --input agents/parser_output.json
    python logic_extractor.py --input agents/parser_output.json --output docs/business_rules.md
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# OPTIONAL COST TRACKING
# ---------------------------------------------------------------------------
# The cost tracker lives in ``agents.cost_tracker``.  When the pipeline
# runs it passes a tracker instance in.  For standalone usage (or when the
# module is missing) we simply skip tracking — no hard dependency.
# ---------------------------------------------------------------------------

try:
    from agents.cost_tracker import CostTracker, PRICING
except Exception:  # pragma: no cover
    CostTracker = None  # type: ignore[misc, assignment]
    PRICING = {}


# ---------------------------------------------------------------------------
# ANTHROPIC API CALL
# ---------------------------------------------------------------------------

# Model used by this agent.  Kept as a constant so it is easy to swap and
# so the cost tracker knows which pricing tier applies.
_CLAUDE_MODEL = "claude-sonnet-4-20250514"


def call_claude(prompt: str, system: str) -> Dict[str, Any]:
    """
    Call the Anthropic API with *prompt* and *system* and return the
    **full** JSON response dict.

    The caller is responsible for extracting the text content and the
    ``usage`` block.  This keeps the transport layer decoupled from
    tracking logic.
    """
    payload = json.dumps({
        "model": _CLAUDE_MODEL,
        "max_tokens": 1000,
        "system": system,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result


# ---------------------------------------------------------------------------
# RULE EXTRACTORS
# ---------------------------------------------------------------------------

def extract_inputs(parse_data: dict) -> dict:
    """Identify the program's inputs."""
    print("[LOGIC] Extracting inputs...")
    inputs = {}
    fields = parse_data.get("data_fields", {})
    for name, field in fields.items():
        if field.get("parent") and "INPUT" in field.get("parent", ""):
            inputs[name] = {
                "field": name,
                "type": field.get("data_type"),
                "length": field.get("field_length"),
                "decimal_places": field.get("decimal_places"),
                "default_value": field.get("value"),
            }
    return inputs


def extract_outputs(parse_data: dict) -> dict:
    """Identify the program's outputs."""
    print("[LOGIC] Extracting outputs...")
    outputs = {}
    fields = parse_data.get("data_fields", {})
    for name, field in fields.items():
        if field.get("parent") and "OUTPUT" in field.get("parent", ""):
            outputs[name] = {
                "field": name,
                "type": field.get("data_type"),
                "length": field.get("field_length"),
                "decimal_places": field.get("decimal_places"),
            }
    return outputs


def extract_constants(parse_data: dict) -> dict:
    """Extract hardcoded business constants."""
    print("[LOGIC] Extracting constants...")
    constants = {}
    fields = parse_data.get("data_fields", {})
    for name, field in fields.items():
        if (field.get("parent") and
            "CONSTANT" in field.get("parent", "") and
            field.get("value") and
            field.get("value") not in ("ZEROS", "SPACES", "0")):
            constants[name] = {
                "field": name,
                "value": field.get("value"),
                "type": field.get("data_type"),
            }
    return constants


def extract_validation_rules(parse_data: dict) -> list:
    """Extract input validation rules from the VALIDATE paragraph."""
    print("[LOGIC] Extracting validation rules...")
    rules = []
    paragraphs = parse_data.get("paragraphs", {})
    for para_name, para in paragraphs.items():
        if "VALIDATE" in para_name:
            for stmt in para.get("statements", []):
                if "IF" in stmt.upper() and ("<=" in stmt or ">=" in stmt or ">" in stmt or "<" in stmt):
                    rules.append({"paragraph": para_name, "raw_statement": stmt.strip()})
    return rules


def extract_calculation_steps(parse_data: dict) -> list:
    """Extract the sequence of calculation paragraphs."""
    print("[LOGIC] Extracting calculation sequence...")
    steps = []
    paragraphs = parse_data.get("paragraphs", {})
    main = paragraphs.get("MAIN-PROCEDURE", {})
    for called in main.get("calls_to", []):
        if called in paragraphs:
            para = paragraphs[called]
            steps.append({"step": len(steps) + 1, "paragraph": called, "statements": para.get("statements", [])})
    return steps


def extract_conditions(parse_data: dict) -> list:
    """Extract 88-level condition names."""
    print("[LOGIC] Extracting named conditions...")
    conditions = []
    raw_conditions = parse_data.get("conditions", {})
    for name, cond in raw_conditions.items():
        conditions.append({
            "name": name,
            "triggers_when": f"{cond.get('parent_field')} = {cond.get('value')}",
            "parent_field": cond.get("parent_field"),
        })
    return conditions


# ---------------------------------------------------------------------------
# AI INTERPRETATION
# ---------------------------------------------------------------------------

def interpret_with_ai(
    parse_data: dict,
    extracted: dict,
    tracker: Optional[Any] = None,
) -> str:
    """
    Send the extracted structure to Claude and ask it to produce
    a plain-English business rules document.

    Parameters
    ----------
    parse_data:
        The full parser output (used for program ID, etc.).
    extracted:
        The dict produced by the extract_* functions.
    tracker:
        An optional *CostTracker* instance.  When provided, token
        usage and elapsed time are recorded automatically.

    Returns
    -------
    str
        The plain-text business rules interpretation.
    """
    print("[LOGIC] Sending to Claude for interpretation...")

    system_prompt = """You are a senior business analyst specialising in
    financial systems modernisation. You are reviewing a COBOL program that
    has been parsed into a structured format.

    Your job is to describe the business logic in plain English that a
    non-technical stakeholder could understand and verify.

    Be specific about:
    - What inputs the program expects
    - What validations are performed
    - What calculations are done
    - What conditions trigger different logic paths
    - What outputs are produced

    Format your response as a well-structured Markdown document with
    clear headings and bullet points.
    """

    prompt = f"""
I have analysed a COBOL program called {parse_data.get('program_id', 'UNKNOWN')}.

Here are the structured findings:

## INPUTS
{json.dumps(extracted.get('inputs', {}), indent=2)}

## OUTPUTS
{json.dumps(extracted.get('outputs', {}), indent=2)}

## CONSTANTS
{json.dumps(extracted.get('constants', {}), indent=2)}

## VALIDATION RULES
{json.dumps(extracted.get('validation_rules', []), indent=2)}

## CALCULATION STEPS
{json.dumps(extracted.get('calculation_steps', []), indent=2)}

## NAMED CONDITIONS
{json.dumps(extracted.get('conditions', []), indent=2)}

Please write a comprehensive business rules document in Markdown format
that explains what this program does in business terms.
"""

    start_time = time.perf_counter()
    response = call_claude(prompt, system_prompt)
    elapsed = time.perf_counter() - start_time

    # Extract the text content — the API returns a list of content blocks.
    try:
        text = response["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        # Fallback: if the shape is unexpected, return the raw string
        # representation so the pipeline does not crash.
        text = str(response)

    # Extract usage information when available.
    usage = response.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    if tracker is not None and CostTracker is not None:
        try:
            tracker.record(
                agent="Logic Extractor",
                model=_CLAUDE_MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_seconds=round(elapsed, 4),
            )
            print(f"[LOGIC] Cost tracked: {input_tokens:,} in / {output_tokens:,} out "
                  f"(${input_tokens/1_000_000*3 + output_tokens/1_000_000*15:.6f})")
        except Exception as exc:  # pragma: no cover
            print(f"[LOGIC] Warning: cost tracking failed ({exc})")

    return text


# ---------------------------------------------------------------------------
# REPORT GENERATION
# ---------------------------------------------------------------------------

def build_report(parse_data: dict, extracted: dict, ai_interpretation: str) -> str:
    """Combine structured extraction and AI into Markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""# Business Rules Document
## Program: {parse_data.get('program_id', 'UNKNOWN')}

**Generated:** {timestamp}
**Source:** Agent 2 — Logic Extractor

---

## 1. Program Inputs

The program expects the following input fields:

"""
    if extracted.get("inputs"):
        for name, info in extracted["inputs"].items():
            report += f"- **{name}** — Type: {info.get('type', 'N/A')}, "
            report += f"Length: {info.get('length', 'N/A')}\n"
    else:
        report += "_No explicit inputs identified._\n"

    report += "\n## 2. Program Outputs\n\n"
    if extracted.get("outputs"):
        for name, info in extracted["outputs"].items():
            report += f"- **{name}** — Type: {info.get('type', 'N/A')}, "
            report += f"Length: {info.get('length', 'N/A')}\n"
    else:
        report += "_No explicit outputs identified._\n"

    report += "\n## 3. Business Constants\n\n"
    if extracted.get("constants"):
        for name, info in extracted["constants"].items():
            report += f"- **{name}** = `{info.get('value')}`\n"
    else:
        report += "_No business constants identified._\n"

    report += "\n## 4. Validation Rules\n\n"
    if extracted.get("validation_rules"):
        for rule in extracted["validation_rules"]:
            report += f"- `{rule['raw_statement']}`\n"
    else:
        report += "_No validation rules identified._\n"

    report += "\n## 5. Named Conditions\n\n"
    if extracted.get("conditions"):
        for cond in extracted["conditions"]:
            report += f"- **{cond['name']}** — triggers when {cond['triggers_when']}\n"
    else:
        report += "_No named conditions identified._\n"

    report += "\n## 6. Calculation Sequence\n\n"
    if extracted.get("calculation_steps"):
        for step in extracted["calculation_steps"]:
            report += f"### Step {step['step']}: {step['paragraph']}\n\n"
            for stmt in step.get("statements", [])[:5]:
                report += f"- `{stmt}`\n"
            if len(step.get("statements", [])) > 5:
                report += f"- ... ({len(step['statements']) - 5} more statements)\n"
            report += "\n"
    else:
        report += "_No calculation steps identified._\n"

    report += f"""---

## 7. AI Business Interpretation

{ai_interpretation}

---

*This document was automatically generated by the COBOL Moderniser pipeline.*
"""
    return report


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    arg_parser = argparse.ArgumentParser(description="COBOL Moderniser — Agent 2: Logic Extractor")
    arg_parser.add_argument("--input", required=True, help="Path to parser output JSON")
    arg_parser.add_argument("--output", default="docs/business_rules.md")
    arg_parser.add_argument("--json-output", default="agents/logic_output.json")
    arg_parser.add_argument("--no-ai", action="store_true")
    args = arg_parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        parse_data = json.load(f)

    extracted = {
        "inputs": extract_inputs(parse_data),
        "outputs": extract_outputs(parse_data),
        "constants": extract_constants(parse_data),
        "validation_rules": extract_validation_rules(parse_data),
        "calculation_steps": extract_calculation_steps(parse_data),
        "conditions": extract_conditions(parse_data),
    }

    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2)

    if args.no_ai:
        ai_text = "*AI interpretation skipped (--no-ai flag set)*"
        print("[LOGIC] Skipping AI interpretation.")
    else:
        ai_text = interpret_with_ai(parse_data, extracted)

    report = build_report(parse_data, extracted, ai_text)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    main()

