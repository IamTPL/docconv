# docconv

Convert any document to Markdown using the best engine for each file type.

## Supported formats

| Format | Engine |
|---|---|
| `.pdf` (digital — text layer) | Docling |
| `.pdf` (scanned — image-only) | Google Gemini API (`gemini-3-flash-preview`) |
| `.xlsx`, `.xls`, `.xlsm`, `.csv`, `.tsv` | pandas + openpyxl |
| `.docx` | MarkItDown |
| `.doc`, `.odt` | LibreOffice → MarkItDown |

## Installation

```bash
# Clone and install
git clone <repo>
cd docconv
python -m venv .venv && source .venv/bin/activate
pip install -e .

# For scanned PDF support (Google Gemini API):
pip install -e ".[cloud]"

# For .doc/.odt support:
sudo apt install libreoffice
```

## Usage

```bash
# Convert a single file
docconv invoice.pdf
docconv report.xlsx -o output/
docconv letter.docx -o result.md

# Batch convert a directory
docconv docs/ -o output/

# Excel options
docconv data.xlsx --sheets "Sheet1,Revenue"
docconv data.xlsx --header-rows 2

# Configuration
docconv --init-config   # create ~/.docconv.yaml
docconv --show-config   # print active configuration
```

## Configuration

Run `docconv --init-config` to create `~/.docconv.yaml`, then add your Gemini API key for scanned PDF support:

```yaml
quality: auto

apis:
  gemini:
    api_key: "your-gemini-api-key"
    model: "gemini-3-flash-preview"
```

## Architecture

```
docconv/
├── cli.py           # argparse entry point
├── router.py        # detect file type → dispatch converter
├── config.py        # YAML config + CLI flag merging
├── converters/
│   ├── base.py      # BaseConverter interface
│   ├── pdf.py       # Digital PDF → Docling
│   ├── pdf_scan.py  # Scanned PDF → Google Gemini API
│   ├── spreadsheet.py
│   └── docx.py      # DOCX/DOC/ODT → MarkItDown
└── utils/
    └── postprocess.py
```

Converters are pure functions: `convert(path, config) → str`. Adding a web UI or REST API requires only a new thin wrapper — no changes to converter code.
