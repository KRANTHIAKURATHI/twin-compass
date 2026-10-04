"""
Centralized configuration.

Every setting is loaded from environment variables (never hardcoded). Local
development reads from `.env` (see `.env.example`); staging/production inject
these through the deployment platform's secret manager.

Two run modes
-------------
`AUTH_PROVIDER` selects where identities live:

  local     - self-contained. Credentials are stored in this backend's own
              `local_credentials` table (bcrypt), tokens are minted and
              verified here, and `DATABASE_URL` normally points at a SQLite
              file. Nothing external is required, so the API boots and every
              auth endpoint works offline.

  supabase  - Supabase Auth is the identity provider and credential store;
              this backend proxies its tokens and keeps `profiles` /
              `user_roles` alongside in Postgres.

The rest of the application is written against the provider interface in
`app/auth/providers/base.py` and does not know which mode is active.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AuthProviderName = Literal["local", "supabase"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App -----------------------------------------------------------
    ENVIRONMENT: Literal["local", "dev", "staging", "prod"] = "local"
    APP_NAME: str = "OncoTwin API"
    API_V1_PREFIX: str = "/api/v1"

    # --- Which identity backend is in use --------------------------------
    AUTH_PROVIDER: AuthProviderName = "local"

    # --- CORS ------------------------------------------------------------
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )

    # --- Storage ----------------------------------------------------------
    # Where file-mode artefacts live: the SQLite database, and the
    # password-reset link log the local provider writes instead of sending
    # email. Relative paths resolve against the backend package root.
    DATA_DIR: Path = Path("./data")

    # Empty means "derive from DATA_DIR" (file mode). Set explicitly to point
    # at Postgres/Supabase. In hosted Supabase use the PgBouncer pooler
    # connection string (port 6543, transaction mode), not the direct port.
    DATABASE_URL: str = ""

    # --- Supabase (required only when AUTH_PROVIDER=supabase) --------------
    SUPABASE_URL: AnyHttpUrl | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # --- Local provider token signing (required only when local) ----------
    # Generated per-process if unset, which is fine for a dev restart but
    # invalidates outstanding tokens; set it explicitly to keep sessions
    # across restarts. Refused outright outside local/dev.
    LOCAL_JWT_SECRET: str = ""
    LOCAL_JWT_AUDIENCE: str = "authenticated"
    ACCESS_TOKEN_TTL_SECONDS: int = 60 * 60
    PASSWORD_RESET_TTL_SECONDS: int = 60 * 30

    # --- Cookies / refresh tokens ------------------------------------------
    REFRESH_COOKIE_NAME: str = "oncotwin_refresh_token"
    REFRESH_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 30
    REFRESH_COOKIE_SECURE: bool = True  # False only makes sense over plain HTTP locally
    # "lax" only works when the frontend and API share a registrable domain. When
    # they are on different sites (e.g. *.vercel.app calling *.onrender.com) the
    # browser drops a Lax cookie set by the cross-site response, so the deployment
    # must set "none" (which requires REFRESH_COOKIE_SECURE=true).
    REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # --- Password policy ----------------------------------------------------
    # One definition, applied identically by register and reset-password.
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 128
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_LETTER: bool = True

    # --- Password reset ------------------------------------------------------
    PASSWORD_RESET_REDIRECT_URL: AnyHttpUrl = "http://localhost:5173/reset-password"  # type: ignore[assignment]

    # --- Rate limiting -----------------------------------------------------
    AUTH_RATE_LIMIT: str = "10/minute"
    RATE_LIMIT_ENABLED: bool = True

    # --- Logging ---------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # --- Document storage (Supabase Storage; requires AUTH_PROVIDER=supabase) --
    SUPABASE_STORAGE_BUCKET: str = "clinical-documents"
    DOCUMENT_MAX_UPLOAD_MB: int = 25
    DOCUMENT_ALLOWED_MIME_TYPES: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "image/jpeg",
            "image/png",
        ]
    )
    # Seconds a signed download/preview URL stays valid for.
    DOCUMENT_SIGNED_URL_TTL_SECONDS: int = 300

    # --- OCR extraction (Phase 7) ------------------------------------------
    # No OCR engine/SDK is installed (see app/services/ocr_provider.py). Unset
    # until a real provider is wired up; extraction fails loudly rather than
    # inventing values. Only formats OCR could plausibly read at all, even
    # once a provider exists - a strict subset of DOCUMENT_ALLOWED_MIME_TYPES.
    OCR_PROVIDER: str | None = None
    OCR_SUPPORTED_MIME_TYPES: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "image/jpeg",
            "image/png",
        ]
    )

    # ------------------------------------------------------------------
    # Derived / validated
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _resolve_and_check(self) -> "Settings":
        # DATA_DIR is created eagerly so the SQLite file and reset-link log
        # have somewhere to live without every call site re-checking.
        data_dir = self.DATA_DIR.expanduser()
        if not data_dir.is_absolute():
            data_dir = (Path(__file__).resolve().parents[2] / data_dir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "DATA_DIR", data_dir)

        if not self.DATABASE_URL:
            object.__setattr__(
                self, "DATABASE_URL", f"sqlite+aiosqlite:///{data_dir / 'oncotwin.db'}"
            )

        if self.AUTH_PROVIDER == "supabase":
            missing = [
                name
                for name in (
                    "SUPABASE_URL",
                    "SUPABASE_ANON_KEY",
                    "SUPABASE_SERVICE_ROLE_KEY",
                    "SUPABASE_JWT_SECRET",
                )
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    "AUTH_PROVIDER=supabase requires: "
                    + ", ".join(missing)
                    + ". Set them in .env, or use AUTH_PROVIDER=local to run without Supabase."
                )
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    "AUTH_PROVIDER=supabase cannot be combined with a SQLite DATABASE_URL - "
                    "profiles must live in the same Postgres database as Supabase Auth."
                )
        else:
            if not self.LOCAL_JWT_SECRET:
                if self.ENVIRONMENT in ("staging", "prod"):
                    raise ValueError(
                        "LOCAL_JWT_SECRET must be set explicitly outside local/dev - a "
                        "generated per-process secret would invalidate every session on restart."
                    )
                object.__setattr__(self, "LOCAL_JWT_SECRET", secrets.token_urlsafe(48))

        if self.ENVIRONMENT == "prod" and not self.REFRESH_COOKIE_SECURE:
            raise ValueError("REFRESH_COOKIE_SECURE must stay true in production.")
        if self.REFRESH_COOKIE_SAMESITE == "none" and not self.REFRESH_COOKIE_SECURE:
            # Browsers silently drop a SameSite=None cookie that is not Secure,
            # which would look exactly like "the refresh cookie never arrives".
            raise ValueError("REFRESH_COOKIE_SAMESITE=none requires REFRESH_COOKIE_SECURE=true.")
        return self

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT == "local"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def uses_supabase(self) -> bool:
        return self.AUTH_PROVIDER == "supabase"

    @property
    def jwt_secret(self) -> str:
        """The key the API verifies incoming access tokens against."""
        return self.SUPABASE_JWT_SECRET if self.uses_supabase else self.LOCAL_JWT_SECRET  # type: ignore[return-value]

    @property
    def jwt_audience(self) -> str:
        return self.SUPABASE_JWT_AUDIENCE if self.uses_supabase else self.LOCAL_JWT_AUDIENCE


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton - avoids re-reading/validating the env on every call."""
    return Settings()  # type: ignore[call-arg]
