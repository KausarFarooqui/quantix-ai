"""Port for building a ``Connector`` from a persisted ``DataSource``.

Separates "which connector class handles which source type" (a registry,
necessarily infrastructure since it imports every concrete connector)
from the use cases that just need "give me something I can call
``.extract()`` on" — use cases depend on this port, not on the registry
directly.
"""

from __future__ import annotations

from typing import Any, Protocol

from quantix_api.application.interfaces.connector import Connector
from quantix_api.domain.entities.data_source import DataSource


class ConnectorFactory(Protocol):
    def build(self, *, data_source: DataSource, secrets: dict[str, Any]) -> Connector:
        """Raises ``UnsupportedSourceTypeError`` if no connector is
        registered for ``data_source.source_type``.
        """
        ...
