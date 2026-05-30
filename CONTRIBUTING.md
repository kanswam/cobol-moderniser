# Contributing to COBOL Moderniser

Thank you for your interest in contributing. This project addresses one of the most consequential maintenance challenges in enterprise technology, and we welcome contributions from developers, financial engineers, COBOL specialists, and researchers.

---

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Running the Pipeline Locally](#running-the-pipeline-locally)
- [Adding New COBOL Sample Programs](#adding-new-cobol-sample-programs)
- [Extending the Agent Pipeline](#extending-the-agent-pipeline)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Code Style](#code-style)
- [Reporting Issues](#reporting-issues)
- [Roadmap: Items Open for Contribution](#roadmap-items-open-for-contribution)

---

## Development Environment Setup

### Prerequisites

- **Python 3.8** or higher
- **Git**
- (Optional) An **Anthropic API key** if you want to run the full AI-powered pipeline

### Setup Steps

```bash
# 1. Clone the repository
git clone https://github.com/kanswam/cobol-moderniser.git
cd cobol-moderniser

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify the installation
python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl --no-ai
```

If the pipeline runs without errors and produces output in the `output/` directory, your environment is correctly configured.

---

## Running the Pipeline Locally

The project includes a full end-to-end demo runner. You can execute it in two modes:

### Offline Mode (no API key required)

This mode uses rule-based parsing and deterministic code generation. It is sufficient for development, testing, and validating structural changes to the pipeline.

```bash
python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl --no-ai
```

### AI-Enhanced Mode (requires Anthropic API key)

This mode leverages large language models for richer business-rule extraction and more idiomatic Python generation.

```bash
export ANTHROPIC_API_KEY=your_key_here
python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl
```

### Pipeline Output

After a successful run you will find:

| File | Description |
|---|---|
| `output/mortgage_calc.py` | Migrated Python module |
| `output/validation_report.txt` | Pass/fail summary of generated behavioural tests |
| `tests/generated/*.json` | Auto-generated test cases and expected outputs |

---

## Adding New COBOL Sample Programs

Expanding the library of supported COBOL patterns is one of the highest-value contributions you can make.

### Steps

1. **Obtain or create a COBOL file**.
   - Use anonymised or synthetic programs only.
   - Ensure the program is self-contained (no external `COPY` books unless you include them).
   - Target fixed-format IBM mainframe COBOL (code in columns 7-72).

2. **Place the `.cbl` file** in `sample_cobol/`.

3. **Run the pipeline** against it:
   ```bash
   python demo/run_pipeline.py --input sample_cobol/your_program.cbl --no-ai
   ```

4. **Verify the output**:
   - Check that `output/your_program.py` is generated.
   - Review `output/validation_report.txt`; all tests should pass.
   - If tests fail, inspect `tests/generated/*.json` to understand the mismatch.

5. **Add a regression test** (if applicable):
   - If you encounter a parsing or logic-extraction bug, add a minimal COBOL snippet that reproduces it to `tests/fixtures/` and include it in your PR.

### What Makes a Good Sample Program

- **Deterministic**: Pure calculation logic with clear inputs and outputs.
- **Representative**: Mirrors real-world financial routines (loans, premiums, pensions, risk calculations).
- **Self-contained**: No dependencies on proprietary copybooks or VSAM datasets.

---

## Extending the Agent Pipeline

Each agent is a standalone Python module in `agents/`. They communicate through well-defined JSON intermediates, so you can modify one agent without breaking the others as long as the contract is preserved.

### Agent Architecture

| Agent | Module | Input | Output | Responsibility |
|---|---|---|---|---|
| 1 — Parser | `agents/parser.py` | `.cbl` file | `agents/parser_output.json` | Structural analysis: `DIVISION`, `SECTION`, `PARAGRAPH`, data definitions |
| 2 — Logic Extractor | `agents/logic_extractor.py` | `parser_output.json` | `agents/logic_output.json` | Business-rule extraction: `COMPUTE`, `IF/EVALUATE`, loop structures, control flow |
| 3 — Test Generator | `agents/test_generator.py` | `logic_output.json` | `tests/generated/*.json` | Behavioural test-suite generation: input/output pairs, edge cases |
| 4 — Code Writer | `agents/code_writer.py` | `logic_output.json` + `tests/generated/*.json` | `output/*.py` | Python migration: idiomatic code, type hints, docstrings |
| 5 — Validator | `agents/validator.py` | `output/*.py` + `tests/generated/*.json` | `output/validation_report.*` | Output comparison: execute Python, compare against expected outputs |

### How to Modify an Agent

1. **Identify the agent** you want to improve (see table above).
2. **Read the module** and note the JSON schema it consumes and produces.
3. **Make your changes** — keep the external interface (function signatures and JSON schema) stable unless you have a compelling reason to change it.
4. **Run the full pipeline** end-to-end to ensure downstream agents still work:
   ```bash
   python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl --no-ai
   ```
5. **Update `docs/architecture.md`** if your change alters an agent's contract or adds a new concept.

### Common Extension Points

- **Parser**: Add support for additional COBOL verbs (`STRING`, `UNSTRING`, `SEARCH`, `SORT`), or handle free-format COBOL.
- **Logic Extractor**: Improve detection of implicit business rules (e.g., rounding modes, date arithmetic, currency conversion).
- **Test Generator**: Add new edge-case generators (negative interest rates, leap-year boundaries, zero-balance scenarios).
- **Code Writer**: Emit additional target languages (Java, Go) or improve the Python output style.
- **Validator**: Add performance benchmarking, memory-usage checks, or fuzzy tolerance for floating-point comparisons.

---

## Pull Request Guidelines

1. **Fork the repository** and create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **One logical change per PR**. Do not bundle unrelated fixes or features.

3. **All tests must pass** before submitting:
   ```bash
   python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl --no-ai
   ```

4. **Include a clear description** in your PR explaining:
   - **What** changed and **why**
   - Which agent(s) were affected
   - Any new dependencies or setup steps
   - References to relevant issues (e.g., `Closes #42`)

5. **Open an issue first** for substantial changes (new agents, breaking schema changes, new target languages) so we can discuss the approach before you invest significant effort.

---

## Code Style

We follow a consistent style to keep the codebase maintainable across contributors:

- **PEP 8** compliance is required.
- **Type hints** are encouraged on all function signatures and public attributes.
- **Docstrings** are required on all public functions, classes, and modules (Google or NumPy style).
- **Line length**: 100 characters soft limit. Go slightly over if breaking the line harms readability.
- **Imports**: Group in the order `stdlib`, `third-party`, `local`; sort alphabetically within groups.
- **Variable names**: Descriptive and unambiguous. Avoid single-letter names except in tight mathematical loops.

### Pre-commit Checks

Before committing, run:

```bash
python -m py_compile agents/*.py demo/*.py
```

If you have `flake8` installed:

```bash
flake8 agents/ demo/ --max-line-length=100
```

---

## Reporting Issues

We use GitHub Issues for bug reports, feature requests, and design discussions.

### Before You Open an Issue

- Search existing issues to avoid duplicates.
- Ensure you are on the latest `main` branch.

### Bug Reports

Please include:

1. **A minimal COBOL snippet** (anonymised / synthetic) that reproduces the problem.
2. **Expected output** vs. **actual output** — paste the relevant section of `output/validation_report.txt` or the generated Python file.
3. **Your environment**: Python version, operating system, whether you used `--no-ai` or an Anthropic API key.
4. **Steps to reproduce** the error.

### Feature Requests

Describe the use case clearly. If you are requesting support for a specific COBOL dialect or financial calculation pattern, include a reference to the COBOL standard or a synthetic example if possible.

---

## Roadmap: Items Open for Contribution

The following items are explicitly open for community contribution. Comment on the relevant issue (or open one) before starting work so we can coordinate.

| Item | Complexity | Description |
|---|---|---|
| **Copybook support** | Medium | Handle nested `COPY` statements by inlining copybook content before parsing. |
| **VSAM file I/O migration** | High | Extend the pipeline to migrate `READ`/`WRITE`/`REWRITE` operations on VSAM files to Python file I/O or database equivalents. |
| **Additional target languages** | Medium | Extend `code_writer.py` to emit Java or Go alongside Python. |
| **More COBOL sample programs** | Low-Medium | Add anonymised or synthetic programs from insurance (premium calculation), pensions (annuity), and loans (amortisation variations). |
| **Hosted web demo** | High | A browser-based interface where users upload a `.cbl` file and receive migrated Python and a validation report. |
| **Performance benchmarking** | Medium | Benchmark pipeline execution time and memory usage against large COBOL programs (10,000+ lines) and publish results. |
| **Free-format COBOL support** | Low | Adapt the parser to handle free-format COBOL (no column restrictions) in addition to fixed format. |
| **JCL pipeline integration** | High | Parse surrounding JCL scripts to extract job-step dependencies and data-set allocations as part of the migration context. |

---

## Questions?

If you are unsure about anything, open a GitHub Issue with the label `question` or reach out via the discussion board. We are happy to help.
