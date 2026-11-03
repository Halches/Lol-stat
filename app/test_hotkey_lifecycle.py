"""Tab must hide after errors, key release, focus loss and cancelled placement."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import ui


class HotkeyLifecycle(unittest.TestCase):
    def setUp(self):
        self.app=ui.App.__new__(ui.App)
        a=self.app
        a.root=Mock();a.hidden=False;a.demo_on=False;a.demo_btn=Mock()
        a.keys_prev={'drag':False,'tab':False}
        a.s={'keys':{'mute':'ctrl+m','hide':'ctrl+h','drag':'alt','scoreboard':'tab'},
            'scoreboard':True,'tab_auto':False,'widgets':{'hints':True,'timers':False}}
        a.last_game=SimpleNamespace(me={'c':'Ahri'},arena=False,sr=True)
        a.tab={'tab':Mock()};a.ov={'hints':Mock(),'timers':Mock()}
        self.tab=a.tab['tab'];self.held=set()
        for target,value in [('ui.combo_down',lambda key:key in self.held),('ui.game_focused',True),
                             ('ui.click_through',None),('ui.log_error',None)]:
            p=patch(target,side_effect=value) if callable(value) else patch(target,return_value=value)
            p.start();self.addCleanup(p.stop)

    def test_exception_hides_tab_and_reschedules_polling(self):
        self.tab.auto_tick.side_effect=RuntimeError('render failed')
        self.held.add('tab')
        self.app.keys()
        self.tab.withdraw.assert_called()
        self.assertFalse(self.app.keys_prev['tab'])
        self.app.root.after.assert_called_once_with(40,self.app.keys)

    def test_released_tab_hides_even_without_previous_pressed_flag(self):
        self.app.keys()
        self.tab.withdraw.assert_called()
        self.tab.deiconify.assert_not_called()
        self.assertFalse(self.app.keys_prev['tab'])

    def test_focus_loss_hides_tab_while_key_is_still_down(self):
        self.held.add('tab')
        with patch('ui.game_focused',return_value=False):self.app.keys()
        self.tab.withdraw.assert_called()
        self.tab.deiconify.assert_not_called()

    def test_alt_alone_does_not_show_scoreboard(self):
        self.held.add('alt')
        self.app.keys()
        self.tab.deiconify.assert_not_called()
        self.tab.withdraw.assert_called()

    def test_scoreboard_can_open_and_close_while_alt_is_held(self):
        self.held.update(('alt','tab'))
        self.app.keys();self.tab.deiconify.assert_called()
        self.tab.reset_mock();self.held.remove('tab')
        self.app.keys();self.tab.withdraw.assert_called();self.tab.deiconify.assert_not_called()

    def test_stopping_placement_hides_tab_before_queued_previews(self):
        self.app.toggle_demo()
        queued=self.app.root.after.call_args.args[1]
        self.app.stop_demo()
        queued()
        self.assertFalse(self.app.demo_on)
        self.tab.withdraw.assert_called()
        self.tab.demo.assert_not_called()

    def test_placement_error_cancels_mode_but_keeps_hotkeys_alive(self):
        self.app.demo_on=True
        self.tab.auto_tick.side_effect=RuntimeError('detection failed')
        self.app.keys()
        self.assertFalse(self.app.demo_on)
        self.tab.withdraw.assert_called()
        self.app.root.after.assert_called_once_with(40,self.app.keys)


if __name__=='__main__':unittest.main()
