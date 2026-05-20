# docconv/converters/pdf_scan.py
from pathlib import Path
from docconv.config import Config
from docconv.converters.base import BaseConverter


class PDFScanConverter(BaseConverter):
    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def convert(self, path: Path, config: Config) -> str:
        raise NotImplementedError
