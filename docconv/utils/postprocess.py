from __future__ import annotations

import re


def clean_markdown(text: str) -> str:
    """Normalize Markdown output from any converter.

    Fixes: CRLF endings, trailing whitespace, excessive blank lines.
    Returns a string ending with exactly one newline.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
