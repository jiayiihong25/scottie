"""Extraction + chunking: turns raw course material into a ContentIndex.

Public entry point: `build_index(data_root) -> ContentIndex`.
"""

from .models import Chunk, ContentIndex, Document, SourceUnit
from .pipeline import build_index

__all__ = ["build_index", "ContentIndex", "Chunk", "Document", "SourceUnit"]
