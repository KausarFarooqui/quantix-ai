"""End-to-end API test for the conversation flow: register a tenant,
start a conversation, send a message, list history — against an
in-memory SQLite database, following the same httpx AsyncClient +
ASGITransport pattern as the other API test suites.

The real ``AgentGraph`` (LangGraph + Anthropic) is swapped for a scripted
fake via FastAPI's dependency-override mechanism, exactly like the DB
session is swapped for SQLite — this test exercises the conversation/
message/agent-run persistence and API contract, not the LLM/LangGraph
integration itself (covered at the unit level with fakes in
``tests/unit/agents/``, since it needs no network access to test).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from quantix_api.application.interfaces.agent_graph import AgentRunResult, AgentState
from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType
from quantix_api.infrastructure.database.models import (  # noqa: F401 — registers tables
    agent_run,
    audit_log,
    conversation,
    data_source,
    dataset,
    message,
    oauth_account,
    refresh_token,
    tenant,
    user,
)
from quantix_api.infrastructure.database.models.base import Base
from quantix_api.interface.api.v1.dependencies.db import get_db_session
from quantix_api.interface.api.v1.dependencies.services import get_agent_graph


class _ScriptedAgentGraph:
    """Always answers with a fixed response, having "consulted" one
    specialist agent — enough to exercise the persistence path end to end
    without a real LLM call.
    """

    async def run(self, *, state: AgentState, context) -> AgentState:  # noqa: ANN001
        state.agent_runs = [
            AgentRunResult(agent_type=AgentType.SUPERVISOR, status=AgentRunStatus.SUCCEEDED),
            AgentRunResult(
                agent_type=AgentType.DATA_PROFILING,
                status=AgentRunStatus.SUCCEEDED,
                output_summary="This dataset has 3 columns and 100 rows.",
                prompt_tokens=12,
                completion_tokens=34,
                latency_ms=250,
            ),
        ]
        state.final_response = "This dataset has 3 columns and 100 rows."
        state.finished = True
        return state


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from quantix_api.main import create_app

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_agent_graph] = lambda: _ScriptedAgentGraph()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    await engine.dispose()


async def _registered_access_token(
    client: AsyncClient, *, email: str = "founder@acme.com", organization_name: str = "Acme Corp"
) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": organization_name,
            "email": email,
            "password": "correct horse battery staple",
            "full_name": "Ada Founder",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


class TestConversationFlow:
    async def test_start_conversation_send_message_list_history(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}

        start_response = await client.post(
            "/api/v1/conversations", headers=headers, json={"title": "Q3 sales review"}
        )
        assert start_response.status_code == 201
        conversation_id = start_response.json()["id"]
        assert start_response.json()["status"] == "active"

        send_response = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "What can you tell me about this dataset?"},
        )
        assert send_response.status_code == 201
        body = send_response.json()
        assert body["message"]["role"] == "assistant"
        assert body["message"]["content"] == "This dataset has 3 columns and 100 rows."
        assert body["message"]["agent_type"] == "data_profiling"
        assert len(body["agent_runs"]) == 2
        assert {r["agent_type"] for r in body["agent_runs"]} == {"supervisor", "data_profiling"}

        history_response = await client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=headers
        )
        assert history_response.status_code == 200
        roles = [m["role"] for m in history_response.json()]
        assert roles == ["user", "assistant"]

        runs_response = await client.get(
            f"/api/v1/conversations/{conversation_id}/agent-runs", headers=headers
        )
        assert runs_response.status_code == 200
        assert len(runs_response.json()) == 2

    async def test_list_conversations_for_tenant(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}
        await client.post("/api/v1/conversations", headers=headers, json={"title": "First"})
        await client.post("/api/v1/conversations", headers=headers, json={"title": "Second"})

        response = await client.get("/api/v1/conversations", headers=headers)

        assert response.status_code == 200
        titles = {c["title"] for c in response.json()}
        assert titles == {"First", "Second"}

    async def test_sending_to_unknown_conversation_returns_404(self, client: AsyncClient) -> None:
        access_token = await _registered_access_token(client)
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.post(
            "/api/v1/conversations/00000000-0000-0000-0000-000000000000/messages",
            headers=headers,
            json={"content": "hello"},
        )

        assert response.status_code == 404

    async def test_cannot_see_another_tenants_conversation(self, client: AsyncClient) -> None:
        token_a = await _registered_access_token(client, email="founder@acme.com")
        start_response = await client.post(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"title": "Private"},
        )
        conversation_id = start_response.json()["id"]

        token_b = await _registered_access_token(
            client, email="founder@globex.com", organization_name="Globex Corp"
        )
        response = await client.get(
            f"/api/v1/conversations/{conversation_id}", headers={"Authorization": f"Bearer {token_b}"}
        )

        assert response.status_code == 404

    async def test_unauthenticated_request_is_rejected(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/conversations", json={"title": "x"})
        # HTTPBearer's default auto_error behavior returns 401 for missing
        # credentials; 403 is for authenticated-but-not-permitted requests.
        assert response.status_code == 401
