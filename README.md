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
┌─────────────────────────────────────────────────────────────┐
│                        INPUT                                │
│              Legacy COBOL Program (.cbl)                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  AGENT 1 — PARSER                                           │
│  Maps the COBOL structure: divisions, paragraphs,           │
│  copybooks, data types, control flow, dependencies          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  AGENT 2 — LOGIC EXTRACTOR                                  │
│  Identifies what the code actually does in business terms   │
│  Interest calculations, penalty clauses, rounding rules     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  AGENT 3 — TEST GENERATOR                                   │
│  Runs the COBOL and captures outputs across hundreds of     │
│  input combinations. These become the migration guardrails. │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  AGENT 4 — CODE WRITER                                      │
│  Produces idiomatic Python that replicates the logic,       │
│  guided by the test suite and the extracted business rules  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  AGENT 5 — VALIDATOR                                        │
│  Runs both programs against every test case. Flags any      │
│  output difference to the decimal place. 100% must pass.   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                       OUTPUT                                │
│   Migrated Python + Full Test Suite + Validation Report     │
└─────────────────────────────────────────────────────────────┘
```

Human intervention is only triggered when an agent flags genuine uncertainty — not for routine translation.

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
│
├── README.md                  ← You are here
│
├── sample_cobol/
│   └── mortgage_calc.cbl      ← Synthetic COBOL input (mortgage amortisation)
│
├── agents/
│   ├── parser.py              ← Agent 1: structural analysis
│   ├── logic_extractor.py     ← Agent 2: business rule extraction
│   ├── test_generator.py      ← Agent 3: behavioural test suite generation
│   ├── code_writer.py         ← Agent 4: Python migration
│   └── validator.py           ← Agent 5: output comparison and validation
│
├── tests/
│   └── generated/             ← Auto-generated test cases (inputs + expected outputs)
│
├── output/
│   └── mortgage_calc.py       ← Migrated Python output
│
├── demo/
│   └── run_pipeline.py        ← End-to-end demo: COBOL in → Python + report out
│
└── docs/
    └── architecture.md        ← Detailed agent design and decision rationale
```

---

## Current Status

| Component | Status |
|---|---|
| COBOL sample (mortgage) | ✅ Complete |
| Agent 1 — Parser | 🔄 In progress |
| Agent 2 — Logic Extractor | 🔄 In progress |
| Agent 3 — Test Generator | 🔄 In progress |
| Agent 4 — Code Writer | 🔄 In progress |
| Agent 5 — Validator | 🔄 In progress |
| End-to-end demo | ⏳ Planned |

---

## Why Now

Three things have converged to make this tractable in 2025 when it wasn't before:

1. **LLMs can read COBOL** — Modern language models have enough COBOL in their training data to parse, interpret, and reason about legacy programmes at a level no previous tool could match
2. **Agent orchestration is mature** — Multi-agent frameworks (LangGraph, CrewAI, AutoGen) now make it practical to run specialised agents in coordinated pipelines without building the infrastructure from scratch
3. **The talent cliff is here** — The window for knowledge transfer from human COBOL developers to any form of automated system is closing. The urgency is no longer theoretical.

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

Open an issue to discuss before submitting a PR.

---

## Roadmap

- [ ] Complete the 5-agent pipeline for mortgage amortisation
- [ ] Add support for COBOL copybooks and nested data structures
- [ ] Extend to insurance premium calculation routines
- [ ] Build a CLI: `cobol-moderniser migrate input.cbl --target python`
- [ ] Hosted demo (upload COBOL, get Python back in browser)
- [ ] Publish results and validation methodology as a technical paper

---

## Licence

MIT — use it, fork it, build on it.

---

*If you work at a bank or insurer with a COBOL modernisation problem and want to talk, open an issue or reach out directly.*
