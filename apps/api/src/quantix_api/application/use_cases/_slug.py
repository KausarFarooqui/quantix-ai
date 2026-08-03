"""Shared helper: derive a unique, URL-safe tenant slug from a name.

Prefixed with an underscore — not a use case itself, just plumbing shared
by ``register_user`` and ``oauth_login``.
"""

from __future__ import annotations

import re
import secrets

from quantix_api.domain.repositories.tenant_repository import TenantRepository

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
_SLUG_MULTI_DASH = re.compile(r"-+")
MAX_SLUG_LENGTH = 63


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = _SLUG_INVALID_CHARS.sub("-", slug)
    slug = _SLUG_MULTI_DASH.sub("-", slug).strip("-")
    return slug[:MAX_SLUG_LENGTH] or "workspace"


async def generate_unique_slug(name: str, tenant_repo: TenantRepository) -> str:
    """Slugify ``name``, appending a short random suffix on collision.

    Bounded retry loop: with a 4-character base36 suffix the collision
    probability is negligible, but we still cap attempts to avoid an
    infinite loop against a misbehaving repository.
    """
    base = slugify(name)
    candidate = base
    for _ in range(10):
        if not await tenant_repo.slug_exists(candidate):
            return candidate
        suffix = secrets.token_hex(3)
        candidate = f"{base[: MAX_SLUG_LENGTH - len(suffix) - 1]}-{suffix}"
    raise RuntimeError("Unable to generate a unique tenant slug after 10 attempts")
