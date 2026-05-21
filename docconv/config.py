# docconv/config.py
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# Note: GLOBAL_CONFIG_PATH is resolved at import time using Path.home().
# It reflects the home directory at module import, not dynamically.
# Use load_config() and init_config() which read os.environ.get("HOME") at call time.
GLOBAL_CONFIG_PATH = Path.home() / ".docconv.yaml"
LOCAL_CONFIG_PATH = Path(".docconv.yaml")

SAMPLE_CONFIG = """\
# DocConvert CLI Configuration
# https://github.com/yourname/docconv

quality: auto  # fast | precise | auto

apis:
  gemini:
    api_key: ""
    model: "gemini-3-flash-preview"
    temperature: 0.1        # lower = more deterministic (recommended for OCR)
    thinking_budget: 0      # 0 = disable thinking mode (faster, cheaper)
    timeout: 240            # seconds before giving up on a single API request
    max_retries: 2          # retries on timeout or 5xx server error (with backoff)
    page_chunk_size: 2      # pages per API call for large PDFs (0 = send whole file at once)
    inline_size_mb: 15.0    # files larger than this use File Upload API instead of inline bytes

spreadsheet:
  max_cell_len: 120
  skip_empty_sheets: true
  header_rows: 1

output:
  dir: ""  # empty = same directory as input
"""


@dataclass
class GeminiConfig:
    api_key: str = ""
    model: str = "gemini-3-flash-preview"
    temperature: float = 0.1
    thinking_budget: int = 0
    timeout: int = 120       # seconds before giving up on a single request
    max_retries: int = 2     # number of retries after a timeout or server error
    page_chunk_size: int = 20  # pages per chunk for large PDFs (0 = no chunking)
    inline_size_mb: float = 15.0  # files above this are uploaded via File API, not inline


@dataclass
class SpreadsheetConfig:
    max_cell_len: int = 120
    skip_empty_sheets: bool = True
    header_rows: int = 1
    sheets: Optional[list[str]] = None


@dataclass
class Config:
    quality: str = "auto"
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    spreadsheet: SpreadsheetConfig = field(default_factory=SpreadsheetConfig)
    output_dir: Optional[Path] = None
    verbose: bool = False

    def has_gemini(self) -> bool:
        return bool(self.gemini.api_key)


def _merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


def _build(data: dict) -> Config:
    config = Config()
    if "quality" in data:
        config.quality = str(data["quality"])
    if "verbose" in data:
        config.verbose = bool(data["verbose"])

    apis = data.get("apis", {})
    if gemini := (apis.get("gemini") or {}):
        config.gemini = GeminiConfig(
            api_key=str(gemini.get("api_key", "")),
            model=str(gemini.get("model", "gemini-3-flash-preview")),
            temperature=float(gemini.get("temperature", 0.1)),
            thinking_budget=int(gemini.get("thinking_budget", 0)),
            timeout=int(gemini.get("timeout", 120)),
            max_retries=int(gemini.get("max_retries", 2)),
            page_chunk_size=int(gemini.get("page_chunk_size", 20)),
            inline_size_mb=float(gemini.get("inline_size_mb", 15.0)),
        )

    if ss := data.get("spreadsheet", {}):
        config.spreadsheet = SpreadsheetConfig(
            max_cell_len=int(ss.get("max_cell_len", 120)),
            skip_empty_sheets=bool(ss.get("skip_empty_sheets", True)),
            header_rows=int(ss.get("header_rows", 1)),
            sheets=ss.get("sheets"),
        )

    if out := data.get("output", {}):
        if dir_val := out.get("dir", ""):
            config.output_dir = Path(dir_val)

    return config


def load_config(cli_overrides: Optional[dict] = None) -> Config:
    """Merge: CLI flags > local .docconv.yaml > ~/.docconv.yaml > defaults."""
    data: dict = {}

    global_path = Path(os.environ.get("HOME", Path.home())) / ".docconv.yaml"
    if global_path.exists():
        with open(global_path) as f:
            data = _merge(data, yaml.safe_load(f) or {})

    if LOCAL_CONFIG_PATH.exists():
        with open(LOCAL_CONFIG_PATH) as f:
            data = _merge(data, yaml.safe_load(f) or {})

    if cli_overrides:
        data = _merge(data, cli_overrides)

    return _build(data)


def _ensure_gitignored(entry: str) -> None:
    """Append `entry` to ./.gitignore if missing. No-op outside a git project."""
    if not Path(".git").exists():
        return
    gitignore = Path(".gitignore")
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if entry in lines:
        return
    with gitignore.open("a", encoding="utf-8") as f:
        if lines and lines[-1] != "":
            f.write("\n")
        f.write(entry + "\n")
    print(f"[✓] Added '{entry}' to .gitignore")


def init_config() -> None:
    """Create .docconv.yaml in the current project directory."""
    local_path = LOCAL_CONFIG_PATH.resolve()
    if local_path.exists():
        print(f"Config already exists at {local_path}")
        return
    local_path.write_text(SAMPLE_CONFIG)
    print(f"[✓] Config created at {local_path}")
    _ensure_gitignored(".docconv.yaml")


def show_config() -> None:
    config = load_config()
    print(f"quality          : {config.quality}")
    print(f"gemini           : {'configured' if config.has_gemini() else 'not configured'}")
    print(f"gemini_model     : {config.gemini.model}")
    print(f"gemini_temperature: {config.gemini.temperature}")
    print(f"thinking_budget  : {config.gemini.thinking_budget}")
    print(f"timeout          : {config.gemini.timeout}s")
    print(f"max_retries      : {config.gemini.max_retries}")
    print(f"max_cell_len     : {config.spreadsheet.max_cell_len}")
    print(f"header_rows      : {config.spreadsheet.header_rows}")
    print(f"skip_empty_sheets: {config.spreadsheet.skip_empty_sheets}")
    print(f"output_dir       : {config.output_dir or '(same as input)'}")
