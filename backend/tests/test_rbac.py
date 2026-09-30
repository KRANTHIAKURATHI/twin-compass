"""Unit tests for app.dependencies.auth.require_roles — no network, no database."""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import AuthorizationError
from app.dependencies.auth import CurrentUser, require_roles


def _user(role: str) -> CurrentUser:
    return CurrentUser(id=uuid.uuid4(), email="user@example.com", role=role)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_require_roles_allows_matching_role():
    dependency = require_roles("admin", "doctor")
    result = await dependency(_user("doctor"))
    assert result.role == "doctor"


@pytest.mark.asyncio
async def test_require_roles_rejects_non_matching_role():
    dependency = require_roles("admin")
    with pytest.raises(AuthorizationError):
        await dependency(_user("patient"))


@pytest.mark.asyncio
async def test_require_roles_rejects_when_no_roles_match_any():
    dependency = require_roles("admin", "researcher")
    with pytest.raises(AuthorizationError):
        await dependency(_user("doctor"))
