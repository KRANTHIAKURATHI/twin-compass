"""
Password hashing and the single shared password policy.

One definition of "is this password acceptable", imported by both the
register and the reset-password schemas. Previously register enforced
letter+digit while reset-password enforced only a length floor, so a user
could register under the policy and then reset their way straight out of it.
"""
from __future__ import annotations

import bcrypt

from app.core.config import get_settings

# bcrypt silently truncates at 72 bytes; rejecting longer input is clearer
# than accepting a password whose tail is ignored.
BCRYPT_MAX_BYTES = 72


def password_policy_errors(password: str) -> list[str]:
    """Every way the password fails the policy, for a single useful message."""
    s = get_settings()
    problems: list[str] = []
    if len(password) < s.PASSWORD_MIN_LENGTH:
        problems.append(f"be at least {s.PASSWORD_MIN_LENGTH} characters")
    if len(password) > s.PASSWORD_MAX_LENGTH:
        problems.append(f"be at most {s.PASSWORD_MAX_LENGTH} characters")
    if s.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        problems.append("contain at least one digit")
    if s.PASSWORD_REQUIRE_LETTER and not any(c.isalpha() for c in password):
        problems.append("contain at least one letter")
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        problems.append(f"be at most {BCRYPT_MAX_BYTES} bytes once encoded")
    return problems


def validate_password(password: str) -> str:
    problems = password_policy_errors(password)
    if problems:
        raise ValueError("Password must " + ", ".join(problems) + ".")
    return password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed stored hash - treat as a failed login, never a 500.
        return False


# A pre-computed hash of a throwaway value. Verifying against this when the
# email is unknown keeps the response time of "no such user" indistinguishable
# from "wrong password", closing the timing side channel that would otherwise
# let an attacker enumerate registered addresses.
_DUMMY_HASH = hash_password("not-a-real-password-0")


def dummy_verify() -> None:
    verify_password("not-a-real-password-0", _DUMMY_HASH)
