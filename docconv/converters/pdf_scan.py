# docconv/converters/pdf_scan.py
from __future__ import annotations

import base64
from pathlib import Path

from docconv.config import Config
from docconv.converters.base import BaseConverter


class PDFScanConverter(BaseConverter):
    """Converts scanned PDFs (image-only) using Google Gemini API."""

    PROMPT = (
        "Extract all text from this scanned PDF and format it as clean Markdown. "
        "Preserve headings, tables, and lists. Return only the Markdown, no commentary."
    )

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def convert(self, path: Path, config: Config) -> str:
        if not config.has_gemini():
            raise RuntimeError(
                "Gemini API key is required for scanned PDFs.\n"
                "Run `docconv --init-config` and add your API key to ~/.docconv.yaml"
            )
        return self._convert_with_gemini(path, config)

    def _convert_with_gemini(self, path: Path, config: Config) -> str:
        import google.generativeai as genai

        genai.configure(api_key=config.gemini.api_key)
        model = genai.GenerativeModel(config.gemini.model)

        pdf_bytes = path.read_bytes()
        pdf_part = {
            "inline_data": {
                "mime_type": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode("utf-8"),
            }
        }
        response = model.generate_content([self.PROMPT, pdf_part])
        return response.text
