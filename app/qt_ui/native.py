"""Граница физических координат Win32 и логических координат Qt."""
import os
from PySide6.QtCore import QPoint
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

def place_overlay(window, bounds, logical_size):
    left, top = bounds["x"], bounds["y"]
    right, bottom = left + bounds["width"], top + bounds["height"]
    if IS_WIN:
        rect = wintypes.RECT(left, top, right, bottom)
        monitor = user.MonitorFromRect(ctypes.byref(rect), 0)
        info = MonitorInfo(ctypes.sizeof(MonitorInfo))
        if not monitor or not user.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        left, top = max(left, info.monitor.left), max(top, info.monitor.top)
        right, bottom = min(right, info.monitor.right), min(bottom, info.monitor.bottom)

    try:
        # Moving to another screen can change the physical window size and DPI.
        for _ in range(2):
            current = geometry(window)
            scale = window.devicePixelRatioF() if IS_WIN else 1
            width = round(logical_size.width() * scale)
            height = round(logical_size.height() * scale)
            target_x = max(left, right - width - round(14 * scale))
            target_y = max(top, min(top + round(16 * scale), bottom - height))
            target = target_x, target_y, width, height
            if current == target:
                break
            move(window, *target)
    except OSError:
        return False
    x, y, width, height = geometry(window)
    return left <= x and x + width <= right and top <= y and y + height <= bottom

def cursor():
    if IS_WIN:
        point=wintypes.POINT();user.GetCursorPos(ctypes.byref(point));return QPoint(point.x,point.y)
    return QCursor.pos()
