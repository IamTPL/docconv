# docconv/router.py
from __future__ import annotations

from pathlib import Path

from docconv.converters.base import BaseConverter, UnsupportedFormatError
from docconv.converters.docx import DocxConverter
from docconv.converters.pdf import PDFConverter, _detect_pdf_type
from docconv.converters.pdf_scan import PDFScanConverter
from docconv.converters.spreadsheet import SpreadsheetConverter

_PDF_CONVERTER = PDFConverter()
_PDF_SCAN_CONVERTER = PDFScanConverter()
_SPREADSHEET_CONVERTER = SpreadsheetConverter()
_DOCX_CONVERTER = DocxConverter()

_NON_PDF_CONVERTERS: list[BaseConverter] = [
    _SPREADSHEET_CONVERTER,
    _DOCX_CONVERTER,
]


def route(path: Path, force_scan: bool = False) -> BaseConverter:
    """Return the appropriate converter for the given file path."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        if force_scan:
            return _PDF_SCAN_CONVERTER
        pdf_type = _detect_pdf_type(path)
        return _PDF_CONVERTER if pdf_type == "digital" else _PDF_SCAN_CONVERTER

    for converter in _NON_PDF_CONVERTERS:
        if converter.can_handle(path):
            return converter

    raise UnsupportedFormatError(
        f"Unsupported format: '{suffix}'. "
        f"Supported: .pdf, .xlsx, .xls, .xlsm, .csv, .tsv, .docx, .doc, .odt"
    )
