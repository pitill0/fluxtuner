from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

ARGON2_MEMORY_COST_KIB = 65536
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_BYTES = 1024

_PASSWORD_HASHER = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST_KIB,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LEN,
    salt_len=ARGON2_SALT_LEN,
    type=Type.ID,
)


class PasswordValidationError(ValueError):
    pass


def validate_password(password: str) -> None:
    if not password:
        raise PasswordValidationError("Password is required.")

    if not password.strip():
        raise PasswordValidationError("Password cannot be only whitespace.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    password_size = len(password.encode("utf-8"))
    if password_size > MAX_PASSWORD_BYTES:
        raise PasswordValidationError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
        )


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password or not password_hash:
        return False

    try:
        return _PASSWORD_HASHER.verify(password_hash, password) is True
    except (InvalidHashError, VerificationError, TypeError, ValueError):
        return False


def password_needs_rehash(password_hash: str | None) -> bool:
    if not password_hash:
        return True

    try:
        return _PASSWORD_HASHER.check_needs_rehash(password_hash)
    except (InvalidHashError, TypeError, ValueError):
        return True


def password_hash_parameters() -> dict[str, int | str]:
    return {
        "algorithm": "argon2id",
        "memory_cost_kib": ARGON2_MEMORY_COST_KIB,
        "time_cost": ARGON2_TIME_COST,
        "parallelism": ARGON2_PARALLELISM,
        "hash_len": ARGON2_HASH_LEN,
        "salt_len": ARGON2_SALT_LEN,
        "min_password_length": MIN_PASSWORD_LENGTH,
        "max_password_bytes": MAX_PASSWORD_BYTES,
    }
