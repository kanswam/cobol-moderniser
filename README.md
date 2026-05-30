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

## How It Works

Five specialised agents, each with a single job:

```
┌─────────────────────────────┐
│  INPUT: Legacy COBOL (.cbl) │
└──────────────┬──────────────┘
               ▼
       AGENT 1 — PARSER
       AGENT 2 — LOGIC EXTRACTOR
       AGENT 3 — TEST GENERATOR
       AGENT 4 — CODE WRITER
       AGENT 5 — VALIDATOR
               ▼
┌─────────────────────────────┐
│  OUTPUT: Python + Tests     │
└─────────────────────────────┘
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

# Run the full pipeline (no API key needed with --no-ai flag)
python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl --no-ai

# Run with AI-generated business rules (requires Anthropic API key)
export ANTHROPIC_API_KEY=your_key_here
python demo/run_pipeline.py --input sample_cobol/mortgage_calc.cbl
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

Cost is tracked automatically and saved to `output/cost_report.json`
after each pipeline run.

---

## The POC: Mortgage Amortisation

The proof of concept migrates a synthetic but realistic COBOL mortgage calculation routine — a programme that calculates:

- Monthly repayment amounts
- Principal/interest split per period
- Early repayment penalties
- Accumulated interest over the loan term

This is representative of the kind of self-contained, mathematically deterministic module that exists in every major bank's codebase — and is the ideal candidate for autonomous migration.

**Success condition:**
> Feed in COBOL. Get back Python + test suite. Every test passes. Zero human intervention.

---

## Project Structure

```
cobol-moderniser/
├── README.md
├── Dockerfile
├── docker-compose.yml
├── setup.py + pyproject.toml
├── requirements.txt
├── sample_cobol/
│   ├── mortgage_calc.cbl
│   ├── mortgage_full.cbl
│   └── copybooks/
├── agents/
│   ├── parser.py
│   ├── logic_extractor.py
│   ├── test_generator.py
│   ├── code_writer.py
│   ├── validator.py
│   └── cost_tracker.py
├── cobol_moderniser/
│   └── cli.py
├── output/
├── tests/generated/
└── demo/
    └── run_pipeline.py
```

---

## Current Status

| Component | Status |
|---|---|
| COBOL sample (mortgage) | Complete |
| Agent 1 — Parser | Complete |
| Agent 2 — Logic Extractor | Complete |
| Agent 3 — Test Generator | Complete |
| Agent 4 — Code Writer | Complete |
| Agent 5 — Validator | Complete |
| End-to-end demo | Complete |

---

## Why Now

Three things have converged to make this tractable in 2025 when it wasn't before:

1. **LLMs can read COBOL** — Modern language models can parse and reason about legacy programmes
2. **Agent orchestration is mature** — Multi-agent frameworks make coordinated pipelines practical
3. **The talent cliff is here** — The window for knowledge transfer from human COBOL developers is closing

---

## How We Compare

| Feature | COBOL Moderniser | onepoint/cobol-converter | LegacyBridge | Microsoft CAMF |
|---|---|---|---|---|
| Agents | 5 specialised | 3 (AutoGen) | 3 | 3 |
| Target language | Python | Python + FastAPI | Java (Quarkus) | Java (Quarkus) |
| Test-driven migration | ✅ Tests before code | ❌ | ❌ | ❌ |
| Behavioural equivalence proof | ✅ 226 tests, £0.01 | ⚠️ Admits failures | ❌ | ❌ |
| Decimal precision | ✅ ROUND_HALF_UP | ❌ Float | ✅ | ✅ |
| Zero human intervention | ✅ | ✅ | ✅ | ❌ Requires review |
| Cost tracking | ✅ | ❌ | ✅ | N/A |
| Docker support | ✅ | ❌ | ✅ | N/A |
| Open source | ✅ MIT | ✅ | ✅ | ❌ |
| Financial domain focus | ✅ | ❌ | ❌ | ✅ (Bankdata) |

Our primary differentiator: **test-driven migration with proven penny-level
behavioural equivalence**. No other open-source tool publicly demonstrates
this level of migration rigour.

---

## Who This Is For

- **Banks and insurers** with COBOL modernisation programmes that have stalled
- **System integrators** (Accenture, Infosys, Capgemini) looking for an automated migration layer
- **CTOs** who need to de-risk a conversation they've been avoiding for a decade
- **Developers** who want to contribute to one of the most consequential open-source problems in enterprise technology

---

## Contributing

This is an early-stage project and contributions are welcome, particularly:

- COBOL parsing improvements
- Additional test case generators
- Support for other target languages (Java, Go)
- Real-world COBOL samples (anonymised / synthetic)

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on development setup, code style, and the pull-request process.

Open an issue to discuss before submitting a PR.

---

## Current Limitations

- **Copybook support**: fully implemented — COPY statements resolved from same directory, `copybooks/` subdirectory, or `--copybook-path` argument
- **Nested copybooks**: supported up to 3 levels deep
- **JCL (Job Control Language)**: pipeline handles the COBOL program only, not surrounding JCL scripts
- **VSAM files**: file I/O not yet migrated, focus is on calculation logic
- **Tested on**: IBM mainframe COBOL (fixed format, columns 7-72)
- **Docker**: Docker and docker-compose support available (see Docker section above)
- **Cost tracking**: API costs are tracked automatically per pipeline run

---

## Roadmap

- [x] Complete the 5-agent pipeline for mortgage amortisation
- [x] Add support for COBOL copybooks and nested data structures
- [x] Build a CLI: `cobol-moderniser migrate input.cbl --target python`
- [ ] Add dependency visualiser (Mermaid diagrams)
- [ ] Support Java target language
- [ ] Fine-tuned LLM for COBOL-specific accuracy
- [ ] Extend to insurance premium calculation routines
- [ ] Hosted demo (upload COBOL, get Python back in browser)
- [ ] Publish results and validation methodology as a technical paper

---

## Licence

[MIT](LICENSE) — use it, fork it, build on it.

---

*If you work at a bank or insurer with a COBOL modernisation problem and want to talk, open an issue or reach out directly.*
