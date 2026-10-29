# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Real FastAPI HTTP contracts for remote catalog subscriptions."""

from __future__ import annotations

from test_web_custom_stations import login

from fluxtuner.core import db
from fluxtuner.network.remote_station_collection import ConditionalCollectionResult
from fluxtuner.web.routes import subscriptions as routes

ENDPOINT = "/api/stations/subscriptions"
URL = "https://catalog.example/radios.m3u"


def catalog(name: str, stream: str) -> bytes:
    return (f"#EXTM3U\n#EXTINF:-1,{name}\nhttps://stream.example/{stream}\n").encode()


def test_http_subscription_full_lifecycle(web_library, monkeypatch):
    client, users = web_library
    headers = login(client)

    snapshots = [catalog("First", "first")]
    downloads = []

    async def download(url, **_kwargs):
        downloads.append(url)
        return ConditionalCollectionResult(200, snapshots[-1])

    monkeypatch.setattr(routes, "_download_catalog", download)

    created = client.post(
        ENDPOINT,
        json={"url": URL},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    source = created.json()["source_id"]
    assert created.json()["revision"] == 1
    assert downloads == [URL]

    listed = client.get(ENDPOINT)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()["subscriptions"]) == 1
    item = listed.json()["subscriptions"][0]
    assert set(item) == {
        "source_id",
        "display_name",
        "label",
        "revision",
        "refreshed_at",
    }
    assert item["source_id"] == source
    assert item["display_name"] is None
    assert item["label"] == URL.split("/")[2]
    assert item["revision"] == 1
    assert "catalog_url" not in item
    assert URL not in listed.text
    assert "catalog_url" not in listed.text

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 0

    snapshots.append(catalog("Second", "second"))

    preview = client.post(
        f"{ENDPOINT}/{source}/preview",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert len(payload["added"]) == 1
    assert len(payload["removed"]) == 1

    count_before_confirmation = len(downloads)

    confirmed = client.post(
        f"{ENDPOINT}/{source}/confirm",
        params={"revision": payload["revision"]},
        headers={
            **headers,
            "X-FluxTuner-Refresh-Receipt": payload["receipt"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["revision"] == 2

    # Confirmation must use the stored snapshot, not fetch again.
    assert len(downloads) == count_before_confirmation

    replay = client.post(
        f"{ENDPOINT}/{source}/confirm",
        params={"revision": payload["revision"]},
        headers={
            **headers,
            "X-FluxTuner-Refresh-Receipt": payload["receipt"],
        },
    )
    assert replay.status_code == 409

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 0
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM remote_catalog_entries WHERE source_id = ?",
                (source,),
            ).fetchone()[0]
            == 1
        )

    deleted = client.delete(
        f"{ENDPOINT}/{source}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert client.get(ENDPOINT).json()["subscriptions"] == []

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] >= 1


def test_http_auth_and_csrf_precede_download(web_library, monkeypatch):
    client, _ = web_library

    async def unexpected(_url, **_kwargs):
        raise AssertionError("Unauthorized request caused a download")

    monkeypatch.setattr(routes, "_download_catalog", unexpected)

    assert client.get(ENDPOINT).status_code == 401

    unauthenticated = client.post(
        ENDPOINT,
        json={"url": URL},
    )
    assert unauthenticated.status_code == 401

    headers = login(client)

    missing_csrf = client.post(
        ENDPOINT,
        json={"url": URL},
    )
    assert missing_csrf.status_code == 403

    invalid_csrf = client.post(
        ENDPOINT,
        json={"url": URL},
        headers={"X-CSRF-Token": "invalid"},
    )
    assert invalid_csrf.status_code == 403

    valid_listing = client.get(ENDPOINT)
    assert valid_listing.status_code == 200

    # A valid session alone must not authorize mutation.
    assert client.post(ENDPOINT, json={"url": URL}).status_code == 403
    assert headers


def test_http_foreign_profile_cannot_access_subscription(
    web_library,
    monkeypatch,
):
    client, users = web_library
    headers = login(client)

    async def download(_url, **_kwargs):
        return ConditionalCollectionResult(200, catalog("One", "one"))

    monkeypatch.setattr(routes, "_download_catalog", download)

    created = client.post(
        ENDPOINT,
        json={"url": URL},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    source = created.json()["source_id"]

    with db.connect() as conn:
        bob_profile = db.get_or_create_profile(
            conn,
            "Bob only",
            user_id=users["bob"][0],
        )
        conn.commit()

    assert bob_profile > 0

    foreign = {"profile": "Bob only"}
    assert (
        client.get(
            ENDPOINT,
            params=foreign,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{ENDPOINT}/{source}/preview",
            params=foreign,
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"{ENDPOINT}/{source}",
            params=foreign,
            headers=headers,
        ).status_code
        == 404
    )

    assert (
        len(
            client.get(
                ENDPOINT,
            ).json()["subscriptions"]
        )
        == 1
    )


def test_http_invalid_refresh_preserves_last_snapshot(
    web_library,
    monkeypatch,
):
    client, users = web_library
    headers = login(client)
    current = [catalog("Original", "original")]

    async def download(_url, **_kwargs):
        return ConditionalCollectionResult(200, current[-1])

    monkeypatch.setattr(routes, "_download_catalog", download)

    created = client.post(
        ENDPOINT,
        json={"url": URL},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    source = created.json()["source_id"]

    current.append(b"#EXTM3U\n#EXTINF:-1,Bad\nfile:///etc/passwd\n")

    preview = client.post(
        f"{ENDPOINT}/{source}/preview",
        headers=headers,
    )
    assert preview.status_code == 409, preview.text

    with db.connect() as conn:
        row = conn.execute(
            "SELECT revision FROM remote_catalog_subscriptions WHERE source_id = ?",
            (source,),
        ).fetchone()
        assert row["revision"] == 1
        assert (
            conn.execute(
                "SELECT name FROM remote_catalog_entries WHERE source_id = ?",
                (source,),
            ).fetchone()["name"]
            == "Original"
        )
        assert users["alice"][1] > 0


def test_http_conditional_304_keeps_committed_catalog(web_library, monkeypatch):
    client, users = web_library
    headers = login(client)
    observed = []

    async def download(url, **kwargs):
        observed.append((url, kwargs))
        if len(observed) == 1:
            return ConditionalCollectionResult(
                200,
                catalog("Original", "old"),
                etag='"version-1"',
                last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
            )
        return ConditionalCollectionResult(304, None)

    monkeypatch.setattr(routes, "_download_catalog", download)

    created = client.post(
        ENDPOINT,
        json={"url": URL},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    source = created.json()["source_id"]

    with db.connect() as conn:
        before = conn.execute(
            """
            SELECT revision, etag, last_modified
            FROM remote_catalog_subscriptions
            WHERE source_id = ?
            """,
            (source,),
        ).fetchone()
        membership_before = [
            tuple(row)
            for row in conn.execute(
                """
                SELECT station_id, first_observed_at, last_observed_at
                FROM station_source_memberships
                WHERE source_id = ? ORDER BY station_id
                """,
                (source,),
            )
        ]
    assert before["revision"] == 1
    assert before["etag"] == '"version-1"'

    checked = client.post(
        f"{ENDPOINT}/{source}/preview",
        headers=headers,
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["not_modified"] is True
    assert checked.json()["revision"] == 1
    assert "receipt" not in checked.json()
    assert observed[1][1]["etag"] == '"version-1"'
    assert observed[1][1]["last_modified"] == ("Wed, 21 Oct 2015 07:28:00 GMT")

    with db.connect() as conn:
        after = conn.execute(
            """
            SELECT revision, etag, last_modified
            FROM remote_catalog_subscriptions
            WHERE source_id = ?
            """,
            (source,),
        ).fetchone()
        membership_after = [
            tuple(row)
            for row in conn.execute(
                """
                SELECT station_id, first_observed_at, last_observed_at
                FROM station_source_memberships
                WHERE source_id = ? ORDER BY station_id
                """,
                (source,),
            )
        ]
        receipts = conn.execute(
            """
            SELECT COUNT(*) FROM remote_catalog_refresh_receipts
            WHERE source_id = ?
            """,
            (source,),
        ).fetchone()[0]

    assert tuple(after) == tuple(before)
    assert membership_after == membership_before
    assert receipts == 0


def test_http_duplicate_subscription_rejected_before_download(
    web_library,
    monkeypatch,
):
    client, _ = web_library
    headers = login(client)
    called = []

    async def download(url, **_kwargs):
        called.append(url)
        return ConditionalCollectionResult(200, catalog("One", "one"))

    monkeypatch.setattr(routes, "_download_catalog", download)

    first = client.post(ENDPOINT, json={"url": URL}, headers=headers)
    assert first.status_code == 200, first.text

    duplicate = client.post(
        ENDPOINT,
        json={"url": URL},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert called == [URL]


def test_http_conditional_candidate_commits_validators_only_on_confirm(
    web_library,
    monkeypatch,
):
    client, _ = web_library
    headers = login(client)
    current = [
        ConditionalCollectionResult(
            200,
            catalog("Initial", "initial"),
            etag='"old"',
        )
    ]

    async def download(_url, **_kwargs):
        return current[-1]

    monkeypatch.setattr(routes, "_download_catalog", download)
    created = client.post(
        ENDPOINT,
        json={"url": URL},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    source = created.json()["source_id"]

    current.append(
        ConditionalCollectionResult(
            200,
            catalog("Updated", "updated"),
            etag='"new"',
        )
    )

    preview = client.post(
        f"{ENDPOINT}/{source}/preview",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    pending = preview.json()

    with db.connect() as conn:
        stored = conn.execute(
            "SELECT revision, etag FROM remote_catalog_subscriptions WHERE source_id = ?",
            (source,),
        ).fetchone()
        assert tuple(stored) == (1, '"old"')

    confirmation = client.post(
        f"{ENDPOINT}/{source}/confirm",
        params={"revision": pending["revision"]},
        headers={
            **headers,
            "X-FluxTuner-Refresh-Receipt": pending["receipt"],
        },
    )
    assert confirmation.status_code == 200, confirmation.text

    with db.connect() as conn:
        stored = conn.execute(
            "SELECT revision, etag FROM remote_catalog_subscriptions WHERE source_id = ?",
            (source,),
        ).fetchone()
        assert tuple(stored) == (2, '"new"')


def test_http_subscription_optional_display_name(web_library, monkeypatch):
    client, _users = web_library
    headers = login(client)

    async def download(_url, **_kwargs):
        return ConditionalCollectionResult(200, catalog("Named", "named"))

    monkeypatch.setattr(routes, "_download_catalog", download)
    created = client.post(
        ENDPOINT,
        json={"url": URL, "display_name": "  My radio collection  "},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    listed = client.get(ENDPOINT)
    assert listed.status_code == 200, listed.text
    item = listed.json()["subscriptions"][0]
    assert item["display_name"] == "My radio collection"
    assert item["label"] == "My radio collection"
    assert "catalog_url" not in item
    detail = client.get(f"{ENDPOINT}/{item['source_id']}/stations")
    assert detail.status_code == 200, detail.text
    assert detail.json()["label"] == "My radio collection"
