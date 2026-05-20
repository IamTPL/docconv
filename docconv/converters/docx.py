# docconv/converters/docx.py
from pathlib import Path
from docconv.config import Config
from docconv.converters.base import BaseConverter

class DocxConverter(BaseConverter):
    EXTENSIONS = {".docx", ".doc", ".odt"}

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.EXTENSIONS

    def convert(self, path: Path, config: Config) -> str:
        raise NotImplementedError
