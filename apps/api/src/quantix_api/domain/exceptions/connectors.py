"""Domain exceptions for the data connector layer."""

from __future__ import annotations

from quantix_api.domain.exceptions.base import DomainError


class ConnectorError(DomainError):
    """Base class for anything that goes wrong talking to a data source."""


class ConnectionTestFailedError(ConnectorError):
    def __init__(self, source_type: str, reason: str) -> None:
        self.source_type = source_type
        self.reason = reason
        super().__init__(f"Could not connect to {source_type} source: {reason}")


class SchemaDiscoveryError(ConnectorError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Failed to discover schema: {reason}")


class ExtractionError(ConnectorError):
    def __init__(self, table_identifier: str, reason: str) -> None:
        self.table_identifier = table_identifier
        self.reason = reason
        super().__init__(f"Failed to extract '{table_identifier}': {reason}")


class UnsupportedSourceTypeError(ConnectorError):
    def __init__(self, source_type: str) -> None:
        self.source_type = source_type
        super().__init__(f"No connector is registered for source type '{source_type}'")


class UnsupportedFileFormatError(ConnectorError):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        super().__init__(f"Could not determine a supported file format for '{filename}'")


class DatasetNotReadyError(DomainError):
    def __init__(self, dataset_id: object, status: str) -> None:
        self.dataset_id = dataset_id
        self.status = status
        super().__init__(f"Dataset {dataset_id!r} is not ready (status={status})")
