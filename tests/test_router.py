# tests/test_router.py
import pytest
from pathlib import Path
from unittest.mock import patch
from docconv.router import route
from docconv.converters.base import BaseConverter, UnsupportedFormatError


def test_route_digital_pdf_returns_pdf_converter(tmp_path):
    f = tmp_path / "doc.pdf"
    f.touch()
    with patch("docconv.router._detect_pdf_type", return_value="digital"):
        converter = route(f)
    assert converter.__class__.__name__ == "PDFConverter"


def test_route_scanned_pdf_returns_pdf_scan_converter(tmp_path):
    f = tmp_path / "scan.pdf"
    f.touch()
    with patch("docconv.router._detect_pdf_type", return_value="scanned"):
        converter = route(f)
    assert converter.__class__.__name__ == "PDFScanConverter"


def test_route_xlsx_returns_spreadsheet_converter(tmp_path):
    f = tmp_path / "data.xlsx"
    f.touch()
    converter = route(f)
    assert converter.__class__.__name__ == "SpreadsheetConverter"


def test_route_csv_returns_spreadsheet_converter(tmp_path):
    f = tmp_path / "data.csv"
    f.touch()
    converter = route(f)
    assert converter.__class__.__name__ == "SpreadsheetConverter"


def test_route_docx_returns_docx_converter(tmp_path):
    f = tmp_path / "letter.docx"
    f.touch()
    converter = route(f)
    assert converter.__class__.__name__ == "DocxConverter"


def test_route_doc_returns_docx_converter(tmp_path):
    f = tmp_path / "letter.doc"
    f.touch()
    converter = route(f)
    assert converter.__class__.__name__ == "DocxConverter"


def test_route_odt_returns_docx_converter(tmp_path):
    f = tmp_path / "letter.odt"
    f.touch()
    converter = route(f)
    assert converter.__class__.__name__ == "DocxConverter"


def test_route_unsupported_raises(tmp_path):
    f = tmp_path / "image.png"
    f.touch()
    with pytest.raises(UnsupportedFormatError) as exc_info:
        route(f)
    assert ".png" in str(exc_info.value)


def test_route_case_insensitive(tmp_path):
    f = tmp_path / "DOC.PDF"
    f.touch()
    with patch("docconv.router._detect_pdf_type", return_value="digital"):
        converter = route(f)
    assert converter.__class__.__name__ == "PDFConverter"
