# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Catalog labels exclude sensitive URL parts and respect display names."""

from fluxtuner.web.routes.subscriptions import _catalog_label


def test_explicit_catalog_name_takes_precedence() -> None:
    assert (
        _catalog_label("  Jazz Collection  ", "https://example.org/feed?secret=yes", 7)
        == "Jazz Collection"
    )


def test_fallback_never_exposes_remote_url_tokens() -> None:
    label = _catalog_label(None, "https://example.org/private/secret.m3u?token=abcdef", 3)
    assert label == "example.org"
    assert "abcdef" not in label
    assert "secret" not in label


def test_missing_url_uses_id_fallback() -> None:
    assert _catalog_label(None, "", 4) == "Catalog #4"


def test_list_owned_includes_safe_labels(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from fluxtuner.web.routes import subscriptions as routes

    conn = MagicMock()
    monkeypatch.setattr(routes.db, "connect", lambda: conn)
    monkeypatch.setattr(routes, "_profile_id", lambda *args, **kwargs: 12)
    monkeypatch.setattr(
        routes,
        "list_subscriptions",
        lambda *args, **kwargs: [
            {
                "source_id": 7,
                "display_name": "Jazz Collection",
                "catalog_url": "https://example.org/jazz?token=private",
                "revision": 2,
                "refreshed_at": None,
            },
            {
                "source_id": 8,
                "display_name": None,
                "catalog_url": "https://example.org/rock?token=secret",
                "revision": 1,
                "refreshed_at": None,
            },
        ],
    )

    result = routes._list_owned(4, None)
    assert [item["label"] for item in result] == [
        "Jazz Collection",
        "example.org",
    ]
    assert [item["source_id"] for item in result] == [7, 8]
    assert [item["revision"] for item in result] == [2, 1]
    assert all("catalog_url" not in item for item in result)
    assert "private" not in str(result)
    assert "secret" not in str(result)
    conn.close.assert_called_once()


def test_github_raw_catalog_label_is_repository_scoped() -> None:
    assert (
        _catalog_label(
            None,
            "https://raw.githubusercontent.com/user/repository/main/folder/list.m3u?token=private",
            7,
        )
        == "user/repository"
    )
    assert (
        _catalog_label(None, "https://raw.githubusercontent.com/?token=private", 8)
        == "raw.githubusercontent.com"
    )
