"""
Profile repository - the only layer permitted to query `profiles` / `roles` /
`user_roles` (FastAPI Backend Architecture Blueprint Section 4: repositories
hold no business logic, services build no SQL).
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.identity import Profile, Role, UserRole


class ProfileRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    # --- reads ---------------------------------------------------------
    async def get_by_id(self, profile_id: uuid.UUID) -> Profile | None:
        stmt = (
            select(Profile)
            .where(Profile.id == profile_id, Profile.deleted_at.is_(None))
            .options(selectinload(Profile.user_roles).selectinload(UserRole.role))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> Profile | None:
        # Compare case-insensitively on BOTH sides. Stored emails are
        # normalized to lowercase on write, but a row created by Supabase's
        # own trigger (or an older migration) may not be, and matching only
        # the input would let a duplicate account slip through.
        stmt = (
            select(Profile)
            .where(
                func.lower(Profile.email) == email.strip().lower(),
                Profile.deleted_at.is_(None),
            )
            .options(selectinload(Profile.user_roles).selectinload(UserRole.role))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Role | None:
        return (
            await self._session.execute(select(Role).where(Role.name == name))
        ).scalar_one_or_none()

    async def list_roles(self) -> list[Role]:
        return list((await self._session.execute(select(Role).order_by(Role.id))).scalars())

    # --- writes --------------------------------------------------------
    async def create_profile_with_role(
        self,
        *,
        profile_id: uuid.UUID,
        full_name: str,
        email: str,
        role_name: str,
        hospital: str | None = None,
        title: str | None = None,
        department: str | None = None,
    ) -> Profile:
        role = await self.get_role_by_name(role_name)
        if role is None:
            raise ValueError(f"Unknown role '{role_name}' - was the roles table seeded?")

        profile = Profile(
            id=profile_id,
            full_name=full_name,
            email=email.strip().lower(),
            hospital=hospital,
            title=title,
            department=department,
        )
        self._session.add(profile)
        await self._session.flush()  # satisfy the FK before linking the role

        self._session.add(UserRole(profile_id=profile.id, role_id=role.id))
        await self._session.flush()
        # Re-read through the loader options so `primary_role_name` has the
        # role relationship populated without a lazy load on an async session.
        refreshed = await self.get_by_id(profile.id)
        return refreshed or profile

    async def update_profile(self, profile: Profile, **fields: object) -> Profile:
        for key, value in fields.items():
            if value is not None and hasattr(profile, key):
                setattr(profile, key, value)
        await self._session.flush()
        return profile

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
