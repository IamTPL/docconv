# docconv/converters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from docconv.config import Config


class UnsupportedFormatError(ValueError):
    pass


class BaseConverter(ABC):
    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Return True if this converter handles the given file extension."""

    @abstractmethod
    def convert(self, path: Path, config: Config) -> str:
        """Convert file to Markdown string. Must not write files or print to stdout."""
