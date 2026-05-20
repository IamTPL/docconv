# tests/test_config.py
import pytest
from pathlib import Path
from docconv.config import load_config, Config, SpreadsheetConfig


def test_load_config_returns_defaults_when_no_files(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.quality == "auto"
    assert config.spreadsheet.max_cell_len == 120
    assert config.spreadsheet.header_rows == 1
    assert config.verbose is False


def test_load_config_cli_overrides_quality(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    config = load_config({"quality": "fast"})
    assert config.quality == "fast"


def test_load_config_reads_global_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".docconv.yaml").write_text("quality: precise\n")
    config = load_config()
    assert config.quality == "precise"


def test_load_config_local_overrides_global(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".docconv.yaml").write_text("quality: precise\n")
    local = tmp_path / "project"
    local.mkdir()
    (local / ".docconv.yaml").write_text("quality: fast\n")
    monkeypatch.chdir(local)
    config = load_config()
    assert config.quality == "fast"


def test_load_config_cli_overrides_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".docconv.yaml").write_text("quality: precise\n")
    config = load_config({"quality": "fast"})
    assert config.quality == "fast"


def test_has_gemini_false_when_empty():
    config = load_config()
    assert config.has_gemini() is False


def test_has_gemini_true_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    yaml_content = """
apis:
  gemini:
    api_key: "my-api-key"
    model: "gemini-3-flash-preview"
"""
    (tmp_path / ".docconv.yaml").write_text(yaml_content)
    config = load_config()
    assert config.has_gemini() is True


def test_init_config_creates_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from docconv.config import init_config, GLOBAL_CONFIG_PATH
    init_config()
    assert (tmp_path / ".docconv.yaml").exists()


def test_init_config_does_not_overwrite_existing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".docconv.yaml").write_text("quality: fast\n")
    from docconv.config import init_config
    init_config()
    assert (tmp_path / ".docconv.yaml").read_text() == "quality: fast\n"
