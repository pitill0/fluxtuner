"""Contract tests for profile-scoped local station discovery."""

import pytest

from fluxtuner.core import db, profiles
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.local_station_search import search_local_stations
from fluxtuner.core.playlists import add_station_to_playlist_record
from fluxtuner.core.stations import station_key


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "library.sqlite3"
    db.init_db(path)
    with db.connect(path) as conn:
        first = profiles.get_or_create_profile(conn, "first")
        second = profiles.get_or_create_profile(conn, "second")
        conn.commit()
        yield conn, first, second


def test_union_of_favorites_and_playlist_stations(library):
    conn, first, second = library

    add_custom_station(
        conn,
        profile_id=first,
        name="Personal Radio",
        url="https://example.org/personal",
    )

    playlist_station = {
        "name": "Playlist Only",
        "url": "https://example.org/playlist",
        "tags": "ambient",
    }
    assert add_station_to_playlist_record(
        conn, "Collection", playlist_station, profile_id=first
    )

    # Adding the same stream to a playlist must not duplicate it.
    assert add_station_to_playlist_record(
        conn,
        "Collection",
        {
            "name": "Personal Radio",
            "url": "https://example.org/personal",
        },
        profile_id=first,
    )

    results = search_local_stations(conn, profile_id=first)

    assert {station_key(item) for item in results} == {
        "https://example.org/personal",
        "https://example.org/playlist",
    }
    assert len(results) == 2


def test_search_never_exposes_another_profile(library):
    conn, first, second = library

    add_custom_station(
        conn,
        profile_id=first,
        name="Private First",
        url="https://example.org/first",
    )
    add_custom_station(
        conn,
        profile_id=second,
        name="Private Second",
        url="https://example.org/second",
    )

    first_results = search_local_stations(conn, profile_id=first)
    second_results = search_local_stations(conn, profile_id=second)

    assert [station_key(item) for item in first_results] == [
        "https://example.org/first"
    ]
    assert [station_key(item) for item in second_results] == [
        "https://example.org/second"
    ]

    assert search_local_stations(
        conn, profile_id=first, query="Private Second"
    ) == []


def test_custom_names_are_searchable_without_changing_shared_identity(library):
    conn, first, second = library

    url = "https://example.org/shared"

    add_custom_station(
        conn, profile_id=first, name="My Jazz Station", url=url
    )
    add_custom_station(
        conn, profile_id=second, name="Work Radio", url=url
    )

    own = search_local_stations(
        conn, profile_id=first, query="My Jazz Station"
    )
    other = search_local_stations(
        conn, profile_id=second, query="My Jazz Station"
    )

    assert len(own) == 1
    assert station_key(own[0]) == url
    assert own[0]["custom_name"] == "My Jazz Station"
    assert other == []


@pytest.mark.parametrize("invalid_profile", [None, 0, -1, True, 999999])
def test_invalid_profile_never_falls_back_to_default(library, invalid_profile):
    conn, first, second = library

    with pytest.raises(ValueError):
        search_local_stations(conn, profile_id=invalid_profile)


def test_discovery_does_not_write_to_database(library):
    conn, first, second = library

    add_custom_station(
        conn,
        profile_id=first,
        name="Read Only",
        url="https://example.org/readonly",
    )
    conn.commit()

    before = conn.total_changes
    results = search_local_stations(conn, profile_id=first)

    assert len(results) == 1
    assert conn.total_changes == before


# N9_SECURITY_CONTRACTS


def test_favorite_tags_are_scoped_to_the_owner(library):
    from fluxtuner.core.favorites import update_favorite_record

    conn, first, second = library
    url = "https://example.org/tagged"

    add_custom_station(conn, profile_id=first, name="Jazz", url=url)
    add_custom_station(conn, profile_id=second, name="Jazz", url=url)

    assert update_favorite_record(
        conn, url, favorite_tags=["private-collection"], profile_id=first
    )

    assert len(search_local_stations(
        conn, profile_id=first, query="private-collection"
    )) == 1

    assert search_local_stations(
        conn, profile_id=second, query="private-collection"
    ) == []


def test_country_and_bitrate_filters_preserve_unknown_metadata(library):
    conn, first, _second = library

    add_station_to_playlist_record(
        conn,
        "Stations",
        {
            "name": "Spanish Jazz",
            "url": "https://example.org/es",
            "country": "Spain",
            "countrycode": "ES",
            "bitrate": 192,
        },
        profile_id=first,
    )

    add_station_to_playlist_record(
        conn,
        "Stations",
        {
            "name": "Unknown Metadata",
            "url": "https://example.org/unknown",
        },
        profile_id=first,
    )

    results = search_local_stations(
        conn, profile_id=first, country="ES", min_bitrate=128
    )

    assert [station_key(item) for item in results] == [
        "https://example.org/es"
    ]

    assert len(search_local_stations(conn, profile_id=first)) == 2


def test_ranking_and_limits_are_deterministic(library):
    conn, first, _second = library

    for name, suffix in [
        ("Jazz Collection", "collection"),
        ("Jazz", "exact"),
        ("Evening Jazz", "evening"),
    ]:
        add_custom_station(
            conn,
            profile_id=first,
            name=name,
            url=f"https://example.org/{suffix}",
        )

    first_run = search_local_stations(
        conn, profile_id=first, query="Jazz", limit=2
    )
    second_run = search_local_stations(
        conn, profile_id=first, query="Jazz", limit=2
    )

    assert [station_key(item) for item in first_run] == [
        "https://example.org/exact",
        "https://example.org/collection",
    ]
    assert first_run == second_run


def test_untrusted_station_metadata_cannot_supply_private_favorite_fields(library):
    """Station metadata must not impersonate per-profile favorite metadata."""
    from fluxtuner.core.stations import upsert_station

    conn, first, second = library
    url = "https://example.org/metadata"

    upsert_station(
        conn,
        {
            "name": "Public Station",
            "url": url,
            "custom_name": "Secret Alias",
            "favorite_tags": ["secret-tag"],
        },
    )

    add_station_to_playlist_record(
        conn,
        "Second Profile Playlist",
        {"name": "Public Station", "url": url},
        profile_id=second,
    )

    results = search_local_stations(conn, profile_id=second)
    assert len(results) == 1

    assert not results[0].get("custom_name")
    assert not results[0].get("favorite_tags")
    assert search_local_stations(
        conn, profile_id=second, query="Secret Alias"
    ) == []
    assert search_local_stations(
        conn, profile_id=second, query="secret-tag"
    ) == []


def test_search_is_scoped_to_profile_even_across_users(tmp_path):
    path = tmp_path / "users.sqlite3"
    db.init_db(path)

    with db.connect(path) as conn:
        first_user = db.get_or_create_user(conn, "discovery-user-a")
        second_user = db.get_or_create_user(conn, "discovery-user-b")

        first_profile = profiles.get_or_create_profile(
            conn, "library", user_id=first_user
        )
        second_profile = profiles.get_or_create_profile(
            conn, "library", user_id=second_user
        )

        add_custom_station(
            conn,
            profile_id=first_profile,
            name="User A Station",
            url="https://example.org/user-a",
        )
        add_custom_station(
            conn,
            profile_id=second_profile,
            name="User B Station",
            url="https://example.org/user-b",
        )

        assert [
            station_key(item)
            for item in search_local_stations(conn, profile_id=first_profile)
        ] == ["https://example.org/user-a"]

        assert [
            station_key(item)
            for item in search_local_stations(conn, profile_id=second_profile)
        ] == ["https://example.org/user-b"]


# N10_LEGACY_METADATA_CONTRACT


@pytest.mark.parametrize("membership", ["favorite", "playlist"])
def test_legacy_metadata_cannot_leak_private_fields(library, membership):
    """Search must not expose per-profile fields from shared metadata_json."""
    import json

    conn, first, second = library
    url = f"https://example.org/legacy-{membership}"

    if membership == "favorite":
        add_custom_station(
            conn,
            profile_id=second,
            name="Public Alias",
            url=url,
        )
    else:
        add_station_to_playlist_record(
            conn,
            "Legacy Collection",
            {"name": "Public Station", "url": url},
            profile_id=second,
        )

    # Deliberately inject legacy metadata AFTER persisting membership.
    # No upsert follows, so the suspicious data cannot be overwritten.
    conn.execute(
        """
        UPDATE stations
        SET metadata_json = ?
        WHERE station_key = ?
        """,
        (
            json.dumps({
                "custom_name": "Other Profile Secret",
                "favorite_tags": ["confidential-tag"],
                "source_profile_id": first,
            }),
            url,
        ),
    )

    results = search_local_stations(conn, profile_id=second)

    assert len(results) == 1
    assert station_key(results[0]) == url
    assert results[0].get("custom_name") in (
        None,
        "Public Alias" if membership == "favorite" else None,
    )
    assert not results[0].get("favorite_tags")
    assert "source_profile_id" not in results[0]

    assert search_local_stations(
        conn, profile_id=second, query="Other Profile Secret"
    ) == []

    assert search_local_stations(
        conn, profile_id=second, query="confidential-tag"
    ) == []


# N14_CODEC_CONTRACT


@pytest.mark.parametrize(
    ("mime_key", "mime_value"),
    [
        ("content_type", "audio/mpeg"),
        ("content-type", "audio/mpeg"),
        ("mime_type", "audio/mpeg"),
        ("mimetype", "audio/mpeg"),
    ],
)
def test_local_discovery_preserves_public_mime_hints(
    library, mime_key, mime_value
):
    """Known MIME hints should remain useful to specialized players."""
    import json

    from fluxtuner.core.compatibility import station_is_supported
    from fluxtuner.players.capabilities import PlayerCapabilities

    conn, first, _second = library
    url = f"https://example.org/unknown-stream-{mime_key}"

    add_custom_station(
        conn,
        profile_id=first,
        name="Codec Discovery",
        url=url,
    )

    # Insert metadata after membership, avoiding a later upsert.
    conn.execute(
        """
        UPDATE stations
        SET metadata_json = ?
        WHERE station_key = ?
        """,
        (
            json.dumps({
                mime_key: mime_value,
                "private_note": "Never expose this",
            }),
            url,
        ),
    )

    result = search_local_stations(conn, profile_id=first)

    assert len(result) == 1
    assert result[0].get(mime_key) == mime_value
    assert "private_note" not in result[0]

    mp3_player = PlayerCapabilities(
        supported_codecs=frozenset({"mp3"})
    )
    assert station_is_supported(result[0], mp3_player)


def test_local_discovery_unknown_codec_remains_unknown(library):
    from fluxtuner.core.compatibility import station_is_supported
    from fluxtuner.players.capabilities import PlayerCapabilities

    conn, first, _second = library
    add_custom_station(
        conn,
        profile_id=first,
        name="Unknown Format",
        url="https://example.org/live",
    )

    result = search_local_stations(conn, profile_id=first)
    assert len(result) == 1

    specialized = PlayerCapabilities(
        supported_codecs=frozenset({"mp3"})
    )
    general = PlayerCapabilities(general_purpose=True)

    assert not station_is_supported(result[0], specialized)
    assert station_is_supported(result[0], general)


# N16_FINAL_CONTRACTS


def test_discovery_works_with_read_only_sqlite_connection(tmp_path):
    import sqlite3

    path = tmp_path / "readonly-library.sqlite3"
    db.init_db(path)

    with db.connect(path) as conn:
        profile_id = profiles.get_or_create_profile(conn, "readonly")
        add_custom_station(
            conn,
            profile_id=profile_id,
            name="Read Only Radio",
            url="https://example.org/readonly-radio",
        )
        conn.commit()

    readonly_uri = f"{path.as_uri()}?mode=ro"
    with sqlite3.connect(readonly_uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row

        results = search_local_stations(conn, profile_id=profile_id)

        assert [station_key(item) for item in results] == [
            "https://example.org/readonly-radio"
        ]
        assert not conn.in_transaction


def test_empty_query_is_deterministic_and_respects_limit(library):
    conn, first, _second = library

    for name, suffix in (
        ("Zulu Radio", "zulu"),
        ("Alpha Radio", "alpha"),
        ("Bravo Radio", "bravo"),
    ):
        add_custom_station(
            conn,
            profile_id=first,
            name=name,
            url=f"https://example.org/{suffix}",
        )

    results = search_local_stations(
        conn, profile_id=first, query="  ", limit=2
    )

    assert [station_key(item) for item in results] == [
        "https://example.org/alpha",
        "https://example.org/bravo",
    ]
    assert results == search_local_stations(
        conn, profile_id=first, query="", limit=2
    )


def test_unknown_bitrate_does_not_satisfy_positive_minimum(library):
    conn, first, _second = library

    add_custom_station(
        conn,
        profile_id=first,
        name="Unknown Bitrate",
        url="https://example.org/unknown-bitrate",
    )

    assert len(search_local_stations(conn, profile_id=first)) == 1

    assert search_local_stations(
        conn, profile_id=first, min_bitrate=128
    ) == []
