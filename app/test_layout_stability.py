"""A stale Configure event must not trigger another full history rebuild."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from history_ui import HistoryScreen


class HistoryLayout(unittest.TestCase):
    def view(self, width):
        view=SimpleNamespace(job=None,last_width=766,after=Mock(return_value='resize'),after_cancel=Mock(),
            winfo_exists=lambda:True,winfo_width=Mock(return_value=width),refresh=Mock())
        view.refresh_if_resized=lambda:HistoryScreen.refresh_if_resized(view)
        return view

    def test_transient_width_returning_to_original_does_not_rebuild(self):
        view=self.view(766)
        HistoryScreen.resized(view,SimpleNamespace(widget=view,width=746))
        view.after.assert_called_once()
        view.after.call_args.args[1]()
        view.refresh.assert_not_called()
        self.assertIsNone(view.job)

    def test_settled_width_change_still_rebuilds(self):
        view=self.view(746)
        HistoryScreen.resized(view,SimpleNamespace(widget=view,width=746))
        view.after.call_args.args[1]()
        view.refresh.assert_called_once()

    def test_unmeasured_width_does_not_rebuild(self):
        view=self.view(1)
        HistoryScreen.refresh_if_resized(view)
        view.refresh.assert_not_called()


if __name__=='__main__':unittest.main()
