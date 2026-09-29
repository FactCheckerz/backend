class IngestionError(Exception):
    """Base Exception for Ingestion related errors"""

class UnsupportedInputError(IngestionError):
    """Raised when the supplied input type or format is unsupported"""

class InvalidInputError(IngestionError):
    """Raised when the supploed input is invalid"""

class MediaTooLargeError(IngestionError):
    """Raised when uploaded or downloaded media exceeds the configured size."""


class MediaTooLongError(IngestionError):
    """Raised when media exceeds the configured duration."""


class DownloadError(IngestionError):
    """Raised when a supported URL cannot be downloaded."""


class AudioExtractionError(IngestionError):
    """Raised when audio cannot be extracted from a video."""