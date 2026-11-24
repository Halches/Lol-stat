"""Semantic Qt controls: discover, read and operate without screen coordinates."""
from itertools import count
import math

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractSlider, QAbstractSpinBox, QApplication, QCheckBox, QComboBox,
    QDialog, QDoubleSpinBox, QLabel, QLineEdit, QScrollArea, QScrollBar, QSpinBox, QWidget,
)
from shiboken6 import isValid


class UIError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def numeric(value, *, integer=False):
    if type(value) not in (int, float) or type(value) is float and not math.isfinite(value) or integer and int(value) != value:
        raise UIError("invalid_value", "Send a finite integer." if integer else "Send a finite number.")
    return int(value) if integer else value


class UIRegistry:
    def __init__(self, window, manual):
        self.window, self.manual = window, manual
        self.ids = count(1)

    def roots(self):
        roots = {"main": self.window}
        overlays = getattr(self.window, "overlays", None)
        for key in ("drawer", "scoreboard", "preview_indicator"):
            widget = getattr(overlays, key, None)
            if isinstance(widget, QWidget) and isValid(widget):
                roots[f"overlay_{key}"] = widget
        for key, widget in getattr(overlays, "cards", {}).items():
            if isValid(widget):
                roots[f"overlay_card_{key}"] = widget
        for dialog in self.window.findChildren(QDialog):
            if isValid(dialog):
                key = dialog.property("automationWindowId")
                if not key:
                    key = f"dialog_{next(self.ids)}"
                    dialog.setProperty("automationWindowId", key)
                roots[key] = dialog
        return roots

    @staticmethod
    def internal(widget):
        if isinstance(widget, QScrollBar):
            return True
        parent = widget
        while parent is not None:
            if parent.property("automationRetired"):
                return True
            if parent is not widget and isinstance(parent, (QComboBox, QAbstractSpinBox, QAbstractSlider)):
                return True
            parent = parent.parentWidget()
        return False

    @staticmethod
    def kind(widget):
        if isinstance(widget, QCheckBox):
            return "checkbox"
        if isinstance(widget, QComboBox):
            return "choice"
        if isinstance(widget, QLineEdit):
            return "text"
        if isinstance(widget, QDoubleSpinBox):
            return "number"
        if isinstance(widget, (QSpinBox, QAbstractSlider)):
            return "integer"
        if isinstance(widget, QAbstractButton):
            return "toggle" if widget.isCheckable() else "button"
        if isinstance(widget, QScrollArea):
            return "scroll"
        return None

    def collect(self):
        result = {key: entry for key, entry in self.manual.items() if isValid(entry[1])}
        known = {widget for _label, widget, _kind in result.values()}
        for root_name, root in self.roots().items():
            for widget in [root, *root.findChildren(QWidget)]:
                kind = self.kind(widget)
                if not kind or widget in known or self.internal(widget):
                    continue
                key = widget.property("automationId")
                if not key:
                    key = f"auto_{root_name}_{kind}_{next(self.ids)}"
                    widget.setProperty("automationId", key)
                if key in result and result[key][1] is not widget:
                    raise UIError("duplicate_control", f"Duplicate UI control ID: {key}")
                title = widget.accessibleName() or (widget.text() if isinstance(widget, QAbstractButton) else
                                                    widget.placeholderText() if isinstance(widget, QLineEdit) else "")
                result[key] = title or widget.toolTip() or key, widget, kind
                known.add(widget)
        return result

    def scope(self, widget):
        for key, root in self.roots().items():
            if key != "main" and (widget is root or root.isAncestorOf(widget)):
                return key
        for name, view in getattr(self.window, "home_views", {}).items():
            if widget is view or view.isAncestorOf(widget):
                return name
        draft = getattr(self.window, "draft_screen", None)
        if isinstance(draft, QWidget) and (widget is draft or draft.isAncestorOf(widget)):
            return "draft"
        return "main"

    @staticmethod
    def available(widget):
        top = widget.window()
        return top.isVisible() and widget.isVisibleTo(top)

    def entry(self, key, title, widget, kind):
        top = widget.window()
        available = self.available(widget)
        actions = ["read", "focus"]
        if kind in ("button", "toggle", "checkbox"):
            actions.insert(0, "click")
        if kind in ("toggle", "checkbox", "choice", "text", "integer", "number"):
            actions.insert(0, "set")
        if kind == "choice":
            actions.append("select")
        if kind == "text":
            actions.append("submit")
        if kind == "scroll":
            actions.append("scroll")
        result = {"id": key, "label": title, "kind": kind, "actions": actions,
                  "scope": self.scope(widget), "visible": available and not top.isMinimized(),
                  "available": available, "enabled": widget.isEnabled(),
                  "tooltip": widget.toolTip(), "description": widget.accessibleDescription(),
                  "stableId": not key.startswith("auto_")}
        if isinstance(widget, QAbstractButton):
            result["text"] = widget.text()
            result["checkable"] = widget.isCheckable()
            if widget.isCheckable():
                result["checked"] = widget.isChecked()
        if kind in ("toggle", "checkbox"):
            result.update(inputType="boolean", value=widget.isChecked())
        elif kind == "choice":
            types = {type(widget.itemData(i)) for i in range(widget.count())} - {type(None)}
            value_type = ("string" if not types or types == {str} else "integer" if types == {int}
                          else "boolean" if types == {bool} else "number" if types <= {int, float} else "choice")
            result.update(inputType=value_type, index=widget.currentIndex(), value=widget.currentData(),
                          text=widget.currentText(), editable=widget.isEditable(), options=[
                              {"value": widget.itemData(i), "label": widget.itemText(i), "index": i,
                               "enabled": bool(widget.model().flags(widget.model().index(i, widget.modelColumn())) & Qt.ItemFlag.ItemIsEnabled)}
                              for i in range(widget.count())])
        elif kind == "text":
            password = widget.echoMode() != QLineEdit.EchoMode.Normal
            result.update(inputType="string", value=None if password else widget.text(), sensitive=password,
                          readOnly=widget.isReadOnly(), placeholder=widget.placeholderText(), maxLength=widget.maxLength())
            if key == "site" and widget.text().strip():
                try:
                    result["value"] = self.window.validated_site()
                except ValueError:
                    result["value"] = None
        elif kind in ("integer", "number"):
            result.update(inputType=kind, value=widget.value(), minimum=widget.minimum(), maximum=widget.maximum(),
                          step=widget.singleStep())
            if isinstance(widget, QDoubleSpinBox):
                result["decimals"] = widget.decimals()
            if isinstance(widget, QAbstractSpinBox):
                result["readOnly"] = widget.isReadOnly()
        elif kind == "scroll":
            result["value"] = {axis: {"value": bar.value(), "minimum": bar.minimum(), "maximum": bar.maximum(),
                                      "pageStep": bar.pageStep()} for axis, bar in
                               (("vertical", widget.verticalScrollBar()), ("horizontal", widget.horizontalScrollBar()))}
        if available:
            point = widget.mapToGlobal(QPoint())
            result["screenBounds"] = {"x": point.x(), "y": point.y(), "width": widget.width(), "height": widget.height()}
            if top is self.window:
                point = widget.mapTo(self.window, QPoint())
                result["bounds"] = {"x": point.x(), "y": point.y(), "width": widget.width(), "height": widget.height()}
        if not available:
            result["unavailableReason"] = "Hidden page, dialog or overlay. Navigate there or explicitly use allowHidden."
        elif not widget.isEnabled():
            result["unavailableReason"] = "Disabled by the current application state. Read status and tooltip."
        return result

    def catalog(self, request=None):
        request = request or {}
        entries = [self.entry(key, *entry) for key, entry in self.collect().items()]
        query, scope = request.get("query", ""), request.get("scope")
        if not isinstance(query, str):
            raise UIError("invalid_value", "query must be a string.")
        if "visibleOnly" in request and type(request["visibleOnly"]) is not bool:
            raise UIError("invalid_value", "visibleOnly must be boolean.")
        if scope is not None and not isinstance(scope, str):
            raise UIError("invalid_value", "scope must be a string.")
        return [entry for entry in entries if (not scope or entry["scope"] == scope)
                and (not request.get("visibleOnly") or entry["visible"])
                and (not query or query.casefold() in " ".join(str(entry.get(k, "")) for k in ("id", "label", "text", "tooltip")).casefold())]

    def texts(self, scope=None):
        if scope is not None and not isinstance(scope, str):
            raise UIError("invalid_value", "scope must be a string.")
        roots = self.roots()
        if scope in getattr(self.window, "home_views", {}):
            roots = {scope: self.window.home_views[scope]}
        elif scope == "draft" and isinstance(getattr(self.window, "draft_screen", None), QWidget):
            roots = {scope: self.window.draft_screen}
        elif scope in roots:
            roots = {scope: roots[scope]}
        elif scope is not None:
            raise UIError("unknown_scope", "Use a page name or an ID from windows.")
        result, seen = [], set()
        for root in roots.values():
            for widget in root.findChildren(QLabel):
                if widget in seen or not self.available(widget):
                    continue
                seen.add(widget)
                text = getattr(widget, "full_text", None) or widget.text()
                title = widget.accessibleName()
                tip = widget.toolTip()
                if text or title or tip:
                    result.append({"text": text, "label": title, "tooltip": tip,
                                   "description": widget.accessibleDescription()})
        return result

    def windows(self):
        return [{"id": key, "title": w.windowTitle() or w.accessibleName(), "visible": w.isVisible(),
                 "minimized": w.isMinimized(), "active": w.isActiveWindow(),
                 "actions": ["read", "restore", "activate", "minimize", "resize", "close"]
                 if key == "main" or isinstance(w, QDialog) else ["read"]}
                for key, w in self.roots().items()]

    def operate(self, request):
        controls = self.collect()
        key, method = request.get("control"), request["method"]
        if not isinstance(key, str) or key not in controls:
            raise UIError("unknown_control", "Read describe/state for the current control IDs.")
        if "allowHidden" in request and type(request["allowHidden"]) is not bool:
            raise UIError("invalid_value", "allowHidden must be boolean.")
        title, widget, kind = controls[key]
        if method == "read":
            return self.entry(key, title, widget, kind)
        modal = QApplication.activeModalWidget()
        if modal is not None and widget.window() is not modal:
            raise UIError("modal_open", "Close or complete the application's modal dialog first.")
        if not self.available(widget) and not request.get("allowHidden", False):
            raise UIError("control_hidden", "Navigate to this control or explicitly use allowHidden for background operation.")
        if not widget.isEnabled():
            raise UIError("control_disabled", "This control is disabled in the current application state.")
        if method == "focus":
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
        elif method == "click" and isinstance(widget, QAbstractButton):
            widget.click()
        elif method in ("set", "select"):
            self.set_value(widget, kind, request)
        elif method == "submit" and isinstance(widget, QLineEdit):
            if not widget.hasAcceptableInput():
                raise UIError("invalid_value", "Complete a valid value before submitting this field.")
            widget.returnPressed.emit()
        elif method == "scroll" and isinstance(widget, QScrollArea):
            axis = request.get("axis", "vertical")
            if axis not in ("vertical", "horizontal"):
                raise UIError("invalid_value", "axis must be vertical or horizontal.")
            bar = widget.verticalScrollBar() if axis == "vertical" else widget.horizontalScrollBar()
            value = numeric(request.get("value"), integer=True)
            if not bar.minimum() <= value <= bar.maximum():
                raise UIError("invalid_value", "Scroll value is outside the reported range.")
            bar.setValue(value)
        else:
            raise UIError("invalid_action", "Use an action listed for this control in describe/state.")
        # Scrolling is handled by Qt itself, including nested popup/overlay views.
        for area in self.roots().values():
            for scroll in area.findChildren(QScrollArea):
                if self.available(widget) and scroll.widget() and scroll.widget().isAncestorOf(widget) and method != "scroll":
                    scroll.ensureWidgetVisible(widget)
        return None

    @staticmethod
    def set_value(widget, kind, request):
        if "value" not in request and not (kind == "choice" and "index" in request):
            raise UIError("invalid_request", "Provide value (or index for a choice).")
        value = request.get("value")
        if kind in ("checkbox", "toggle"):
            if type(value) is not bool:
                raise UIError("invalid_value", "Send true or false.")
            if widget.isChecked() != value:
                group = widget.group()
                if not value and (widget.autoExclusive() or group is not None and group.exclusive()):
                    raise UIError("invalid_action", "Select another option in this exclusive button group.")
                widget.click()
        elif kind == "choice":
            if "index" in request:
                index = numeric(request["index"], integer=True)
            else:
                index = next((i for i in range(widget.count()) if type(widget.itemData(i)) is type(value)
                              and widget.itemData(i) == value), -1)
            if index < 0 or index >= widget.count():
                raise UIError("invalid_value", "Select one of the reported option values or indices.")
            flags = widget.model().flags(widget.model().index(index, widget.modelColumn()))
            if not flags & Qt.ItemFlag.ItemIsEnabled or not flags & Qt.ItemFlag.ItemIsSelectable:
                raise UIError("control_disabled", "This option is disabled.")
            widget.setCurrentIndex(index)
            if isValid(widget) and widget.currentIndex() == index:
                widget.activated.emit(index)
        elif kind == "text":
            if widget.isReadOnly():
                raise UIError("control_disabled", "This field is read-only.")
            if not isinstance(value, str) or len(value) > widget.maxLength():
                raise UIError("invalid_value", "Send text within maxLength.")
            validator = widget.validator()
            if validator is not None and validator.validate(value, len(value))[0] == QValidator.State.Invalid:
                raise UIError("invalid_value", "This text is rejected by the field validator.")
            widget.setText(value)
            if isValid(widget) and widget.text() == value:
                widget.textEdited.emit(value)
        elif kind in ("integer", "number"):
            if isinstance(widget, QAbstractSpinBox) and widget.isReadOnly():
                raise UIError("control_disabled", "This numeric field is read-only.")
            value = numeric(value, integer=kind == "integer")
            if not widget.minimum() <= value <= widget.maximum():
                raise UIError("invalid_value", "Value is outside the reported range.")
            if isinstance(widget, QDoubleSpinBox) and abs(round(value, widget.decimals()) - value) > 1e-9:
                raise UIError("invalid_value", "Value exceeds the reported decimal precision.")
            widget.setValue(value)
        else:
            raise UIError("invalid_action", "This control does not support set/select.")
