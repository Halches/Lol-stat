import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import ui


class AppLifecycle(unittest.TestCase):
    def test_manual_close_hides_and_keeps_current_dashboard(self):
        window=SimpleNamespace(app=SimpleNamespace(s={'dashboard':True}),withdraw=Mock())
        ui.Dashboard.close(window)
        self.assertTrue(window._manual_hidden)
        self.assertTrue(window.app.s['dashboard'])
        window.withdraw.assert_called_once()

    def test_draft_updates_do_not_reopen_but_next_draft_does(self):
        cs={'role':'MIDDLE','me':'Ahri','enemies':[],'unavailable':set(),'locked':False,'allies':[]}
        dash=Mock();dash._manual_hidden=True
        app=SimpleNamespace(draft=cs,dash=dash,role_override=None,s={'draft_scope':'pool'},lola={},draft_sig=None,player=None,data=None,status=Mock())
        ui.App.on_draft(app,cs);dash.deiconify.assert_not_called()
        app.draft=None;app.draft_sig=None
        ui.App.on_draft(app,cs);dash.deiconify.assert_called_once()
        self.assertFalse(dash._manual_hidden)

    def test_missing_player_hides_windows_and_waits(self):
        windows={k:Mock() for k in ('hints','perf','lane','timers','item','arena','inventory')}
        app=SimpleNamespace(last_game=None,result=None,hidden=False,s={'widgets':dict.fromkeys(windows,True)},ov=windows,tab={'tab':Mock()},status=Mock(),SR_ONLY=ui.App.SR_ONLY)
        app.apply_visibility=lambda:ui.App.apply_visibility(app)
        ui.App.on_game(app,SimpleNamespace(me=None,arena=False,sr=True),[],None)
        for window in windows.values():window.deiconify.assert_not_called();window.withdraw.assert_called()
        app.tab['tab'].withdraw.assert_called_once()


if __name__=='__main__':unittest.main()
