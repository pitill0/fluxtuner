import json
import logging
import time
from pathlib import Path

from fluxtuner.core import cache


def patch_cache_file(tmp_path: Path, monkeypatch) -> Path:
    cache_file = tmp_path / "search_cache.json"
    monkeypatch.setattr(cache, "CACHE_FILE", cache_file)
    return cache_file


def test_make_search_key_normalizes_values() -> None:
    key = cache.make_search_key(
        "  Rock ",
        country=" ES ",
        min_bitrate=128,
        limit=25,
    )

    assert key == "query=rock|country=es|min_bitrate=128|limit=25"


def test_get_cached_search_returns_none_for_missing_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_cache_file(tmp_path, monkeypatch)

    assert cache.get_cached_search("missing") is None


def test_set_and_get_cached_search_roundtrip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_cache_file(tmp_path, monkeypatch)

    results = [{"name": "Test Radio", "url": "https://example.com/stream"}]

    cache.set_cached_search("key", results)

    assert cache.get_cached_search("key") == results


def test_get_cached_search_ignores_invalid_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_file = patch_cache_file(tmp_path, monkeypatch)
    cache_file.write_text("{not-json", encoding="utf-8")

    assert cache.get_cached_search("key") is None


def test_get_cached_search_ignores_expired_entries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_file = patch_cache_file(tmp_path, monkeypatch)
    cache_file.write_text(
        json.dumps(
            {
                "key": {
                    "created_at": time.time() - 10,
                    "results": [{"name": "Old Radio"}],
                }
            }
        ),
        encoding="utf-8",
    )

    assert cache.get_cached_search("key", ttl_seconds=1) is None


def test_clear_search_cache_removes_cache_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_file = patch_cache_file(tmp_path, monkeypatch)
    cache_file.write_text("{}", encoding="utf-8")

    cache.clear_search_cache()

    assert not cache_file.exists()


def test_set_cached_search_logs_and_ignores_write_error(monkeypatch, caplog) -> None:
    def fake_write_json_atomic(*_args, **_kwargs) -> None:
        raise OSError("write failed")

    monkeypatch.setattr(cache, "write_json_atomic", fake_write_json_atomic)
    monkeypatch.setattr(cache, "_load_cache", lambda: {})

    with caplog.at_level(logging.DEBUG):
        cache.set_cached_search("key", [{"name": "Test"}])

    assert "Could not write search cache" in caplog.text


def test_get_cached_search_ignores_non_dict_cache_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_file = patch_cache_file(tmp_path, monkeypatch)
    cache_file.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

    assert cache.get_cached_search("key") is None


def test_get_cached_search_ignores_malformed_entry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_file = patch_cache_file(tmp_path, monkeypatch)
    cache_file.write_text(
        json.dumps(
            {
                "key": {
                    "created_at": "not-a-timestamp",
                    "results": [{"name": "Invalid"}],
                }
            }
        ),
        encoding="utf-8",
    )

    assert cache.get_cached_search("key") is None


def test_get_cached_search_ignores_entry_with_non_list_results(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_file = patch_cache_file(tmp_path, monkeypatch)
    cache_file.write_text(
        json.dumps(
            {
                "key": {
                    "created_at": time.time(),
                    "results": {"name": "Invalid"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert cache.get_cached_search("key") is None
