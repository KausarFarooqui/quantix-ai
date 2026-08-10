"""Auth bootstrap for the shared demo workspace.

There's no login/signup UI in this build (see ADR-0008). Every visitor is
authenticated into one fixed tenant + owner user, get-or-created here and
minted a real, valid token pair — no password check, since there's no
credential for a visitor to present. `routes/auth.py::demo_login` is the
only route that calls this; it must never be wired into any other route,
since it's an unauthenticated way to obtain a valid session for a known
account and that's only acceptable because that account is intentionally
public and shared, holding no data any single visitor should expect to be
private from any other.

This is the app's actual, permanent auth-bootstrap mechanism — not a
temporary local-debugging shim — so unlike a real login it deliberately
has no environment guard: it needs to work in every deployment, including
production, or nothing can get past the app shell (see ADR-0008's
Alternatives section for why the pre-existing register/login UI was
removed rather than kept as the entry point).
"""

from __future__ import annotations

from quantix_api.application.dto.auth import AuthResult
from quantix_api.application.interfaces.audit_logger import AuditLogger
from quantix_api.application.interfaces.password_hasher import PasswordHasher
from quantix_api.application.interfaces.token_service import TokenService
from quantix_api.application.use_cases._token_issuance import issue_tokens
from quantix_api.domain.entities.audit_log import AuditAction
from quantix_api.domain.entities.tenant import Tenant
from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.repositories.refresh_token_repository import RefreshTokenRepository
from quantix_api.domain.repositories.tenant_repository import TenantRepository
from quantix_api.domain.repositories.user_repository import UserRepository

DEMO_TENANT_SLUG = "demo"
DEMO_TENANT_NAME = "Demo Workspace"
DEMO_USER_EMAIL = "demo@quantix.local"
DEMO_USER_FULL_NAME = "Demo User"
# Never actually checked — demo-login skips password verification entirely.
# Only needed because User.hashed_password is a non-optional-at-the-DB-layer
# column for password accounts.
_DEMO_PASSWORD_PLACEHOLDER = "demo-bypass-not-a-real-password-do-not-use"  # noqa: S105


class DemoLoginUseCase:
    """Idempotent: safe to call on every app load. First call anywhere
    against a given database creates the demo tenant/user, every
    subsequent call just re-issues tokens for it.
    """

    def __init__(
        self,
        *,
        tenant_repo: TenantRepository,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        audit_logger: AuditLogger,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._audit_logger = audit_logger

    async def execute(self) -> AuthResult:
        tenant = await self._tenant_repo.get_by_slug(DEMO_TENANT_SLUG)
        if tenant is None:
            tenant = await self._tenant_repo.add(
                Tenant(name=DEMO_TENANT_NAME, slug=DEMO_TENANT_SLUG)
            )

        user = await self._user_repo.get_by_email(tenant.id, DEMO_USER_EMAIL)
        if user is None:
            user = await self._user_repo.add(
                User(
                    tenant_id=tenant.id,
                    email=DEMO_USER_EMAIL,
                    hashed_password=self._password_hasher.hash(_DEMO_PASSWORD_PLACEHOLDER),
                    full_name=DEMO_USER_FULL_NAME,
                    role=UserRole.OWNER,
                    is_active=True,
                    is_email_verified=True,
                )
            )
            await self._audit_logger.record(
                action=AuditAction.TENANT_CREATED,
                tenant_id=tenant.id,
                actor_user_id=user.id,
                resource_type="tenant",
                resource_id=str(tenant.id),
                ip_address=None,
            )
            await self._audit_logger.record(
                action=AuditAction.USER_REGISTERED,
                tenant_id=tenant.id,
                actor_user_id=user.id,
                resource_type="user",
                resource_id=str(user.id),
                ip_address=None,
            )

        tokens = await issue_tokens(
            user=user,
            token_service=self._token_service,
            refresh_token_repo=self._refresh_token_repo,
        )

        await self._audit_logger.record(
            action=AuditAction.USER_LOGIN_SUCCEEDED,
            tenant_id=tenant.id,
            actor_user_id=user.id,
            ip_address=None,
        )

        return AuthResult(tokens=tokens, user_id=user.id, tenant_id=tenant.id)
