"""Base domain entity.

Domain entities are plain Python dataclasses with identity — they carry no
persistence or framework concerns. Infrastructure-layer ORM models are
mapped to/from these via repository implementations, keeping the domain
layer free of SQLAlchemy imports (Dependency Inversion Principle).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(kw_only=True, eq=False)
class Entity:
    """Base class for all domain entities.

    Identity equality: two entities are equal iff their ``id`` matches,
    regardless of other attribute values.

    ``eq=False`` is load-bearing, here and on every subclass. Python's
    ``@dataclass`` decides whether to generate its own ``__eq__``/
    ``__hash__`` per class, based only on that class's *own* body — it
    does not know or care that a base class already defined identity
    semantics. Without ``eq=False`` on a subclass, dataclass silently
    generates a field-by-field ``__eq__`` (comparing every attribute,
    including timestamps) and sets ``__hash__ = None`` (making the class
    unhashable), both shadowing what's defined here. Every entity
    subclass's own ``@dataclass(...)`` decorator must include ``eq=False``
    to actually inherit this identity-based behavior instead of silently
    replacing it.
    """

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(kw_only=True, eq=False)
class TenantScopedEntity(Entity):
    """Base class for entities that belong to a single tenant.

    Every table/query touching tenant-scoped data must filter by
    ``tenant_id`` — enforced at the repository layer, never left to
    individual call sites, to prevent cross-tenant data leakage.
    """

    tenant_id: UUID
