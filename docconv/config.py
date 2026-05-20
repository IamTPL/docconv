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
  google_document_ai:
    project_id: ""
    location: "us"
    processor_id: ""
  aws_textract:
    region: "us-east-1"

spreadsheet:
  max_cell_len: 120
  skip_empty_sheets: true
  header_rows: 1

output:
  dir: ""  # empty = same directory as input
"""


@dataclass
class GoogleDocAIConfig:
    project_id: str = ""
    location: str = "us"
    processor_id: str = ""


@dataclass
class AWSTextractConfig:
    region: str = ""


@dataclass
class SpreadsheetConfig:
    max_cell_len: int = 120
    skip_empty_sheets: bool = True
    header_rows: int = 1
    sheets: Optional[list[str]] = None


@dataclass
class Config:
    quality: str = "auto"
    google_document_ai: GoogleDocAIConfig = field(default_factory=GoogleDocAIConfig)
    aws_textract: AWSTextractConfig = field(default_factory=AWSTextractConfig)
    spreadsheet: SpreadsheetConfig = field(default_factory=SpreadsheetConfig)
    output_dir: Optional[Path] = None
    verbose: bool = False

    def has_google_docai(self) -> bool:
        return bool(
            self.google_document_ai.project_id
            and self.google_document_ai.processor_id
        )

    def has_aws_textract(self) -> bool:
        return bool(self.aws_textract.region)


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
    if gdai := apis.get("google_document_ai", {}):
        config.google_document_ai = GoogleDocAIConfig(
            project_id=str(gdai.get("project_id", "")),
            location=str(gdai.get("location", "us")),
            processor_id=str(gdai.get("processor_id", "")),
        )
    if textract := apis.get("aws_textract", {}):
        config.aws_textract = AWSTextractConfig(
            region=str(textract.get("region", "us-east-1")),
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
    print(f"google_docai     : {'configured' if config.has_google_docai() else 'not configured'}")
    print(f"aws_textract     : {'configured' if config.has_aws_textract() else 'not configured'}")
    print(f"max_cell_len     : {config.spreadsheet.max_cell_len}")
    print(f"header_rows      : {config.spreadsheet.header_rows}")
    print(f"skip_empty_sheets: {config.spreadsheet.skip_empty_sheets}")
    print(f"output_dir       : {config.output_dir or '(same as input)'}")
