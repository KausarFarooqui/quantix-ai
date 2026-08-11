"""Domain exceptions for forecast generation."""

from __future__ import annotations

from quantix_api.domain.exceptions.base import DomainError


class ForecastingError(DomainError):
    """Base class for anything that goes wrong generating a forecast."""


class UnknownForecastColumnError(ForecastingError):
    def __init__(self, column: str, dataset_id: object) -> None:
        self.column = column
        self.dataset_id = dataset_id
        super().__init__(f"Column '{column}' was not found on dataset {dataset_id!r}")


class NonNumericForecastColumnError(ForecastingError):
    def __init__(self, column: str) -> None:
        self.column = column
        super().__init__(f"Column '{column}' is not numeric and cannot be forecast")


class InsufficientDataForForecastError(ForecastingError):
    def __init__(self, column: str, available_points: int, minimum_required: int) -> None:
        self.column = column
        self.available_points = available_points
        self.minimum_required = minimum_required
        super().__init__(
            f"Column '{column}' has only {available_points} numeric point(s); at least "
            f"{minimum_required} are needed to forecast"
        )
