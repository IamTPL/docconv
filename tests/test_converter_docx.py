# tests/test_converter_docx.py
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from docconv.converters.docx import DocxConverter
from docconv.config import load_config


@pytest.fixture
def converter():
    return DocxConverter()


@pytest.fixture
def config():
    return load_config()


def test_can_handle_docx(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.docx") is True


def test_can_handle_doc(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.doc") is True


def test_can_handle_odt(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.odt") is True


def test_cannot_handle_pdf(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.pdf") is False


def test_docx_returns_markdown_string(simple_docx, converter, config):
    result = converter.convert(simple_docx, config)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Hello World" in result
    assert "test document" in result


def test_docx_does_not_write_files(simple_docx, converter, config, tmp_path):
    before = set(tmp_path.iterdir())
    converter.convert(simple_docx, config)
    after = set(tmp_path.iterdir())
    assert before == after


def test_doc_raises_runtime_error_when_libreoffice_missing(tmp_path, converter, config):
    f = tmp_path / "old.doc"
    f.write_bytes(b"\xd0\xcf\x11\xe0")  # OLE2 magic bytes
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="LibreOffice"):
            converter.convert(f, config)


def test_doc_converts_via_libreoffice(tmp_path, converter, config):
    f = tmp_path / "old.doc"
    f.write_bytes(b"\xd0\xcf\x11\xe0")

    def fake_run(cmd, **kwargs):
        outdir = Path(cmd[cmd.index("--outdir") + 1])
        out = outdir / "old.docx"
        from docx import Document
        doc = Document()
        doc.add_paragraph("Converted content")
        doc.save(str(out))
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("shutil.which", return_value="/usr/bin/libreoffice"):
        with patch("subprocess.run", side_effect=fake_run):
            result = converter.convert(f, config)
    assert "Converted content" in result
