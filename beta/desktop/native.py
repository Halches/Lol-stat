"""Граница физических координат Win32 и логических координат Qt."""
import os
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QCursor
IS_WIN=os.name=='nt'
if IS_WIN:
    import ctypes
    from ctypes import wintypes
    user=ctypes.windll.user32
    user.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int];user.GetWindowLongW.restype=wintypes.LONG
    user.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.LONG];user.SetWindowLongW.restype=wintypes.LONG
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                    ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

    user.MonitorFromRect.argtypes = (ctypes.POINTER(wintypes.RECT), wintypes.DWORD)
    user.MonitorFromRect.restype = wintypes.HMONITOR
    user.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MonitorInfo))
    user.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user.GetAsyncKeyState.restype = ctypes.c_short

def styles(window,through):
    if not IS_WIN:return
    h=int(window.winId());style=user.GetWindowLongW(h,-20)|0x80000|0x80|0x08000000
    user.SetWindowLongW(h,-20,style|0x20 if through else style & ~0x20)

def geometry(window):
    if IS_WIN:
        rect=wintypes.RECT()
        if user.GetWindowRect(int(window.winId()),ctypes.byref(rect)):return rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top
    return window.x(),window.y(),window.width(),window.height()

def move(window,x,y,width=None,height=None):
    if IS_WIN:
        flags=0x10|0x4|(0x1 if width is None else 0)
        if not user.SetWindowPos(int(window.winId()),None,round(x),round(y),round(width or 0),round(height or 0),flags):raise ctypes.WinError()
    else:
        window.move(round(x),round(y))
        if width is not None:window.resize(round(width),round(height))

def overlay_area(bounds):
    area = QRect(bounds["x"], bounds["y"], bounds["width"], bounds["height"])
    if IS_WIN:
        rect = wintypes.RECT(area.x(), area.y(), area.right() + 1, area.bottom() + 1)
        monitor = user.MonitorFromRect(ctypes.byref(rect), 0)
        info = MonitorInfo(ctypes.sizeof(MonitorInfo))
        if not monitor or not user.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return QRect()
        display = info.monitor
        area = area.intersected(QRect(display.left, display.top,
                                     display.right - display.left, display.bottom - display.top))
    return area


def place_overlay(window, area, logical_size, position=None):
    try:
        # Moving to another screen can change the physical window size and DPI.
        for _ in range(2):
            current = geometry(window)
            scale = window.devicePixelRatioF() if IS_WIN else 1
            width = round(logical_size.width() * scale)
            height = round(logical_size.height() * scale)
            travel_x = max(0, area.width() - width)
            travel_y = max(0, area.height() - height)
            if position is None:
                offset_x = max(0, travel_x - round(14 * scale))
                offset_y = min(travel_y, round(16 * scale))
            else:
                offset_x = round(travel_x * position[0])
                offset_y = round(travel_y * position[1])
            target = area.x() + offset_x, area.y() + offset_y, width, height
            if current == target:
                break
            move(window, *target)
    except OSError:
        return False
    x, y, width, height = geometry(window)
    return area.contains(QRect(x, y, width, height))


def overlay_edit_key():
    return IS_WIN and user.GetAsyncKeyState(0x12) < 0 and user.GetAsyncKeyState(0x09) >= 0  # Alt, Tab


def scoreboard_key():
    return IS_WIN and user.GetAsyncKeyState(0x09) < 0 and user.GetAsyncKeyState(0x12) >= 0


def primary_mouse_down():
    if not IS_WIN:
        return False
    primary_button = 0x02 if user.GetSystemMetrics(23) else 0x01  # SM_SWAPBUTTON
    return user.GetAsyncKeyState(primary_button) < 0

def cursor():
    if IS_WIN:
        point=wintypes.POINT();user.GetCursorPos(ctypes.byref(point));return QPoint(point.x,point.y)
    return QCursor.pos()
