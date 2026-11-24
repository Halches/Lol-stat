import unittest
from concurrent.futures import Future
from unittest.mock import patch
import test_connection_ux as ux
import test_voice as voice
import test_desktop as desktop
from desktop.live_overlays import live_cards


class FlexTests(unittest.TestCase):
    snapshots = desktop.GameflowTests.snapshots

    def test_import_accepts_observed_stale_flow_but_refuses_changed_context(self):
        from desktop.worker import Companion
        from unittest.mock import Mock
        for flow_id, draft_id, champion, expected in ((14,15,112,True),(16,15,112,False),(14,16,112,False),(14,15,103,False)):
            with self.subTest(flow=flow_id,draft=draft_id,champion=champion):
                client=Mock(port=123,token='test')
                client.region.return_value='EUW'
                client.call.return_value=desktop.gameflow('ChampSelect',flow_id,440)
                draft={'gameId':draft_id,'localPlayerCellId':0,
                       'myTeam':[{'cellId':0,'championId':champion,'assignedPosition':'middle'}],
                       'actions':[[{'actorCellId':0,'type':'pick','championId':champion,'completed':True}]]}
                client.champ_select.return_value=draft
                client.set_runes.side_effect=lambda *args,**kwargs: bool(kwargs['draft_session']())
                client.set_items.side_effect=lambda *args,**kwargs: bool(kwargs['draft_session']())
                catalog=desktop.DraftRosterTests.catalog
                with patch('desktop.worker.read_catalog',return_value=catalog),patch.object(Companion,'update_catalog',return_value=catalog):
                    companion=Companion(client)
                self.addCleanup(companion.close)
                companion.build_key=('Viktor','MIDDLE',112,15)
                companion.draft_flow_binding=((companion.flow_generation,15),14)
                companion.build={'pick':{'variant':{'prim':8200,'sec':8000,'perks':[],'shards':[]},'sets':[]}}
                result=companion.export(list(companion.build_key),'pick')
                self.assertEqual(client.set_runes.called,expected)
                if expected:
                    self.assertEqual(result['results'],['Руны применены','Набор предметов добавлен'])
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
    def test_tab_geometry_ignores_recorded_four_pixel_jitter_and_confirms_movement(self):
        from overlay_tab import TabFrameFinder
        finder=TabFrameFinder();self.addCleanup(finder.close)
        def observed(top=465,x=315,columns=None):
            return {'frame':(x,537,x+1539,1061,top), 'teams':('ORDER','CHAOS'),
                    'columns':columns or (('A','B',None,None,None),('C','D',None,None,None)),'confidence':.9}
        finder.accept_observation(observed(),0)
        self.assertIsNone(finder.frame)
        finder.accept_observation(observed(469),.2)
        anchor=finder.frame['frame']
        for index,top in enumerate((465,469,465,469),1):
            finder.accept_observation(observed(top),.2+index*.1)
            self.assertEqual(finder.frame['frame'],anchor)
        finder.accept_observation(observed(x=500),.8)
        self.assertEqual(finder.frame['frame'],anchor)
        finder.accept_observation(observed(x=501),1.0)
        self.assertGreater(finder.frame['frame'][0],490)

    def test_tab_identity_grace_is_bounded_and_row_reorder_invalidates_cache(self):
        from overlay_tab import TabFrameFinder
        finder=TabFrameFinder();self.addCleanup(finder.close)
        def observed(columns):
            return {'frame':(315,537,1854,1061,465),'teams':('ORDER','CHAOS'),
                    'columns':columns,'confidence':.9}
        full=(('A','B'),('C','D'))
        finder.accept_observation(observed(full),0)
        finder.accept_observation(observed(full),.2)
        finder.accept_observation(observed((('A',None),('C',None))),.8)
        self.assertEqual(finder.frame['columns'],full)
        finder.accept_observation(observed((('B',None),('C',None))),1.0)
        self.assertEqual(finder.frame['columns'][0],('B',None))
        finder.accept_observation(observed((('B',None),('C',None))),2.0)
        self.assertIsNone(finder.frame['columns'][1][1])
        finder.accept_observation(None,2.1)
        self.assertIsNotNone(finder.frame)
        finder.accept_observation(None,4)
        self.assertIsNone(finder.frame)

    def test_tab_rows_follow_recognized_portraits_and_team_side(self):
        from overlays import tab_values
        live = {'myTeam':'CHAOS','players':[{'c':'A','team':'ORDER','gold':100},
                {'c':'B','team':'CHAOS','gold':300},{'c':'C','team':'ORDER','gold':500},
                {'c':'D','team':'CHAOS','gold':50}]}
        detected = {'teams':['ORDER','CHAOS'], 'columns':[['C','A',None],['B','D',None]]}
        result = tab_values(live,detected)
        self.assertFalse(result['ownLeft'])
        self.assertEqual(result['gold'],[600,350])
        self.assertEqual(result['differences'],[-200,-50,None])
        detected={'teams':['CHAOS','ORDER'],'columns':[['B','D',None],['C','A',None]]}
        result=tab_values(live,detected)
        self.assertTrue(result['ownLeft'])
        self.assertEqual(result['differences'],[-200,-50,None])

    def test_releasing_tab_discards_pending_detection(self):
        from overlay_tab import TabFrameFinder
        from unittest.mock import Mock
        finder=TabFrameFinder()
        finder.executor.shutdown(wait=True)
        finder.executor=Mock()
        pending=Future()
        finder.executor.submit.return_value=pending
        self.addCleanup(finder.close)
        with patch('overlay_tab.monotonic',return_value=0):
            finder.update((0,0,1920,1080))
        with patch('overlay_tab.monotonic',return_value=.3):
            finder.update((0,0,1920,1080))
            finder.update(None)
            pending.set_result((1,2,3,4,0))
            self.assertIsNone(finder.update(None))

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

    def test_repeated_tab_attach_does_not_resize_move_or_repaint_unchanged_window(self):
        from PySide6.QtCore import QRect
        import overlays
        surface=self.window.overlays.scoreboard
        frame=(300,300,1600,800,200)
        target=(300,167,1300,633)
        with patch.object(overlays.native,'geometry',return_value=target), \
             patch.object(overlays.native,'move') as move, \
             patch.object(surface,'resize') as resize, \
             patch.object(surface.decoration,'update') as repaint:
            for _ in range(5):
                surface.attach(QRect(0,0,1920,1080),{'x':0,'y':0},frame,overlays.THEMES[overlays.DEFAULT_THEME],1)
            move.assert_not_called();resize.assert_not_called()
            repaint.assert_called_once()

    def test_each_phrase_has_independent_output_channels_and_reset(self):
        self.call('click',control='menu_assistant')
        self.call('click',control='assistant_phrases_expand')
        self.call('set',control='assistant_phrase_hoard_voice',value=False)
        self.call('set',control='assistant_phrase_hoard_text',value=True)
        self.call('set',control='assistant_phrase_hoard_sound',value=True)
        assistant=self.window.assistant
        with patch.object(ux.checks.qt.QApplication,'beep') as beep, patch.object(assistant.player,'submit') as submit:
            assistant.deliver_phrase('hoard')
            beep.assert_called_once();submit.assert_not_called()
        self.assertIn('золота',assistant.text_message)
        model=self.call('read',model='assistant')['data']
        self.assertEqual(model['phrases']['hoard']['channels'],{'voice':False,'text':True,'sound':True})
        self.assertEqual(model['phrases']['trinket']['channels'],{'voice':True,'text':False,'sound':False})
        self.call('click',control='assistant_phrase_hoard_reset')
        model=self.call('read',model='assistant')['data']
        self.assertEqual(model['phrases']['hoard']['channels'],model['phrases']['trinket']['channels'])

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
