"""Domain-level exceptions.

These carry no HTTP/framework concerns — the interface layer translates
them into appropriate HTTP responses (see
``interface.api.v1.exception_handlers``). Keeping exceptions in the domain
layer lets application/use-case code raise meaningful errors without
importing FastAPI.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain/business-rule violations."""


class EntityNotFoundError(DomainError):
    """Raised when a lookup by identity fails."""

    def __init__(self, entity_name: str, entity_id: object) -> None:
        self.entity_name = entity_name
        self.entity_id = entity_id
        super().__init__(f"{entity_name} with id={entity_id!r} was not found")


class EntityAlreadyExistsError(DomainError):
    """Raised on uniqueness constraint violations at the domain level."""

    def __init__(self, entity_name: str, field_name: str, value: object) -> None:
        self.entity_name = entity_name
        self.field_name = field_name
        self.value = value
        super().__init__(f"{entity_name} with {field_name}={value!r} already exists")


class AuthorizationError(DomainError):
    """Raised when an actor lacks permission to perform an action."""


class TenantSuspendedError(DomainError):
    """Raised when an operation is attempted against a suspended tenant."""

    def __init__(self, tenant_id: object) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"Tenant {tenant_id!r} is suspended")
