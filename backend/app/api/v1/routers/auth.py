"""
Auth router.

Implements exactly the eight endpoints the frontend's endpoint registry
(`src/services/endpoints.ts`) and the task brief specify — no more, no less:

    POST /auth/register
    POST /auth/login
    POST /auth/logout
    POST /auth/refresh
    POST /auth/forgot-password
    POST /auth/reset-password
    GET  /auth/me
    PATCH /users/profile

Refresh-token handling: the refresh token is set as an httpOnly, Secure
cookie (SameSite=Lax by default; SameSite=None when the frontend and API are
on different sites - see REFRESH_COOKIE_SAMESITE in core/config.py) on login/refresh and cleared on logout. It is never
present in any JSON response body, so it can't be read or exfiltrated by
JavaScript (mitigates XSS-driven token theft) and Supabase's
SameSite=Lax + `credentials: "include"` combination is the primary CSRF
mitigation for the two cookie-reading endpoints (`/auth/refresh`,
`/auth/logout`) per FastAPI Backend Architecture Blueprint Section 19 /
the task's CSRF requirement. `AuthSession.accessToken` (short-lived, ~1
hour) is returned in the body and held in memory/localStorage by the
frontend exactly as `AuthProvider.tsx` already does — this is unchanged
from the existing frontend design.
"""
from fastapi import APIRouter, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.dependencies.auth import CurrentUser, get_current_user
from app.dependencies.services import get_auth_service
from app.schemas.auth import (
    AuthSession,
    AuthUser,
    Credentials,
    ForgotPasswordRequest,
    MutationResult,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])
users_router = APIRouter(tags=["users"])

settings = get_settings()
# `enabled=False` makes every @limiter.limit a no-op, so a test suite or a
# load test does not trip the public-endpoint budget.
limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    # Attributes must match the ones the cookie was set with: a deletion that
    # omits SameSite/Secure is treated as SameSite=Lax by the browser and is
    # ignored when it arrives on a cross-site response, so logout would not clear it.
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


@router.post("/auth/register", response_model=MutationResult[AuthUser], status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def register(
    request: Request,  # required positional arg for slowapi's limiter
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> MutationResult[AuthUser]:
    return await service.register(payload)


@router.post("/auth/login", response_model=AuthSession)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def login(
    request: Request,
    payload: Credentials,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> AuthSession:
    session, refresh_token = await service.login(payload.email, payload.password)
    _set_refresh_cookie(response, refresh_token)
    return session


@router.post("/auth/refresh", response_model=AuthSession)
async def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> AuthSession:
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise AuthenticationError("No active session to refresh.")
    session, new_refresh_token = await service.refresh(refresh_token)
    _set_refresh_cookie(response, new_refresh_token)  # rotation: old token is replaced, not reused
    return session


@router.post("/auth/logout", response_model=MutationResult)
async def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> MutationResult:
    access_token = None
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        access_token = auth_header.split(" ", 1)[1].strip()
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    result = await service.logout(access_token, refresh_token)
    _clear_refresh_cookie(response)
    return result


@router.post("/auth/forgot-password", response_model=MutationResult)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MutationResult:
    return await service.forgot_password(payload.email)


@router.post("/auth/reset-password", response_model=MutationResult)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> MutationResult:
    result = await service.reset_password(payload.token, payload.password)
    # Every refresh token for the account was just revoked; drop the cookie
    # so the browser does not keep presenting one that can no longer work.
    _clear_refresh_cookie(response)
    return result


@router.get("/auth/me", response_model=AuthUser)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> AuthUser:
    return await service.get_current_user(current_user.id)


@users_router.patch("/users/profile", response_model=AuthUser)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> AuthUser:
    return await service.update_profile(current_user.id, **payload.model_dump(exclude_unset=True))
