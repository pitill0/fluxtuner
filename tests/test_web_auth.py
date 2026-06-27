import pytest

from fluxtuner.web import auth

VALID_PASSWORD = "correct horse battery staple"


def test_hash_password_returns_argon2id_hash() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert password_hash.startswith("$argon2id$")
    assert password_hash != VALID_PASSWORD
    assert VALID_PASSWORD not in password_hash


def test_hash_password_uses_random_salt() -> None:
    first_hash = auth.hash_password(VALID_PASSWORD)
    second_hash = auth.hash_password(VALID_PASSWORD)

    assert first_hash != second_hash
    assert auth.verify_password(VALID_PASSWORD, first_hash) is True
    assert auth.verify_password(VALID_PASSWORD, second_hash) is True


def test_verify_password_accepts_correct_password() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert auth.verify_password(VALID_PASSWORD, password_hash) is True


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert auth.verify_password("wrong horse battery staple", password_hash) is False


def test_verify_password_rejects_invalid_hash() -> None:
    assert auth.verify_password(VALID_PASSWORD, "not-a-valid-hash") is False
    assert auth.verify_password(VALID_PASSWORD, None) is False
    assert auth.verify_password("", "not-a-valid-hash") is False


def test_password_needs_rehash_is_false_for_current_hash() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert auth.password_needs_rehash(password_hash) is False


def test_password_needs_rehash_is_true_for_invalid_hash() -> None:
    assert auth.password_needs_rehash("not-a-valid-hash") is True
    assert auth.password_needs_rehash(None) is True


def test_validate_password_rejects_weak_passwords() -> None:
    with pytest.raises(auth.PasswordValidationError):
        auth.validate_password("short")

    with pytest.raises(auth.PasswordValidationError):
        auth.validate_password("               ")

    with pytest.raises(auth.PasswordValidationError):
        auth.validate_password("a" * (auth.MAX_PASSWORD_BYTES + 1))


def test_password_hash_parameters_are_explicit() -> None:
    parameters = auth.password_hash_parameters()

    assert parameters == {
        "algorithm": "argon2id",
        "memory_cost_kib": 65536,
        "time_cost": 3,
        "parallelism": 4,
        "hash_len": 32,
        "salt_len": 16,
        "min_password_length": 15,
        "max_password_bytes": 1024,
    }
