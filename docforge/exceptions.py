"""
Custom exceptions for DocForge.

All DocForge errors inherit from DocForgeError so callers can catch broadly
or specifically as needed.
"""


class DocForgeError(Exception):
    """Base exception for all DocForge errors."""


class ParseError(DocForgeError):
    """Raised when a parser cannot extract content from a document."""


class UnsupportedFormatError(DocForgeError):
    """Raised when no parser supports the given file format."""


class EmbedError(DocForgeError):
    """Raised when embedding generation fails."""


class IntelligenceError(DocForgeError):
    """Raised when LLM-powered enrichment fails."""


class UDFWriteError(DocForgeError):
    """Raised when writing a .udf file fails."""


class UDFReadError(DocForgeError):
    """Raised when reading or parsing a .udf file fails."""


class SizeLimitError(DocForgeError):
    """Raised when the estimated .udf size exceeds the configured limit."""


class ConnectorError(DocForgeError):
    """Raised when a source connector fails to fetch documents."""


class QuantizationError(DocForgeError):
    """Raised when embedding quantization or dequantization fails."""
