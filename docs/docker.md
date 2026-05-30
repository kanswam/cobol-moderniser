# Docker Usage Guide — COBOL Moderniser

> **Target audience:** Developers, DevOps engineers, and financial-institution
> administrators who want to run the COBOL Moderniser pipeline inside a
> container without installing Python or its dependencies locally.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Building the image](#2-building-the-image)
3. [Running in `--no-ai` mode (offline)](#3-running-in---no-ai-mode-offline)
4. [Running in AI mode](#4-running-in-ai-mode)
5. [Mounting your own COBOL files](#5-mounting-your-own-cobol-files)
6. [Getting output files back](#6-getting-output-files-back)
7. [Running the full 226-test validation](#7-running-the-full-226-test-validation)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

- **Docker Engine** >= 24.0 (or **Docker Desktop** >= 4.20)
- (Optional) **Docker Compose** >= 2.20 for `docker compose` commands
- A local clone of the repository:

```bash
git clone https://github.com/kanswam/cobol-moderniser.git
cd cobol-moderniser
```

Verify your installation:

```bash
docker --version
docker compose version
```

---

## 2. Building the image

Build the production image from the repository root:

```bash
docker build -t cobol-moderniser .
```

For a tagged release build:

```bash
docker build -t cobol-moderniser:0.1.0 .
```

The build uses a multi-stage Dockerfile:

| Stage | Purpose | Base image |
|---|---|---|
| `builder` | Compiles & installs Python deps into a virtualenv | `python:3.11-slim` |
| `production` | Runs the pipeline with a non-root user | `python:3.11-slim` |

### Build-time tips

- Ensure a `.dockerignore` file exists to keep the build context small.
- The image size is approximately **~180 MB** (production stage only).
- Build cache is layer-optimised; changing `requirements.txt` invalidates only
  the pip-install layer.

---

## 3. Running in `--no-ai` mode (offline)

This is the **default** and recommended mode for CI/CD or air-gapped
environments.  Agent 2 (business-rules extraction via Anthropic API) is
skipped.

### Quick run (built-in sample)

```bash
docker run --rm \
  -v $(pwd)/sample_cobol:/app/sample_cobol \
  -v $(pwd)/output:/app/output \
  cobol-moderniser \
  --no-ai \
  --input sample_cobol/mortgage_calc.cbl
```

### What happens

1. Agent 1 (Parser) reads `mortgage_calc.cbl` and writes
   `agents/parser_output.json`.
2. Agent 2 is skipped (`--no-ai`).
3. Agent 3 (Test Generator) creates regression tests in
   `tests/generated/`.
4. Agent 4 (Code Writer) emits `output/mortgage_calc.py`.
5. Agent 5 (Validator) produces `output/validation_report.md` and
   `output/validation_report.json`.

### Using Docker Compose (offline)

```bash
docker compose up cobol-moderniser
```

---

## 4. Running in AI mode

AI mode enables Agent 2 to query the **Anthropic API** for richer business-rule
extraction.  You must provide an API key.

### Option A — inline environment variable

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY=sk-ant-your-key-here \
  -v $(pwd)/sample_cobol:/app/sample_cobol \
  -v $(pwd)/output:/app/output \
  cobol-moderniser \
  --input sample_cobol/mortgage_calc.cbl
```

### Option B — `.env` file (recommended)

Create a `.env` file in the repository root:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env
```

> **Security note:** `.env` is listed in `.gitignore` and `.dockerignore`.
> Never commit secrets to version control.

Then run:

```bash
docker run --rm \
  --env-file .env \
  -v $(pwd)/sample_cobol:/app/sample_cobol \
  -v $(pwd)/output:/app/output \
  cobol-moderniser \
  --input sample_cobol/mortgage_calc.cbl
```

### Using Docker Compose (AI mode)

```bash
docker compose up cobol-moderniser-ai
```

The `docker-compose.yml` automatically sources the `.env` file for the
`cobol-moderniser-ai` service.

---

## 5. Mounting your own COBOL files

Place your `.cbl` source files and any copybooks (`.cpy`) in a local
 directory, then mount it into the container:

```bash
mkdir -p my_cobol_source
cp /path/to/legacy/*.cbl my_cobol_source/
cp /path/to/legacy/*.cpy my_cobol_source/
```

### Single file

```bash
docker run --rm \
  -v $(pwd)/my_cobol_source:/app/sample_cobol:ro \
  -v $(pwd)/output:/app/output \
  cobol-moderniser \
  --no-ai \
  --input sample_cobol/PROGRAM.cbl
```

### Entire directory (batch)

The pipeline entry point processes one file at a time.  For batch conversion,
use a shell loop:

```bash
mkdir -p output
for f in my_cobol_source/*.cbl; do
  fname=$(basename "$f")
  docker run --rm \
    -v $(pwd)/my_cobol_source:/app/sample_cobol:ro \
    -v $(pwd)/output:/app/output \
    cobol-moderniser \
    --no-ai \
    --input "sample_cobol/${fname}"
done
```

### Copybook resolution

If your COBOL programs reference copybooks via `COPY` statements, ensure the
`.cpy` files are in the mounted directory alongside the `.cbl` files:

```
my_cobol_source/
├── main_program.cbl
└── MORTGDEF.cpy
```

The parser searches the same directory as the source file for copybooks.

---

## 6. Getting output files back

The pipeline writes all generated artefacts to `/app/output` inside the
container.  Use a volume mount to persist them on the host:

```bash
-v $(pwd)/output:/app/output
```

### Output artefacts

| File | Description |
|---|---|
| `output/<name>.py` | Generated Python translation |
| `output/validation_report.md` | Human-readable validation report |
| `output/validation_report.json` | Machine-readable validation results |
| `docs/business_rules.md` | Extracted business rules (AI mode only) |
| `tests/generated/test_cases.json` | Generated test cases (JSON) |
| `tests/generated/test_cases.md` | Generated test cases (Markdown) |

### Tip: inspect output without re-running

```bash
cat output/validation_report.md
```

---

## 7. Running the full 226-test validation

The extended test suite validates the generated Python against 226 edge-case
scenarios.

### Step 1 — generate the extended tests (host-side, once)

```bash
python generate_extended_tests.py
```

This produces `tests/generated/extended_test_cases.json` and
`tests/generated/extended_test_cases.md`.

### Step 2 — mount the extended tests into the container

```bash
docker run --rm \
  -v $(pwd)/sample_cobol:/app/sample_cobol:ro \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/tests/generated:/app/tests/generated:ro \
  cobol-moderniser \
  --no-ai \
  --input sample_cobol/mortgage_calc.cbl
```

### Step 3 — run the validation manually inside the container

If you need to execute the validation directly:

```bash
docker run --rm -it \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/tests/generated:/app/tests/generated:ro \
  --entrypoint /bin/bash \
  cobol-moderniser \
  -c "python -m pytest tests/ -v --tb=short"
```

> Note: The base image does **not** include `pytest` by default.  Install it
> temporarily for validation runs, or extend the Dockerfile with a
> `pytest` layer if validation is a frequent use-case.

---

## 8. Troubleshooting

### Issue: `Permission denied` when writing to `output/`

**Cause:** The container runs as UID 1000 (`appuser`).  The host `output/`
directory may be owned by a different UID.

**Fix:**

```bash
# Ensure the host directory is writable by UID 1000
mkdir -p output
chmod 777 output        # quick fix
docker run --rm ...

# Or run with your host user (less secure)
docker run --rm --user $(id -u):$(id -g) ...
```

### Issue: `ANTHROPIC_API_KEY not set` or API errors in AI mode

**Cause:** The `ANTHROPIC_API_KEY` environment variable is missing or invalid.

**Fix:**

```bash
# Verify the key is set
echo $ANTHROPIC_API_KEY

# Run with explicit flag
docker run -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" ...
```

If you do not have a key, use `--no-ai` mode instead.

### Issue: `COPY` statement fails — missing copybook

**Cause:** The COBOL source references a `.cpy` file that is not in the
mounted directory.

**Fix:** Ensure all copybooks are included in the mount:

```bash
# Verify copybooks are present
ls sample_cobol/*.cpy

# Mount the parent directory that contains both .cbl and .cpy files
docker run -v $(pwd)/sample_cobol:/app/sample_cobol:ro ...
```

### Issue: Container exits immediately with no output

**Cause:** The default `CMD` is `--no-ai`, which expects an `--input` file.
If none is provided, the entry point may exit silently.

**Fix:** Always provide `--input`:

```bash
docker run --rm cobol-moderniser --no-ai --input sample_cobol/mortgage_calc.cbl
```

### Issue: Large build context / slow build

**Cause:** The Docker build context includes unnecessary files.

**Fix:** Ensure `.dockerignore` is present in the build root:

```bash
ls -la .dockerignore
# If missing, copy it:
cp .dockerignore.example .dockerignore
```

### Issue: Image size concerns

**Cause:** The production image is based on `python:3.11-slim` (~180 MB).

**Mitigation options:**

| Approach | Expected size | Trade-off |
|---|---|---|
| Current (`python:3.11-slim`) | ~180 MB | Good balance |
| `python:3.11-alpine` | ~120 MB | May break compiled deps |
| `gcr.io/distroless/python3` | ~90 MB | Harder to debug |

To switch bases, edit the `FROM` line in the Dockerfile.

---

## Security considerations for financial institutions

1. **Non-root user** — the container runs as `appuser` (UID 1000), reducing
   privilege-escalation risk.
2. **No secrets in image** — `ANTHROPIC_API_KEY` is injected at runtime, never
   baked into layers.
3. **Minimal attack surface** — uses `slim` variant; no compiler toolchain in
   the production stage.
4. **Read-only source mounts** — COBOL input directories are mounted `:ro`
   where possible.
5. **Multi-stage build** — build dependencies are discarded, keeping the final
   image lean.

---

## Next steps

- Read [architecture.md](architecture.md) for details on the 5-agent pipeline.
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for development workflows.
- Report issues at https://github.com/kanswam/cobol-moderniser/issues
