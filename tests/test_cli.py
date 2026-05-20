# tests/test_cli.py
import pytest
import subprocess
import sys
from pathlib import Path


def run_cli(*args, env=None):
    """Helper to invoke docconv CLI via subprocess."""
    result = subprocess.run(
        [sys.executable, "-m", "docconv.cli", *args],
        capture_output=True, text=True, env=env
    )
    return result


def test_cli_no_args_exits_nonzero():
    result = run_cli()
    assert result.returncode != 0


def test_cli_nonexistent_file_exits_nonzero(tmp_path):
    result = run_cli(str(tmp_path / "ghost.pdf"))
    assert result.returncode != 0
    assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


def test_cli_unsupported_format_exits_nonzero(tmp_path):
    f = tmp_path / "image.png"
    f.touch()
    result = run_cli(str(f))
    assert result.returncode != 0


def test_cli_converts_csv_to_md(csv_comma, tmp_path):
    out = tmp_path / "result.md"
    result = run_cli(str(csv_comma), "-o", str(out))
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert "Alice" in out.read_text()


def test_cli_converts_docx_to_md(simple_docx, tmp_path):
    out = tmp_path / "letter.md"
    result = run_cli(str(simple_docx), "-o", str(out))
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert "Hello World" in out.read_text()


def test_cli_requires_output_flag(csv_comma):
    result = run_cli(str(csv_comma))
    assert result.returncode != 0
    assert "output" in result.stderr.lower()


def test_cli_batch_dir(tmp_path):
    (tmp_path / "a.csv").write_text("X,Y\n1,2\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("A,B\n3,4\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    result = run_cli(str(tmp_path), "-o", str(out_dir))
    assert result.returncode == 0, result.stderr
    assert (out_dir / "a.md").exists()
    assert (out_dir / "b.md").exists()


def test_cli_init_config_creates_yaml_in_cwd(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "docconv.cli", "--init-config"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".docconv.yaml").exists()


def test_cli_init_config_adds_gitignore_entry(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("__pycache__/\n")
    result = subprocess.run(
        [sys.executable, "-m", "docconv.cli", "--init-config"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert ".docconv.yaml" in (tmp_path / ".gitignore").read_text()


def test_cli_verbose_flag_accepted(csv_comma, tmp_path):
    out = tmp_path / "result.md"
    result = run_cli(str(csv_comma), "-o", str(out), "--verbose")
    assert result.returncode == 0, result.stderr
