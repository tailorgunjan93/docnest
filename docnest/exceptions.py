"""
Custom exceptions for DOCNEST.

All DOCNEST errors inherit from DOCNESTError so callers can catch broadly
or specifically as needed.
"""


class DOCNESTError(Exception):
    """Base exception for all DOCNEST errors."""


class ParseError(DOCNESTError):
    """Raised when a parser cannot extract content from a document."""


class UnsupportedFormatError(DOCNESTError):
    """Raised when no parser supports the given file format."""


class EmbedError(DOCNESTError):
    """Raised when embedding generation fails."""


class IntelligenceError(DOCNESTError):
    """Raised when LLM-powered enrichment fails."""


class UDFWriteError(DOCNESTError):
    """Raised when writing a .udf file fails."""


class UDFReadError(DOCNESTError):
    """Raised when reading or parsing a .udf file fails."""


class SizeLimitError(DOCNESTError):
    """Raised when the estimated .udf size exceeds the configured limit."""


class ConnectorError(DOCNESTError):
    """Raised when a source connector fails to fetch documents."""


class QuantizationError(DOCNESTError):
    """Raised when embedding quantization or dequantization fails."""
