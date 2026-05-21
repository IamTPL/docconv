# docconv — Architecture & Technical Reference

> Version: 0.1.0 | Last updated: 2026-05-21

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Module Map](#2-module-map)
3. [Configuration System](#3-configuration-system)
4. [Routing Logic](#4-routing-logic)
5. [Converters](#5-converters)
   - [Digital PDF — Docling](#51-digital-pdf--docling)
   - [Scanned PDF — Gemini API](#52-scanned-pdf--gemini-api)
   - [Excel & CSV — Spreadsheet](#53-excel--csv--spreadsheet)
   - [Word Documents — Docx](#54-word-documents--docx)
6. [CLI Interface](#6-cli-interface)
7. [Post-processing](#7-post-processing)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
9. [Error Handling Strategy](#9-error-handling-strategy)
10. [Extending the System](#10-extending-the-system)
11. [Known Limitations & Roadmap](#11-known-limitations--roadmap)

---

## 1. System Overview

docconv is a CLI tool that converts document files (PDF, Excel, Word, CSV) into clean Markdown. It uses a **router-based converter pattern**: a central router inspects the file and selects the appropriate converter. All converters are stateless and return a raw Markdown string; post-processing is applied universally at the end.

```
Input File
    │
    ▼
┌─────────────────────────────────┐
│  Config (3-level hierarchy)     │
│  CLI args → .docconv.yaml →     │
│  ~/.docconv.yaml → defaults     │
└──────────────┬──────────────────┘
               │
    ▼
┌──────────────────────┐
│  Router              │  ← decides which converter handles the file
│  router.py           │
└──────┬───────────────┘
       │
  ┌────┴────────────────────────┐
  │                             │
  ▼                             ▼
PDF files               Non-PDF files
  │                             │
  ├─ digital ──► PDFConverter   ├─ .xlsx/.xls/.xlsm/.csv/.tsv ──► SpreadsheetConverter
  └─ scanned ──► PDFScanConv.   └─ .docx/.doc/.odt            ──► DocxConverter
       │
  (force-scan flag overrides detection)
       │
       ▼
  Markdown string
       │
       ▼
┌──────────────────┐
│  clean_markdown  │  ← normalise whitespace, line endings
│  postprocess.py  │
└──────────────────┘
       │
       ▼
  stdout  OR  file write
```

**Key design principles:**

- Converters never write files or print to stdout — they only return a string.
- All log/progress output goes to **stderr**; only markdown content goes to **stdout**.
- Config is an immutable dataclass; no global mutable state.
- New formats require only one new converter class + one line in `router.py`.

---

## 2. Module Map

```
docconv/
├── cli.py              # Entry point, argument parsing, orchestration
├── config.py           # Config dataclasses, YAML loading, merge hierarchy
├── router.py           # File-type detection and converter selection
├── converters/
│   ├── base.py         # Abstract BaseConverter + UnsupportedFormatError
│   ├── pdf.py          # Digital PDF via Docling
│   ├── pdf_scan.py     # Scanned PDF via Gemini API (with chunking)
│   ├── spreadsheet.py  # Excel (.xlsx/.xls/.xlsm) and CSV/TSV
│   └── docx.py         # Word (.docx) and legacy (.doc/.odt) via LibreOffice
└── utils/
    └── postprocess.py  # clean_markdown() normalisation
```

---

## 3. Configuration System

### 3.1 Config Dataclasses

```python
@dataclass
class GeminiConfig:
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.1       # low = deterministic (good for OCR)
    thinking_budget: int = 0       # 0 = disable thinking mode
    timeout: int = 120             # seconds per single API request
    max_retries: int = 2           # retries on timeout or 5xx
    page_chunk_size: int = 20      # pages per API call (0 = no chunking)
    inline_size_mb: float = 15.0   # threshold for File Upload API

@dataclass
class SpreadsheetConfig:
    max_cell_len: int = 120        # truncate cells beyond this with "…"
    skip_empty_sheets: bool = True
    header_rows: int = 1           # 0 = auto Col0/Col1…, >1 = multi-row join
    sheets: list[str] | None = None  # filter to named sheets (Excel only)

@dataclass
class Config:
    quality: str = "auto"          # "fast" | "precise" | "auto" (unused internally yet)
    gemini: GeminiConfig = ...
    spreadsheet: SpreadsheetConfig = ...
    output_dir: Path | None = None
    verbose: bool = False
```

### 3.2 Load Hierarchy (lowest → highest priority)

```
1. Dataclass defaults (in code)
2. ~/.docconv.yaml          (global user config)
3. ./.docconv.yaml          (project-local config, overrides global)
4. CLI overrides            (--verbose, --sheets, --header-rows)
```

Merging is **recursive**: nested dicts are merged key-by-key, not replaced wholesale. So a local config that only sets `gemini.model` still inherits all other keys from global config.

```python
def _merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge(result[k], v)   # recursive
        else:
            result[k] = v
    return result
```

### 3.3 CLI → Config Mapping

| CLI flag          | Config field                     | Transform                 |
| ----------------- | -------------------------------- | ------------------------- |
| `--verbose`       | `config.verbose`                 | `True` if present         |
| `--sheets A,B`    | `config.spreadsheet.sheets`      | `"A,B"` → `["A", "B"]`    |
| `--header-rows N` | `config.spreadsheet.header_rows` | `int(N)`                  |
| `--force-scan`    | (routing only, not Config)       | Forces `PDFScanConverter` |

### 3.4 YAML Structure

```yaml
quality: auto

apis:
  gemini:
    api_key: '' # Required for scanned PDFs
    model: gemini-2.5-flash
    temperature: 0.1
    thinking_budget: 0
    timeout: 120
    max_retries: 2
    page_chunk_size: 20
    inline_size_mb: 15.0

spreadsheet:
  max_cell_len: 120
  skip_empty_sheets: true
  header_rows: 1

output:
  dir: '' # empty = same directory as input
```

---

## 4. Routing Logic

`router.py` exposes a single function: `route(path, force_scan=False) → BaseConverter`

### Decision Tree

```
route(path)
    │
    ├─ suffix == ".pdf"?
    │       │
    │       ├─ force_scan=True ──────────────────► PDFScanConverter
    │       │
    │       └─ force_scan=False
    │               │
    │               └─ _detect_pdf_type(path)
    │                       │
    │                       ├─ "digital" ─────────► PDFConverter
    │                       └─ "scanned" ─────────► PDFScanConverter
    │
    └─ non-PDF: iterate _NON_PDF_CONVERTERS list
            │
            ├─ SpreadsheetConverter.can_handle()? ─► SpreadsheetConverter
            ├─ DocxConverter.can_handle()?         ─► DocxConverter
            └─ no match ──────────────────────────► UnsupportedFormatError
```

### PDF Type Detection

```python
_TEXT_THRESHOLD = 100   # average chars/page

def _detect_pdf_type(path) -> "digital" | "scanned":
    doc = fitz.open(str(path))
    pages = min(3, len(doc))          # sample first 3 pages only
    if pages == 0:
        return "scanned"
    total = sum(
        len(doc[i].get_text().replace(" ", "").replace("\n", ""))
        for i in range(pages)
    )
    return "digital" if (total / pages) > _TEXT_THRESHOLD else "scanned"
```

A PDF with an average of ≤ 100 non-whitespace characters across its first 3 pages is treated as scanned. This threshold works well for documents that are purely image-based but may misclassify very sparse digital PDFs (e.g., a cover page with only a title). Adjust `_TEXT_THRESHOLD` in `router.py` if needed.

### Converter Singletons

Converter instances are created once at module load time:

```python
_PDF_CONVERTER       = PDFConverter()
_PDF_SCAN_CONVERTER  = PDFScanConverter()
_SPREADSHEET_CONVERTER = SpreadsheetConverter()
_DOCX_CONVERTER      = DocxConverter()
```

---

## 5. Converters

### 5.1 Digital PDF — Docling

**File:** `converters/pdf.py`  
**Handles:** `.pdf` files classified as "digital"

```python
def convert(self, path, config) -> str:
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(str(path))
    return result.document.export_to_markdown()
```

**Characteristics:**

- Local processing, no API calls, no cost.
- Docling downloads layout/table models on first run (~500 MB).
- Works on CPU; GPU accelerates inference but does not improve accuracy.
- Docling is imported lazily (inside `convert`) to avoid startup cost when only using other converters.

**Known limitation:** Docling quality can be poor on PDFs with complex multi-column layouts or non-standard fonts. See [§11 Roadmap](#11-known-limitations--roadmap) for alternatives.

---

### 5.2 Scanned PDF — Gemini API

**File:** `converters/pdf_scan.py`  
**Handles:** `.pdf` files classified as "scanned", or any PDF with `--force-scan`

#### System Prompt (sent with every API call)

```
Extract all content from this PDF and convert it to clean Markdown.
Rules:
- Preserve all text exactly as written — do not paraphrase, summarise, or add anything.
- Reproduce every number, amount, date, and code character-for-character.
- Render tables as Markdown pipe tables; keep every column and row.
- Preserve headings (use # / ## / ###), bullet lists, and bold/italic where present.
- Output only the Markdown. No explanations, no comments, no code fences.
```

#### Chunking Strategy

Gemini has per-request token limits. Large PDFs are split into page-range chunks:

```
page_chunk_size = config.gemini.page_chunk_size   # default: 20

if page_chunk_size <= 0 OR total_pages <= page_chunk_size:
    → single API call (whole file)
else:
    → chunks: [0–20), [20–40), [40–60), ...
    → one independent API call per chunk
    → results joined with "\n\n"
```

**Important:** Each chunk is a fully independent API call. Gemini has **no memory** between chunks. Content that spans a chunk boundary (e.g., a table split across pages 20–21) may be rendered inconsistently.

#### File Size Handling

```
chunk size ≤ inline_size_mb (default 15 MB)?
    YES → types.Part.from_bytes(data, mime_type="application/pdf")
    NO  → File Upload API:
           client.files.upload(...)
           poll until state == "ACTIVE"
           types.Part.from_uri(uploaded.uri)
```

#### Retry Logic

```python
for attempt in range(1, max_retries + 2):   # 3 total attempts by default
    try:
        response = client.models.generate_content(...)
        return response.text
    except (TimeoutError, ServerError):
        wait = 2 ** attempt   # 2s, 4s, 8s...
        sleep(wait)
raise RuntimeError("failed after N attempts")
```

#### Timeout Scope

`timeout` (default 120s) applies **per API call**, not per file. A 60-page file with `page_chunk_size=2` results in 3 calls, each with up to 120s. Total worst-case: 3 × 120s = 6 minutes.

#### Configuration Reference

| Key               | Default | Effect                                                            |
| ----------------- | ------- | ----------------------------------------------------------------- |
| `page_chunk_size` | 20      | Pages per API call. Lower = more calls, less risk of timeout.     |
| `timeout`         | 120     | Seconds before `TimeoutError` per call. Increase for slow models. |
| `max_retries`     | 2       | Retry attempts on 5xx/timeout (exponential backoff).              |
| `inline_size_mb`  | 15.0    | Threshold for File Upload API vs inline bytes.                    |
| `thinking_budget` | 0       | 0 = disable Gemini thinking mode (faster/cheaper).                |
| `temperature`     | 0.1     | Lower = more deterministic. Recommended for OCR-like tasks.       |

---

### 5.3 Excel & CSV — Spreadsheet

**File:** `converters/spreadsheet.py`  
**Handles:** `.xlsx`, `.xls`, `.xlsm`, `.csv`, `.tsv`

#### Excel Conversion Flow

```
openpyxl.load_workbook(..., data_only=True)
    │
    ▼
_fill_merged(ws) → rectangular grid
    │
    ▼
_grid_to_df(grid, sc) → pandas DataFrame
    │
    ├─ header_rows=0  → headers: Col0, Col1, Col2...
    ├─ header_rows=1  → first row as headers
    └─ header_rows>1  → combine rows with " › " separator
    │
    ▼
cell formatting:
    bool    → "TRUE" / "FALSE"
    datetime → "YYYY-MM-DD HH:MM:SS" (or "YYYY-MM-DD" if time is 00:00:00)
    float   → "N" if integer, "N.NNN" if decimal, "" if NaN
    other   → str(), strip, collapse newlines to space, escape "|" as "\|"
    overlong → truncate at max_cell_len with "…"
    │
    ▼
df.to_markdown(index=False, tablefmt="pipe")
    │
    ▼
## SheetName\n\n| col | col |...
```

#### Merged Cell Handling

Markdown tables do not support `colspan`/`rowspan`. The current strategy fills every cell in a merged range with the top-left value:

```
Excel merged range (A1:C1 = "Reference"):
┌───────────────┬──────────┐
│  Reference    │  Value   │  ← A1:C1 merged
├────┬────┬─────┼──────────┤
│ D  │ E  │  F  │  G       │
└────┴────┴─────┴──────────┘

After _fill_merged():
┌────┬─────────┬─────────┬──────────┐
│ A  │Reference│Reference│ Value    │
├────┼─────────┼─────────┼──────────┤
│ D  │    E    │    F    │    G     │
└────┴─────────┴─────────┴──────────┘

Markdown output:
| A | Reference | Reference | Value |
|---|-----------|-----------|-------|
| D | E         | F         | G     |
```

Duplicate column names are deduplicated: `Reference`, `Reference_1`, `Reference_2`, ...

#### CSV Detection

| Step      | Method                                                     | Fallback           |
| --------- | ---------------------------------------------------------- | ------------------ |
| Encoding  | Check BOM (UTF-16, UTF-8-sig), then chardet on first 65 KB | UTF-8              |
| Delimiter | `csv.Sniffer` on first 8 KB (tries `,;\t\|`)               | Most frequent char |

#### Fallback Path

If `openpyxl.load_workbook` raises (e.g., corrupt file, password-protected):

```python
except Exception:
    xl = pd.ExcelFile(str(path))   # pandas fallback
    df_raw = xl.parse(name, header=None, dtype=str).fillna("")
```

---

### 5.4 Word Documents — Docx

**File:** `converters/docx.py`  
**Handles:** `.docx`, `.doc`, `.odt`

#### Routing Within Converter

```
.docx  ──► _convert_docx()
              └─ markitdown.MarkItDown().convert(path)

.doc   ──► _convert_legacy()
.odt   ──► _convert_legacy()
              └─ 1. find LibreOffice binary (libreoffice or soffice)
                 2. libreoffice --headless --convert-to docx <file> --outdir <tmp>
                 3. _convert_docx(tmp_docx)
                 4. cleanup temp dir
```

LibreOffice is an **optional system dependency** — required only for `.doc`/`.odt`. If not found, a RuntimeError is raised with installation instructions.

---

## 6. CLI Interface

**File:** `cli.py`  
**Entry point:** `docconv.cli:main`

### Arguments

| Argument            | Type       | Description                                              |
| ------------------- | ---------- | -------------------------------------------------------- |
| `input`             | positional | File or directory to convert                             |
| `-o, --output PATH` | optional   | Output `.md` file or directory. Omit to print to stdout. |
| `--sheets A,B`      | optional   | Excel sheets to include (comma-separated)                |
| `--header-rows N`   | optional   | Number of header rows in Excel (default: 1)              |
| `--force-scan`      | flag       | Force Gemini/OCR path for any PDF                        |
| `--verbose`         | flag       | Print full traceback on errors                           |
| `--init-config`     | flag       | Create `.docconv.yaml` template in CWD                   |
| `--show-config`     | flag       | Print active merged config and exit                      |

### Output Behaviour

| Command                        | Result                            |
| ------------------------------ | --------------------------------- |
| `docconv input.pdf -o out.md`  | Write to `out.md`                 |
| `docconv input.pdf -o output/` | Write to `output/input.md`        |
| `docconv input.pdf > out.md`   | Print to stdout, redirect to file |
| `docconv input/ -o output/`    | Batch convert all supported files |
| `docconv input/` _(no -o)_     | Error: batch mode requires `-o`   |

**Log messages** (`[•]`, `[✓]`, `[ERROR]`) always go to **stderr** and never pollute redirected stdout.

### Batch Mode

When input is a directory, `_convert_dir` processes all files with supported extensions:

```python
_SUPPORTED = {".pdf", ".xlsx", ".xls", ".xlsm", ".csv", ".tsv", ".docx", ".doc", ".odt"}
```

Each file is converted independently; failures do not abort the batch. Final output:

```
Done: 8/10 converted.
```

---

## 7. Post-processing

**File:** `utils/postprocess.py`

`clean_markdown(text: str) -> str` is applied to **every converter's output** before writing:

1. Normalise line endings: `\r\n` → `\n`, `\r` → `\n`
2. Strip trailing whitespace from each line
3. Collapse 3+ consecutive blank lines → 2 blank lines
4. Strip leading/trailing whitespace from the full document
5. Ensure exactly one trailing newline

---

## 8. Data Flow Diagrams

### Digital PDF

```
input.pdf
    │ route() → PDFConverter
    ▼
Docling.DocumentConverter.convert(path)
    │ export_to_markdown()
    ▼
raw markdown string
    │ clean_markdown()
    ▼
normalised markdown
    │ stdout or file.write()
    ▼
output.md
```

### Scanned PDF (chunked, 53 pages, chunk_size=20)

```
input.pdf  (53 pages)
    │ route() → PDFScanConverter
    ▼
_convert_with_gemini()
    │ chunk_size=20 → 3 chunks
    ├─── chunk 1: pages 1–20
    │       │ _extract_pages(0,20) → bytes (0.37 MB < 15 MB inline)
    │       │ types.Part.from_bytes(...)
    │       │ _call_with_retry() → Gemini API
    │       └──────────────────────────── markdown_1
    │
    ├─── chunk 2: pages 21–40 → markdown_2
    └─── chunk 3: pages 41–53 → markdown_3
    │
    │ "\n\n".join([md1, md2, md3])
    ▼
combined markdown
    │ clean_markdown()
    ▼
output.md
```

### Excel (with merged cells)

```
data.xlsx
    │ route() → SpreadsheetConverter
    ▼
openpyxl.load_workbook(data_only=True)
    │ for each sheet:
    ▼
_fill_merged(ws) → rectangular grid (merged values propagated)
    │
    ▼
_grid_to_df(grid, sc)
    │ header_rows=1 → row[0] = headers
    │ format cells (bool, date, float, truncate)
    │ deduplicate column names
    ▼
pandas.DataFrame
    │ df.to_markdown(tablefmt="pipe")
    ▼
## SheetName\n\n| col | col |...\n
    │ clean_markdown()
    ▼
output.md
```

---

## 9. Error Handling Strategy

### Propagation Model

```
Converter raises Exception
    │
    ▼
cli._convert_file() catches:
    ├─ UnsupportedFormatError → stderr + return False
    └─ Exception             → stderr (+ traceback if --verbose) + return False
    │
    ▼
_convert_dir() sums booleans → "Done: N/M converted"
```

### Per-Converter Error Matrix

| Converter            | Error                   | Handling                               |
| -------------------- | ----------------------- | -------------------------------------- |
| PDFConverter         | Docling crash           | Caught generically; logged             |
| PDFScanConverter     | Missing API key         | RuntimeError with setup instructions   |
| PDFScanConverter     | 504/ServerError         | Retry with exponential backoff (2^n s) |
| PDFScanConverter     | File upload fails       | RuntimeError (state != ACTIVE)         |
| SpreadsheetConverter | openpyxl fails          | Fallback to pandas ExcelFile           |
| SpreadsheetConverter | CSV delimiter ambiguous | Count occurrences, pick most frequent  |
| DocxConverter        | LibreOffice missing     | RuntimeError with install instructions |
| DocxConverter        | LibreOffice fails       | RuntimeError if temp .docx not found   |

---

## 10. Extending the System

### Add a New File Format

1. Create `docconv/converters/myformat.py`:

```python
from docconv.converters.base import BaseConverter
from docconv.config import Config
from pathlib import Path

class MyConverter(BaseConverter):
    EXTENSIONS = {".xyz"}

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.EXTENSIONS

    def convert(self, path: Path, config: Config) -> str:
        # ... return markdown string
        return "# output"
```

2. Register in `router.py`:

```python
from docconv.converters.myformat import MyConverter
_MY_CONVERTER = MyConverter()
_NON_PDF_CONVERTERS = [_SPREADSHEET_CONVERTER, _DOCX_CONVERTER, _MY_CONVERTER]
```

3. Add extension to `_SUPPORTED` in `cli.py`.

### Add a New Config Option

1. Add field to the appropriate dataclass in `config.py`.
2. Add parsing in `_build()`.
3. Update the `SAMPLE_CONFIG` string.
4. Access via `config.field_name` inside converters.

### Change the PDF Detection Threshold

Edit `_TEXT_THRESHOLD` in `router.py` (currently `100` chars/page average).

---

## 11. Known Limitations & Roadmap

### PDF Conversion Quality (Docling)

**Current issue:** Docling can produce poor output on PDFs with complex multi-column layouts, non-standard fonts, or borderless tables.

**Researched alternatives:**

| Tool              | Accuracy\* | GPU needed  | License        | Recommendation                                                     |
| ----------------- | ---------- | ----------- | -------------- | ------------------------------------------------------------------ |
| **pymupdf4llm**   | 0.905      | No          | AGPL-3.0       | Best drop-in. `fitz` already installed. 2-line change in `pdf.py`. |
| **MinerU**        | 0.831+     | Recommended | Apache 2.0     | Best for CJK/academic PDFs. Heavy install.                         |
| **marker-pdf**    | 0.861      | Recommended | GPL-3 + Rail-M | High quality but licensing concerns for commercial use.            |
| Docling (current) | 0.877      | No          | MIT            | Baseline                                                           |

\*Benchmark: opendataloader-bench / pdfmux 200-PDF test (2025–2026)

**Recommended migration:** Replace Docling with `pymupdf4llm` as default; add MinerU as `--high-quality` flag backend.

```python
# converters/pdf.py — proposed change
import pymupdf4llm

def convert(self, path, config) -> str:
    return pymupdf4llm.to_markdown(str(path))
```

### Excel Files with Embedded Images

openpyxl reads cell values but silently skips images. Images embedded in `.xlsx` files fall into two categories:

| Type                             | Storage in .xlsx        | Extraction method                                    |
| -------------------------------- | ----------------------- | ---------------------------------------------------- |
| Floating images (Insert → Image) | `xl/media/*.png` in ZIP | `ws._images` or direct ZIP extraction                |
| Cell-anchored images             | Same ZIP path           | `openpyxl-image-loader` library                      |
| Charts (bar, pie, etc.)          | `xl/charts/*.xml`       | Cannot extract as image; requires LibreOffice render |

**Recommended approach:**

1. Extract `xl/media/` images via stdlib `zipfile`.
2. For charts: `libreoffice --headless --convert-to pdf`, then extract page images via PyMuPDF.
3. Send image bytes to Gemini vision API and insert description as Markdown block.

### .ods File Support

`.ods` (LibreOffice Calc) is not currently supported. `openpyxl` cannot read `.ods`.

**Fix (minimal change to `spreadsheet.py`):**

```python
# Add to dependencies: odfpy
# pip install odfpy

EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".csv", ".tsv", ".ods"}  # +.ods

def convert(self, path, config):
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm", ".ods"):
        return self._convert_excel(path, config.spreadsheet)
    return self._convert_csv(path, config.spreadsheet)

def _convert_excel(self, path, sc):
    if path.suffix.lower() == ".ods":
        xl = pd.ExcelFile(str(path), engine="odf")   # requires odfpy
        # rest of logic unchanged ...
```

Also add `.ods` to `_SUPPORTED` in `cli.py`.

### Chunk Boundary Artifacts (Scanned PDF)

Because each chunk is an independent Gemini call with no shared context, content spanning a chunk boundary may be rendered inconsistently (repeated headings, broken tables, reset numbering). Mitigation options:

- Reduce `page_chunk_size` (fewer pages per call = less chance of meaningful content at boundaries).
- Add a 1–2 page overlap between chunks and deduplicate during merge (not yet implemented).

---

## Dependencies Reference

| Package          | Version | Purpose                                     |
| ---------------- | ------- | ------------------------------------------- |
| docling          | latest  | Digital PDF extraction                      |
| markitdown[docx] | latest  | DOCX to Markdown                            |
| google-genai     | ≥ 1.0   | Gemini API client                           |
| openpyxl         | ≥ 3.0   | Excel read/write, merged cell access        |
| xlrd             | ≥ 2.0   | Legacy `.xls` fallback                      |
| pandas           | ≥ 1.5   | DataFrame operations, Markdown table render |
| PyMuPDF (fitz)   | ≥ 1.23  | PDF type detection, page slicing            |
| chardet          | ≥ 4.0   | CSV encoding detection                      |
| pyyaml           | ≥ 6.0   | YAML config parsing                         |
| tabulate         | ≥ 0.9   | Used by pandas `to_markdown()`              |
| LibreOffice      | system  | `.doc`/`.odt` conversion (optional)         |
