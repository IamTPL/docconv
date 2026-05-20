# tests/test_converter_pdf_scan.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from docconv.converters.pdf_scan import PDFScanConverter
from docconv.config import load_config


@pytest.fixture
def converter():
    return PDFScanConverter()


def test_can_handle_pdf(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.pdf") is True


def test_cannot_handle_docx(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.docx") is False


def test_raises_when_no_api_key(scanned_pdf, converter):
    config = load_config()
    assert not config.has_gemini()
    with pytest.raises(RuntimeError, match="Gemini API key"):
        converter.convert(scanned_pdf, config)


def test_calls_gemini_api(scanned_pdf, converter):
    config = load_config()
    config.gemini.api_key = "fake-key"

    mock_response = MagicMock()
    mock_response.text = "# Extracted from scan\n\nSome text."

    with patch("google.generativeai.GenerativeModel") as MockModel:
        MockModel.return_value.generate_content.return_value = mock_response
        result = converter.convert(scanned_pdf, config)

    assert "Extracted from scan" in result
    MockModel.return_value.generate_content.assert_called_once()


def test_does_not_write_files(scanned_pdf, converter, tmp_path):
    config = load_config()
    config.gemini.api_key = "fake-key"
    before = set(tmp_path.iterdir())

    mock_response = MagicMock()
    mock_response.text = "# Test"

    with patch("google.generativeai.GenerativeModel") as MockModel:
        MockModel.return_value.generate_content.return_value = mock_response
        converter.convert(scanned_pdf, config)

    after = set(tmp_path.iterdir())
    assert before == after


def test_passes_model_name_from_config(scanned_pdf, converter):
    config = load_config()
    config.gemini.api_key = "fake-key"
    config.gemini.model = "gemini-3-flash-preview"

    mock_response = MagicMock()
    mock_response.text = "# Result"

    with patch("google.generativeai.GenerativeModel") as MockModel:
        MockModel.return_value.generate_content.return_value = mock_response
        converter.convert(scanned_pdf, config)

    MockModel.assert_called_once_with("gemini-3-flash-preview")
