"""The connector registry — concrete implementation of
``application.interfaces.connector_factory.ConnectorFactory``.

This is the single place that maps a ``SourceType`` to the class that
handles it. Extending Quantix with a new integration touches exactly this
file (plus the new connector class itself): add the ``SourceType`` member
in ``domain.entities.data_source``, implement ``Connector``, register the
mapping here.

Imports for each connector are lazy (inside ``build``) so that, say, a
deployment that never configures Snowflake never pays for importing
``snowflake-sqlalchemy`` at process startup.
"""

from __future__ import annotations

from typing import Any

from quantix_api.application.interfaces.connector import Connector
from quantix_api.application.interfaces.file_storage import FileStorage
from quantix_api.domain.entities.data_source import (
    DATABASE_SOURCE_TYPES,
    FILE_SOURCE_TYPES,
    DataSource,
    SourceType,
)
from quantix_api.domain.exceptions.connectors import UnsupportedSourceTypeError


class ConnectorRegistry:
    def __init__(self, *, file_storage: FileStorage) -> None:
        self._file_storage = file_storage

    def build(self, *, data_source: DataSource, secrets: dict[str, Any]) -> Connector:
        source_type = data_source.source_type

        if source_type in FILE_SOURCE_TYPES:
            from quantix_api.infrastructure.connectors.file_connector import FileConnector

            return FileConnector(
                source_type=source_type,
                file_storage=self._file_storage,
                storage_path=data_source.config["storage_path"],
                filename=data_source.config.get("original_filename", data_source.name),
            )

        if source_type in DATABASE_SOURCE_TYPES:
            from quantix_api.infrastructure.connectors.sql_connector import SqlDatabaseConnector

            return SqlDatabaseConnector(
                source_type=source_type, config=data_source.config, secrets=secrets
            )

        if source_type is SourceType.BIGQUERY:
            from quantix_api.infrastructure.connectors.bigquery_connector import BigQueryConnector

            return BigQueryConnector(config=data_source.config, secrets=secrets)

        if source_type is SourceType.GOOGLE_SHEETS:
            from quantix_api.infrastructure.connectors.google_sheets_connector import (
                GoogleSheetsConnector,
            )

            return GoogleSheetsConnector(config=data_source.config, secrets=secrets)

        raise UnsupportedSourceTypeError(source_type.value)
