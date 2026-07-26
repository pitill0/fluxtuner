from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_light_theme_defines_complete_color_tokens() -> None:
    client = TestClient(create_app())

    styles_response = client.get("/static/styles.css")
    forms_response = client.get("/static/forms.css")

    assert styles_response.status_code == 200
    assert forms_response.status_code == 200

    assert styles_response.text.count("--action-fill: #6ee7d8;") == 2
    assert "--action-fill-hover: #0e7490;" in styles_response.text

    assert "--help-text: #b8ccde;" in forms_response.text
    assert "--help-text: #47637f;" in forms_response.text
    assert "--help-text:" not in styles_response.text


def test_primary_actions_share_the_same_palette_across_themes() -> None:
    client = TestClient(create_app())

    search_css = client.get("/static/search.css").text
    auth_css = client.get("/static/auth.css").text
    station_css = client.get("/static/station-actions.css").text
    admin_css = client.get("/static/admin.css").text

    assert ".search-form button {" in search_css
    assert ".auth-form button," in auth_css
    assert ".station-actions button[data-play-station] {" in station_css
    assert ".admin-user-form button {" in admin_css

    assert 'html[data-theme="light"] .search-form button' not in search_css
    assert 'html[data-theme="light"] .auth-form button' not in auth_css
    assert 'html[data-theme="light"] .station-actions button[data-play-station]' not in station_css
    assert 'html[data-theme="light"] .admin-user-form button' not in admin_css


def test_light_theme_overrides_dark_diagnostic_and_destructive_surfaces() -> None:
    client = TestClient(create_app())

    search_css = client.get("/static/search.css").text
    station_css = client.get("/static/station-actions.css").text
    admin_css = client.get("/static/admin.css").text

    assert 'html[data-theme="light"] .search-debug-panel' in search_css
    assert 'html[data-theme="light"] .search-debug-panel div' in search_css
    assert 'html[data-theme="light"] .station-actions [data-delete-playlist]' in station_css
    assert (
        'html[data-theme="light"] .admin-user-actions [data-admin-user-action="reject"]'
        in admin_css
    )
    assert (
        'html[data-theme="light"] .admin-user-actions [data-admin-user-action="delete"]'
        in admin_css
    )
