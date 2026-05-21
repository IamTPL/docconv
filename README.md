# docconv

Convert any document to Markdown using the best engine for each file type.

## Supported formats

| Format                                   | Engine                   |
| ---------------------------------------- | ------------------------ |
| `.pdf` (digital — text layer)            | Docling                  |
| `.pdf` (scanned — image-only)            | Google Gemini API        |
| `.xlsx`, `.xls`, `.xlsm`, `.csv`, `.tsv` | pandas + openpyxl        |
| `.docx`                                  | MarkItDown               |
| `.doc`, `.odt`                           | LibreOffice → MarkItDown |

---

## First-time setup

Run these steps **once** after cloning the repository. They assume Linux / macOS / WSL.

### 1. Clone the repository

```bash
git clone <repo-url> docconv
cd docconv      # you are now at the PROJECT ROOT — every command below runs from here
```

> **Note for non-developers:** "Project root" is the folder that contains `README.md`, `pyproject.toml`, and the `docconv/` sub-folder. All commands in this guide must be run from there, **not** from inside the inner `docconv/` package folder.

You can verify you are in the right place:

```bash
ls    # you should see: README.md  pyproject.toml  docconv/  tests/
```

### 2. Run the installer

The installer creates a virtual environment, installs all Python dependencies, installs LibreOffice, and creates the project config file — all in one step:

```bash
bash install.sh
```

What it does:

1. Creates `.venv/` (Python virtual environment)
2. Runs `pip install -e .` — installs docconv and all dependencies including the Gemini client
3. Installs LibreOffice via `apt` / `brew` (needed for `.doc` / `.odt` files)
4. Runs `docconv --init-config` — creates `.docconv.yaml` in the project root

### 3. Activate the virtual environment

After the installer finishes, activate the venv in your shell:

```bash
source .venv/bin/activate      # Linux / macOS / WSL
# Windows PowerShell:  .venv\Scripts\Activate.ps1
```

Your prompt will become `(.venv) ...` to confirm it's active.

### 4. (Only if converting scanned PDFs) Add your Gemini API key

If you will convert PDFs that are image-only / scanned, open `.docconv.yaml` and paste your Gemini API key:

```yaml
apis:
  gemini:
    api_key: 'paste-your-key-here'
```

Get a key at <https://aistudio.google.com/apikey>. If you only convert digital PDFs / DOCX / XLSX / CSV, you can ignore this — the library is installed but unused.

---

## Day-to-day usage

Every time you open a new terminal session, you only need to **activate the virtual environment** before using `docconv`:

```bash
cd /path/to/docconv          # go to the project root
source .venv/bin/activate    # re-activate the venv (prompt becomes "(.venv) ...")
docconv --help               # confirm it works
```

When you're done, you can leave the environment with `deactivate` (or just close the terminal).

---

## Command reference

**Convert a single file:**

```bash
docconv report.pdf -o report.md
docconv letter.docx -o result.md
docconv data.xlsx -o data.md
```

**Convert a single file into a folder** (output filename is auto-named):

```bash
docconv report.pdf -o output/
# → writes output/report.md
```

**Batch convert an entire folder:**

```bash
docconv input/ -o output/
# → converts every supported file in input/ and writes results into output/
```

### How PDF conversion works

You use the **same command** for both digital and scanned PDFs — `docconv` detects the type automatically. Use `--force-scan` to override and always use the Gemini engine:

```bash
docconv report.pdf -o report.md --force-scan
```

The tool reads the first 3 pages with PyMuPDF and counts extractable characters:

- **> 100 chars/page on average** → PDF has a text layer → converted with **Docling** (fast, no API key needed)
- **≤ 100 chars/page** → PDF is image-only / scanned → converted with **Gemini API** (requires `api_key` in `.docconv.yaml`)

If you run a scanned PDF without a Gemini API key configured, the tool will exit with a clear error message.

**Large PDFs (50+ pages)** are automatically split into chunks of 20 pages per API call to stay within Gemini's limits. Files above 15 MB are uploaded via the File Upload API instead of inline bytes. Both thresholds are configurable in `.docconv.yaml`.

### Examples

```bash
# Word document → Markdown
docconv letter.docx -o result.md

# PDF (digital or scanned — auto-detected)
docconv invoice.pdf -o output/

# Force Gemini engine even for a digital PDF
docconv report.pdf -o report.md --force-scan

# Batch convert an entire folder
docconv docs/ -o output/

# Excel: select specific sheets
docconv data.xlsx -o data.md --sheets "Sheet1,Revenue"

# Excel: treat first 2 rows as headers
docconv data.xlsx -o data.md --header-rows 2

# Print which engine is used and detailed progress
docconv report.pdf -o report.md --verbose
```

### Configuration commands

```bash
docconv --init-config   # create ./.docconv.yaml in current folder
docconv --show-config   # print active configuration
```

---

## Configuration

`docconv --init-config` creates `.docconv.yaml` in the current directory. The file is automatically added to `.gitignore` so your API keys are never committed.

```yaml
quality: auto # fast | precise | auto

apis:
  gemini:
    api_key: ''
    model: 'gemini-2.5-flash'
    temperature: 0.1 # lower = more deterministic (recommended for OCR)
    thinking_budget: 0 # 0 = disable thinking mode (faster, cheaper)
    timeout: 120 # seconds before giving up on a single API request
    max_retries: 2 # retries on timeout or 5xx server error (with backoff)
    page_chunk_size: 20 # pages per API call for large PDFs (0 = send whole file at once)
    inline_size_mb: 15.0 # files larger than this use File Upload API instead of inline bytes

spreadsheet:
  max_cell_len: 120
  skip_empty_sheets: true
  header_rows: 1
```

Lookup order (later overrides earlier):

1. Defaults
2. `~/.docconv.yaml` — global, per-user
3. `./.docconv.yaml` — local, per-project (created by `--init-config`)
4. CLI flags — highest priority

---

## Architecture

```
docconv/
├── cli.py           # argparse entry point
├── router.py        # detect file type → dispatch converter
├── config.py        # YAML config + CLI flag merging
├── converters/
│   ├── base.py      # BaseConverter interface
│   ├── pdf.py       # Digital PDF → Docling
│   ├── pdf_scan.py  # Scanned PDF → Google Gemini API (chunked for large files)
│   ├── spreadsheet.py
│   └── docx.py      # DOCX/DOC/ODT → MarkItDown
└── utils/
    └── postprocess.py
```

Converters are pure functions: `convert(path, config) → str`. Adding a web UI or REST API requires only a new thin wrapper — no changes to converter code.
