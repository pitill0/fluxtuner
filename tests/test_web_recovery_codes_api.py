# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import create_app
from fluxtuner.web.security import CSRF_HEADER_NAME

VALID_PASSWORD = "correct horse battery staple"


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "web-recovery-codes.db")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()

    with db.connect() as conn:
        db.get_or_create_user(
            conn,
            "alice",
            password_hash=auth.hash_password(VALID_PASSWORD),
            is_active=True,
        )
        conn.commit()

    return TestClient(create_app())


def login(client: TestClient):
    return client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )


def test_first_successful_login_returns_recovery_codes_once(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first = login(client)

    assert first.status_code == 200
    first_payload = first.json()
    codes = first_payload["recovery_codes"]

    assert len(codes) == 8
    assert len(set(codes)) == 8
    assert all(code.startswith("FT-RCV-") for code in codes)

    second = login(client)

    assert second.status_code == 200
    assert "recovery_codes" not in second.json()


def test_recovery_codes_are_not_stored_in_plaintext(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = login(client)

    assert response.status_code == 200
    codes = response.json()["recovery_codes"]

    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT code_hash
            FROM web_recovery_codes
            ORDER BY id
            """
        ).fetchall()

    assert len(rows) == 8

    stored_hashes = {str(row["code_hash"]) for row in rows}

    for code in codes:
        assert code not in stored_hashes
        assert code.encode() not in db.DB_FILE.read_bytes()


NEW_PASSWORD = "new correct horse battery staple"
OTHER_PASSWORD = "other correct horse battery staple"
RECOVERY_ERROR_DETAIL = "Invalid recovery credentials."


def recover_password(
    client: TestClient,
    *,
    username: str = "alice",
    recovery_code: str,
    new_password: str = NEW_PASSWORD,
):
    return client.post(
        "/api/auth/recover-password",
        json={
            "username": username,
            "recovery_code": recovery_code,
            "new_password": new_password,
        },
    )


def test_valid_recovery_code_changes_password_and_rotates_codes(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200
    old_codes = first_login.json()["recovery_codes"]
    old_code = old_codes[0]

    recovery = recover_password(
        client,
        recovery_code=old_code,
    )

    assert recovery.status_code == 200
    payload = recovery.json()
    new_codes = payload["recovery_codes"]

    assert payload["status"] == "ok"
    assert len(new_codes) == 8
    assert len(set(new_codes)) == 8
    assert set(new_codes).isdisjoint(old_codes)

    assert client.get("/api/auth/me").status_code == 401

    old_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": NEW_PASSWORD},
    )
    assert new_login.status_code == 200
    assert "recovery_codes" not in new_login.json()


def test_old_recovery_set_is_invalid_after_successful_recovery(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    old_codes = first_login.json()["recovery_codes"]

    first_recovery = recover_password(
        client,
        recovery_code=old_codes[0],
    )
    assert first_recovery.status_code == 200

    replay = recover_password(
        client,
        recovery_code=old_codes[0],
        new_password=OTHER_PASSWORD,
    )
    sibling = recover_password(
        client,
        recovery_code=old_codes[1],
        new_password=OTHER_PASSWORD,
    )

    assert replay.status_code == 401
    assert replay.json() == {"detail": RECOVERY_ERROR_DETAIL}
    assert sibling.status_code == 401
    assert sibling.json() == {"detail": RECOVERY_ERROR_DETAIL}

    current_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": NEW_PASSWORD},
    )
    assert current_login.status_code == 200

    rejected_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": OTHER_PASSWORD},
    )
    assert rejected_login.status_code == 401


def test_invalid_recovery_credentials_are_generic_and_do_not_change_password(
    tmp_path, monkeypatch
) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200

    wrong_code = recover_password(
        client,
        recovery_code="FT-RCV-00000000-00000000-00000000-00000000",
    )
    missing_user = recover_password(
        client,
        username="missing",
        recovery_code="FT-RCV-00000000-00000000-00000000-00000000",
    )

    assert wrong_code.status_code == 401
    assert missing_user.status_code == 401
    assert wrong_code.json() == {"detail": RECOVERY_ERROR_DETAIL}
    assert missing_user.json() == {"detail": RECOVERY_ERROR_DETAIL}

    original_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert original_login.status_code == 200


def test_authenticated_user_can_regenerate_recovery_codes(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200
    original_codes = first_login.json()["recovery_codes"]
    csrf_token = first_login.json()["csrf_token"]

    response = client.post(
        "/api/auth/recovery-codes/regenerate",
        headers={CSRF_HEADER_NAME: csrf_token},
        json={"current_password": VALID_PASSWORD},
    )

    assert response.status_code == 200
    new_codes = response.json()["recovery_codes"]

    assert len(new_codes) == 8
    assert len(set(new_codes)) == 8
    assert set(new_codes).isdisjoint(original_codes)

    rejected = recover_password(
        client,
        recovery_code=original_codes[0],
        new_password=OTHER_PASSWORD,
    )
    assert rejected.status_code == 401
    assert rejected.json() == {"detail": RECOVERY_ERROR_DETAIL}


def test_recovery_code_regeneration_requires_current_password(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200
    original_codes = first_login.json()["recovery_codes"]
    csrf_token = first_login.json()["csrf_token"]

    missing_password = client.post(
        "/api/auth/recovery-codes/regenerate",
        headers={CSRF_HEADER_NAME: csrf_token},
        json={},
    )
    assert missing_password.status_code == 401
    assert "recovery_codes" not in missing_password.json()

    wrong_password = client.post(
        "/api/auth/recovery-codes/regenerate",
        headers={CSRF_HEADER_NAME: csrf_token},
        json={"current_password": "wrong horse battery staple"},
    )
    assert wrong_password.status_code == 401
    assert "recovery_codes" not in wrong_password.json()

    # Failed reauthentication must not rotate or invalidate the existing set.
    recovery = recover_password(
        client,
        recovery_code=original_codes[0],
        new_password=OTHER_PASSWORD,
    )
    assert recovery.status_code == 200


def test_recovery_code_regeneration_requires_authentication_and_csrf(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    anonymous = client.post("/api/auth/recovery-codes/regenerate")
    assert anonymous.status_code == 401

    first_login = login(client)
    assert first_login.status_code == 200

    missing_csrf = client.post("/api/auth/recovery-codes/regenerate")
    assert missing_csrf.status_code == 403


def test_same_recovery_code_cannot_be_consumed_twice(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    code = first_login.json()["recovery_codes"][0]

    first = recover_password(
        client,
        recovery_code=code,
        new_password=NEW_PASSWORD,
    )
    second = recover_password(
        client,
        recovery_code=code,
        new_password=OTHER_PASSWORD,
    )

    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json() == {"detail": RECOVERY_ERROR_DETAIL}

    valid_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": NEW_PASSWORD},
    )
    assert valid_login.status_code == 200

    rejected_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": OTHER_PASSWORD},
    )
    assert rejected_login.status_code == 401


def test_recovery_rate_limit_does_not_block_normal_login(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200

    invalid_code = "FT-RCV-00000000-00000000-00000000-00000000"

    for _ in range(5):
        response = recover_password(
            client,
            recovery_code=invalid_code,
        )
        assert response.status_code == 401
        assert response.json() == {"detail": RECOVERY_ERROR_DETAIL}

    limited = recover_password(
        client,
        recovery_code=invalid_code,
    )

    assert limited.status_code == 429
    assert limited.json() == {"detail": "Too many recovery attempts. Try again later."}

    normal_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert normal_login.status_code == 200


def test_concurrent_recovery_with_same_code_has_exactly_one_winner(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200
    code = first_login.json()["recovery_codes"][0]

    # Align the two expensive password-hash operations so both recovery
    # requests reach the database as close together as possible.
    original_hash_password = auth.hash_password
    hash_barrier = Barrier(2)

    def synchronized_hash_password(password: str) -> str:
        hash_barrier.wait(timeout=10)
        return original_hash_password(password)

    monkeypatch.setattr(auth, "hash_password", synchronized_hash_password)

    first_client = TestClient(create_app())
    second_client = TestClient(create_app())

    def recover_with(client: TestClient, password: str):
        return client.post(
            "/api/auth/recover-password",
            json={
                "username": "alice",
                "recovery_code": code,
                "new_password": password,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            recover_with,
            first_client,
            NEW_PASSWORD,
        )
        second_future = executor.submit(
            recover_with,
            second_client,
            OTHER_PASSWORD,
        )

        first = first_future.result(timeout=15)
        second = second_future.result(timeout=15)

    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [200, 401]

    loser = first if first.status_code == 401 else second
    assert loser.json() == {"detail": RECOVERY_ERROR_DETAIL}

    # Exactly one of the competing passwords became the credential.
    monkeypatch.setattr(auth, "hash_password", original_hash_password)

    first_password_login = first_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": NEW_PASSWORD},
    )
    second_password_login = second_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": OTHER_PASSWORD},
    )

    assert sorted(
        [
            first_password_login.status_code,
            second_password_login.status_code,
        ]
    ) == [200, 401]


def test_recovery_code_accepts_lowercase_compact_input(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200
    code = first_login.json()["recovery_codes"][0]

    normalized_variant = code.replace("-", "").lower()

    recovery = recover_password(
        client,
        recovery_code=normalized_variant,
    )

    assert recovery.status_code == 200
    assert recovery.json()["status"] == "ok"

    new_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": NEW_PASSWORD},
    )
    assert new_login.status_code == 200


def test_recovery_code_accepts_whitespace_and_hyphen_variants(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200
    code = first_login.json()["recovery_codes"][0]

    compact = code.replace("-", "")
    variant = f"  {compact[:10]} \n {compact[10:22]} \t {compact[22:]}  "

    recovery = recover_password(
        client,
        recovery_code=variant,
    )

    assert recovery.status_code == 200
    assert recovery.json()["status"] == "ok"


def test_malformed_recovery_codes_count_toward_rate_limit_before_password_hash(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200

    original_hash_password = auth.hash_password
    fallback_hash = original_hash_password(NEW_PASSWORD)
    hash_calls = 0

    def counted_hash_password(password: str) -> str:
        nonlocal hash_calls
        hash_calls += 1
        return fallback_hash

    monkeypatch.setattr(auth, "hash_password", counted_hash_password)

    for _ in range(5):
        response = recover_password(
            client,
            recovery_code="not-a-recovery-code",
        )
        assert response.status_code == 401
        assert response.json() == {"detail": RECOVERY_ERROR_DETAIL}

    limited = recover_password(
        client,
        recovery_code="still-not-a-recovery-code",
    )

    assert limited.status_code == 429
    assert hash_calls == 0


def test_invalid_recovery_code_rejects_before_password_hash(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200

    original_hash_password = auth.hash_password
    fallback_hash = original_hash_password(NEW_PASSWORD)
    hash_calls = 0

    def counted_hash_password(password: str) -> str:
        nonlocal hash_calls
        hash_calls += 1
        return fallback_hash

    monkeypatch.setattr(auth, "hash_password", counted_hash_password)

    response = recover_password(
        client,
        recovery_code="FT-RCV-00000000-00000000-00000000-00000000",
    )

    assert response.status_code == 401
    assert response.json() == {"detail": RECOVERY_ERROR_DETAIL}
    assert hash_calls == 0


def test_rate_limited_recovery_rejects_before_password_hash(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    first_login = login(client)
    assert first_login.status_code == 200

    invalid_code = "FT-RCV-00000000-00000000-00000000-00000000"

    for _ in range(5):
        response = recover_password(
            client,
            recovery_code=invalid_code,
        )
        assert response.status_code == 401

    original_hash_password = auth.hash_password
    fallback_hash = original_hash_password(NEW_PASSWORD)
    hash_calls = 0

    def counted_hash_password(password: str) -> str:
        nonlocal hash_calls
        hash_calls += 1
        return fallback_hash

    monkeypatch.setattr(auth, "hash_password", counted_hash_password)

    limited = recover_password(
        client,
        recovery_code=invalid_code,
    )

    assert limited.status_code == 429
    assert hash_calls == 0
