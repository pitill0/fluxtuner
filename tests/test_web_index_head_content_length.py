"""HTTP HEAD contract for the FluxTuner Web index."""

import pytest
from fastapi.testclient import TestClient

from fluxtuner import paths
from fluxtuner.web.app import create_app


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.parametrize("encoding", ["identity", "gzip"])
def test_index_head_matches_get_representation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    versioned: bool,
    encoding: str,
) -> None:
    """HEAD must describe the GET representation without sending a body."""
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setenv(
        "FLUXTUNER_WEB_VERSIONED_STATIC",
        "1" if versioned else "0",
    )

    client = TestClient(create_app())
    headers = {"Accept-Encoding": encoding}

    get = client.get("/", headers=headers)
    head = client.head("/", headers=headers)

    assert get.status_code == 200
    assert head.status_code == 200
    assert head.content == b""

    assert int(get.headers["content-length"]) > 0
    assert head.headers["content-length"] == get.headers["content-length"]
    assert head.headers["etag"] == get.headers["etag"]
    assert head.headers["vary"] == get.headers["vary"]
    assert head.headers.get("content-encoding") == get.headers.get("content-encoding")

    conditional = client.head(
        "/",
        headers={
            **headers,
            "If-None-Match": get.headers["etag"],
        },
    )

    assert conditional.status_code == 304
    assert conditional.content == b""
    assert "content-length" not in conditional.headers
    assert conditional.headers["etag"] == get.headers["etag"]
