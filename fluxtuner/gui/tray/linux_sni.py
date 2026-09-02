"""Linux StatusNotifierItem backend for FluxTuner GTK."""

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
    <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
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
      <arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
      <arg type="u" direction="out"/><arg type="(ia{{sv}}av)" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/>
    </method>
    <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
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
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self.application_id = application_id
        self.icon_name = icon_name
        self._on_show = on_show
        self._on_quit = on_quit
        self._connection: Any = None
        self._registration_id: int | None = None
        self._menu_registration_id: int | None = None

    def _gio_glib(self):
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        return Gio, GLib

    def _property_value(self, name: str):
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
        return values.get(name)

    def _menu_property_value(self, name: str):
        _gio, GLib = self._gio_glib()
        values = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return values.get(name)

    def _menu_item_properties(self, item_id: int) -> dict[str, Any]:
        _gio, GLib = self._gio_glib()
        if item_id == 1:
            return {
                "label": GLib.Variant("s", "Show FluxTuner"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
        if item_id == 2:
            return {"type": GLib.Variant("s", "separator"), "visible": GLib.Variant("b", True)}
        if item_id == 3:
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
            for item_id in (1, 2, 3)
        ]
        return (0, {"children-display": GLib.Variant("s", "submenu")}, children)

    def _on_method_call(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        method_name,
        _parameters,
        invocation,
    ) -> None:
        if method_name == "Activate" and self._on_show is not None:
            self._on_show()
        invocation.return_value(None)

    def _on_get_property(self, _connection, _sender, _object_path, _interface_name, property_name):
        return self._property_value(property_name)

    def _on_menu_method_call(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        method_name,
        parameters,
        invocation,
    ) -> None:
        _gio, GLib = self._gio_glib()
        if method_name == "GetLayout":
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (1, self._menu_layout())))
            return
        if method_name == "Event":
            item_id, event_id, _data, _timestamp = parameters.unpack()
            if event_id == "clicked":
                if item_id == 1 and self._on_show is not None:
                    self._on_show()
                elif item_id == 3 and self._on_quit is not None:
                    self._on_quit()
            invocation.return_value(None)
            return
        if method_name == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
            return
        invocation.return_value(None)

    def _on_menu_get_property(
        self, _connection, _sender, _object_path, _interface_name, property_name
    ):
        return self._menu_property_value(property_name)

    def start(self) -> bool:
        if self._registration_id is not None:
            return True
        Gio, GLib = self._gio_glib()
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_INTROSPECTION_XML)
        menu_node = Gio.DBusNodeInfo.new_for_xml(MENU_INTROSPECTION_XML)
        reg = connection.register_object(
            SNI_OBJECT_PATH,
            sni_node.interfaces[0],
            self._on_method_call,
            self._on_get_property,
            None,
        )
        if not reg:
            return False
        menu_reg = connection.register_object(
            MENU_OBJECT_PATH,
            menu_node.interfaces[0],
            self._on_menu_method_call,
            self._on_menu_get_property,
            None,
        )
        if not menu_reg:
            connection.unregister_object(reg)
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
            connection.unregister_object(menu_reg)
            connection.unregister_object(reg)
            return False
        self._connection = connection
        self._registration_id = reg
        self._menu_registration_id = menu_reg
        return True

    def stop(self) -> None:
        if self._connection is not None and self._menu_registration_id is not None:
            self._connection.unregister_object(self._menu_registration_id)
        if self._connection is not None and self._registration_id is not None:
            self._connection.unregister_object(self._registration_id)
        self._connection = None
        self._registration_id = None
        self._menu_registration_id = None
