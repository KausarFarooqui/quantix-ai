"""Unit tests for tenant slug generation."""

from __future__ import annotations

import pytest

from _auth_fakes import FakeTenantRepository

from quantix_api.application.use_cases._slug import generate_unique_slug, slugify
from quantix_api.domain.entities.tenant import Tenant


class TestSlugify:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Acme Corp", "acme-corp"),
            ("  Spaced Out  ", "spaced-out"),
            ("Weird!!Chars??", "weird-chars"),
            ("Already-slugged", "already-slugged"),
            ("Multiple   Spaces", "multiple-spaces"),
            ("", "workspace"),
        ],
    )
    def test_slugify_produces_url_safe_output(self, name: str, expected: str) -> None:
        assert slugify(name) == expected


class TestGenerateUniqueSlug:
    async def test_returns_base_slug_when_available(self) -> None:
        repo = FakeTenantRepository()
        slug = await generate_unique_slug("Acme Corp", repo)
        assert slug == "acme-corp"

    async def test_appends_suffix_on_collision(self) -> None:
        repo = FakeTenantRepository()
        await repo.add(Tenant(name="Acme Corp", slug="acme-corp"))

        slug = await generate_unique_slug("Acme Corp", repo)

        assert slug != "acme-corp"
        assert slug.startswith("acme-corp-")
