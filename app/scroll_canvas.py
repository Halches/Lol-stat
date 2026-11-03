"""Bounded wheel updates and Windows child-window repaint for scrollable forms."""
import os
import tkinter as tk


def repaint_children(canvas):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        redraw = ctypes.windll.user32.RedrawWindow
        redraw.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.HRGN, wintypes.UINT]
        redraw.restype = wintypes.BOOL
        # Tk moves native child windows inside the Canvas. Repaint the visible
        # subtree after Tk has processed their geometry, including covered rows.
        redraw(canvas.winfo_id(), None, None, 0x0001 | 0x0080 | 0x0100)


class ScrollCanvas(tk.Canvas):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('yscrollincrement', 24)
        super().__init__(parent, **kwargs)
        self._scroll_job = self._paint_job = None
        self._pending_units = 0
        self._wheel_remainder = 0
        self.bind('<Destroy>', self._cleanup, add='+')
        self.bind('<Configure>', lambda e: self._repaint_later(), add='+')

    def yview(self, *args):
        if args:
            self._cancel_scroll()
        result = super().yview(*args)
        if args:
            self._repaint_later()
        return result

    def yview_moveto(self, fraction):
        self._cancel_scroll()
        super().yview_moveto(fraction)
        self._repaint_later()

    def yview_scroll(self, number, what):
        if what != 'units':
            self._cancel_scroll()
            super().yview_scroll(number, what)
            self._repaint_later()
            return
        # One movement per frame; a burst must not queue hundreds of native
        # window moves. Keep at most one viewport of pending movement.
        limit = max(1, self.winfo_height() // int(self.cget('yscrollincrement')))
        self._pending_units = max(-limit, min(limit, self._pending_units + int(number)))
        if self._scroll_job is None:
            self._scroll_job = self.after(16, self._flush_scroll)

    def wheel(self, event):
        num = getattr(event, 'num', None)
        if num in (4, 5):
            units = -3 if num == 4 else 3
        else:
            self._wheel_remainder += getattr(event, 'delta', 0)
            notches = int(self._wheel_remainder / 120)
            self._wheel_remainder -= notches * 120
            units = -3 * notches
        if units:
            self.yview_scroll(units, 'units')
        return 'break'

    def _flush_scroll(self):
        self._scroll_job = None
        units, self._pending_units = self._pending_units, 0
        if units:
            super().yview_scroll(units, 'units')
            self._repaint_later()

    def _cancel_scroll(self):
        if self._scroll_job is not None:
            self.after_cancel(self._scroll_job)
        self._scroll_job = None
        self._pending_units = 0

    def _repaint_later(self):
        if os.name == 'nt' and self._paint_job is None:
            self._paint_job = self.after(16, self._repaint)

    def _repaint(self):
        self._paint_job = None
        if self.winfo_exists() and self.winfo_ismapped():
            repaint_children(self)

    def _cleanup(self, event):
        if event.widget is self:
            self._cancel_scroll()
            if self._paint_job is not None:
                self.after_cancel(self._paint_job)
            self._paint_job = None
