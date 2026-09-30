"""Unit tests for the shared password policy and hashing - no I/O."""
from __future__ import annotations

import pytest

from app.core.passwords import (
    dummy_verify,
    hash_password,
    password_policy_errors,
    validate_password,
    verify_password,
)


@pytest.mark.parametrize("good", ["secret123", "Passw0rd", "a1" * 8])
def test_policy_accepts_compliant_passwords(good):
    assert password_policy_errors(good) == []


@pytest.mark.parametrize(
    "bad,fragment",
    [
        ("sh0rt", "at least 8"),
        ("alllettersnodigits", "one digit"),
        ("12345678", "one letter"),
        ("a1" + "x" * 200, "at most 128"),
    ],
)
def test_policy_rejects_and_explains(bad, fragment):
    problems = " ".join(password_policy_errors(bad))
    assert fragment in problems


def test_validate_password_raises_with_a_combined_message():
    with pytest.raises(ValueError) as exc:
        validate_password("abc")
    assert "at least 8" in str(exc.value) and "one digit" in str(exc.value)


def test_hash_and_verify_round_trip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("secret124", h)


def test_each_hash_is_uniquely_salted():
    assert hash_password("secret123") != hash_password("secret123")


def test_verify_against_a_corrupt_hash_is_false_not_an_exception():
    # A damaged stored hash must fail the login, never raise a 500.
    assert verify_password("secret123", "not-a-bcrypt-hash") is False


def test_bcrypt_72_byte_truncation_is_rejected_not_silently_accepted():
    # bcrypt ignores everything past 72 bytes; accepting such a password
    # would mean two different passwords unlocking the same account.
    long_password = "a1" + "x" * 100
    assert any("bytes" in p or "at most" in p for p in password_policy_errors(long_password))


def test_dummy_verify_is_callable_for_timing_equalisation():
    dummy_verify()
