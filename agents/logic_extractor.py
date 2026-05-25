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
 
import json
import argparse
import re
from datetime import datetime
import urllib.request
 
 
# ---------------------------------------------------------------------------
# ANTHROPIC API CALL
# ---------------------------------------------------------------------------
 
def call_claude(prompt: str, system: str) -> str:
    """
    Call the Anthropic API with a prompt and return the text response.
    No API key needed — handled by the environment.
    """
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
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
        return result["content"][0]["text"]
 
 
# ---------------------------------------------------------------------------
# RULE EXTRACTORS
# ---------------------------------------------------------------------------
 
def extract_inputs(parse_data: dict) -> dict:
    """
    Identify the program's inputs — what data does it receive?
    Maps field names to human-readable descriptions.
    """
    print("[LOGIC] Extracting inputs...")
    inputs = {}
    fields = parse_data.get("data_fields", {})
 
    # Find input group fields (WS-INPUT pattern)
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
    """
    Identify the program's outputs — what data does it produce?
    """
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
    """
    Extract hardcoded business constants — these are often
    the most important and least-documented business rules.
    """
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
    """
    Extract input validation rules from the VALIDATE paragraph.
    """
    print("[LOGIC] Extracting validation rules...")
    rules = []
    paragraphs = parse_data.get("paragraphs", {})
 
    for para_name, para in paragraphs.items():
        if "VALIDATE" in para_name:
            for stmt in para.get("statements", []):
                if "IF" in stmt.upper() and (
                    "<=" in stmt or ">=" in stmt or ">" in stmt or "<" in stmt
                ):
                    rules.append({
                        "paragraph": para_name,
                        "raw_statement": stmt.strip(),
                    })
 
    return rules
 
 
def extract_calculation_steps(parse_data: dict) -> list:
    """
    Extract the sequence of calculation paragraphs
    in the order they are called.
    """
    print("[LOGIC] Extracting calculation sequence...")
    steps = []
    paragraphs = parse_data.get("paragraphs", {})
 
    # Find main procedure and follow its PERFORM calls in order
    main = paragraphs.get("MAIN-PROCEDURE", {})
    for called in main.get("calls_to", []):
        if called in paragraphs:
            para = paragraphs[called]
            steps.append({
                "step": len(steps) + 1,
                "paragraph": called,
                "statements": para.get("statements", []),
            })
 
    return steps
 
 
def extract_conditions(parse_data: dict) -> list:
    """
    Extract 88-level condition names — these are named business states.
    E.g. FIXED-RATE means WS-RATE-TYPE = 'F'
    """
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
 
def interpret_with_ai(parse_data: dict, extracted: dict) -> str:
    """
    Send the extracted structure to Claude and ask it to produce
    a plain-English business rules document.
    """
    print("[LOGIC] Sending to Claude for interpretation...")
 
    system_prompt = """You are a senior business analyst specialising in 
    financial systems modernisation. You have been given a structured analysis 
    of a legacy COBOL program. Your job is to write a clear, precise business 
    rules document that explains what this program does — in plain English that 
    a bank CTO or compliance officer could read and verify.
 
    Be specific about numbers, conditions, and formulas. Do not use technical 
    COBOL terminology. Write as if explaining to an intelligent non-programmer.
    Format your response in clean Markdown."""
 
    prompt = f"""
    I have analysed a COBOL program called {parse_data.get('program_id')}.
    
    Here is what I found:
 
    PROGRAM INPUTS:
    {json.dumps(extracted['inputs'], indent=2)}
 
    PROGRAM OUTPUTS:
    {json.dumps(extracted['outputs'], indent=2)}
 
    BUSINESS CONSTANTS:
    {json.dumps(extracted['constants'], indent=2)}
 
    NAMED BUSINESS CONDITIONS:
    {json.dumps(extracted['conditions'], indent=2)}
 
    VALIDATION RULES (raw statements):
    {json.dumps(extracted['validation_rules'], indent=2)}
 
    CALCULATION SEQUENCE:
    {json.dumps(extracted['calculation_steps'], indent=2)}
 
    Please produce a business rules document with these sections:
    1. Program Purpose (1 paragraph summary)
    2. Inputs — what data the program receives and any constraints
    3. Business Rules — the core logic explained in plain English,
       including the amortisation formula, penalty rules, and rounding
    4. Outputs — what the program produces
    5. Edge Cases and Validations — what invalid inputs are rejected and why
    6. Key Business Constants — hardcoded values and what they mean
    7. Migration Risk Notes — anything a developer should be careful about
       when translating this to Python
    """
 
    return call_claude(prompt, system_prompt)
 
 
# ---------------------------------------------------------------------------
# REPORT GENERATION
# ---------------------------------------------------------------------------
 
def build_report(
    parse_data: dict,
    extracted: dict,
    ai_interpretation: str
) -> str:
    """
    Combine the structured extraction and AI interpretation
    into a single Markdown report.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 
    report = f"""# Business Rules Document
## Program: {parse_data.get('program_id', 'UNKNOWN')}
 
*Generated by COBOL Moderniser — Agent 2 (Logic Extractor)*
*Date: {timestamp}*
 
---
 
{ai_interpretation}
 
---
 
## Appendix: Structured Extraction (Machine-Readable)
 
### Input Fields
| Field | Type | Length | Decimal Places | Default |
|---|---|---|---|---|
"""
    for name, inp in extracted["inputs"].items():
        report += (
            f"| {name} | {inp['type']} | "
            f"{inp['length']} | {inp['decimal_places']} | "
            f"{inp['default_value']} |\n"
        )
 
    report += """
### Output Fields
| Field | Type | Length | Decimal Places |
|---|---|---|---|
"""
    for name, out in extracted["outputs"].items():
        report += (
            f"| {name} | {out['type']} | "
            f"{out['length']} | {out['decimal_places']} |\n"
        )
 
    report += """
### Named Conditions (88-Level)
| Condition Name | Triggers When |
|---|---|
"""
    for cond in extracted["conditions"]:
        report += f"| {cond['name']} | {cond['triggers_when']} |\n"
 
    report += """
### Calculation Sequence
| Step | Paragraph |
|---|---|
"""
    for step in extracted["calculation_steps"]:
        report += f"| {step['step']} | {step['paragraph']} |\n"
 
    report += f"""
---
*Source: {parse_data.get('metadata', {}).get('source_file', 'unknown')}*
*Parser found: {parse_data.get('metadata', {}).get('total_fields', 0)} fields, \
{parse_data.get('metadata', {}).get('total_paragraphs', 0)} paragraphs*
"""
    return report
 
 
# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
 
def main():
    arg_parser = argparse.ArgumentParser(
        description="COBOL Moderniser — Agent 2: Logic Extractor"
    )
    arg_parser.add_argument(
        "--input", required=True,
        help="Path to parser output JSON (from Agent 1)"
    )
    arg_parser.add_argument(
        "--output", default="docs/business_rules.md",
        help="Path to write the business rules Markdown document"
    )
    arg_parser.add_argument(
        "--json-output", default="agents/logic_output.json",
        help="Path to write the structured JSON output"
    )
    arg_parser.add_argument(
        "--no-ai", action="store_true",
        help="Skip the AI interpretation step (useful for testing)"
    )
    args = arg_parser.parse_args()
 
    # Load parser output
    print(f"[LOGIC] Loading parser output: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        parse_data = json.load(f)
 
    # Run extractions
    extracted = {
        "inputs":           extract_inputs(parse_data),
        "outputs":          extract_outputs(parse_data),
        "constants":        extract_constants(parse_data),
        "validation_rules": extract_validation_rules(parse_data),
        "calculation_steps": extract_calculation_steps(parse_data),
        "conditions":       extract_conditions(parse_data),
    }
 
    print(f"\n[LOGIC] Extraction complete:")
    print(f"        Inputs identified    : {len(extracted['inputs'])}")
    print(f"        Outputs identified   : {len(extracted['outputs'])}")
    print(f"        Constants found      : {len(extracted['constants'])}")
    print(f"        Validation rules     : {len(extracted['validation_rules'])}")
    print(f"        Calculation steps    : {len(extracted['calculation_steps'])}")
    print(f"        Named conditions     : {len(extracted['conditions'])}")
 
    # Save structured JSON
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2)
    print(f"\n[LOGIC] Structured JSON written to: {args.json_output}")
 
    # AI interpretation
    if args.no_ai:
        ai_text = "*AI interpretation skipped (--no-ai flag set)*"
        print("[LOGIC] Skipping AI interpretation.")
    else:
        ai_text = interpret_with_ai(parse_data, extracted)
 
    # Build and save report
    report = build_report(parse_data, extracted, ai_text)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
 
    print(f"[LOGIC] Business rules document written to: {args.output}")
    print("\n--- DONE ---")
    print("Next step: Run Agent 3 (Test Generator) using logic_output.json")
 
 
if __name__ == "__main__":
    main()
