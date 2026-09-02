"""Linux StatusNotifierItem backend for the GTK tray integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

SNI_OBJECT_PATH = "/StatusNotifierItem"
SNI_INTERFACE = "org.kde.StatusNotifierItem"
MENU_OBJECT_PATH = "/MenuBar"
DBUSMENU_INTERFACE = "com.canonical.dbusmenu"

WATCHER_BUS_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_OBJECT_PATH = "/StatusNotifierWatcher"
WATCHER_INTERFACE = "org.kde.StatusNotifierWatcher"

SNI_INTROSPECTION_XML = f"""
<node>
  <interface name="{SNI_INTERFACE}">
    <method name="ContextMenu"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <method name="Activate"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <method name="Scroll"><arg type="i" name="delta" direction="in"/><arg type="s" name="orientation" direction="in"/></method>
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="u" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
  </interface>
</node>
"""

MENU_INTROSPECTION_XML = f"""
<node>
  <interface name="{DBUSMENU_INTERFACE}">
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{{sv}}av)" name="layout" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
  </interface>
</node>
"""


def introspection_xml() -> str:
    return SNI_INTROSPECTION_XML


class LinuxStatusNotifierItem:
    def __init__(
        self,
        *,
        application_id: str,
        icon_name: str = "audio-radio-symbolic",
        on_show: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        get_now_playing: Callable[[], str] | None = None,
        can_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.application_id = application_id
        self.icon_name = icon_name
        self._on_show = on_show
        self._on_stop = on_stop
        self._on_quit = on_quit
        self._get_now_playing = get_now_playing
        self._can_stop = can_stop
        self._connection: Any = None
        self._registration_id: int | None = None
        self._menu_registration_id: int | None = None

    def _gio_glib(self):
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        return Gio, GLib

    def _property_value(self, property_name: str):
        _gio, GLib = self._gio_glib()
        values = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "fluxtuner"),
            "Title": GLib.Variant("s", "FluxTuner"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("u", 0),
            "IconName": GLib.Variant("s", self.icon_name),
            "IconPixmap": GLib.Variant("a(iiay)", []),
            "OverlayIconName": GLib.Variant("s", ""),
            "OverlayIconPixmap": GLib.Variant("a(iiay)", []),
            "AttentionIconName": GLib.Variant("s", ""),
            "AttentionIconPixmap": GLib.Variant("a(iiay)", []),
            "AttentionMovieName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], "FluxTuner", "Internet radio")),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_OBJECT_PATH),
        }
        return values.get(property_name)

    def _menu_property_value(self, property_name: str):
        _gio, GLib = self._gio_glib()
        values = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return values.get(property_name)

    def _now_playing_text(self) -> str:
        if self._get_now_playing is None:
            return "Nothing playing"
        text = self._get_now_playing().strip()
        return text or "Nothing playing"

    def _stop_enabled(self) -> bool:
        return bool(self._can_stop is not None and self._can_stop())

    def _menu_item_properties(self, item_id: int) -> dict[str, Any]:
        _gio, GLib = self._gio_glib()
        if item_id == 1:
            return {
                "label": GLib.Variant("s", f"Now playing: {self._now_playing_text()}"),
                "enabled": GLib.Variant("b", False),
                "visible": GLib.Variant("b", True),
            }
        if item_id in (2, 5):
            return {"type": GLib.Variant("s", "separator"), "visible": GLib.Variant("b", True)}
        if item_id == 3:
            return {
                "label": GLib.Variant("s", "Show FluxTuner"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
        if item_id == 4:
            return {
                "label": GLib.Variant("s", "Stop"),
                "enabled": GLib.Variant("b", self._stop_enabled()),
                "visible": GLib.Variant("b", True),
            }
        if item_id == 6:
            return {
                "label": GLib.Variant("s", "Quit"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
        return {}

    def _menu_layout(self):
        _gio, GLib = self._gio_glib()
        children = [
            GLib.Variant("(ia{sv}av)", (item_id, self._menu_item_properties(item_id), []))
            for item_id in (1, 2, 3, 4, 5, 6)
        ]
        return (0, {"children-display": GLib.Variant("s", "submenu")}, children)

    def _on_method_call(
        self,
        _connection: object,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        _parameters: object,
        invocation: Any,
    ) -> None:
        if method_name == "Activate" and self._on_show is not None:
            self._on_show()
        invocation.return_value(None)

    def _on_get_property(
        self,
        _connection: object,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        property_name: str,
    ):
        return self._property_value(property_name)

    def _on_menu_method_call(
        self,
        _connection: object,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        parameters: Any,
        invocation: Any,
    ) -> None:
        _gio, GLib = self._gio_glib()
        if method_name == "GetLayout":
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (1, self._menu_layout())))
            return
        if method_name == "Event":
            item_id, event_id, _data, _timestamp = parameters.unpack()
            if event_id == "clicked":
                if item_id == 3 and self._on_show is not None:
                    self._on_show()
                elif item_id == 4 and self._on_stop is not None:
                    self._on_stop()
                elif item_id == 6 and self._on_quit is not None:
                    self._on_quit()
            invocation.return_value(None)
            return
        if method_name == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (True,)))
            return
        invocation.return_value(None)

    def _on_menu_get_property(
        self,
        _connection: object,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        property_name: str,
    ):
        return self._menu_property_value(property_name)

    def start(self) -> bool:
        if self._registration_id is not None:
            return True
        Gio, GLib = self._gio_glib()
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_INTROSPECTION_XML)
        menu_node = Gio.DBusNodeInfo.new_for_xml(MENU_INTROSPECTION_XML)
        registration_id = connection.register_object(
            SNI_OBJECT_PATH,
            sni_node.interfaces[0],
            self._on_method_call,
            self._on_get_property,
            None,
        )
        if not registration_id:
            return False
        menu_registration_id = connection.register_object(
            MENU_OBJECT_PATH,
            menu_node.interfaces[0],
            self._on_menu_method_call,
            self._on_menu_get_property,
            None,
        )
        if not menu_registration_id:
            connection.unregister_object(registration_id)
            return False
        try:
            connection.call_sync(
                WATCHER_BUS_NAME,
                WATCHER_OBJECT_PATH,
                WATCHER_INTERFACE,
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (SNI_OBJECT_PATH,)),
                None,
                Gio.DBusCallFlags.NONE,
                2000,
                None,
            )
        except Exception:
            connection.unregister_object(menu_registration_id)
            connection.unregister_object(registration_id)
            return False
        self._connection = connection
        self._registration_id = registration_id
        self._menu_registration_id = menu_registration_id
        return True

    def stop(self) -> None:
        if self._connection is not None and self._menu_registration_id is not None:
            self._connection.unregister_object(self._menu_registration_id)
        if self._connection is not None and self._registration_id is not None:
            self._connection.unregister_object(self._registration_id)
        self._connection = None
        self._registration_id = None
        self._menu_registration_id = None
