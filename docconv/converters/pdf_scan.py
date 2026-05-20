# docconv/converters/pdf_scan.py
from __future__ import annotations

import io
import time
from pathlib import Path

from docconv.config import Config
from docconv.converters.base import BaseConverter

_MB = 1024 * 1024


class PDFScanConverter(BaseConverter):
    """Converts scanned PDFs (image-only) using Google Gemini API.

    Large PDFs are automatically split into page chunks so that each API call
    stays within Gemini's token and request-size limits. Files above
    config.gemini.inline_size_mb are uploaded via the File Upload API instead
    of being sent as inline bytes.
    """

    PROMPT = (
        "Extract all content from this PDF and convert it to clean Markdown.\n"
        "Rules:\n"
        "- Preserve all text exactly as written — do not paraphrase, summarise, or add anything.\n"
        "- Reproduce every number, amount, date, and code character-for-character.\n"
        "- Render tables as Markdown pipe tables; keep every column and row.\n"
        "- Preserve headings (use # / ## / ###), bullet lists, and bold/italic where present.\n"
        "- Output only the Markdown. No explanations, no comments, no code fences."
    )

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def convert(self, path: Path, config: Config) -> str:
        if not config.has_gemini():
            raise RuntimeError(
                "Gemini API key is required for scanned PDFs.\n"
                "Run `docconv --init-config` and add your API key to .docconv.yaml"
            )
        return self._convert_with_gemini(path, config)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _convert_with_gemini(self, path: Path, config: Config) -> str:
        import fitz  # PyMuPDF — already a project dependency
        from google import genai
        from google.genai import types
        from google.genai.errors import ServerError

        client = genai.Client(
            api_key=config.gemini.api_key,
            http_options=types.HttpOptions(timeout=config.gemini.timeout * 1000),
        )
        generation_config = types.GenerateContentConfig(
            temperature=config.gemini.temperature,
            thinking_config=types.ThinkingConfig(
                thinking_budget=config.gemini.thinking_budget,
            ),
        )

        doc = fitz.open(str(path))
        total_pages = len(doc)
        doc.close()

        chunk_size = config.gemini.page_chunk_size
        if chunk_size <= 0 or total_pages <= chunk_size:
            # Single call — whole file
            print(f"    pages: {total_pages}  |  mode: single call")
            pdf_part = self._make_part(path, config, client)
            return self._call_with_retry(client, config, generation_config, pdf_part)

        # Multi-chunk
        chunks = list(range(0, total_pages, chunk_size))
        print(f"    pages: {total_pages}  |  mode: chunked ({len(chunks)} chunks of ≤{chunk_size} pages)")
        parts: list[str] = []
        for i, start in enumerate(chunks):
            end = min(start + chunk_size, total_pages)
            print(f"    chunk {i + 1}/{len(chunks)}: pages {start + 1}–{end}")
            chunk_bytes = self._extract_pages(path, start, end)
            pdf_part = self._make_part_from_bytes(chunk_bytes, config, client, path.name)
            chunk_md = self._call_with_retry(client, config, generation_config, pdf_part)
            parts.append(chunk_md)

        return "\n\n".join(parts)

    def _extract_pages(self, path: Path, start: int, end: int) -> bytes:
        """Return a new PDF containing only pages [start, end) as bytes."""
        import fitz
        src = fitz.open(str(path))
        dst = fitz.open()
        dst.insert_pdf(src, from_page=start, to_page=end - 1)
        buf = io.BytesIO()
        dst.save(buf)
        src.close()
        dst.close()
        return buf.getvalue()

    def _make_part(self, path: Path, config: Config, client) -> object:
        """Return a Gemini Part — inline bytes if small, File API if large."""
        size_mb = path.stat().st_size / _MB
        if size_mb <= config.gemini.inline_size_mb:
            return self._make_part_from_bytes(path.read_bytes(), config, client, path.name)
        # Large file → upload via File API
        print(f"    file size: {size_mb:.1f} MB > {config.gemini.inline_size_mb} MB threshold → using File Upload API")
        return self._upload_file(path.read_bytes(), client, path.name)

    def _make_part_from_bytes(self, data: bytes, config: Config, client, name: str) -> object:
        from google.genai import types
        size_mb = len(data) / _MB
        if size_mb <= config.gemini.inline_size_mb:
            return types.Part.from_bytes(data=data, mime_type="application/pdf")
        return self._upload_file(data, client, name)

    def _upload_file(self, data: bytes, client, name: str) -> object:
        """Upload PDF bytes to Gemini File API and return a Part referencing it."""
        from google.genai import types
        uploaded = client.files.upload(
            file=io.BytesIO(data),
            config=types.UploadFileConfig(mime_type="application/pdf", display_name=name),
        )
        # Poll until file is ACTIVE (processing can take a few seconds)
        while uploaded.state.name == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        if uploaded.state.name != "ACTIVE":
            raise RuntimeError(f"File upload failed, state: {uploaded.state.name}")
        return types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf")

    def _call_with_retry(self, client, config: Config, generation_config, pdf_part) -> str:
        from google.genai.errors import ServerError
        last_exc: Exception | None = None
        for attempt in range(1, config.gemini.max_retries + 2):
            try:
                response = client.models.generate_content(
                    model=config.gemini.model,
                    contents=[self.PROMPT, pdf_part],
                    config=generation_config,
                )
                return response.text
            except (TimeoutError, ServerError) as exc:
                last_exc = exc
                if attempt <= config.gemini.max_retries:
                    wait = 2 ** attempt
                    print(f"    [!] attempt {attempt} failed ({type(exc).__name__}), retrying in {wait}s…")
                    time.sleep(wait)
        raise RuntimeError(
            f"Gemini API failed after {config.gemini.max_retries + 1} attempts: {last_exc}"
        )
