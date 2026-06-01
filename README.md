# COBOL Moderniser
### Autonomous migration of legacy COBOL to modern Python — with zero human intervention.

> *800 billion lines of COBOL still run the world's financial infrastructure. The developers who wrote it are retiring. The banks that depend on it are stuck. This project is an attempt to fix that.*

---

## The Problem

COBOL isn't a legacy curiosity. It is the engine of global finance:

- **$3 trillion** in daily transactions run through COBOL systems
- **95%** of ATM swipes touch COBOL code
- **80%** of in-person transactions are processed by COBOL
- The average COBOL programmer is **over 60 years old** — the knowledge is dying with them

Banks and insurers want to modernise. They can't. The risk is existential — Commonwealth Bank of Australia spent **$1 billion+** on a manual migration and abandoned it. Every attempt at line-by-line human rewriting has failed at scale.

The problem isn't that the code is hard to read. The problem is that **no single person understands all of it** — and the people who did are gone.

---

## The Insight

You don't need to understand legacy code to migrate it safely.

You need to **preserve its behaviour**.

If new code produces identical outputs to old code — across thousands of test cases, across edge cases, across decades of accumulated business logic — then the migration succeeded. Full stop.

This project uses an **autonomous agent swarm** to do exactly that: read the COBOL, extract the behaviour, generate a test suite, write modern Python, and validate it — without a human in the loop.

---

## Beyond Migration — The Simplification Layer

Migration alone moves complexity. It doesn't reduce it.

Agents 6 and 7 go further:

- **Agent 6 — Simplifier** restructures the migrated Python so any developer can read and maintain it — separating business rules from calculation logic, naming variables meaningfully, adding plain-English docstrings.

- **Agent 7 — Externaliser** extracts business rules into standalone YAML, JSON and Markdown files that business analysts and compliance teams can read, verify and update without touching code.

When a regulation changes, a business analyst edits `business_rules.yaml`. No developer required.

---

## How It Works

Seven specialised agents, each with a single job:

```
┌─────────────────────────────────┐
│   INPUT: Legacy COBOL (.cbl)    │
└────────────────┬────────────────┘
                 ▼
        AGENT 1 — PARSER
        Maps every field, paragraph,
        condition and dependency

                 ▼
        AGENT 2 — LOGIC EXTRACTOR
        Translates structure into plain
        English business rules

                 ▼
        AGENT 3 — TEST GENERATOR
        Builds test suite before any
        code is written (truly test-driven)

                 ▼
        AGENT 4 — CODE GENERATOR
        Produces clean idiomatic Python
        guided by the test suite

                 ▼
        AGENT 5 — VALIDATOR
        Runs all 226 tests automatically,
        confirms outputs match to £0.01

                 ▼
        AGENT 6 — SIMPLIFIER
        Restructures Python for
        readability and maintainability

                 ▼
        AGENT 7 — EXTERNALISER
        Extracts business rules into
        YAML / JSON / Markdown

┌─────────────────────────────────────────────┐
│   OUTPUT: Python + Tests + Business Rules   │
│   Validated to £0.01. Zero human intervention│
└─────────────────────────────────────────────┘
```

Human intervention is only triggered when an agent flags genuine uncertainty — not for routine translation.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/kanswam/cobol-moderniser.git
cd cobol-moderniser

# Install dependencies
pip install -r requirements.txt

# Run the full 7-agent pipeline (no API key needed)
python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl --no-ai

# Run with AI-generated business rules (requires Anthropic API key)
export ANTHROPIC_API_KEY=your_key_here
python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl
```

Expected output:
```
STEP 1/7 -- Parser          ✅  35 fields, 12 paragraphs
STEP 2/7 -- Logic Extractor ✅  business rules extracted
STEP 3/7 -- Test Generator  ✅  226 test cases generated
STEP 4/7 -- Code Generator  ✅  Python module written
STEP 5/7 -- Validator       ✅  226/226 tests passed
STEP 6/7 -- Simplifier      ✅  readable Python written
STEP 7/7 -- Externaliser    ✅  YAML / JSON / Markdown written

Status: PASS | 226/226 tests | 0.5s | $0.00 (offline)
```

---

## Docker

The fastest way to run COBOL Moderniser without installing Python dependencies:

```bash
# Build
docker build -t cobol-moderniser .

# Run (no API key needed)
docker run -v $(pwd)/sample_cobol:/app/sample_cobol \
           -v $(pwd)/output:/app/output \
           cobol-moderniser --no-ai

# Run with AI business rules generation
docker run -e ANTHROPIC_API_KEY=your_key \
           -v $(pwd)/sample_cobol:/app/sample_cobol \
           -v $(pwd)/output:/app/output \
           cobol-moderniser
```

See [docs/docker.md](docs/docker.md) for full documentation.

---

## Cost

Running the pipeline in `--no-ai` mode is completely free — no API calls are made.

Running with AI business rules generation (Agent 2) uses the Anthropic API.
Typical cost for a single COBOL module migration:

| Module size | Typical cost |
|---|---|
| Small (< 200 lines) | < $0.01 |
| Medium (200–500 lines) | $0.01 – $0.05 |
| Large (500–2000 lines) | $0.05 – $0.20 |

Cost is tracked automatically and saved to `output/cost_report.json` after each pipeline run.

---

## The POC: Mortgage Amortisation

The proof of concept migrates a synthetic but realistic COBOL mortgage calculation routine — a programme that calculates:

- Monthly repayment amounts
- Principal/interest split per period
- Early repayment penalties
- Accumulated interest over the loan term

This is representative of the kind of self-contained, mathematically deterministic module that exists in every major bank's codebase — and is the ideal candidate for autonomous migration.

**Success condition:**
> Feed in COBOL. Get back Python + test suite + business rules. Every test passes. Zero human intervention.

---

## What Agent 7 Produces

After migration, Agent 7 extracts all business rules into three formats:

**`business_rules.yaml`** — for business analysts and compliance teams:
```yaml
penalty_rules:
  early_repayment:
    description: >
      A penalty is charged when a borrower repays a fixed-rate
      mortgage early within the first 3 years (36 months).
    penalty_rate: 0.03        # 3% of outstanding balance
    applies_when:
      rate_type: FIXED
      repayment_month_max: 36
    regulatory_basis: "FSA mortgage conduct rules 1992"
```

**`business_rules.json`** — machine-readable, for APIs and tooling

**`business_rules.md`** — plain English narrative, for CTOs and regulators

The simplified Python reads business rules from `business_rules.yaml` at runtime. Change a value in the YAML file — the calculation changes. No code change. No developer required.

---

## Project Structure

```
cobol-moderniser/
├── README.md
├── LIMITATIONS.md               ← honest scope assessment
├── Dockerfile
├── docker-compose.yml
├── setup.py + pyproject.toml    ← pip install cobol-moderniser
├── requirements.txt
├── sample_cobol/
│   ├── mortgage_calc.cbl        ← synthetic 1987 COBOL input
│   ├── mortgage_full.cbl        ← extended COBOL with copybook
│   └── copybooks/
│       ├── MORTGDEF.cpy
│       └── COMMONERR.cpy
├── agents/
│   ├── parser.py                ← Agent 1
│   ├── logic_extractor.py       ← Agent 2
│   ├── test_generator.py        ← Agent 3
│   ├── code_writer.py           ← Agent 4
│   ├── validator.py             ← Agent 5
│   ├── simplifier.py            ← Agent 6
│   ├── externaliser.py          ← Agent 7
│   └── cost_tracker.py          ← API cost tracking
├── cobol_moderniser/
│   ├── __init__.py
│   └── cli.py                   ← CLI entry point
├── output/
│   ├── mortgage_calc_simplified.py   ← Agent 6 output
│   ├── business_rules.yaml           ← Agent 7 output
│   ├── business_rules.json           ← Agent 7 output
│   ├── business_rules.md             ← Agent 7 output
│   ├── simplification_report.md      ← Agent 6 report
│   └── validation_report.md          ← Agent 5 report (auto-generated)
├── tests/
│   └── generated/
│       ├── all_test_cases.json       ← 226 test cases
│       └── extended_test_cases.md
├── demo/
│   └── run_pipeline.py          ← single command, 7 agents
└── docs/
    ├── docker.md
    └── agents_6_7.md
```

---

## Current Status

| Component | Status |
|---|---|
| COBOL sample (mortgage) | ✅ Complete |
| Agent 1 — Parser | ✅ Complete |
| Agent 2 — Logic Extractor | ✅ Complete |
| Agent 3 — Test Generator | ✅ Complete |
| Agent 4 — Code Generator | ✅ Complete |
| Agent 5 — Validator | ✅ Complete (226 tests, auto-run) |
| Agent 6 — Simplifier | ✅ Complete |
| Agent 7 — Externaliser | ✅ Complete |
| End-to-end demo | ✅ Complete (7 agents, 0.5 seconds) |
| Docker support | ✅ Complete |
| Cost tracking | ✅ Complete |
| pip install cobol-moderniser | ✅ Complete |

---

## Why Now

Three things have converged to make this tractable in 2026 when it wasn't before:

1. **LLMs can read COBOL** — Modern language models have enough COBOL in their training data to parse, interpret and reason about legacy programmes at a level no previous tool could match
2. **Agent orchestration is mature** — Multi-agent frameworks make it practical to run specialised agents in coordinated pipelines without building infrastructure from scratch
3. **The talent cliff is here** — The window for knowledge transfer from human COBOL developers to any form of automated system is closing. The urgency is no longer theoretical.

---

## How We Compare

| Feature | COBOL Moderniser | onepoint/cobol-converter | LegacyBridge | Microsoft CAMF |
|---|---|---|---|---|
| Agents | 7 specialised | 3 (AutoGen) | 3 | 3 |
| Target language | Python | Python + FastAPI | Java (Quarkus) | Java (Quarkus) |
| Test-driven migration | ✅ Tests before code | ❌ | ❌ | ❌ |
| Behavioural equivalence proof | ✅ 226 tests, £0.01 | ⚠️ Admits failures | ❌ | ❌ |
| Decimal precision | ✅ ROUND_HALF_UP | ❌ Float | ✅ | ✅ |
| Zero human intervention | ✅ | ✅ | ✅ | ❌ Requires review |
| Business rules externalised | ✅ YAML/JSON/Markdown | ❌ | ❌ | ❌ |
| Simplified output | ✅ Agent 6 | ❌ | ❌ | ❌ |
| Cost tracking | ✅ | ❌ | ✅ | N/A |
| Docker support | ✅ | ❌ | ✅ | N/A |
| Open source | ✅ MIT | ✅ | ✅ | ❌ |
| Financial domain focus | ✅ | ❌ | ❌ | ✅ (Bankdata) |

Our primary differentiators:
- **Test-driven migration** — tests generated before code is written. No other open-source tool does this.
- **Proven penny-level equivalence** — 226 tests, auto-run every migration, results published openly.
- **Business rules externalised** — compliance teams can own and modify rules without touching code. Nobody else in this space does this.

---

## Who This Is For

- **Banks and insurers** with COBOL modernisation programmes that have stalled
- **System integrators** (Accenture, Infosys, Capgemini) looking for an automated migration layer
- **CTOs** who need to de-risk a conversation they've been avoiding for a decade
- **Compliance teams** who want to own their business rules rather than depend on developers
- **Developers** who want to contribute to one of the most consequential open-source problems in enterprise technology

---

## Contributing

This is an early-stage project and contributions are welcome, particularly:

- COBOL parsing improvements (EXEC SQL, EXEC CICS, JCL support)
- Additional test case generators
- Support for other target languages (Java, Go)
- Real-world COBOL samples (anonymised / synthetic)
- Dependency visualisation (Mermaid diagrams)

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on development setup, code style, and the pull-request process.

Open an issue to discuss before submitting a PR.

---

## Current Limitations

- **Copybook support**: fully implemented — COPY statements resolved from same directory, `copybooks/` subdirectory, or `--copybook-path` argument
- **Nested copybooks**: supported up to 3 levels deep
- **EXEC SQL**: not yet supported — programs with embedded SQL require additional parsing
- **EXEC CICS**: not yet supported — online transaction programs are out of scope
- **JCL (Job Control Language)**: pipeline handles the COBOL program only, not surrounding JCL scripts
- **VSAM files**: file I/O not yet migrated, focus is on calculation logic
- **Java target**: Python only — Java target is on the roadmap
- **Tested on**: IBM mainframe COBOL (fixed format, columns 7-72)

See [LIMITATIONS.md](LIMITATIONS.md) for a complete, honest assessment of current scope and what's planned.

---

## Roadmap

- [x] Complete the 7-agent pipeline for mortgage amortisation
- [x] Copybook support (COPY statements, nested up to 3 levels)
- [x] Extended test suite — 226 validated test cases, auto-run every migration
- [x] pip-installable CLI: `cobol-moderniser migrate input.cbl --target python`
- [x] Docker support
- [x] Cost tracking per agent
- [x] Agent 6 — Simplifier: readable, maintainable Python output
- [x] Agent 7 — Externaliser: business rules as YAML / JSON / Markdown
- [ ] Dependency visualiser (Mermaid diagrams from parser output)
- [ ] Support Java target language
- [ ] EXEC SQL support
- [ ] Extend to insurance premium calculation routines
- [ ] Hosted demo (upload COBOL, get Python back in browser)
- [ ] Publish results and validation methodology as a technical paper

---

## Licence

[MIT](LICENSE) — use it, fork it, build on it.

---

*If you work at a bank or insurer with a COBOL modernisation problem and want to talk, open an issue or reach out directly.*

