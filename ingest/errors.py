"""Ingestion errors.

This pipeline eventually runs unattended on a cron schedule, so ingestion
failures are raised loudly rather than swallowed — a half-extracted content
index silently produces a half-empty morning packet, which is worse than a
run that stops and says why.
"""


class IngestError(Exception):
    """Base class for every ingestion failure."""


class UnsupportedFormatError(IngestError):
    """A source file has no extractor registered for its extension."""


class ExtractionError(IngestError):
    """A source file matched an extractor but could not be read."""


class EmptyExtractionError(ExtractionError):
    """A source file parsed fine but yielded no usable text.

    Usually means a scanned/image-only PDF that needs OCR, or a slide deck
    whose content lives entirely in images.
    """


class LayoutError(IngestError):
    """Course material is not laid out the way the ingester expects."""
