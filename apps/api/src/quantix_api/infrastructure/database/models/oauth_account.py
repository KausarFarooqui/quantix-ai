"""ORM model for linked OAuth identities."""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from quantix_api.domain.entities.oauth_account import OAuthProviderName
from quantix_api.infrastructure.database.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class OAuthAccountModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_oauth_accounts_provider_provider_user_id"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[OAuthProviderName] = mapped_column(
        Enum(OAuthProviderName, name="oauth_provider_name", native_enum=True), nullable=False
    )
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email_at_provider: Mapped[str] = mapped_column(String(320), nullable=False)
