"""A stale Configure event must not trigger another full history rebuild."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from history_ui import HistoryScreen, MatchWindow


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

    def test_settled_width_change_still_rebuilds(self):
        view=self.view(746)
        HistoryScreen.resized(view,SimpleNamespace(widget=view,width=746))
        view.after.call_args.args[1]()
        view.refresh.assert_called_once()

    def test_unmeasured_width_does_not_rebuild(self):
        view=self.view(1)
        HistoryScreen.refresh_if_resized(view)
        view.refresh.assert_not_called()


class MatchLayout(unittest.TestCase):
    def view(self,width):
        view=SimpleNamespace(job='resize',closed=False,last_width=1200,winfo_exists=lambda:True,
            cv=SimpleNamespace(winfo_width=lambda:width),app=SimpleNamespace(fs=lambda n:n),
            render=Mock(),fluid_labels=[Mock()])
        view.layout_mode=lambda w:MatchWindow.layout_mode(view,w)
        return view

    def test_width_change_with_same_layout_keeps_participant_cards(self):
        view=self.view(1223)
        MatchWindow.render_if_resized(view)
        view.render.assert_not_called()
        self.assertEqual(view.last_width,1223)
        view.fluid_labels[0].configure.assert_called_once_with(wraplength=1153)

    def test_structural_breakpoints_still_rebuild(self):
        for width in (1140,840,570):
            view=self.view(width)
            MatchWindow.render_if_resized(view)
            view.render.assert_called_once()

    def test_stale_event_and_closed_window_do_not_rebuild(self):
        for width in (1,1200):
            view=self.view(width);MatchWindow.render_if_resized(view)
            view.render.assert_not_called()
        view=self.view(800);view.closed=True
        MatchWindow.render_if_resized(view);view.render.assert_not_called()
        self.assertIsNone(view.job)



if __name__=='__main__':unittest.main()
