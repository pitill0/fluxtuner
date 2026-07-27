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


def test_search_primary_action_is_owned_by_shared_buttons_css() -> None:
    client = TestClient(create_app())

    buttons_css = client.get("/static/buttons.css").text
    search_css = client.get("/static/search.css").text

    assert 'html .search-form button[type="submit"] {' in buttons_css
    assert "color: #04111f;" in buttons_css
    assert "border-color: var(--action-fill);" in buttons_css
    assert "background: var(--action-fill);" in buttons_css
    assert 'html .search-form button[type="submit"]:not(:disabled):hover {' in buttons_css
    assert "border-color: var(--action-fill-hover);" in buttons_css
    assert "background: var(--action-fill-hover);" in buttons_css

    assert (
        """\\
.search-form button {
  color: #04111f;
  border-color: var(--action-fill);
  background: var(--action-fill);
}
"""
        not in search_css
    )

    assert (
        """\\
.search-form button:not(:disabled):hover {
  color: #ffffff;
  border-color: var(--action-fill-hover);
  background: var(--action-fill-hover);
}
"""
        not in search_css
    )


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
