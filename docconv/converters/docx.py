# docconv/converters/docx.py
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from docconv.config import Config
from docconv.converters.base import BaseConverter


class DocxConverter(BaseConverter):
    EXTENSIONS = {".docx", ".doc", ".odt"}

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.EXTENSIONS

    def convert(self, path: Path, config: Config) -> str:
        if path.suffix.lower() in (".doc", ".odt"):
            return self._convert_legacy(path, config)
        return self._convert_docx(path)

    def _convert_docx(self, path: Path) -> str:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(str(path))
        return result.text_content

    def _convert_legacy(self, path: Path, config: Config) -> str:
        lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
        if not lo_bin:
            raise RuntimeError(
                "LibreOffice is required to convert .doc/.odt files.\n"
                "Install with: sudo apt install libreoffice"
            )
        tmp_dir = Path(tempfile.mkdtemp(prefix="docconv_"))
        try:
            subprocess.run(
                [lo_bin, "--headless", "--convert-to", "docx",
                 str(path), "--outdir", str(tmp_dir)],
                capture_output=True,
                check=True,
            )
            tmp_docx = tmp_dir / (path.stem + ".docx")
            if not tmp_docx.exists():
                raise RuntimeError(
                    f"LibreOffice conversion failed: output not found at {tmp_docx}"
                )
            return self._convert_docx(tmp_docx)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
