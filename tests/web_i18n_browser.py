# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Real Chromium acceptance checks; run separately from the default pytest suite."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

LOCALES = (
    "en",
    "es",
    "ca",
    "fr",
    "de",
    "zh-CN",
    "zh-TW",
    "ko",
    "ja",
    "gl",
    "eu",
    "it",
    "pl",
    "ru",
)
SELECTOR = "[data-language-select]"
USER = "[data-auth-user]"
MENU = "[data-nav-toggle]"
HEADER = "[data-app-header]"


def wait_for_server(url, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Development server exited")
        try:
            if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError("Development server did not become ready")


def set_mobile_menu(page, opened):
    """Use semantic menu state rather than transient layout geometry."""
    assert page.evaluate('matchMedia("(max-width: 58rem)").matches')
    toggle = page.locator(MENU)
    expect(toggle).to_be_visible()

    desired = str(opened).lower()
    current = toggle.get_attribute("aria-expanded")
    assert current in ("true", "false"), current

    if current != desired:
        toggle.click()

    expect(toggle).to_have_attribute("aria-expanded", desired)
    expect(page.locator(HEADER)).to_have_attribute("data-mobile-menu-open", desired)

    selector = page.locator(SELECTOR)
    if opened:
        expect(selector).to_be_visible()
    else:
        expect(selector).not_to_be_visible()


def select_language(page, language, authenticated):
    selector = page.locator(SELECTOR)
    if authenticated:
        set_mobile_menu(page, True)
    expect(selector).to_be_visible()
    assert selector.evaluate("node => parseFloat(getComputedStyle(node).fontSize)") >= 16
    selector.select_option(language)
    expect(page.locator("html")).to_have_attribute("lang", language)
    expect(selector).to_have_value(language)
    if authenticated:
        set_mobile_menu(page, False)


def geometry(page, authenticated):
    header = page.locator(HEADER).bounding_box()
    assert header is not None
    assert header["height"] <= 120, header
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if not authenticated:
        return None
    menu = page.locator(MENU).bounding_box()
    theme = page.locator("[data-theme-toggle]").bounding_box()
    assert menu is not None and theme is not None
    assert abs(menu["y"] + menu["height"] / 2 - theme["y"] - theme["height"] / 2) <= 3
    assert 0 <= header["x"] + header["width"] - menu["x"] - menu["width"] <= 20
    return menu["x"], menu["y"]


def check_mobile(page, authenticated):
    if authenticated:
        expect(page.locator(USER)).to_be_visible()
    else:
        expect(page.locator(USER)).not_to_be_visible()
    for width in (320, 375, 600):
        page.set_viewport_size({"width": width, "height": 740})
        positions = []
        for language in LOCALES:
            select_language(page, language, authenticated)
            positions.append(geometry(page, authenticated))
        if authenticated:
            first = positions[0]
            assert first is not None
            assert all(
                point is not None
                and max(abs(a - b) for a, b in zip(first, point, strict=True)) <= 2
                for point in positions
            ), positions
        print(f"PASS: {width}px, authenticated={authenticated}, {len(LOCALES)} locales")


def check_dashboard_geometry(page):
    """Cover desktop widths immediately above the sidebar breakpoint."""
    widths = (929, 930, 935, 940, 948, 960, 1024, 1280)
    page.set_viewport_size({"width": 1024, "height": 800})
    expect(page.locator("[data-dashboard-panel]")).to_be_visible()
    expect(page.locator("[data-dashboard-user-metrics] .dashboard-metric")).to_have_count(4)
    expect(page.locator("[data-dashboard-admin-metrics] .dashboard-metric")).to_have_count(6)

    for language in LOCALES:
        selector = page.locator(SELECTOR)
        expect(selector).to_be_visible()
        selector.select_option(language)
        expect(page.locator("html")).to_have_attribute("lang", language)
        for width in widths:
            page.set_viewport_size({"width": width, "height": 800})
            overflow = page.evaluate("""() => {
                const panel = document.querySelector(".dashboard-panel");
                const box = panel.getBoundingClientRect();
                const nodes = [...panel.querySelectorAll(
                    ".dashboard-grid,.dashboard-sections,.dashboard-card,"
                    + ".dashboard-metric,.panel-heading"
                )].filter(node => node.getClientRects().length);
                return {
                    page: document.documentElement.scrollWidth - innerWidth,
                    panel: Math.round(Math.max(
                        0, ...nodes.map(node =>
                            node.getBoundingClientRect().right - box.right)
                    )),
                    internal: Math.max(
                        0, ...nodes.map(node => node.scrollWidth - node.clientWidth)
                    ),
                };
            }""")
            assert max(overflow.values()) <= 1, (language, width, overflow)

    print(f"PASS: dashboard geometry, {len(widths) * len(LOCALES)} cases")


def check_viewport_transitions(page):
    """Exercise desktop-to-mobile transitions without visibility races."""
    cases = (
        (1280, 375, "es"),
        (1024, 320, "ru"),
        (929, 600, "de"),
        (940, 375, "en"),
    )

    for _ in range(5):
        for desktop, mobile, language in cases:
            page.set_viewport_size({"width": desktop, "height": 800})
            expect(page.locator(SELECTOR)).to_be_visible()
            page.set_viewport_size({"width": mobile, "height": 740})
            select_language(page, language, True)

    print(f"PASS: {len(cases) * 5} desktop-to-mobile transitions")


def check_cached_switches(page):
    page.locator(MENU).click()
    selector = page.locator(SELECTOR)
    expect(selector).to_be_visible()
    page.wait_for_load_state("networkidle")
    requests = []

    def record(request):
        requests.append(request)

    page.on("request", record)
    try:
        for language in (*LOCALES[1:], "en"):
            selector.select_option(language)
            expect(page.locator("html")).to_have_attribute("lang", language)
        page.wait_for_timeout(250)
    finally:
        page.remove_listener("request", record)
    assert not requests, [request.url for request in requests]
    page.locator(MENU).click()
    print(f"PASS: {len(LOCALES)} cached language switches without network requests")


def check_catalog_warmup(browser, url):
    """Warm catalogs independently of the DOM translation bootstrap."""
    cases = (
        ("es-ES", None, "es"),
        ("ru-RU", None, "ru"),
        ("en-US", "ru", "ru"),
        ("en-US", None, "en"),
        ("zh-Hant-HK", None, "zh-TW"),
    )

    for preference, saved, selected in cases:
        context = browser.new_context(locale=preference)
        try:
            if saved:
                context.add_init_script(f"localStorage.setItem('fluxtuner.language', '{saved}')")

            page = context.new_page()
            requests = []
            responses = []
            errors = []

            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            page.on(
                "request",
                lambda request, requests=requests: (
                    requests.append(request.url) if "/locales/" in request.url else None
                ),
            )
            page.on(
                "response",
                lambda response, responses=responses: (
                    responses.append(response.url)
                    if "/locales/" in response.url and response.ok
                    else None
                ),
            )

            page.route("**/app.js", lambda route: route.abort())
            page.route("**/js/i18n-early.js", lambda route: route.abort())

            expected = {"en.json", f"{selected}.json"}

            page.goto(url)

            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if {item.rsplit("/", 1)[-1] for item in responses} == expected:
                    break
                page.wait_for_timeout(50)

            actual = [item.rsplit("/", 1)[-1] for item in requests]

            assert set(actual) == expected, (preference, saved, actual)
            assert len(actual) == len(expected), actual
            assert {item.rsplit("/", 1)[-1] for item in responses} == expected, responses

            expect(page.locator("html")).to_have_attribute("lang", "en")
            expect(page.locator("[data-login-submit]")).to_have_text("Login")

            assert not errors, errors
            assert all("/static/build/" in item for item in requests), requests

            print(f"PASS: independent warmup, {preference}, saved={saved}")
        finally:
            context.close()


def check_early_and_fallback(browser, url):
    # Block only the application entry point: the independent bootstrap must
    # still translate the actual HTML with the preferred catalog.
    context = browser.new_context(locale="es-ES")
    try:
        page = context.new_page()
        page.route("**/app.js", lambda route: route.abort())
        page.route("**/locales/en.json", lambda route: route.abort())
        page.goto(url)
        expect(page.locator("html")).to_have_attribute("lang", "es")
        expect(page.locator("[data-login-submit]")).not_to_have_text("Login")
    finally:
        context.close()
    context = browser.new_context(locale="es-ES")
    try:
        page = context.new_page()
        page.route("**/locales/es.json", lambda route: route.abort())
        page.goto(url)
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator(SELECTOR)).to_have_value("en")
    finally:
        context.close()
    print("PASS: independent early bootstrap, missing English and missing preferred catalog")


def check_portability_errors(page):
    page.set_viewport_size({"width": 375, "height": 740})
    select_language(page, "es", True)
    page.locator(MENU).click()
    page.locator('[data-nav-group-toggle="actions"]').click()
    page.locator("[data-nav-manage-subscriptions]").click()
    expect(page.locator("[data-subscriptions-dialog]")).to_be_visible()
    field = page.locator("[data-subscriptions-url]")
    message = page.locator("[data-subscriptions-message]")
    field.fill("ftp://example.invalid/list.m3u")
    page.locator("[data-subscriptions-add]").click()
    expect(message).to_have_text("Se requiere una URL HTTP o HTTPS válida.")
    page.locator("[data-subscriptions-close]").click()
    expect(page.locator("[data-subscriptions-dialog]")).not_to_be_visible()

    page.locator(MENU).click()
    page.locator('[data-nav-group-toggle="actions"]').click()
    page.locator("[data-nav-station-import]").click()
    expect(page.locator("[data-station-import-url]")).to_be_visible()

    def unreachable(route):
        route.fulfill(
            status=502,
            json={"detail": "Could not retrieve the remote collection."},
        )

    endpoint = "**/api/stations/import/remote*"
    page.route(endpoint, unreachable)
    try:
        page.locator("[data-station-import-url]").fill("https://example.invalid/list.m3u")
        page.locator("[data-station-import-preview-button]").click()
        expect(page.locator("[data-station-import-message]")).to_have_text(
            "No se ha podido obtener la colección remota."
        )
    finally:
        page.unroute(endpoint, unreachable)
    page.locator("[data-station-import-cancel]").click()
    assert page.locator("[data-player-bar]").get_attribute("aria-live") is None
    expect(page.locator("[data-player-status]")).to_have_attribute("aria-live", "polite")
    print("PASS: translated subscription and import errors; live region scoped to status")


def check_csp_enforcement(browser, url):
    """Verify strict CSP enforcement without weakening media playback."""
    context = browser.new_context(locale="en-US")
    violations = []
    errors = []
    external_requests = []

    try:
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def record_violation(_source, event):
            violations.append(event)

        page.expose_binding("auditRecordViolation", record_violation)

        external_url = "https://csp-control.invalid/audit.svg"

        def external_image(route):
            external_requests.append(route.request.url)
            route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body=('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/>'),
            )

        page.route(external_url, external_image)

        response = page.goto(url)
        assert response is not None
        assert response.ok

        policy = response.headers["content-security-policy"]
        directives = {
            part.strip().split()[0]: part.strip().split()[1:]
            for part in policy.split(";")
            if part.strip()
        }

        assert directives["script-src"] == ["'self'"]
        assert directives["style-src"] == ["'self'"]
        assert directives["img-src"] == ["'self'"]
        assert directives["media-src"] == ["'self'", "blob:", "http:", "https:"]

        expect(page.locator("[data-login-submit]")).to_be_enabled()

        page.evaluate("""() => {
            document.addEventListener(
                "securitypolicyviolation",
                event => {
                    void window.auditRecordViolation({
                        directive: event.effectiveDirective,
                        blocked: event.blockedURI,
                        disposition: event.disposition
                    });
                }
            );
        }""")

        page.evaluate("""async () => {
            await window.auditRecordViolation({
                directive: "binding-probe"
            });
        }""")

        assert violations == [{"directive": "binding-probe"}], violations
        violations.clear()

        result = page.evaluate(
            """async external => {
            const svg = '<svg xmlns="http://www.w3.org/2000/svg" '
                + 'width="16" height="16"/>';

            function imageResult(src) {
                return new Promise(resolve => {
                    const image = new Image();

                    const timer = setTimeout(
                        () => finish(false, true),
                        5000
                    );

                    function finish(loaded, timedOut = false) {
                        clearTimeout(timer);

                        const result = {
                            loaded,
                            timedOut,
                            width: image.naturalWidth
                        };

                        image.onload = null;
                        image.onerror = null;
                        image.remove();

                        resolve(result);
                    }

                    image.onload = () => finish(true);
                    image.onerror = () => finish(false);

                    document.body.append(image);
                    image.src = src;
                });
            }

            const style = document.createElement("style");
            style.textContent =
                "#audit-style-block { opacity: 0.123 }";
            document.head.append(style);

            const block = document.createElement("div");
            block.id = "audit-style-block";
            document.body.append(block);

            const attribute = document.createElement("div");
            attribute.setAttribute("style", "opacity: 0.456");
            document.body.append(attribute);

            const cssom = document.createElement("div");
            cssom.style.opacity = "0.789";
            cssom.style.setProperty("--audit-distance", "-120px");
            document.body.append(cssom);

            const objectUrl = URL.createObjectURL(
                new Blob([svg], {type: "image/svg+xml"})
            );

            try {
                const images = await Promise.all([
                    imageResult(external),
                    imageResult(
                        "data:image/svg+xml," + encodeURIComponent(svg)
                    ),
                    imageResult(objectUrl),
                    imageResult("/static/brand-icon.webp"),
                    imageResult("/static/icons/icon-192.png"),
                    imageResult("/static/icons/icon-512.png"),
                    imageResult("/static/app-icon.png")
                ]);

                return {
                    block: getComputedStyle(block).opacity,
                    attribute: getComputedStyle(attribute).opacity,
                    cssom: getComputedStyle(cssom).opacity,
                    property: getComputedStyle(cssom)
                        .getPropertyValue("--audit-distance").trim(),
                    images
                };
            } finally {
                URL.revokeObjectURL(objectUrl);
                style.remove();
                block.remove();
                attribute.remove();
                cssom.remove();
            }
        }""",
            external_url,
        )

        assert result["block"] == "1", result
        assert result["attribute"] == "1", result
        assert result["cssom"] == "0.789", result
        assert result["property"] == "-120px", result

        images = result["images"]

        assert not any(item["timedOut"] for item in images), images

        assert all(not item["loaded"] and item["width"] == 0 for item in images[:3]), images

        assert all(item["loaded"] and item["width"] > 0 for item in images[3:]), images

        deadline = time.monotonic() + 5

        while len(violations) < 5 and time.monotonic() < deadline:
            page.wait_for_timeout(25)

        assert len(violations) == 5, violations

        styles = [item for item in violations if item["directive"].startswith("style-src")]

        blocked_images = [item for item in violations if item["directive"] == "img-src"]

        assert len(styles) == 2, styles
        assert len(blocked_images) == 3, blocked_images

        assert all(item["disposition"] == "enforce" for item in violations), violations

        for prefix in ("https://csp-control.invalid", "data", "blob"):
            assert any(item["blocked"].startswith(prefix) for item in blocked_images), (
                blocked_images
            )

        assert not external_requests, external_requests
        assert not errors, errors

        print(
            "PASS: strict CSP enforcement, five intentional blocks, "
            "local images and CSSOM preserved"
        )

    finally:
        context.close()


def check_initial_navigation_menu(browser, url):
    """Initial route restoration must not close a user-opened menu."""
    routes = (
        ("dashboard", "[data-dashboard-panel]"),
        ("explore", "[data-search-panel]"),
        ("favorites", "[data-search-panel]"),
        ("playlists", "[data-search-panel]"),
        ("history", "[data-search-panel]"),
        ("stations", "[data-search-panel]"),
        ("catalogs", "[data-search-panel]"),
        ("account", "[data-account-panel]"),
        ("admin", "[data-admin-panel]"),
    )

    for view, panel in routes:
        context = browser.new_context(
            locale="en-US",
            viewport={"width": 320, "height": 740},
            is_mobile=True,
            has_touch=True,
        )
        held = []
        errors = []
        try:
            result = context.request.post(
                f"{url}/api/auth/login",
                data={
                    "username": "audit",
                    "password": "disposable browser test password",
                },
            )
            assert result.ok, (result.status, result.text())

            page = context.new_page()
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

            dashboard_requests = []

            def hold_dashboard(route, *, dashboard_requests=dashboard_requests, held=held):
                dashboard_requests.append(route.request.url)
                if len(dashboard_requests) == 1:
                    held.append(route)
                else:
                    route.continue_()

            page.route("**/api/dashboard", hold_dashboard)

            destination = url if view == "dashboard" else f"{url}/?view={view}"

            with page.expect_request("**/api/dashboard"):
                page.goto(destination)

            expect(page.locator(USER)).to_be_visible()

            deadline = time.monotonic() + 10
            while not held and time.monotonic() < deadline:
                page.wait_for_timeout(20)

            assert len(held) == 1, view

            set_mobile_menu(page, True)

            selector = page.locator(SELECTOR)
            toggle = page.locator(MENU)

            expect(selector).to_be_visible()

            with page.expect_response(
                lambda response: response.url == f"{url}/api/dashboard" and response.ok
            ) as response:
                held.pop().continue_()

            assert response.value.finished() is None

            if view == "dashboard":
                deadline = time.monotonic() + 10
                while len(dashboard_requests) < 2 and time.monotonic() < deadline:
                    page.wait_for_timeout(20)
                assert len(dashboard_requests) >= 2

            expect(page.locator(panel)).to_be_visible()

            # Wait for the restored route's network activity to finish.
            page.wait_for_load_state("networkidle")

            assert page.url.rstrip("/") == destination.rstrip("/")

            assert toggle.get_attribute("aria-expanded") == "true", (
                "INITIAL_NAVIGATION_CLOSED_MENU",
                view,
            )

            expect(page.locator(HEADER)).to_have_attribute("data-mobile-menu-open", "true")
            expect(selector).to_be_visible()

            selector.select_option("es")

            expect(page.locator("html")).to_have_attribute("lang", "es")
            expect(selector).to_have_value("es")

            page.locator("[data-nav-dashboard]").click()

            expect(toggle).to_have_attribute("aria-expanded", "false")
            expect(selector).not_to_be_visible()
            expect(page.locator("[data-dashboard-panel]")).to_be_visible()
            page.wait_for_load_state("networkidle")

            # Explicit navigation and browser history must retain
            # their normal menu-closing semantics.
            if view == "account":
                expect(page).to_have_url(url + "/")

                set_mobile_menu(page, True)
                page.go_back()

                expect(page.locator(panel)).to_be_visible()
                expect(toggle).to_have_attribute("aria-expanded", "false")
                expect(selector).not_to_be_visible()

                set_mobile_menu(page, True)
                page.go_forward()

                expect(page.locator("[data-dashboard-panel]")).to_be_visible()
                expect(toggle).to_have_attribute("aria-expanded", "false")
                expect(selector).not_to_be_visible()

                print("PASS: browser back/forward closes mobile menu")

            select_language(page, "en", True)
            assert not errors, errors

            print(f"PASS: initial navigation preserves mobile menu: {view}")

        finally:
            for route in held:
                route.abort()
            context.close()


def run_browser(url):
    with sync_playwright() as playwright:
        executable = os.environ.get("FLUXTUNER_TEST_CHROMIUM")
        browser = playwright.chromium.launch(executable_path=executable)
        try:
            check_csp_enforcement(browser, url)
            check_catalog_warmup(browser, url)
            check_early_and_fallback(browser, url)
            for preference, locale in (
                ("de-DE", "de"),
                ("zh-Hans-TW", "zh-CN"),
                ("zh-Hant-CN", "zh-TW"),
                ("ko-KR", "ko"),
                ("ja-JP", "ja"),
                ("gl-ES", "gl"),
                ("eu-ES", "eu"),
                ("it-IT", "it"),
                ("pl-PL", "pl"),
                ("ru-RU", "ru"),
            ):
                localized = browser.new_context(locale=preference)
                try:
                    localized_page = localized.new_page()
                    localized_page.goto(url)
                    expect(localized_page.locator("html")).to_have_attribute("lang", locale)
                    expect(localized_page.locator(SELECTOR)).to_have_value(locale)
                finally:
                    localized.close()
            context = browser.new_context(
                locale="en-US",
                viewport={"width": 375, "height": 740},
                is_mobile=True,
                has_touch=True,
            )
            page = context.new_page()
            page.goto(url)
            check_mobile(page, False)
            result = context.request.post(
                f"{url}/api/setup/create-admin",
                data={"username": "audit", "password": "disposable browser test password"},
            )
            assert result.ok, (result.status, result.text())
            page.reload()
            expect(page.locator(USER)).to_be_visible()
            check_mobile(page, True)
            page.set_viewport_size({"width": 375, "height": 740})
            check_cached_switches(page)
            check_dashboard_geometry(page)
            page.set_viewport_size({"width": 375, "height": 740})
            check_portability_errors(page)
            check_viewport_transitions(page)
            select_language(page, "ca", True)
            page.reload()
            expect(page.locator("html")).to_have_attribute("lang", "ca")
            context.close()
            check_initial_navigation_menu(browser, url)
        finally:
            browser.close()


def main():
    with tempfile.TemporaryDirectory(prefix="fluxtuner-i18n-browser-") as directory:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        env = dict(os.environ)
        env.update(
            FLUXTUNER_DATA_DIR=directory,
            FLUXTUNER_WEB_SECURE_COOKIES="false",
            FLUXTUNER_WEB_VERSIONED_STATIC="1",
            FLUXTUNER_WEB_SETUP_TOKEN="",
        )
        with (Path(directory) / "server.log").open("w+") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "fluxtuner.web.app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                wait_for_server(url, process)
                run_browser(url)
            except Exception:
                log.seek(0)
                print(log.read())
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
