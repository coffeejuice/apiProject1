class MaterialServiceError(Exception):
    """Base class for material parser and visual payload errors."""


class MaterialParserError(MaterialServiceError):
    """Raised when a material source file cannot be parsed."""


class MaterialSourceNotSupportedError(MaterialServiceError):
    """Raised when a material source cannot be mapped to a registered parser."""


class MaterialFileNotFoundError(MaterialServiceError):
    """Raised when a material source file cannot be found on disk."""
