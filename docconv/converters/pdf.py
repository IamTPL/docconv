# docconv/converters/pdf.py
from __future__ import annotations
import warnings
from pathlib import Path
import fitz  # PyMuPDF
from docconv.config import Config
from docconv.converters.base import BaseConverter

warnings.filterwarnings("ignore")

_TEXT_THRESHOLD = 100  # avg chars/page below this → scanned


def _detect_pdf_type(path: Path) -> str:
    """Return 'digital' or 'scanned' based on extractable text in first 3 pages."""
    doc = fitz.open(str(path))
    pages = min(3, len(doc))
    if pages == 0:
        return "scanned"
    total = sum(
        len(doc[i].get_text().replace(" ", "").replace("\n", ""))
        for i in range(pages)
    )
    return "digital" if (total / pages) > _TEXT_THRESHOLD else "scanned"


class PDFConverter(BaseConverter):
    """Converts digital PDFs (text layer present) using Docling."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def convert(self, path: Path, config: Config) -> str:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(str(path))
        return result.document.export_to_markdown()
