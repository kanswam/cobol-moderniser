# LIMITATIONS — COBOL Moderniser

*We believe in proving what we claim. This document describes exactly what 
this pipeline handles today and what it doesn't. No marketing. No hedging.*

*Last updated: June 2026*

---

## What We Have Proven

- ✅ End-to-end autonomous migration of a self-contained COBOL calculation module
- ✅ 226 test cases, 100% pass rate, £0.01 behavioural equivalence
- ✅ Decimal precision matching COBOL fixed-point arithmetic (ROUND_HALF_UP)
- ✅ Copybook support — COPY statements resolved up to 3 levels deep
- ✅ Standard COBOL divisions — IDENTIFICATION, ENVIRONMENT, DATA, PROCEDURE
- ✅ WORKING-STORAGE data structures including group and elementary items
- ✅ 88-level condition names
- ✅ PERFORM UNTIL loops
- ✅ GO TO statements
- ✅ PIC clauses: 9(n)V9(n), PIC X, numeric integers
- ✅ ROUNDED arithmetic
- ✅ Multi-level data hierarchy (01, 05 levels)
- ✅ IBM mainframe COBOL fixed format (columns 7–72)

---

## What We Have Not Proven

We list these not to discourage — but because a bank's risk team will ask 
every one of these questions. We would rather you read them here than 
discover them in a CTO meeting.

---

### Scale

**Current:** One program, approximately 200 lines of COBOL, 5 paragraphs.

**Real-world:** Enterprise COBOL codebases contain thousands of programs, 
millions of lines, hundreds of copybooks, and decades of patches applied 
on top of patches.

**What this means:** We have not demonstrated that the pipeline handles 
a full enterprise codebase. We have demonstrated that the approach is 
sound on a contained, representative module. Scale testing is the next 
priority.

---

### EXEC SQL (Embedded SQL)

**Current:** Not supported.

**Real-world:** Most COBOL programs that interact with databases use 
embedded SQL statements like `EXEC SQL SELECT ... END-EXEC`. These are 
preprocessed before compilation and require a different parsing strategy.

**What this means:** Programs with database interactions cannot currently 
be migrated end-to-end. The parser will flag unresolved EXEC SQL blocks 
rather than silently failing.

**Planned:** EXEC SQL support is on the roadmap.

---

### EXEC CICS (Transaction Processing)

**Current:** Not supported.

**Real-world:** CICS (Customer Information Control System) is the 
transaction processing middleware used by most major banks. COBOL programs 
that handle online transactions — screen input/output, terminal management, 
queue management — use EXEC CICS statements.

**What this means:** Online transaction programs cannot currently be 
migrated. Batch programs (calculations, reports, file processing) are in 
scope. Online programs are not.

**Planned:** CICS support is a significant undertaking and is not on the 
near-term roadmap. It requires understanding the CICS runtime context, 
not just the COBOL code.

---

### JCL (Job Control Language)

**Current:** Not supported.

**Real-world:** COBOL programs on IBM mainframes are executed via JCL 
scripts that define inputs, outputs, execution parameters and job 
dependencies. A complete migration includes migrating the JCL alongside 
the COBOL.

**What this means:** The pipeline migrates the COBOL program itself. 
The surrounding JCL — defining how the program is run, what files it 
reads and writes, and how it fits into a batch schedule — is not 
currently in scope.

**Planned:** JCL analysis is on the roadmap as a standalone agent.

---

### VSAM Files (Virtual Storage Access Method)

**Current:** Not supported.

**Real-world:** VSAM is IBM's file management system, used extensively 
for indexed sequential file access in COBOL batch programs. READ, WRITE, 
REWRITE, DELETE and START statements against VSAM files are common in 
production COBOL.

**What this means:** Programs that read from or write to VSAM files 
cannot currently be fully migrated. The calculation logic can be 
extracted and migrated, but the file I/O layer requires separate 
treatment.

**Planned:** VSAM migration to Python file/database equivalents is 
on the roadmap.

---

### Java Target Language

**Current:** Python only.

**Real-world:** Most enterprise banks target Java for COBOL migration, 
particularly Java running on modern cloud infrastructure. Java is the 
dominant language in existing bank technology stacks.

**What this means:** If your organisation requires a Java output, 
this pipeline does not currently provide it. The architecture is 
designed for multi-language output — the agent pipeline is language-agnostic 
in principle — but only the Python code writer has been implemented 
and tested.

**Planned:** Java target is on the roadmap. It will be built with and 
for the first enterprise client that requires it.

**Why Python first:** Python is the dominant language for AI and data 
science integration. A COBOL-to-Python migration enables direct 
connection of legacy calculations to modern ML models — something 
Java cannot do as elegantly. We believe this is the right 
architectural choice for the AI era, even if it is not yet the 
industry default.

---

### COBOL REPLACING Clause in COPY Statements

**Current:** Partial support.

**Real-world:** COPY statements can include a REPLACING clause that 
substitutes text within the copied copybook: 
`COPY MORTGDEF REPLACING ==MORTGAGE== BY ==PERSONAL-LOAN==`

**What this means:** Simple COPY statements are fully supported. 
COPY ... REPLACING across an entire project — where the same copybook 
is used with different substitutions in different programs — is not 
yet fully handled.

**Planned:** Full REPLACING support is in progress.

---

### Multi-Program Dependency Graphs

**Current:** Each program is migrated independently.

**Real-world:** Enterprise COBOL applications are not single programs. 
They are ecosystems of hundreds of programs that call each other, 
share copybooks, pass data through files and databases, and depend 
on execution order defined in JCL.

**What this means:** The pipeline does not currently map cross-program 
dependencies or migrate an application as a whole. It migrates 
individual programs correctly in isolation.

**Planned:** A dependency mapping agent is on the roadmap, building 
on the parser's existing call graph output.

---

### Fine-Tuned LLM

**Current:** Uses general-purpose Claude (Anthropic).

**Real-world:** Morgan Stanley and similar institutions have reported 
significantly higher accuracy using LLMs fine-tuned specifically on 
COBOL code and financial domain documentation.

**What this means:** For complex, ambiguous, or poorly documented COBOL, 
a general-purpose LLM may produce business rule interpretations that 
require human review. Our test-driven approach mitigates this — the 
validator catches behavioural differences regardless of how the rules 
were interpreted — but the Logic Extractor's plain-English output 
may occasionally require correction.

**Planned:** Fine-tuning is a longer-term initiative, likely pursued 
with a specific enterprise client's codebase as training data.

---

### REST API Generation

**Current:** Not supported.

**Real-world:** Some migration tools (notably onepoint/cobol-converter) 
automatically wrap migrated code in REST API endpoints, making the 
migrated logic immediately accessible as a microservice.

**What this means:** The pipeline produces a Python module, not an API. 
Wrapping in FastAPI or Flask is straightforward and well-documented 
but is not automated.

**Planned:** REST API generation is on the roadmap as an optional 
post-migration step.

---

### Dependency Visualisation

**Current:** Text-based dependency output in parser_output.json.

**Real-world:** Competitors including LegacyBridge provide visual 
dependency graphs — Mermaid diagrams, Neo4j graph databases — that 
allow technical teams to explore program relationships visually.

**What this means:** The parser correctly identifies all dependencies 
but presents them as structured JSON, not as a visual diagram.

**Planned:** Mermaid diagram generation from parser output is on 
the near-term roadmap.

---

## Our Position on These Limitations

We could have omitted this document. We chose not to.

Every tool in this space has limitations. Most don't publish them. 
We believe that a bank evaluating a migration tool deserves to know 
exactly what they are getting — and what questions to ask.

The limitations above represent a clear development roadmap. None of 
them are architectural dead ends. The pipeline was designed from the 
start to be extended — each agent is independent, testable and 
replaceable.

If you are evaluating this tool and a limitation above is a 
blocker for your use case, we would rather know that now and 
build toward it together than discover it after an engagement begins.

---

## What This Means for a First Engagement

The pipeline is production-ready for:

- **Self-contained calculation modules** — interest, premiums, 
  penalties, amortisation, benefit calculations
- **Batch processing programs** — file transformation, report 
  generation, data validation
- **Programs without EXEC SQL or EXEC CICS** — pure COBOL logic

The typical first engagement we recommend:

1. Identify one contained, well-understood COBOL module
2. Run the pipeline end-to-end
3. Review the validation report and business rules document
4. Validate the business rules against institutional knowledge
5. Deploy the migrated Python in parallel with the COBOL
6. Run both in production for 90 days, comparing outputs
7. Decommission COBOL when confidence is established

This approach de-risks the migration while building organisational 
confidence in the tool — and produces a case study that informs 
the broader programme.

---

## Contributing to Close These Gaps

If you have expertise in any of the unsupported areas — CICS, EXEC SQL, 
JCL, VSAM, Java code generation — contributions are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved.

---

*COBOL Moderniser — github.com/kanswam/cobol-moderniser*
*MIT Licence — use it, fork it, build on it.*
