# tests/test_converter_pdf.py
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from docconv.converters.pdf import PDFConverter, _detect_pdf_type
from docconv.config import load_config


@pytest.fixture
def converter():
    return PDFConverter()


@pytest.fixture
def config():
    return load_config()


def test_can_handle_pdf(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.pdf") is True


def test_cannot_handle_docx(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.docx") is False


def test_detect_digital_pdf(digital_pdf):
    assert _detect_pdf_type(digital_pdf) == "digital"


def test_detect_scanned_pdf_empty_page(tmp_path):
    """A PDF page with no text layer is classified as scanned."""
    from fpdf import FPDF
    path = tmp_path / "blank.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.output(str(path))
    assert _detect_pdf_type(path) == "scanned"


def test_digital_pdf_uses_docling(digital_pdf, converter, config):
    # Mock the docling module and its DocumentConverter
    mock_dc_class = MagicMock()
    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = "# Digital Content\n\nParagraph."
    mock_dc_class.return_value.convert.return_value = mock_result

    # Create mock modules
    mock_docling = MagicMock()
    mock_document_converter = MagicMock()
    mock_document_converter.DocumentConverter = mock_dc_class
    mock_docling.document_converter = mock_document_converter

    with patch.dict(sys.modules, {"docling": mock_docling, "docling.document_converter": mock_document_converter}):
        result = converter.convert(digital_pdf, config)
    assert "Digital Content" in result
    mock_dc_class.return_value.convert.assert_called_once()


def test_convert_does_not_write_files(digital_pdf, converter, config, tmp_path):
    before = set(tmp_path.iterdir())

    # Mock the docling module and its DocumentConverter
    mock_dc_class = MagicMock()
    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = "# Test"
    mock_dc_class.return_value.convert.return_value = mock_result

    # Create mock modules
    mock_docling = MagicMock()
    mock_document_converter = MagicMock()
    mock_document_converter.DocumentConverter = mock_dc_class
    mock_docling.document_converter = mock_document_converter

    with patch.dict(sys.modules, {"docling": mock_docling, "docling.document_converter": mock_document_converter}):
        converter.convert(digital_pdf, config)

    after = set(tmp_path.iterdir())
    assert before == after
