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

    NEW: Full COPY statement resolution with nested copybook support
    up to 3 levels deep. Copybook fields are tracked with source
    provenance via the `source_copybook` attribute.

Output:
    A Python dictionary (also saved as JSON) representing the full structure
    of the COBOL program — used by all downstream agents.

Usage:
    python parser.py --input sample_cobol/mortgage_calc.cbl
    python parser.py --input sample_cobol/mortgage_full.cbl \\
                     --copybook-path sample_cobol/copybooks
=============================================================================
"""

import re
import json
import argparse
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict


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


@dataclass
class Condition:
    """Represents an 88-level condition name.

    Attributes:
        name: Condition name (e.g. MC-ACTIVE)
        value: VALUE clause literal
        parent_field: Name of the field this condition applies to
        line_number: Source line number
        source_copybook: Name of copybook this condition came from, or None
    """
    name: str
    value: str
    parent_field: str
    line_number: int = 0
    source_copybook: Optional[str] = None


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
    """
    name: str
    start_line: int
    end_line: int = 0
    statements: list = field(default_factory=list)
    calls_to: list = field(default_factory=list)
    called_by: list = field(default_factory=list)


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

    def parse(self) -> ParseResult:
        """Main entry point — runs all parsing passes.

        Returns:
            Fully populated ParseResult
        """
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
            "copybooks_resolved": sum(
                1 for c in self.result.copybooks if c.resolved
            ),
            "copybooks_unresolved": len(self.result.unresolved_copybooks),
        }

        print(f"[PARSER] Complete:")
        print(f"         Fields parsed    : "
              f"{self.result.metadata['total_fields']}")
        print(f"         Paragraphs found : "
              f"{self.result.metadata['total_paragraphs']}")
        print(f"         Conditions found : "
              f"{self.result.metadata['total_conditions']}")
        print(f"         Copybooks        : "
              f"{self.result.metadata['copybooks_referenced']} "
              f"({self.result.metadata['copybooks_resolved']} resolved, "
              f"{self.result.metadata['copybooks_unresolved']} unresolved)")

        return self.result

    # ------------------------------------------------------------------
    # FILE LOADING
    # ------------------------------------------------------------------

    def _load_file(self) -> None:
        """Load the COBOL source file into memory."""
        with open(self.source_path, 'r', encoding='utf-8',
                  errors='replace') as f:
            self.lines = f.readlines()
        self.result.raw_lines = [l.rstrip('\n') for l in self.lines]

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
            print(f"[PARSER] WARNING: Max copybook nesting depth "
                  f"({self.MAX_COPYBOOK_DEPTH}) exceeded for "
                  f"'{copybook_name}' — skipping nested copybooks")
            return []

        full_path = self._resolve_copybook_path(copybook_name)

        if full_path is None:
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
                source_copybook=source_copybook
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

        field = DataField(
            level=level,
            name=name,
            picture=picture,
            value=value,
            parent=parent_name,
            line_number=line_num,
            source_copybook=source_copybook
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
        """Parse the PROCEDURE DIVISION into paragraphs."""
        in_procedure = False
        current_para = None
        current_statements = []

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

            if para_match and upper.strip() not in (
                'STOP RUN.', 'END-IF.', 'END-PERFORM.', 'EXIT.'
            ):
                if current_para:
                    self.result.paragraphs[current_para].end_line = i
                    self.result.paragraphs[current_para].statements = \
                        current_statements

                current_para = para_match.group(1).rstrip('.')
                current_statements = []

                self.result.paragraphs[current_para] = Paragraph(
                    name=current_para,
                    start_line=i + 1,
                    end_line=0
                )
            else:
                if current_para:
                    current_statements.append(content)

        if current_para:
            self.result.paragraphs[current_para].end_line = len(
                self.result.raw_lines
            )
            self.result.paragraphs[current_para].statements = \
                current_statements

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
                    if target not in para.calls_to:
                        para.calls_to.append(target)
                    if target in self.result.paragraphs:
                        if para_name not in \
                           self.result.paragraphs[target].called_by:
                            self.result.paragraphs[target].called_by.append(
                                para_name
                            )

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

