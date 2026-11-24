import unittest
from concurrent.futures import Future
from unittest.mock import patch
import test_connection_ux as ux
import test_voice as voice
import test_desktop as desktop
from desktop.live_overlays import live_cards


class FlexTests(unittest.TestCase):
    snapshots = desktop.GameflowTests.snapshots
    def test_flex_game_and_reconnect_remain_connected(self):
        playing, reconnect = self.snapshots(desktop.gameflow('InProgress', 123, 440),
                                            desktop.gameflow('Reconnect', 123, 440), home=True)
        self.assertEqual(playing['phase'], 'game')
        self.assertEqual(reconnect['phase'], 'game')
        self.assertEqual(reconnect['queueId'], 440)

    def test_flex_champ_select_enters_draft_reader(self):
        from desktop.worker import Companion
        from unittest.mock import Mock
        client = Mock(port=123, token='test')
        client.region.return_value = 'EUW'
        client.call.return_value = desktop.gameflow('ChampSelect', 123, 440)
        with patch('desktop.worker.read_catalog', return_value={}), patch.object(Companion,'update_catalog',return_value={}):
            companion = Companion(client)
        self.addCleanup(companion.close)
        with patch.object(companion, 'read_draft',return_value={'phase':'pick'}) as draft:
            self.assertEqual(companion.read_status(100)['phase'],'pick')
            draft.assert_called_once_with(100,123,None)


class LiveCardsTests(unittest.TestCase):
    def test_old_request_is_discarded_on_match_change_and_frozen_clock_is_hidden(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from desktop.live_overlays import LiveFeed
        ux.ConnectionUXTests.setUpClass()
        companion = SimpleNamespace(voice_context={'active':True,'observedAt':104,'generation':0,'gameId':2},catalog=voice.CATALOG)
        feed = LiveFeed(companion)
        feed.timer.stop()
        feed.executor.shutdown(wait=True)
        feed.executor = Mock()
        feed.executor.submit.return_value = Future()
        self.addCleanup(feed.close)
        raw = voice.snapshot(gold=100)
        old = Future();old.set_result(raw)
        feed.session = (0,1);feed.contents = {'metrics':{'lines':['old']}}
        feed.job = ((0,1),old)
        with patch('desktop.live_overlays.monotonic',return_value=104):
            feed.poll()
        self.assertEqual(feed.contents,{})
        same = Future();same.set_result(raw)
        feed.job=((0,2),same)
        feed.clock=raw['gameData']['gameTime'];feed.clock_at=100;feed.observed=104
        with patch('desktop.live_overlays.monotonic',return_value=104):
            feed.poll()
        self.assertEqual(feed.contents,{})

    def test_live_values_and_missing_input_do_not_use_samples(self):
        raw = voice.snapshot(gold=2345)
        cards = live_cards(raw, voice.CATALOG, 'TOP')
        self.assertIn('2345', str(cards['metrics']))
        self.assertIn('objectives', cards)
        self.assertEqual(live_cards(None, voice.CATALOG), {})
        raw['events']['Events'].append({'EventName':'GameEnd','EventTime':0})
        self.assertEqual(live_cards(raw, voice.CATALOG), {})


class NewSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ux.ConnectionUXTests.setUpClass()
        cls.app = ux.ConnectionUXTests.app

    setUp = ux.ConnectionUXTests.setUp
    call = ux.ConnectionUXTests.call

    def test_live_portraits_request_actual_champion_and_use_preview_dimensions(self):
        from overlay_samples import SampleCard
        card = SampleCard(self.window.artwork, {}, kind='standings')
        self.addCleanup(card.close)
        card.set_content({'title':'Стоимость предметов','lines':['Виего: 500'],
                          'visual':{'version':'16.23.1','rows':[['Viego','Виего',500,True]]}})
        card.resize(card.sizeHint())
        with patch.object(self.window.artwork,'image',return_value=ux.checks.QPixmap()) as images:
            card.grab()
        self.assertEqual(card.sizeHint().width(),232)
        images.assert_any_call('https://ddragon.leagueoflegends.com/cdn/16.23.1/img/champion/Viego.png')
        self.assertEqual(card.live_content['visual']['rows'][0][2],500)
    def test_phrase_switch_and_output_modes_through_api(self):
        self.call('click',control='menu_assistant')
        self.call('click',control='assistant_phrases_expand')
        self.call('set',control='assistant_phrase_hoard',value=False)
        assistant=self.window.assistant
        with patch.object(assistant.player,'submit') as submit:
            assistant.deliver_phrase('hoard')
            submit.assert_not_called()
        self.assertFalse(self.call('read',model='assistant')['data']['phrases']['hoard']['enabled'])
        self.call('set',control='assistant_output',value='sound')
        self.call('set',control='assistant_text',value=True)
        with patch.object(ux.checks.qt.QApplication,'beep') as beep, patch.object(assistant.player,'submit') as submit:
            self.call('click',control='assistant_test_output')
            beep.assert_called_once()
            submit.assert_not_called()
        self.assertIn('помощник готов',assistant.text_message)
        self.assertFalse(self.window.automation.dispatch({'method':'set','control':'assistant_output','value':'invalid'})['ok'])
        self.call('set',control='assistant_output',value='none')
        with patch.object(ux.checks.qt.QApplication,'beep') as beep, patch.object(assistant.player,'submit') as submit:
            self.call('click',control='assistant_test_output')
            beep.assert_not_called();submit.assert_not_called()
