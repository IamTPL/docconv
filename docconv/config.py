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


def init_config() -> None:
    global_path = Path(os.environ.get("HOME", Path.home())) / ".docconv.yaml"
    if global_path.exists():
        print(f"Config already exists at {global_path}")
        return
    global_path.write_text(SAMPLE_CONFIG)
    print(f"[✓] Config created at {global_path}")


def show_config() -> None:
    config = load_config()
    print(f"quality          : {config.quality}")
    print(f"gemini           : {'configured' if config.has_gemini() else 'not configured'}")
    print(f"gemini_model     : {config.gemini.model}")
    print(f"max_cell_len     : {config.spreadsheet.max_cell_len}")
    print(f"header_rows      : {config.spreadsheet.header_rows}")
    print(f"skip_empty_sheets: {config.spreadsheet.skip_empty_sheets}")
    print(f"output_dir       : {config.output_dir or '(same as input)'}")
