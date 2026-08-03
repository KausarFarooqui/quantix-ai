"""Authentication (``get_current_user``) and authorization (``require_role``)
dependencies — the enforcement points for RBAC across every protected route.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from quantix_api.domain.entities.user import User, UserRole
from quantix_api.domain.exceptions.auth import InactiveUserError, InvalidCredentialsError
from quantix_api.domain.exceptions.base import AuthorizationError
from quantix_api.interface.api.v1.dependencies.repositories import UserRepo
from quantix_api.interface.api.v1.dependencies.services import TokenServiceDep

_bearer_scheme = HTTPBearer(auto_error=True, description="Access token issued by /auth/login")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    user_repo: UserRepo,
    token_service: TokenServiceDep,
) -> User:
    claims = token_service.decode_access_token(credentials.credentials)

    user = await user_repo.get_by_id(claims.user_id)
    if user is None or user.tenant_id != claims.tenant_id:
        raise InvalidCredentialsError
    if not user.is_active:
        raise InactiveUserError

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum_role: UserRole):
    """Dependency factory: ``Depends(require_role(UserRole.ADMIN))`` on a
    route guarantees the caller is at least an admin in their tenant.
    Raises the domain ``AuthorizationError`` (mapped to 403) otherwise —
    resolved once per request, so the check happens before any handler
    body runs.
    """

    async def _check(current_user: CurrentUser) -> User:
        if not current_user.has_at_least(minimum_role):
            raise AuthorizationError(
                f"This action requires the '{minimum_role.value}' role or higher"
            )
        return current_user

    return _check


def get_client_ip(request: Request) -> str | None:
    """Prefer the left-most X-Forwarded-For entry (set by a trusted
    reverse proxy/load balancer) over the raw socket address, which is
    almost always the proxy's own IP behind one.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


ClientIp = Annotated[str | None, Depends(get_client_ip)]
