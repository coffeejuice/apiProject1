"""Engineer-readable cogging/prolongation calculation package."""

from .adapter import calculate_cogging
from .models import (
    CoggingCalculationInput,
    CoggingComputationResult,
    CoggingMathError,
    CoggingStrains,
    CoggingVariantResult,
    FeedSchedule,
)

__all__ = [
    "CoggingCalculationInput",
    "CoggingComputationResult",
    "CoggingMathError",
    "CoggingStrains",
    "CoggingVariantResult",
    "FeedSchedule",
    "calculate_cogging",
]
