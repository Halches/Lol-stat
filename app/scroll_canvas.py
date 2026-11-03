"""Scroll embedded forms by moving their window, without Canvas pixel-copy scrolling."""
import tkinter as tk


class ScrollCanvas(tk.Canvas):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('yscrollincrement', 24)
        self._scrollbar = kwargs.pop('yscrollcommand', None)
        self._offset = 0
        self._content_window = None
        self._origin = (0, 0)
        self._region = (0, 0, 0, 0)
        self._scroll_job = None
        self._pending_units = self._wheel_remainder = 0
        super().__init__(parent, **kwargs)
        self.bind('<Destroy>', self._cleanup, add='+')
        self.bind('<Configure>', lambda e: self._move_to(self._offset), add='+')

    def create_window(self, *args, **kwargs):
        window = super().create_window(*args, **kwargs)
        self._content_window = window
        self._origin = tuple(super().coords(window))
        return window

    def bbox(self, *args):
        box = super().bbox(*args)
        if box and args == ('all',):
            # Callers measure content height after Configure. Its logical extent
            # must stay fixed even though the embedded window has moved upward.
            return (box[0], box[1] + self._offset, box[2], box[3] + self._offset)
        return box

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
            cnf = None
        changed = False
        if 'yscrollcommand' in kwargs:
            self._scrollbar = kwargs.pop('yscrollcommand')
            changed = True
        if 'scrollregion' in kwargs:
            value = kwargs.pop('scrollregion')
            if value:
                self._region = tuple(map(float, self.tk.splitlist(value)))
            else:
                self._region = (0, 0, 0, 0)
            changed = True
        result = super().configure(cnf, **kwargs) if cnf is not None or kwargs or not changed else None
        if changed:
            self._move_to(self._offset)
        return result

    config = configure

    def _height(self):
        return max(1, self._region[3] - self._region[1])

    def yview(self, *args):
        if not args:
            height = self._height()
            return self._offset / height, min(1., (self._offset + self.winfo_height()) / height)
        if args[0] == 'moveto':
            self.yview_moveto(float(args[1]))
        elif args[0] == 'scroll':
            self.yview_scroll(int(args[1]), args[2])
        else:
            raise tk.TclError('Unknown scroll operation: ' + str(args[0]))

    def canvasy(self, screeny, gridspacing=None):
        value = float(screeny) + self._offset
        return round(value / float(gridspacing)) * float(gridspacing) if gridspacing else value

    def yview_moveto(self, fraction):
        self._cancel_scroll()
        self._move_to(float(fraction) * self._height())

    def yview_scroll(self, number, what):
        if what == 'pages':
            self._cancel_scroll()
            self._move_to(self._offset + int(number) * max(1, self.winfo_height() * .9))
            return
        if what != 'units':
            raise tk.TclError('Unknown scroll unit: ' + str(what))
        increment = max(1, int(self.cget('yscrollincrement')))
        limit = max(1, self.winfo_height() // increment)
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

    def _move_to(self, offset):
        offset = round(max(0, min(offset, max(0, self._height() - self.winfo_height()))))
        if offset != self._offset:
            self._offset = offset
            if self._content_window is not None:
                # Do not call Tk's canvas yview: on Windows it copies old pixels
                # while moving a complex native widget subtree. Moving the item
                # instead lets Tk repaint its newly exposed children normally.
                super().coords(self._content_window, self._origin[0], self._origin[1] - offset)
        if self._scrollbar:
            if callable(self._scrollbar):
                self._scrollbar(*self.yview())
            else:
                self.tk.call(self._scrollbar, *self.yview())

    def _flush_scroll(self):
        self._scroll_job = None
        units, self._pending_units = self._pending_units, 0
        if units:
            self._move_to(self._offset + units * max(1, int(self.cget('yscrollincrement'))))

    def _cancel_scroll(self):
        if self._scroll_job is not None:
            self.after_cancel(self._scroll_job)
        self._scroll_job = None
        self._pending_units = 0

    def _cleanup(self, event):
        if event.widget is self:
            self._cancel_scroll()
