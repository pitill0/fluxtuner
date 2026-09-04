from fluxtuner.gui.tray.linux_sni import (
    DBUSMENU_INTERFACE,
    MENU_INTROSPECTION_XML,
    MENU_OBJECT_PATH,
    SNI_INTERFACE,
    SNI_OBJECT_PATH,
    TRAY_ICON_PATH,
    WATCHER_BUS_NAME,
    WATCHER_INTERFACE,
    WATCHER_OBJECT_PATH,
    LinuxStatusNotifierItem,
    introspection_xml,
)


def test_sni_introspection_contains_required_identity() -> None:
    xml = introspection_xml()
    assert SNI_INTERFACE in xml
    assert 'property name="IconName"' in xml
    assert 'property name="Status"' in xml
    assert 'method name="Activate"' in xml


def test_linux_sni_defaults_are_stable() -> None:
    tray = LinuxStatusNotifierItem(application_id="io.github.pitill0.Fluxtuner")
    assert tray.application_id == "io.github.pitill0.Fluxtuner"
    assert tray.icon_name == "io.github.pitill0.Fluxtuner"
    assert tray.fallback_icon_name == "audio-radio-symbolic"


def test_linux_sni_protocol_constants() -> None:
    assert SNI_OBJECT_PATH == "/StatusNotifierItem"
    assert WATCHER_BUS_NAME == "org.kde.StatusNotifierWatcher"
    assert WATCHER_OBJECT_PATH == "/StatusNotifierWatcher"
    assert WATCHER_INTERFACE == "org.kde.StatusNotifierWatcher"


def test_sni_menu_contract_is_exposed() -> None:
    assert MENU_OBJECT_PATH == "/MenuBar"
    assert DBUSMENU_INTERFACE == "com.canonical.dbusmenu"
    assert 'method name="GetLayout"' in MENU_INTROSPECTION_XML
    assert 'method name="GetGroupProperties"' in MENU_INTROSPECTION_XML
    assert 'method name="GetProperty"' in MENU_INTROSPECTION_XML
    assert 'method name="Event"' in MENU_INTROSPECTION_XML
    assert 'method name="EventGroup"' in MENU_INTROSPECTION_XML
    assert 'method name="AboutToShow"' in MENU_INTROSPECTION_XML
    assert 'method name="AboutToShowGroup"' in MENU_INTROSPECTION_XML
    assert 'signal name="ItemsPropertiesUpdated"' in MENU_INTROSPECTION_XML
    assert 'signal name="LayoutUpdated"' in MENU_INTROSPECTION_XML
    assert 'signal name="ItemActivationRequested"' in MENU_INTROSPECTION_XML


def test_sni_accepts_show_and_quit_callbacks() -> None:
    tray = LinuxStatusNotifierItem(
        application_id="io.github.pitill0.Fluxtuner",
        on_show=lambda: None,
        on_quit=lambda: None,
    )
    assert tray._on_show is not None
    assert tray._on_quit is not None


def test_sni_now_playing_defaults_and_stop_state() -> None:
    tray = LinuxStatusNotifierItem(
        application_id="io.github.pitill0.Fluxtuner",
        get_now_playing=lambda: "",
        can_stop=lambda: False,
    )

    assert tray._now_playing_text() == "Nothing playing"
    assert tray._stop_enabled() is False


def test_sni_now_playing_and_stop_callbacks() -> None:
    tray = LinuxStatusNotifierItem(
        application_id="io.github.pitill0.Fluxtuner",
        get_now_playing=lambda: "Radio Test",
        can_stop=lambda: True,
    )

    assert tray._now_playing_text() == "Radio Test"
    assert tray._stop_enabled() is True


def test_sni_fallback_icon_name_is_stable() -> None:
    tray = LinuxStatusNotifierItem(application_id="io.github.pitill0.Fluxtuner")

    assert tray.fallback_icon_name == "audio-radio-symbolic"


def test_sni_packaged_icon_exists() -> None:
    assert TRAY_ICON_PATH.name == "io.github.pitill0.Fluxtuner.png"
    assert TRAY_ICON_PATH.is_file()
