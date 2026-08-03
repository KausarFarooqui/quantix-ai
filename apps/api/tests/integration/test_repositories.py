"""Integration tests for concrete SQLAlchemy repositories against a real
(SQLite, in-memory) database — verifies entity<->ORM mapping and query
logic beyond what the fake-repository unit tests can prove.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from quantix_api.domain.entities.agent_run import AgentRun, AgentRunStatus, AgentType
from quantix_api.domain.entities.conversation import Conversation, ConversationStatus
from quantix_api.domain.entities.data_source import DataSource, DataSourceStatus, SourceType
from quantix_api.domain.entities.dataset import (
    Dataset,
    DatasetColumn,
    DatasetColumnType,
    DatasetStatus,
)
from quantix_api.domain.entities.message import Message, MessageRole
from quantix_api.domain.entities.oauth_account import OAuthAccount, OAuthProviderName
from quantix_api.domain.entities.refresh_token import RefreshToken
from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.infrastructure.database.repositories.agent_run_repository import (
    SqlAlchemyAgentRunRepository,
)
from quantix_api.infrastructure.database.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from quantix_api.infrastructure.database.repositories.data_source_repository import (
    SqlAlchemyDataSourceRepository,
)
from quantix_api.infrastructure.database.repositories.dataset_repository import (
    SqlAlchemyDatasetRepository,
)
from quantix_api.infrastructure.database.repositories.message_repository import (
    SqlAlchemyMessageRepository,
)
from quantix_api.infrastructure.database.repositories.oauth_account_repository import (
    SqlAlchemyOAuthAccountRepository,
)
from quantix_api.infrastructure.database.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from quantix_api.infrastructure.database.repositories.tenant_repository import (
    SqlAlchemyTenantRepository,
)
from quantix_api.infrastructure.database.repositories.user_repository import (
    SqlAlchemyUserRepository,
)


class TestTenantRepository:
    async def test_add_and_get_by_id_roundtrip(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyTenantRepository(async_session)
        tenant = await repo.add(Tenant(name="Acme Corp", slug="acme"))
        await async_session.commit()

        fetched = await repo.get_by_id(tenant.id)

        assert fetched is not None
        assert fetched.name == "Acme Corp"
        assert fetched.slug == "acme"

    async def test_get_by_slug(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyTenantRepository(async_session)
        await repo.add(Tenant(name="Acme Corp", slug="acme"))
        await async_session.commit()

        found = await repo.get_by_slug("acme")
        missing = await repo.get_by_slug("does-not-exist")

        assert found is not None
        assert missing is None

    async def test_slug_exists(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyTenantRepository(async_session)
        await repo.add(Tenant(name="Acme Corp", slug="acme"))
        await async_session.commit()

        assert await repo.slug_exists("acme") is True
        assert await repo.slug_exists("nope") is False

    async def test_duplicate_slug_violates_unique_constraint(
        self, async_session: AsyncSession
    ) -> None:
        repo = SqlAlchemyTenantRepository(async_session)
        await repo.add(Tenant(name="Acme Corp", slug="acme"))
        await async_session.commit()

        with pytest.raises(IntegrityError):
            await repo.add(Tenant(name="Acme Impersonator", slug="acme"))

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyTenantRepository(async_session)
        tenant = await repo.add(Tenant(name="Acme Corp", slug="acme"))
        await async_session.commit()

        tenant.suspend()
        await repo.update(tenant)
        await async_session.commit()

        fetched = await repo.get_by_id(tenant.id)
        assert fetched is not None
        assert fetched.is_active is False

    async def test_delete_removes_record(self, async_session: AsyncSession) -> None:
        # Exercises `SQLAlchemyRepository.delete()` — the generic base
        # implementation, since no concrete repository overrides it.
        repo = SqlAlchemyTenantRepository(async_session)
        tenant = await repo.add(Tenant(name="Acme Corp", slug="acme"))
        await async_session.commit()

        await repo.delete(tenant.id)
        await async_session.commit()

        assert await repo.get_by_id(tenant.id) is None

    async def test_delete_nonexistent_id_is_a_noop(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyTenantRepository(async_session)
        await repo.delete(uuid4())  # should not raise

    async def test_list_all_returns_records(self, async_session: AsyncSession) -> None:
        # Exercises `SQLAlchemyRepository.list_all()` — the generic base
        # implementation, since no concrete repository overrides it.
        repo = SqlAlchemyTenantRepository(async_session)
        await repo.add(Tenant(name="Acme Corp", slug="acme"))
        await repo.add(Tenant(name="Globex", slug="globex"))
        await async_session.commit()

        results = await repo.list_all()

        assert len(results) == 2


class TestUserRepository:
    async def test_get_by_email_is_scoped_to_tenant(self, async_session: AsyncSession) -> None:
        tenant_repo = SqlAlchemyTenantRepository(async_session)
        user_repo = SqlAlchemyUserRepository(async_session)

        tenant_a = await tenant_repo.add(Tenant(name="A", slug="a"))
        tenant_b = await tenant_repo.add(Tenant(name="B", slug="b"))
        await async_session.flush()

        await user_repo.add(
            User(
                tenant_id=tenant_a.id,
                email="shared@example.com",
                hashed_password="hash",
                full_name="User A",
                role=UserRole.OWNER,
            )
        )
        await async_session.commit()

        found_in_a = await user_repo.get_by_email(tenant_a.id, "shared@example.com")
        found_in_b = await user_repo.get_by_email(tenant_b.id, "shared@example.com")

        assert found_in_a is not None
        assert found_in_b is None

    async def test_same_email_allowed_across_different_tenants(
        self, async_session: AsyncSession
    ) -> None:
        tenant_repo = SqlAlchemyTenantRepository(async_session)
        user_repo = SqlAlchemyUserRepository(async_session)

        tenant_a = await tenant_repo.add(Tenant(name="A", slug="a"))
        tenant_b = await tenant_repo.add(Tenant(name="B", slug="b"))
        await async_session.flush()

        await user_repo.add(
            User(
                tenant_id=tenant_a.id,
                email="shared@example.com",
                hashed_password="hash",
                full_name="User A",
                role=UserRole.OWNER,
            )
        )
        await user_repo.add(
            User(
                tenant_id=tenant_b.id,
                email="shared@example.com",
                hashed_password="hash",
                full_name="User B",
                role=UserRole.OWNER,
            )
        )

        await async_session.commit()  # should not raise — unique constraint is per-tenant

    async def test_email_exists_in_any_tenant(self, async_session: AsyncSession) -> None:
        tenant_repo = SqlAlchemyTenantRepository(async_session)
        user_repo = SqlAlchemyUserRepository(async_session)
        tenant = await tenant_repo.add(Tenant(name="A", slug="a"))
        await async_session.flush()

        await user_repo.add(
            User(
                tenant_id=tenant.id,
                email="taken@example.com",
                hashed_password="hash",
                full_name="User",
                role=UserRole.OWNER,
            )
        )
        await async_session.commit()

        assert await user_repo.email_exists_in_any_tenant("taken@example.com") is True
        assert await user_repo.email_exists_in_any_tenant("free@example.com") is False

    async def test_update_persists_role_change(self, async_session: AsyncSession) -> None:
        tenant_repo = SqlAlchemyTenantRepository(async_session)
        user_repo = SqlAlchemyUserRepository(async_session)
        tenant = await tenant_repo.add(Tenant(name="A", slug="a"))
        await async_session.flush()

        user = await user_repo.add(
            User(
                tenant_id=tenant.id,
                email="u@example.com",
                hashed_password="hash",
                full_name="User",
                role=UserRole.VIEWER,
            )
        )
        await async_session.commit()

        user.role = UserRole.ADMIN
        await user_repo.update(user)
        await async_session.commit()

        fetched = await user_repo.get_by_id(user.id)
        assert fetched is not None
        assert fetched.role is UserRole.ADMIN


class TestDataSourceRepository:
    async def test_add_and_list_for_tenant(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyDataSourceRepository(async_session)
        tenant_id = uuid4()
        await repo.add(
            DataSource(tenant_id=tenant_id, name="Orders CSV", source_type=SourceType.CSV)
        )
        await async_session.commit()

        results = await repo.list_for_tenant(tenant_id)

        assert len(results) == 1
        assert results[0].name == "Orders CSV"

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyDataSourceRepository(async_session)
        data_source = await repo.add(
            DataSource(tenant_id=uuid4(), name="Orders CSV", source_type=SourceType.CSV)
        )
        await async_session.commit()

        data_source.mark_tested(success=True)
        data_source.name = "Orders CSV (renamed)"
        await repo.update(data_source)
        await async_session.commit()

        fetched = await repo.get_by_id(data_source.id)
        assert fetched is not None
        assert fetched.name == "Orders CSV (renamed)"
        assert fetched.status is DataSourceStatus.ACTIVE
        assert fetched.last_tested_at is not None


class TestDatasetRepository:
    async def test_add_and_list_for_tenant(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyDatasetRepository(async_session)
        tenant_id = uuid4()
        await repo.add(
            Dataset(
                tenant_id=tenant_id,
                data_source_id=uuid4(),
                name="orders",
                table_identifier="public.orders",
            )
        )
        await async_session.commit()

        results = await repo.list_for_tenant(tenant_id)

        assert len(results) == 1

    async def test_list_for_data_source(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyDatasetRepository(async_session)
        data_source_id = uuid4()
        await repo.add(
            Dataset(
                tenant_id=uuid4(),
                data_source_id=data_source_id,
                name="orders",
                table_identifier="public.orders",
            )
        )
        await async_session.commit()

        results = await repo.list_for_data_source(data_source_id)

        assert len(results) == 1

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyDatasetRepository(async_session)
        dataset = await repo.add(
            Dataset(
                tenant_id=uuid4(),
                data_source_id=uuid4(),
                name="orders",
                table_identifier="public.orders",
            )
        )
        await async_session.commit()

        dataset.mark_ready(
            schema=[DatasetColumn(name="id", data_type=DatasetColumnType.INTEGER, nullable=False)],
            row_count=100,
            size_bytes=2048,
            storage_uri="/tmp/orders.parquet",
        )
        await repo.update(dataset)
        await async_session.commit()

        fetched = await repo.get_by_id(dataset.id)
        assert fetched is not None
        assert fetched.status is DatasetStatus.READY
        assert fetched.row_count == 100
        assert fetched.schema == [
            DatasetColumn(name="id", data_type=DatasetColumnType.INTEGER, nullable=False)
        ]


class TestConversationRepository:
    async def test_add_and_list_for_tenant(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyConversationRepository(async_session)
        tenant_id = uuid4()
        await repo.add(
            Conversation(tenant_id=tenant_id, title="New chat", created_by_user_id=uuid4())
        )
        await async_session.commit()

        results = await repo.list_for_tenant(tenant_id)

        assert len(results) == 1

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyConversationRepository(async_session)
        conversation = await repo.add(
            Conversation(tenant_id=uuid4(), title="New chat", created_by_user_id=uuid4())
        )
        await async_session.commit()

        conversation.rename("Renamed chat")
        conversation.archive()
        await repo.update(conversation)
        await async_session.commit()

        fetched = await repo.get_by_id(conversation.id)
        assert fetched is not None
        assert fetched.title == "Renamed chat"
        assert fetched.status is ConversationStatus.ARCHIVED


class TestMessageRepository:
    async def test_add_and_list_for_conversation(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyMessageRepository(async_session)
        conversation_id = uuid4()
        await repo.add(
            Message(
                tenant_id=uuid4(),
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="hello",
            )
        )
        await async_session.commit()

        results = await repo.list_for_conversation(conversation_id)

        assert len(results) == 1
        assert results[0].content == "hello"

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyMessageRepository(async_session)
        message = await repo.add(
            Message(
                tenant_id=uuid4(),
                conversation_id=uuid4(),
                role=MessageRole.ASSISTANT,
                content="draft",
            )
        )
        await async_session.commit()

        message.content = "final answer"
        message.agent_type = AgentType.SQL_GENERATION
        await repo.update(message)
        await async_session.commit()

        fetched = await repo.get_by_id(message.id)
        assert fetched is not None
        assert fetched.content == "final answer"
        assert fetched.agent_type is AgentType.SQL_GENERATION


class TestAgentRunRepository:
    async def test_add_and_list_for_conversation(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyAgentRunRepository(async_session)
        conversation_id = uuid4()
        await repo.add(
            AgentRun(
                tenant_id=uuid4(),
                conversation_id=conversation_id,
                agent_type=AgentType.SQL_GENERATION,
            )
        )
        await async_session.commit()

        results = await repo.list_for_conversation(conversation_id)

        assert len(results) == 1

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyAgentRunRepository(async_session)
        agent_run = await repo.add(
            AgentRun(
                tenant_id=uuid4(),
                conversation_id=uuid4(),
                agent_type=AgentType.SQL_GENERATION,
            )
        )
        await async_session.commit()

        agent_run.mark_succeeded(
            output_summary="done", prompt_tokens=10, completion_tokens=5, latency_ms=123
        )
        await repo.update(agent_run)
        await async_session.commit()

        fetched = await repo.get_by_id(agent_run.id)
        assert fetched is not None
        assert fetched.status is AgentRunStatus.SUCCEEDED
        assert fetched.output_summary == "done"
        assert fetched.prompt_tokens == 10


class TestRefreshTokenRepository:
    async def test_add_and_get_by_token_hash(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyRefreshTokenRepository(async_session)
        await repo.add(
            RefreshToken(
                tenant_id=uuid4(),
                user_id=uuid4(),
                token_hash="hash-abc",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        await async_session.commit()

        found = await repo.get_by_token_hash("hash-abc")
        missing = await repo.get_by_token_hash("does-not-exist")

        assert found is not None
        assert missing is None

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyRefreshTokenRepository(async_session)
        token = await repo.add(
            RefreshToken(
                tenant_id=uuid4(),
                user_id=uuid4(),
                token_hash="hash-def",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        await async_session.commit()

        token.revoke()
        await repo.update(token)
        await async_session.commit()

        fetched = await repo.get_by_id(token.id)
        assert fetched is not None
        assert fetched.is_revoked is True

    async def test_revoke_all_for_user(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyRefreshTokenRepository(async_session)
        user_id = uuid4()
        first = await repo.add(
            RefreshToken(
                tenant_id=uuid4(),
                user_id=user_id,
                token_hash="hash-1",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        second = await repo.add(
            RefreshToken(
                tenant_id=uuid4(),
                user_id=user_id,
                token_hash="hash-2",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        await async_session.commit()

        await repo.revoke_all_for_user(user_id)
        await async_session.commit()

        assert (await repo.get_by_id(first.id)).is_revoked is True
        assert (await repo.get_by_id(second.id)).is_revoked is True


class TestOAuthAccountRepository:
    async def test_add_and_get_by_provider_identity(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyOAuthAccountRepository(async_session)
        await repo.add(
            OAuthAccount(
                user_id=uuid4(),
                provider=OAuthProviderName.GOOGLE,
                provider_user_id="google-123",
                email_at_provider="user@example.com",
            )
        )
        await async_session.commit()

        found = await repo.get_by_provider_identity(OAuthProviderName.GOOGLE, "google-123")
        missing = await repo.get_by_provider_identity(OAuthProviderName.GOOGLE, "nope")

        assert found is not None
        assert missing is None

    async def test_list_for_user(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyOAuthAccountRepository(async_session)
        user_id = uuid4()
        await repo.add(
            OAuthAccount(
                user_id=user_id,
                provider=OAuthProviderName.GITHUB,
                provider_user_id="gh-1",
                email_at_provider="user@example.com",
            )
        )
        await async_session.commit()

        results = await repo.list_for_user(user_id)

        assert len(results) == 1

    async def test_update_persists_changes(self, async_session: AsyncSession) -> None:
        repo = SqlAlchemyOAuthAccountRepository(async_session)
        account = await repo.add(
            OAuthAccount(
                user_id=uuid4(),
                provider=OAuthProviderName.MICROSOFT,
                provider_user_id="ms-1",
                email_at_provider="old@example.com",
            )
        )
        await async_session.commit()

        account.email_at_provider = "new@example.com"
        await repo.update(account)
        await async_session.commit()

        fetched = await repo.get_by_id(account.id)
        assert fetched is not None
        assert fetched.email_at_provider == "new@example.com"
