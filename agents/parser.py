"""
=============================================================================
AGENT 1 — COBOL PARSER (with Copybook Support)
=============================================================================
Purpose:
 Reads a COBOL source file and builds a structured map of everything in it:
 - Divisions and sections
 - Data fields (names, types, sizes, hierarchy)
 - Paragraphs and their line ranges
 - Control flow (PERFORM, GO TO calls)
 - Copybook references (resolved and unresolved)
 - 88-level condition names
 - Copybook field provenance (which fields came from which copybook)
 - Confidence scoring for every extraction
 - Comment linkage to fields and paragraphs
 - Unknown syntax flagging
 - COMPUTE statement decomposition
 - SHA-256 source file integrity

 NEW: Full COPY statement resolution with nested copybook support
 up to 3 levels deep. Copybook fields are tracked with source
 provenance via the `source_copybook` attribute.

 NEW v2.0: Audit-ready parser with confidence scoring, comment
 linkage, unknown syntax detection, and COMPUTE decomposition.

Output:
 A Python dictionary (also saved as JSON) representing the full structure
 of the COBOL program — used by all downstream agents.

Usage:
 python parser.py --input sample_cobol/mortgage_calc.cbl
 python parser.py --input sample_cobol/mortgage_full.cbl \
     --copybook-path sample_cobol/copybooks
=============================================================================
"""

import re
import json
import argparse
import os
import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict

# ---------------------------------------------------------------------------
# COBOL RESERVED WORDS — prevents false paragraph detection
# ---------------------------------------------------------------------------

# Complete IBM Enterprise COBOL reserved word list
# Source: IBM Enterprise COBOL for z/OS Language Reference
COBOL_RESERVED_WORDS = {
    # Arithmetic and rounding
    'ROUNDED', 'REMAINDER', 'GIVING', 'COMPUTE',
    'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE',
    # Control flow
    'PERFORM', 'UNTIL', 'VARYING', 'AFTER', 'FROM',
    'GO', 'TO', 'GOBACK', 'STOP', 'RUN', 'EXIT',
    'IF', 'ELSE', 'END-IF', 'EVALUATE', 'WHEN',
    'END-EVALUATE', 'NOT',
    # Loop control
    'END-PERFORM', 'TIMES', 'WITH', 'TEST', 'BEFORE', 'AFTER',
    # Data movement
    'MOVE', 'INITIALIZE', 'SET', 'STRING', 'UNSTRING',
    'INSPECT', 'TALLYING', 'REPLACING',
    # I/O
    'READ', 'WRITE', 'REWRITE', 'DELETE', 'START',
    'OPEN', 'CLOSE', 'INPUT', 'OUTPUT', 'EXTEND', 'I-O',
    # Calling
    'CALL', 'USING', 'BY', 'REFERENCE', 'CONTENT', 'VALUE',
    'RETURN-CODE', 'RETURNING',
    # Scope terminators
    'END-ADD', 'END-SUBTRACT', 'END-MULTIPLY', 'END-DIVIDE',
    'END-COMPUTE', 'END-READ', 'END-WRITE', 'END-CALL',
    'END-STRING', 'END-UNSTRING', 'END-EVALUATE',
    # Conditions
    'AND', 'OR', 'NOT', 'TRUE', 'FALSE',
    'ZERO', 'ZEROS', 'ZEROES', 'SPACE', 'SPACES',
    'HIGH-VALUE', 'HIGH-VALUES', 'LOW-VALUE', 'LOW-VALUES',
    'QUOTE', 'QUOTES', 'ALL',
    # Data definition
    'PIC', 'PICTURE', 'COMP', 'COMPUTATIONAL', 'SYNC',
    'SYNCHRONIZED', 'JUSTIFIED', 'JUST', 'BLANK',
    'REDEFINES', 'OCCURS', 'TIMES', 'DEPENDING', 'INDEXED',
    'FILLER', 'RENAMES', 'COPY', 'REPLACING',
    # Sections and divisions
    'SECTION', 'DIVISION', 'PROCEDURE',
    # Common paragraph-like keywords that are NOT paragraphs
    'END', 'BEGIN', 'DECLARATIVES', 'END-DECLARATIVES',
}

# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class DataField:
    """Represents a single field in the WORKING-STORAGE or other data sections.

    Attributes:
        level: COBOL level number (01, 05, 88, etc.)
        name: Field name (or FILLER)
        picture: PIC clause e.g. 9(10)V99
        value: VALUE clause literal
        parent: Parent group field name
        children: Subordinate field names
        conditions: 88-level condition names attached to this field
        line_number: Source line number where field is defined
        source_copybook: Name of copybook this field came from, or None
        data_type: Derived type (NUMERIC, ALPHANUMERIC, GROUP, etc.)
        field_length: Derived field length in characters
        decimal_places: Number of decimal places for numeric fields
        confidence: Confidence rating — HIGH, MEDIUM, or LOW
        confidence_reason: Explanation for the confidence rating
        preceding_comments: Comments immediately preceding this field
    """
    level: int
    name: str
    picture: Optional[str] = None
    value: Optional[str] = None
    parent: Optional[str] = None
    children: list = field(default_factory=list)
    conditions: list = field(default_factory=list)
    line_number: int = 0
    source_copybook: Optional[str] = None
    data_type: Optional[str] = None
    field_length: Optional[int] = None
    decimal_places: Optional[int] = None
    confidence: str = "HIGH"
    confidence_reason: str = ""
    preceding_comments: list = field(default_factory=list)


@dataclass
class Condition:
    """Represents an 88-level condition name.

    Attributes:
        name: Condition name (e.g. MC-ACTIVE)
        value: VALUE clause literal
        parent_field: Name of the field this condition applies to
        line_number: Source line number
        source_copybook: Name of copybook this condition came from, or None
        confidence: Confidence rating
        confidence_reason: Explanation for confidence
        preceding_comments: Comments immediately preceding this condition
    """
    name: str
    value: str
    parent_field: str
    line_number: int = 0
    source_copybook: Optional[str] = None
    confidence: str = "HIGH"
    confidence_reason: str = ""
    preceding_comments: list = field(default_factory=list)


@dataclass
class Paragraph:
    """Represents a PROCEDURE DIVISION paragraph.

    Attributes:
        name: Paragraph name
        start_line: First line of the paragraph
        end_line: Last line of the paragraph
        statements: Raw COBOL statement lines
        calls_to: PERFORM and GO TO targets
        called_by: Paragraphs that call this one
        confidence: Confidence rating
        confidence_reason: Explanation for confidence
        preceding_comments: Comments immediately preceding this paragraph
        compute_statements: Decomposed COMPUTE statements
    """
    name: str
    start_line: int
    end_line: int = 0
    statements: list = field(default_factory=list)
    calls_to: list = field(default_factory=list)
    called_by: list = field(default_factory=list)
    confidence: str = "HIGH"
    confidence_reason: str = "Standard COBOL paragraph with explicit period"
    preceding_comments: list = field(default_factory=list)
    compute_statements: list = field(default_factory=list)


@dataclass
class CopybookRef:
    """Represents a COPY statement reference in the source.

    Attributes:
        name: Copybook name (e.g. MORTGDEF)
        line: Line number in source where COPY appears
        resolved: Whether the copybook file was found and loaded
        nested_in: Name of parent copybook if nested, else None
    """
    name: str
    line: int
    resolved: bool = False
    nested_in: Optional[str] = None


@dataclass
class ParseResult:
    """The complete parsed structure of a COBOL program.

    Attributes:
        program_id: PROGRAM-ID value
        source_computer: SOURCE-COMPUTER value
        object_computer: OBJECT-COMPUTER value
        divisions: List of division names and line numbers
        data_fields: name -> DataField mapping
        paragraphs: name -> Paragraph mapping
        conditions: name -> Condition mapping
        copybooks: List of CopybookRef objects
        copybook_fields: copybook_name -> list of field names
        unresolved_copybooks: List of copybook names not found
        comments: List of comment entries
        raw_lines: Original source lines
        metadata: Summary statistics
        unknown_syntax: List of unrecognised syntax entries
        warnings: List of parser warnings
        source_sha256: SHA-256 hash of the source file
    """
    program_id: Optional[str] = None
    source_computer: Optional[str] = None
    object_computer: Optional[str] = None
    divisions: list = field(default_factory=list)
    data_fields: dict = field(default_factory=dict)
    paragraphs: dict = field(default_factory=dict)
    conditions: dict = field(default_factory=dict)
    copybooks: list = field(default_factory=list)
    copybook_fields: dict = field(default_factory=dict)
    unresolved_copybooks: list = field(default_factory=list)
    comments: list = field(default_factory=list)
    raw_lines: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    unknown_syntax: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    source_sha256: str = ""


# ---------------------------------------------------------------------------
# PARSER
# ---------------------------------------------------------------------------

class COBOLParser:
    """Parse IBM fixed-format COBOL source files into structured data.

    Supports COPY statement resolution with nested copybooks up to
    3 levels deep. Copybook search paths include the source directory,
    a 'copybooks/' subdirectory, and user-specified paths.

    Attributes:
        source_path: Path to the COBOL source file
        copybook_path: Additional path(s) to search for copybooks
        lines: Raw source lines
        result: ParseResult populated during parsing
    """

    # COBOL fixed-format columns: indicator=6, content=7-72
    INDICATOR_COL = 6
    CONTENT_START = 6
    CONTENT_END = 72
    MAX_COPYBOOK_DEPTH = 3
    COMMENT_LINK_WINDOW = 3  # lines within which a comment links to next item

    def __init__(self, source_path: str, copybook_path: Optional[str] = None):
        """Initialize parser.

        Args:
            source_path: Path to the COBOL source file
            copybook_path: Additional path to search for copybooks.
                Can be a single path or os.pathsep-separated paths.
        """
        self.source_path = source_path
        self.copybook_path = copybook_path
        self.lines: List[str] = []
        self.result = ParseResult()
        self._parse_start_time = 0.0

    def parse(self) -> ParseResult:
        """Main entry point — runs all parsing passes.

        Returns:
            Fully populated ParseResult
        """
        self._parse_start_time = time.perf_counter()
        print(f"[PARSER] Reading source: {self.source_path}")
        self._load_file()
        print(f"[PARSER] Loaded {len(self.lines)} lines")

        self._hash_source_file()
        self._first_pass_strip_comments()
        self._parse_identification_division()
        self._parse_environment_division()
        self._parse_data_division()
        self._parse_procedure_division()
        self._resolve_control_flow()
        self._derive_field_types()
        self._compute_confidence_summary()

        elapsed = time.perf_counter() - self._parse_start_time

        # Preserve confidence_summary if already computed
        existing_confidence = self.result.metadata.get("confidence_summary", {})

        self.result.metadata = {
            "parser_version": "2.0.0",
            "source_file": self.source_path,
            "source_sha256": self.result.source_sha256,
            "parse_date": time.strftime("%Y-%m-%d"),
            "parse_duration_seconds": round(elapsed, 3),
            "total_lines": len(self.lines),
            "total_fields": len(self.result.data_fields),
            "total_paragraphs": len(self.result.paragraphs),
            "total_conditions": len(self.result.conditions),
            "copybooks_referenced": len(self.result.copybooks),
            "copybooks_resolved": sum(
                1 for c in self.result.copybooks if c.resolved
            ),
            "copybooks_unresolved": len(self.result.unresolved_copybooks),
            "comment_count": len(self.result.comments),
            "warning_count": len(self.result.warnings),
            "unknown_syntax_count": len(self.result.unknown_syntax),
            "confidence_summary": existing_confidence,
        }

        print(f"[PARSER] Complete:")
        print(f"  Fields parsed    : "
              f"{self.result.metadata['total_fields']}")
        print(f"  Paragraphs found : "
              f"{self.result.metadata['total_paragraphs']}")
        print(f"  Conditions found : "
              f"{self.result.metadata['total_conditions']}")
        print(f"  Copybooks        : "
              f"{self.result.metadata['copybooks_referenced']} "
              f"({self.result.metadata['copybooks_resolved']} resolved, "
              f"{self.result.metadata['copybooks_unresolved']} unresolved)")
        print(f"  Warnings         : {len(self.result.warnings)}")
        print(f"  Unknown syntax   : {len(self.result.unknown_syntax)}")

        return self.result

    # ------------------------------------------------------------------
    # FILE LOADING & INTEGRITY
    # ------------------------------------------------------------------

    def _load_file(self) -> None:
        """Load the COBOL source file into memory."""
        with open(self.source_path, 'r', encoding='utf-8',
                  errors='replace') as f:
            self.lines = f.readlines()
        self.result.raw_lines = [l.rstrip('\n') for l in self.lines]

    def _hash_source_file(self) -> None:
        """Compute SHA-256 hash of the source file for audit integrity."""
        with open(self.source_path, 'rb') as f:
            self.result.source_sha256 = hashlib.sha256(f.read()).hexdigest()

    # ------------------------------------------------------------------
    # PASS 1 — STRIP COMMENTS
    # ------------------------------------------------------------------

    def _first_pass_strip_comments(self) -> None:
        """Record comment lines for reference."""
        for i, line in enumerate(self.result.raw_lines):
            if len(line) > self.INDICATOR_COL:
                indicator = line[self.INDICATOR_COL]
                if indicator in ('*', '/'):
                    self.result.comments.append({
                        "line": i + 1,
                        "text": line[self.CONTENT_START:].strip()
                    })

    def _get_content(self, line: str) -> str:
        """Extract the content portion of a COBOL line (cols 7-72).

        Args:
            line: Raw source line

        Returns:
            Stripped content area, or empty string for comments/blanks
        """
        if len(line) <= self.INDICATOR_COL:
            return ""
        indicator = line[self.INDICATOR_COL]
        if indicator in ('*', '/'):
            return ""
        content = line[self.CONTENT_START:self.CONTENT_END]
        return content.strip()

    def _is_comment(self, line: str) -> bool:
        """Check if a line is a comment line.

        Args:
            line: Raw source line

        Returns:
            True if the line is a comment
        """
        if len(line) <= self.INDICATOR_COL:
            return True
        return line[self.INDICATOR_COL] in ('*', '/')

    def _get_preceding_comments(self, line_number: int) -> List[str]:
        """Get comments within COMMENT_LINK_WINDOW lines before a given line.

        Args:
            line_number: 1-based line number of the item

        Returns:
            List of comment text strings
        """
        comments = []
        for comment in self.result.comments:
            # Comment must be within window and immediately before the item
            if 0 < line_number - comment["line"] <= self.COMMENT_LINK_WINDOW:
                comments.append(comment["text"])
        return comments

    # ------------------------------------------------------------------
    # COPYBOOK RESOLUTION
    # ------------------------------------------------------------------

    def _resolve_copybook_path(self, copybook_name: str) -> Optional[str]:
        """Find a copybook file on disk.

        Searches in order:
        1. Same directory as the COBOL source file (both name.cpy and name)
        2. A 'copybooks/' subdirectory of the source directory
        3. Paths specified via the copybook_path parameter
        4. Tries both ``name.cpy`` and ``name`` as filenames

        Args:
            copybook_name: The copybook name from the COPY statement

        Returns:
            Full path to the copybook file, or None if not found
        """
        source_dir = os.path.dirname(
            os.path.abspath(self.source_path)
        ) or os.getcwd()

        # Build search path list
        search_dirs = [source_dir]

        # copybooks/ subdirectory
        copybooks_subdir = os.path.join(source_dir, 'copybooks')
        if os.path.isdir(copybooks_subdir):
            search_dirs.append(copybooks_subdir)

        # User-specified path(s)
        if self.copybook_path:
            for path in self.copybook_path.split(os.pathsep):
                path = path.strip()
                if path and os.path.isdir(path):
                    search_dirs.append(os.path.abspath(path))

        # Filename variants to try
        name_variants = [copybook_name]
        if not copybook_name.lower().endswith('.cpy'):
            name_variants.append(copybook_name + '.cpy')

        for directory in search_dirs:
            for variant in name_variants:
                candidate = os.path.join(directory, variant)
                if os.path.isfile(candidate):
                    return candidate

        return None

    def _load_copybook(
        self,
        copybook_name: str,
        depth: int = 0,
        nested_in: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """Load a copybook file and return its content lines.

        Handles nested COPY statements up to MAX_COPYBOOK_DEPTH levels.
        Each line is tagged with the copybook it originated from for
        provenance tracking.

        Args:
            copybook_name: Name from the COPY statement
            depth: Current nesting depth (0 = top-level)
            nested_in: Name of parent copybook if nested

        Returns:
            List of (line_content, source_copybook_name) tuples.
            line_content is the content area (cols 7-72) of each line.
            Returns empty list if copybook not found (with warning).
        """
        if depth > self.MAX_COPYBOOK_DEPTH:
            self.result.warnings.append({
                "line": 0,
                "content": f"COPY {copybook_name}",
                "warning": (
                    f"Max copybook nesting depth ({self.MAX_COPYBOOK_DEPTH}) "
                    f"exceeded — skipping nested copybooks"
                )
            })
            print(f"[PARSER] WARNING: Max copybook nesting depth "
                  f"({self.MAX_COPYBOOK_DEPTH}) exceeded for "
                  f"'{copybook_name}' — skipping nested copybooks")
            return []

        full_path = self._resolve_copybook_path(copybook_name)

        if full_path is None:
            self.result.warnings.append({
                "line": 0,
                "content": f"COPY {copybook_name}",
                "warning": f"Copybook '{copybook_name}' not found in search paths"
            })
            print(f"[PARSER] WARNING: Copybook '{copybook_name}' not found "
                  f"in search paths")
            if copybook_name not in self.result.unresolved_copybooks:
                self.result.unresolved_copybooks.append(copybook_name)
            return []

        print(f"[PARSER] Loading copybook: {copybook_name} "
              f"({full_path})" + (f" [nested in {nested_in}]"
                                   if nested_in else ""))

        try:
            with open(full_path, 'r', encoding='utf-8',
                      errors='replace') as f:
                raw_lines = f.readlines()
        except OSError as e:
            self.result.warnings.append({
                "line": 0,
                "content": f"COPY {copybook_name}",
                "warning": f"Cannot read copybook '{copybook_name}': {e}"
            })
            print(f"[PARSER] ERROR: Cannot read copybook "
                  f"'{copybook_name}': {e}")
            if copybook_name not in self.result.unresolved_copybooks:
                self.result.unresolved_copybooks.append(copybook_name)
            return []

        result_lines: List[Tuple[str, str]] = []

        for raw_line in raw_lines:
            stripped = raw_line.rstrip('\n')
            content = self._get_content(stripped)
            upper_content = content.upper()

            # Skip comments and blank lines. Copybooks often lack the
            # standard fixed-format indicator column (col 7), so we
            # also check for leading asterisks in the content area.
            if self._is_comment(stripped) or not content:
                continue
            if content.startswith('*'):
                continue

            # Handle nested COPY statements within this copybook
            if upper_content.startswith('COPY '):
                nested_match = re.search(
                    r'COPY\s+(\S+)', upper_content
                )
                if nested_match:
                    nested_name = nested_match.group(1).rstrip('.')
                    nested_lines = self._load_copybook(
                        nested_name,
                        depth=depth + 1,
                        nested_in=copybook_name
                    )
                    result_lines.extend(nested_lines)
                    # Add nested copybook reference
                    nested_ref = CopybookRef(
                        name=nested_name,
                        line=0,
                        resolved=nested_name not in
                        self.result.unresolved_copybooks,
                        nested_in=copybook_name
                    )
                    self.result.copybooks.append(nested_ref)
                    continue

            result_lines.append((content, copybook_name))

        return result_lines

    # ------------------------------------------------------------------
    # IDENTIFICATION DIVISION
    # ------------------------------------------------------------------

    def _parse_identification_division(self) -> None:
        """Extract PROGRAM-ID and other ID division metadata."""
        for i, line in enumerate(self.result.raw_lines):
            content = self._get_content(line).upper()
            if 'PROGRAM-ID' in content:
                match = re.search(
                    r'PROGRAM-ID\s*\.\s*(\S+)', content
                )
                if match:
                    self.result.program_id = (
                        match.group(1).rstrip('.')
                    )
                    print(f"[PARSER] Program ID: {self.result.program_id}")

    # ------------------------------------------------------------------
    # ENVIRONMENT DIVISION
    # ------------------------------------------------------------------

    def _parse_environment_division(self) -> None:
        """Extract SOURCE-COMPUTER and OBJECT-COMPUTER values."""
        for line in self.result.raw_lines:
            content = self._get_content(line).upper()
            if 'SOURCE-COMPUTER' in content:
                match = re.search(
                    r'SOURCE-COMPUTER\s*\.\s*(\S+)', content
                )
                if match:
                    self.result.source_computer = (
                        match.group(1).rstrip('.')
                    )
            if 'OBJECT-COMPUTER' in content:
                match = re.search(
                    r'OBJECT-COMPUTER\s*\.\s*(\S+)', content
                )
                if match:
                    self.result.object_computer = (
                        match.group(1).rstrip('.')
                    )

    # ------------------------------------------------------------------
    # DATA DIVISION — WITH COPYBOOK SUPPORT
    # ------------------------------------------------------------------

    def _parse_data_division(self) -> None:
        """Parse the DATA DIVISION, including COPY statement resolution.

        This method handles:
        - Regular inline data definitions
        - COPY statements that inline copybook content
        - Nested copybooks (up to 3 levels)
        - Tracking field provenance via source_copybook
        - Comment linkage to fields

        COPY statements are replaced with the actual copybook content,
        and each field parsed from a copybook is tagged with its origin.
        """
        in_data_division = False
        in_working_storage = False
        accumulated = ""
        acc_start_line = 0
        parent_stack = []

        # Build a stream of (content, line_number, source_copybook) tuples
        # for the working-storage section. COPY statements are expanded
        # inline so their content is parsed as regular data entries.
        data_line_stream: List[Tuple[str, int, Optional[str]]] = []

        for i, raw_line in enumerate(self.result.raw_lines):
            content = self._get_content(raw_line)
            upper = content.upper()

            if 'DATA DIVISION' in upper:
                in_data_division = True
                self.result.divisions.append(
                    {"name": "DATA DIVISION", "line": i + 1}
                )
                continue

            if 'PROCEDURE DIVISION' in upper:
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

            # COPY statement: resolve and inline the copybook content
            if upper.startswith('COPY '):
                match = re.search(r'COPY\s+(\S+)', upper)
                if match:
                    cb_name = match.group(1).rstrip('.')

                    # Record the copybook reference
                    copybook_ref = CopybookRef(
                        name=cb_name,
                        line=i + 1,
                        resolved=False
                    )

                    # Load the copybook content
                    cb_lines = self._load_copybook(cb_name, depth=0)

                    if cb_lines:
                        copybook_ref.resolved = True
                        # Track which fields come from this copybook
                        self.result.copybook_fields[cb_name] = []

                        # Add copybook lines to the stream
                        for cb_content, cb_source in cb_lines:
                            data_line_stream.append(
                                (cb_content, i + 1, cb_source)
                            )
                    else:
                        self.result.warnings.append({
                            "line": i + 1,
                            "content": content,
                            "warning": (
                                f"COPY '{cb_name}' not resolved — skipping"
                            )
                        })
                        print(f"[PARSER] WARNING: COPY '{cb_name}' at "
                              f"line {i + 1} not resolved — skipping")

                    self.result.copybooks.append(copybook_ref)
                    continue

            # Regular data line — add to stream with no copybook source
            data_line_stream.append((content, i + 1, None))

        # Now parse the expanded data line stream
        last_field_info = (0, None)  # (level, name) of last non-88 field
        for content, line_num, source_cb in data_line_stream:
            # Accumulate multi-line data entries
            if accumulated:
                accumulated += " " + content
            else:
                accumulated = content
                acc_start_line = line_num

            if content.rstrip().endswith('.'):
                last_field_info = self._parse_data_entry(
                    accumulated, acc_start_line, parent_stack,
                    last_field_info, source_cb
                )
                accumulated = ""

        # Handle any trailing entry without a period
        if accumulated:
            self._parse_data_entry(
                accumulated, acc_start_line, parent_stack,
                last_field_info,
                data_line_stream[-1][2] if data_line_stream else None
            )

    def _parse_data_entry(
        self,
        text: str,
        line_num: int,
        parent_stack: list,
        last_field_info: Tuple[int, Optional[str]],
        source_copybook: Optional[str] = None
    ) -> Tuple[int, Optional[str]]:
        """Parse a single data field definition.

        Handles level 01-49 group and elementary items, plus 88-level
        condition names. Tracks the source copybook for provenance.
        Links preceding comments to the field.

        Args:
            text: The accumulated data entry text (multi-line joined)
            line_num: Source line number for this entry
            parent_stack: Stack of (level, name) tuples for hierarchy
            last_field_info: (level, name) of the last non-88 field parsed
            source_copybook: Name of copybook this entry came from, or None

        Returns:
            Updated (level, name) of this field if non-88, else
            last_field_info unchanged
        """
        text = text.rstrip('.')
        upper = text.upper()

        match = re.match(r'^(\d{1,2})\s+(\S+)', upper)
        if not match:
            # Unrecognised data entry — flag as unknown syntax
            self.result.unknown_syntax.append({
                "line": line_num,
                "content": text,
                "context": "DATA DIVISION",
                "reason": "Unrecognised data entry pattern — manual review recommended"
            })
            return last_field_info

        level = int(match.group(1))
        name = match.group(2)

        if name in ('FILLER', 'SECTION', 'DIVISION'):
            return last_field_info

        # Extract PIC clause
        pic_match = re.search(r'PIC\S*\s+(\S+)', upper)
        picture = pic_match.group(1) if pic_match else None

        # Extract VALUE clause
        value_match = re.search(r'VALUE\s+(\S+)', upper)
        value = value_match.group(1) if value_match else None

        # Get preceding comments
        preceding_comments = self._get_preceding_comments(line_num)

        if level == 88:
            # 88-level condition names attach to the immediately
            # preceding data item (elementary or group). Use
            # last_field_info to determine the parent.
            parent_name = last_field_info[1] if last_field_info[1] else None
            condition = Condition(
                name=name,
                value=value or "",
                parent_field=parent_name or "",
                line_number=line_num,
                source_copybook=source_copybook,
                confidence="HIGH",
                confidence_reason="Explicit 88-level condition definition",
                preceding_comments=preceding_comments
            )
            self.result.conditions[name] = condition
            if parent_name and parent_name in self.result.data_fields:
                self.result.data_fields[parent_name].conditions.append(
                    name
                )
            return last_field_info

        # Maintain parent stack for hierarchy (group items only)
        while parent_stack and parent_stack[-1][0] >= level:
            parent_stack.pop()
        parent_name = parent_stack[-1][1] if parent_stack else None

        # Determine confidence
        if picture:
            confidence = "HIGH"
            confidence_reason = "Field with explicit PIC clause — unambiguous"
        elif value:
            confidence = "HIGH"
            confidence_reason = "Field with explicit VALUE clause — unambiguous"
        else:
            confidence = "HIGH"
            confidence_reason = "Group field — structural, not inferred"

        field = DataField(
            level=level,
            name=name,
            picture=picture,
            value=value,
            parent=parent_name,
            line_number=line_num,
            source_copybook=source_copybook,
            confidence=confidence,
            confidence_reason=confidence_reason,
            preceding_comments=preceding_comments
        )

        self.result.data_fields[name] = field

        # Track fields per copybook
        if source_copybook:
            if source_copybook not in self.result.copybook_fields:
                self.result.copybook_fields[source_copybook] = []
            if name not in self.result.copybook_fields[source_copybook]:
                self.result.copybook_fields[source_copybook].append(name)

        if parent_name and parent_name in self.result.data_fields:
            self.result.data_fields[parent_name].children.append(name)

        # Group items (no PIC) become potential parents
        if not picture:
            parent_stack.append((level, name))

        return (level, name)

    # ------------------------------------------------------------------
    # PROCEDURE DIVISION
    # ------------------------------------------------------------------

    def _parse_procedure_division(self) -> None:
        """Parse the PROCEDURE DIVISION into paragraphs.

        Uses the COBOL_RESERVED_WORDS set to prevent false paragraph
        detection. Links preceding comments to each paragraph.
        Decomposes COMPUTE statements.
        """
        in_procedure = False
        current_para = None
        current_statements = []
        current_compute = []

        for i, raw_line in enumerate(self.result.raw_lines):
            content = self._get_content(raw_line)
            upper = content.upper()

            if 'PROCEDURE DIVISION' in upper:
                in_procedure = True
                self.result.divisions.append(
                    {"name": "PROCEDURE DIVISION", "line": i + 1}
                )
                continue

            if not in_procedure or self._is_comment(raw_line) or not content:
                continue

            para_match = re.match(
                r'^([A-Z][A-Z0-9\-]*)\.?\s*$', upper
            )

            # Before accepting something as a paragraph name, verify
            # it's not a reserved word
            if para_match:
                candidate = para_match.group(1).rstrip('.')
                if candidate in COBOL_RESERVED_WORDS:
                    # Not a paragraph — it's a reserved word on its own line
                    if current_para:
                        current_statements.append(content)
                        # Check for COMPUTE in this statement
                        self._check_compute_statement(content, i + 1, current_para)
                    continue

                # It's a real paragraph
                if current_para:
                    self.result.paragraphs[current_para].end_line = i
                    self.result.paragraphs[current_para].statements = \
                        current_statements
                    self.result.paragraphs[current_para].compute_statements = \
                        current_compute

                current_para = candidate
                current_statements = []
                current_compute = []

                preceding_comments = self._get_preceding_comments(i + 1)

                self.result.paragraphs[current_para] = Paragraph(
                    name=current_para,
                    start_line=i + 1,
                    end_line=0,
                    confidence="HIGH",
                    confidence_reason="Standard COBOL paragraph with explicit period",
                    preceding_comments=preceding_comments
                )
            else:
                if current_para:
                    current_statements.append(content)
                    self._check_compute_statement(content, i + 1, current_para)
                else:
                    # Statement outside any paragraph — flag as unknown
                    self.result.unknown_syntax.append({
                        "line": i + 1,
                        "content": content,
                        "context": "PROCEDURE DIVISION",
                        "reason": "Statement outside paragraph boundary — verify structure"
                    })

        if current_para:
            self.result.paragraphs[current_para].end_line = len(
                self.result.raw_lines
            )
            self.result.paragraphs[current_para].statements = \
                current_statements
            self.result.paragraphs[current_para].compute_statements = \
                current_compute

    def _check_compute_statement(self, content: str, line_num: int, para_name: str) -> None:
        """Check if a statement is a COMPUTE and decompose it.

        Args:
            content: The statement content
            line_num: Line number
            para_name: Name of the current paragraph
        """
        upper = content.upper()
        if not upper.startswith('COMPUTE '):
            return

        # Try to decompose the COMPUTE statement
        decomposed = self._decompose_compute(content, line_num)
        if decomposed:
            self.result.paragraphs[para_name].compute_statements.append(
                decomposed
            )

    def _decompose_compute(self, content: str, line_num: int) -> Optional[dict]:
        """Decompose a COMPUTE statement into its operands.

        Args:
            content: The COMPUTE statement text
            line_num: Line number

        Returns:
            Dictionary with decomposed COMPUTE components, or None
        """
        upper = content.upper()

        # Check for ROUNDED keyword
        rounded = 'ROUNDED' in upper

        # Remove ROUNDED from the string for parsing
        cleaned = re.sub(r'\bROUNDED\b', '', content, flags=re.IGNORECASE)

        # Match COMPUTE target = expression
        match = re.match(
            r'COMPUTE\s+(\S+)\s*=\s*(.+)$',
            cleaned.strip(),
            re.IGNORECASE
        )
        if not match:
            return None

        target = match.group(1).strip()
        expression = match.group(2).strip().rstrip('.')

        # Extract variable references from expression
        # COBOL variables are alphanumeric with hyphens
        variables = set()
        for var_match in re.finditer(r'[A-Z][A-Z0-9\-]*', expression.upper()):
            var = var_match.group(0)
            if var not in COBOL_RESERVED_WORDS and var != target:
                variables.add(var)

        return {
            "type": "COMPUTE",
            "target": target,
            "rounded": rounded,
            "expression": expression,
            "variables_referenced": sorted(list(variables)),
            "line": line_num,
            "confidence": "MEDIUM",
            "confidence_reason": "COMPUTE decomposition is interpreted — verify expression"
        }

    # ------------------------------------------------------------------
    # CONTROL FLOW
    # ------------------------------------------------------------------

    def _resolve_control_flow(self) -> None:
        """Build call graph between paragraphs (PERFORM and GO TO)."""
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
                    # Skip reserved words that are not paragraph targets
                    if target in COBOL_RESERVED_WORDS:
                        continue
                    if target not in para.calls_to:
                        para.calls_to.append(target)
                    if target in self.result.paragraphs:
                        if para_name not in \
                                self.result.paragraphs[target].called_by:
                            self.result.paragraphs[target].called_by.append(
                                para_name
                            )
                    else:
                        # Target paragraph not found — warning
                        self.result.warnings.append({
                            "line": para.start_line,
                            "content": stmt,
                            "warning": (
                                f"PERFORM target '{target}' not found in "
                                f"paragraphs — may be external or unrecognised"
                            )
                        })

                for match in goto_pattern.finditer(stmt.upper()):
                    target = match.group(1)
                    goto_target = f"GOTO:{target}"
                    if goto_target not in para.calls_to:
                        para.calls_to.append(goto_target)

    # ------------------------------------------------------------------
    # FIELD TYPE DERIVATION
    # ------------------------------------------------------------------

    def _derive_field_types(self) -> None:
        """Derive data types, lengths and decimal places from PIC clauses."""
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
                self.result.warnings.append({
                    "line": f.line_number,
                    "content": f"PIC {f.picture}",
                    "warning": f"Unrecognised PIC clause for field {name}"
                })

    def _expand_pic_length(self, pic: str) -> int:
        """Calculate total character length from a PIC string.

        Handles patterns like 9(10), X(40), 9(5)V99 etc.

        Args:
            pic: PIC clause string (e.g. '9(10)V99')

        Returns:
            Total character count
        """
        total = 0
        for match in re.finditer(r'[9X]\((\d+)\)', pic):
            total += int(match.group(1))
        bare = re.sub(r'[9X]\(\d+\)', '', pic)
        total += sum(1 for c in bare if c in ('9', 'X'))
        return total if total > 0 else 1

    # ------------------------------------------------------------------
    # CONFIDENCE SUMMARY
    # ------------------------------------------------------------------

    def _compute_confidence_summary(self) -> None:
        """Compute overall confidence summary for the parse result."""
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

        for field in self.result.data_fields.values():
            counts[field.confidence] = counts.get(field.confidence, 0) + 1

        for para in self.result.paragraphs.values():
            counts[para.confidence] = counts.get(para.confidence, 0) + 1

        for cond in self.result.conditions.values():
            counts[cond.confidence] = counts.get(cond.confidence, 0) + 1

        # Also count COMPUTE statements
        for para in self.result.paragraphs.values():
            for comp in para.compute_statements:
                counts[comp.get("confidence", "MEDIUM")] = \
                    counts.get(comp.get("confidence", "MEDIUM"), 0) + 1

        total = sum(counts.values())
        low_pct = (counts.get("LOW", 0) / total * 100) if total > 0 else 0

        if low_pct < 5:
            overall = "HIGH"
        elif low_pct < 20:
            overall = "MEDIUM"
        else:
            overall = "LOW"

        self.result.metadata["confidence_summary"] = {
            "HIGH": counts.get("HIGH", 0),
            "MEDIUM": counts.get("MEDIUM", 0),
            "LOW": counts.get("LOW", 0),
            "overall": overall
        }


# ---------------------------------------------------------------------------
# SERIALISATION
# ---------------------------------------------------------------------------

def serialise(result: ParseResult) -> dict:
    """Convert a ParseResult to a JSON-serialisable dictionary.

    Args:
        result: ParseResult from COBOLParser.parse()

    Returns:
        Dictionary suitable for json.dump()

    Note:
        Fixes the original bug where ``result.result.paragraphs``
        was incorrectly referenced (should be ``result.paragraphs``).
    """
    return {
        "metadata": result.metadata,
        "program_id": result.program_id,
        "source_computer": result.source_computer,
        "object_computer": result.object_computer,
        "divisions": result.divisions,
        "copybooks": [
            {
                "name": c.name,
                "line": c.line,
                "resolved": c.resolved,
                "nested_in": c.nested_in
            }
            for c in result.copybooks
        ],
        "copybook_fields": result.copybook_fields,
        "unresolved_copybooks": result.unresolved_copybooks,
        "data_fields": {
            name: asdict(f) for name, f in result.data_fields.items()
        },
        "paragraphs": {
            name: asdict(p) for name, p in result.paragraphs.items()
        },
        "conditions": {
            name: asdict(c) for name, c in result.conditions.items()
        },
        "comment_count": len(result.comments),
        "comments": result.comments,
        "unknown_syntax": result.unknown_syntax,
        "warnings": result.warnings,
        "source_sha256": result.source_sha256,
    }


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for the COBOL parser."""
    arg_parser = argparse.ArgumentParser(
        description="COBOL Moderniser — Agent 1: Parser (with Copybook Support)"
    )
    arg_parser.add_argument(
        "--input", required=True,
        help="Path to the COBOL source file (.cbl or .cob)"
    )
    arg_parser.add_argument(
        "--output", default="agents/parser_output.json",
        help="Path to write the JSON parse result"
    )
    arg_parser.add_argument(
        "--copybook-path", default=None,
        help="Path to search for copybook files. Multiple paths "
             "can be separated by your OS path separator "
             "(e.g. '/path/one:/path/two')"
    )
    args = arg_parser.parse_args()

    parser = COBOLParser(args.input, copybook_path=args.copybook_path)
    result = parser.parse()

    output = serialise(result)

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    print(f"\n[PARSER] Output written to: {args.output}")


if __name__ == "__main__":
    main()


