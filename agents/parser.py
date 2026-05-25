"""
=============================================================================
AGENT 1 — COBOL PARSER
=============================================================================
Purpose:
    Reads a COBOL source file and builds a structured map of everything in it:
    - Divisions and sections
    - Data fields (names, types, sizes, hierarchy)
    - Paragraphs and their line ranges
    - Control flow (PERFORM, GO TO calls)
    - Copybook references
    - 88-level condition names
 
Output:
    A Python dictionary (also saved as JSON) representing the full structure
    of the COBOL program — used by all downstream agents.
 
Usage:
    python parser.py --input sample_cobol/mortgage_calc.cbl
    python parser.py --input sample_cobol/mortgage_calc.cbl --output my_parse.json
=============================================================================
"""
 
import re
import json
import argparse
from dataclasses import dataclass, field, asdict
from typing import Optional
 
 
# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------
 
@dataclass
class DataField:
    """Represents a single field in the WORKING-STORAGE or other data sections."""
    level: int
    name: str
    picture: Optional[str]        # PIC clause e.g. 9(10)V99
    value: Optional[str]          # VALUE clause
    parent: Optional[str]         # Parent group field name
    children: list = field(default_factory=list)
    conditions: list = field(default_factory=list)  # 88-level entries
    line_number: int = 0
 
    # Derived from PIC
    data_type: Optional[str] = None    # NUMERIC, ALPHANUMERIC, etc.
    field_length: Optional[int] = None
    decimal_places: Optional[int] = None
 
 
@dataclass
class Condition:
    """Represents an 88-level condition name."""
    name: str
    value: str
    parent_field: str
    line_number: int = 0
 
 
@dataclass
class Paragraph:
    """Represents a PROCEDURE DIVISION paragraph."""
    name: str
    start_line: int
    end_line: int
    statements: list = field(default_factory=list)   # Raw statement lines
    calls_to: list = field(default_factory=list)     # PERFORMs and GO TOs
    called_by: list = field(default_factory=list)    # Which paragraphs call this
 
 
@dataclass
class ParseResult:
    """The complete parsed structure of a COBOL program."""
    program_id: Optional[str]
    source_computer: Optional[str]
    object_computer: Optional[str]
    divisions: list
    data_fields: dict        # name -> DataField
    paragraphs: dict         # name -> Paragraph
    conditions: dict         # name -> Condition
    copybooks: list
    comments: list
    raw_lines: list
    metadata: dict
 
 
# ---------------------------------------------------------------------------
# PARSER
# ---------------------------------------------------------------------------
 
class COBOLParser:
 
    # COBOL fixed-format columns: indicator=6, content=7-72
    INDICATOR_COL = 6
    CONTENT_START = 6
    CONTENT_END = 72
 
    def __init__(self, source_path: str):
        self.source_path = source_path
        self.lines = []
        self.result = ParseResult(
            program_id=None,
            source_computer=None,
            object_computer=None,
            divisions=[],
            data_fields={},
            paragraphs={},
            conditions={},
            copybooks=[],
            comments=[],
            raw_lines=[],
            metadata={}
        )
 
    def parse(self) -> ParseResult:
        """Main entry point — runs all parsing passes."""
        print(f"[PARSER] Reading source: {self.source_path}")
        self._load_file()
        print(f"[PARSER] Loaded {len(self.lines)} lines")
 
        self._first_pass_strip_comments()
        self._parse_identification_division()
        self._parse_environment_division()
        self._parse_data_division()
        self._parse_procedure_division()
        self._resolve_control_flow()
        self._derive_field_types()
 
        self.result.metadata = {
            "source_file": self.source_path,
            "total_lines": len(self.lines),
            "total_fields": len(self.result.data_fields),
            "total_paragraphs": len(self.result.paragraphs),
            "total_conditions": len(self.result.conditions),
            "copybooks_referenced": len(self.result.copybooks),
        }
 
        print(f"[PARSER] Complete:")
        print(f"         Fields parsed    : {self.result.metadata['total_fields']}")
        print(f"         Paragraphs found : {self.result.metadata['total_paragraphs']}")
        print(f"         Conditions found : {self.result.metadata['total_conditions']}")
        print(f"         Copybooks        : {self.result.metadata['copybooks_referenced']}")
 
        return self.result
 
    # -----------------------------------------------------------------------
    # FILE LOADING
    # -----------------------------------------------------------------------
 
    def _load_file(self):
        with open(self.source_path, 'r', encoding='utf-8', errors='replace') as f:
            self.lines = f.readlines()
        self.result.raw_lines = [l.rstrip('\n') for l in self.lines]
 
    # -----------------------------------------------------------------------
    # PASS 1 — STRIP COMMENTS, IDENTIFY STRUCTURE
    # -----------------------------------------------------------------------
 
    def _first_pass_strip_comments(self):
        """
        COBOL fixed format: column 7 (index 6) is the indicator column.
        '*' = comment line, '/' = page eject (also a comment), '-' = continuation.
        Sequence numbers in columns 1-6 are ignored.
        """
        for i, line in enumerate(self.result.raw_lines):
            if len(line) > self.INDICATOR_COL:
                indicator = line[self.INDICATOR_COL]
                if indicator in ('*', '/'):
                    self.result.comments.append({
                        "line": i + 1,
                        "text": line[self.CONTENT_START:].strip()
                    })
 
    def _get_content(self, line: str) -> str:
        """Extract the content portion of a COBOL line (cols 7-72)."""
        if len(line) <= self.INDICATOR_COL:
            return ""
        indicator = line[self.INDICATOR_COL]
        if indicator in ('*', '/'):
            return ""
        content = line[self.CONTENT_START:self.CONTENT_END]
        return content.strip()
 
    def _is_comment(self, line: str) -> bool:
        if len(line) <= self.INDICATOR_COL:
            return True
        return line[self.INDICATOR_COL] in ('*', '/')
 
    # -----------------------------------------------------------------------
    # IDENTIFICATION DIVISION
    # -----------------------------------------------------------------------
 
    def _parse_identification_division(self):
        for i, line in enumerate(self.result.raw_lines):
            content = self._get_content(line).upper()
 
            if 'PROGRAM-ID' in content:
                match = re.search(r'PROGRAM-ID\s*\.\s*(\S+)', content)
                if match:
                    self.result.program_id = match.group(1).rstrip('.')
                    print(f"[PARSER] Program ID: {self.result.program_id}")
 
    # -----------------------------------------------------------------------
    # ENVIRONMENT DIVISION
    # -----------------------------------------------------------------------
 
    def _parse_environment_division(self):
        for line in self.result.raw_lines:
            content = self._get_content(line).upper()
            if 'SOURCE-COMPUTER' in content:
                match = re.search(r'SOURCE-COMPUTER\s*\.\s*(\S+)', content)
                if match:
                    self.result.source_computer = match.group(1).rstrip('.')
            if 'OBJECT-COMPUTER' in content:
                match = re.search(r'OBJECT-COMPUTER\s*\.\s*(\S+)', content)
                if match:
                    self.result.object_computer = match.group(1).rstrip('.')
 
    # -----------------------------------------------------------------------
    # DATA DIVISION
    # -----------------------------------------------------------------------
 
    def _parse_data_division(self):
        """
        Parse WORKING-STORAGE SECTION fields.
        Handles multi-line definitions by joining continuation lines.
        """
        in_data_division = False
        in_working_storage = False
        accumulated = ""
        acc_start_line = 0
        parent_stack = []   # Track group hierarchy: list of (level, name)
 
        for i, raw_line in enumerate(self.result.raw_lines):
            content = self._get_content(raw_line)
            upper = content.upper()
 
            if 'DATA DIVISION' in upper:
                in_data_division = True
                self.result.divisions.append({"name": "DATA DIVISION", "line": i + 1})
                continue
 
            if 'PROCEDURE DIVISION' in upper:
                # Flush any accumulated line before leaving data division
                if accumulated:
                    self._parse_data_entry(accumulated, acc_start_line, parent_stack)
                break
 
            if not in_data_division:
                continue
 
            if 'WORKING-STORAGE SECTION' in upper:
                in_working_storage = True
                continue
 
            if not in_working_storage:
                continue
 
            if self._is_comment(raw_line) or not content:
                continue
 
            # Check for COPY (copybook reference)
            if upper.startswith('COPY '):
                match = re.search(r'COPY\s+(\S+)', upper)
                if match:
                    self.result.copybooks.append({
                        "name": match.group(1).rstrip('.'),
                        "line": i + 1
                    })
                continue
 
            # Accumulate multi-line data entries (entry ends with '.')
            if accumulated:
                accumulated += " " + content
            else:
                accumulated = content
                acc_start_line = i + 1
 
            if content.rstrip().endswith('.'):
                self._parse_data_entry(accumulated, acc_start_line, parent_stack)
                accumulated = ""
 
    def _parse_data_entry(self, text: str, line_num: int, parent_stack: list):
        """Parse a single (possibly multi-line joined) data field definition."""
        text = text.rstrip('.')
        upper = text.upper()
 
        # Match level number and name
        match = re.match(r'^(\d{1,2})\s+(\S+)', upper)
        if not match:
            return
 
        level = int(match.group(1))
        name = match.group(2)
 
        # Skip FILLER and structural keywords
        if name in ('FILLER', 'SECTION', 'DIVISION'):
            return
 
        # Determine parent
        # Pop stack until we find a parent with a lower level number
        while parent_stack and parent_stack[-1][0] >= level:
            parent_stack.pop()
        parent_name = parent_stack[-1][1] if parent_stack else None
 
        # Extract PIC clause
        pic_match = re.search(r'PIC\S*\s+(\S+)', upper)
        picture = pic_match.group(1) if pic_match else None
 
        # Extract VALUE clause
        value_match = re.search(r'VALUE\s+(\S+)', upper)
        value = value_match.group(1) if value_match else None
 
        # Handle 88-level conditions
        if level == 88:
            condition = Condition(
                name=name,
                value=value or "",
                parent_field=parent_name or "",
                line_number=line_num
            )
            self.result.conditions[name] = condition
            # Add to parent field's conditions list
            if parent_name and parent_name in self.result.data_fields:
                self.result.data_fields[parent_name].conditions.append(name)
            return
 
        field = DataField(
            level=level,
            name=name,
            picture=picture,
            value=value,
            parent=parent_name,
            line_number=line_num
        )
 
        self.result.data_fields[name] = field
 
        # Add to parent's children list
        if parent_name and parent_name in self.result.data_fields:
            self.result.data_fields[parent_name].children.append(name)
 
        # Push this field onto the stack if it could be a group (no PIC)
        if not picture:
            parent_stack.append((level, name))
 
    # -----------------------------------------------------------------------
    # PROCEDURE DIVISION
    # -----------------------------------------------------------------------
 
    def _parse_procedure_division(self):
        """
        Identify all paragraphs and their content.
        A paragraph starts with a name in area A (cols 8-11, index 7-11)
        followed by a period.
        """
        in_procedure = False
        current_para = None
        current_statements = []
        current_start = 0
 
        for i, raw_line in enumerate(self.result.raw_lines):
            content = self._get_content(raw_line)
            upper = content.upper()
 
            if 'PROCEDURE DIVISION' in upper:
                in_procedure = True
                self.result.divisions.append({"name": "PROCEDURE DIVISION", "line": i + 1})
                continue
 
            if not in_procedure or self._is_comment(raw_line) or not content:
                continue
 
            # Paragraph header: a word followed by a period on its own line
            # In COBOL fixed format, paragraph names start in Area A (col 8)
            # We detect: line that is just WORD. or WORD-NAME.
            para_match = re.match(r'^([A-Z][A-Z0-9\-]*)\.?\s*$', upper)
 
            # Also catch EXIT paragraph
            if para_match and upper.strip() not in (
                'STOP RUN.', 'END-IF.', 'END-PERFORM.', 'EXIT.'
            ):
                # Save previous paragraph
                if current_para:
                    self.result.paragraphs[current_para].end_line = i
                    self.result.paragraphs[current_para].statements = current_statements
 
                current_para = para_match.group(1).rstrip('.')
                current_statements = []
                current_start = i + 1
 
                self.result.paragraphs[current_para] = Paragraph(
                    name=current_para,
                    start_line=current_start,
                    end_line=0
                )
            else:
                if current_para:
                    current_statements.append(content)
 
        # Close last paragraph
        if current_para:
            self.result.paragraphs[current_para].end_line = len(self.result.raw_lines)
            self.result.paragraphs[current_para].statements = current_statements
 
    # -----------------------------------------------------------------------
    # CONTROL FLOW RESOLUTION
    # -----------------------------------------------------------------------
 
    def _resolve_control_flow(self):
        """
        For each paragraph, find PERFORM and GO TO statements.
        Build a call graph: which paragraphs call which.
        """
        perform_pattern = re.compile(
            r'PERFORM\s+([A-Z][A-Z0-9\-]+)', re.IGNORECASE
        )
        goto_pattern = re.compile(
            r'GO\s+TO\s+([A-Z][A-Z0-9\-]+)', re.IGNORECASE
        )
 
        for para_name, para in self.result.paragraphs.items():
            for stmt in para.statements:
                for match in perform_pattern.finditer(stmt.upper()):
                    target = match.group(1)
                    if target not in para.calls_to:
                        para.calls_to.append(target)
                    # Mark reverse relationship
                    if target in self.result.paragraphs:
                        if para_name not in self.result.paragraphs[target].called_by:
                            self.result.paragraphs[target].called_by.append(para_name)
 
                for match in goto_pattern.finditer(stmt.upper()):
                    target = match.group(1)
                    if target not in para.calls_to:
                        para.calls_to.append(f"GOTO:{target}")
 
    # -----------------------------------------------------------------------
    # FIELD TYPE DERIVATION
    # -----------------------------------------------------------------------
 
    def _derive_field_types(self):
        """
        Analyse PIC clauses to derive human-readable type information.
        PIC 9(10)V99  -> NUMERIC, length 12, 2 decimal places
        PIC X(30)     -> ALPHANUMERIC, length 30
        PIC 9(3)      -> NUMERIC INTEGER, length 3
        """
        for name, f in self.result.data_fields.items():
            if not f.picture:
                f.data_type = "GROUP"
                continue
 
            pic = f.picture.upper()
 
            if 'X' in pic:
                f.data_type = "ALPHANUMERIC"
                f.field_length = self._expand_pic_length(pic)
            elif '9' in pic and 'V' in pic:
                f.data_type = "NUMERIC_DECIMAL"
                parts = pic.split('V')
                f.field_length = self._expand_pic_length(parts[0])
                f.decimal_places = self._expand_pic_length(parts[1])
            elif '9' in pic:
                f.data_type = "NUMERIC_INTEGER"
                f.field_length = self._expand_pic_length(pic)
            else:
                f.data_type = "UNKNOWN"
 
    def _expand_pic_length(self, pic: str) -> int:
        """
        Convert a PIC clause fragment to a character count.
        9(10) -> 10, XXX -> 3, 9(3)V9(6) handled by caller splitting on V.
        """
        total = 0
        # Match patterns like 9(10) or X(30)
        for match in re.finditer(r'[9X]\((\d+)\)', pic):
            total += int(match.group(1))
        # Match bare characters like XXX or 999
        bare = re.sub(r'[9X]\(\d+\)', '', pic)
        total += sum(1 for c in bare if c in ('9', 'X'))
        return total if total > 0 else 1
 
 
# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------
 
def serialise_result(result: ParseResult) -> dict:
    """Convert ParseResult to a JSON-serialisable dict."""
    return {
        "metadata": result.metadata,
        "program_id": result.program_id,
        "source_computer": result.source_computer,
        "object_computer": result.object_computer,
        "divisions": result.divisions,
        "copybooks": result.copybooks,
        "data_fields": {
            name: asdict(f) for name, f in result.data_fields.items()
        },
        "paragraphs": {
            name: asdict(p) for name, p in result.result.paragraphs.items()
            if hasattr(result, 'result')
        },
        "conditions": {
            name: asdict(c) for name, c in result.conditions.items()
        },
        "comment_count": len(result.comments),
    }
 
 
def serialise(result: ParseResult) -> dict:
    return {
        "metadata": result.metadata,
        "program_id": result.program_id,
        "source_computer": result.source_computer,
        "object_computer": result.object_computer,
        "divisions": result.divisions,
        "copybooks": result.copybooks,
        "data_fields": {
            name: asdict(f) for name, f in result.data_fields.items()
        },
        "paragraphs": {
            name: asdict(p) for name, p in result.result.paragraphs.items()
        } if False else {
            name: asdict(p) for name, p in result.paragraphs.items()
        },
        "conditions": {
            name: asdict(c) for name, c in result.conditions.items()
        },
        "comment_count": len(result.comments),
    }
 
 
# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
 
def main():
    arg_parser = argparse.ArgumentParser(
        description="COBOL Moderniser — Agent 1: Parser"
    )
    arg_parser.add_argument(
        "--input", required=True,
        help="Path to the COBOL source file (.cbl or .cob)"
    )
    arg_parser.add_argument(
        "--output", default="agents/parser_output.json",
        help="Path to write the JSON parse result (default: agents/parser_output.json)"
    )
    args = arg_parser.parse_args()
 
    parser = COBOLParser(args.input)
    result = parser.parse()
 
    output = serialise(result)
 
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
 
    print(f"\n[PARSER] Output written to: {args.output}")
    print("\n--- SUMMARY ---")
    print(f"Program ID      : {result.program_id}")
    print(f"Divisions found : {[d['name'] for d in result.divisions]}")
    print(f"Data fields     : {len(result.data_fields)}")
    print(f"Paragraphs      : {list(result.paragraphs.keys())}")
    print(f"Conditions (88) : {len(result.conditions)}")
    print(f"Copybooks       : {result.copybooks}")
 
 
if __name__ == "__main__":
    main()
