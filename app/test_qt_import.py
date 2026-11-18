"""Client export snapshots, failures and cancellation, with no Tk display or network."""
import io
import queue
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app_services as services


class QtServiceImportTests(unittest.TestCase):
    def app(self, fail_items=False, blocked=False):
        app = object.__new__(services.ApplicationServices)
        app.draft = {'me': 'Ahri', 'role': 'MIDDLE'}
        app.player = SimpleNamespace()
        app.s = {'rune_pick': 'win'}
        app.account = {'id': 7}
        app.data = SimpleNamespace(cn=lambda c: c, ids={'103': 'Ahri'})
        app.last_game = None
        app.imported = None
        app.role_override = None
        app.messages, app.calls = [], []
        app.set_import_msg = app.messages.append
        callbacks = queue.Queue()
        app.root = SimpleNamespace(after=lambda delay, fn: callbacks.put(fn))
        entered, release = threading.Event(), threading.Event()
        if not blocked: release.set()
        def runes(*args):
            app.calls.append(('runes', args, threading.get_ident()))
            entered.set()
            self.assertTrue(release.wait(2))
            return True
        def items(*args):
            app.calls.append(('items', args, threading.get_ident()))
            return not fail_items
        app.client = SimpleNamespace(last_error='', set_runes=runes, set_items=items)
        base = {'prim':8100, 'sec':8200, 'perks':[8112], 'shards':[],
                'start':[1056], 'core':[6655], 'i4':[], 'i5':[], 'i6':[]}
        win = dict(base, perks=[8214], core=[3118])
        app.lola_build = lambda champion, role: {'pick': base, 'win': win}
        return app, callbacks, entered, release

    def test_selected_variant_and_item_order_are_exported_off_ui_thread(self):
        app, callbacks, _, _ = self.app()
        main_thread = threading.get_ident()
        app.do_import(('runes', 'items'))
        callbacks.get(timeout=2)()
        self.assertEqual(app.calls[0][1][3], [8214])
        self.assertIn('лучший винрейт', app.calls[1][1][2][0][0])
        self.assertTrue(all(call[2] != main_thread for call in app.calls))
        self.assertEqual(app.imported, 'Ahri')

    def test_partial_failure_never_claims_complete_success(self):
        app, callbacks, _, _ = self.app(fail_items=True)
        with patch.object(services, 'log_error'):
            app.do_import(('runes', 'items'))
            callbacks.get(timeout=2)()
        self.assertIsNone(app.imported)
        self.assertIn('Руны: применено', app.messages[-1])
        self.assertIn('Предметы: не получилось', app.messages[-1])

    def test_manual_import_uses_desktop_selection(self):
        app, callbacks, _, _ = self.app()
        app.s['auto_parts'] = dict(runes=True, items=False, spells=False)
        app.do_import()
        callbacks.get(timeout=2)()
        self.assertEqual([part for part, *_ in app.calls], ['runes'])

    def test_auto_retries_only_unconfirmed_parts_on_same_locked_pick(self):
        app, callbacks, _, _ = self.app(fail_items=True)
        app.s.update(auto_import=True, auto_parts=dict(runes=True, items=True, spells=False))
        app.draft['locked'] = True
        with patch.object(services, 'log_error'):
            app.auto_import_locked(app.draft)
            callbacks.get(timeout=2)()
            self.assertIsNone(app.imported)
            app.client.set_items = lambda *args: app.calls.append(('items', args)) or True
            app.auto_import_locked(app.draft)
            callbacks.get(timeout=2)()
            app.auto_import_locked(app.draft)
        self.assertEqual([c[0] for c in app.calls], ['runes', 'items', 'items'])
        self.assertEqual(app.imported, 'Ahri')

    def test_auto_waits_for_requested_build_without_importing_personal_runes(self):
        app, callbacks, _, _ = self.app()
        app.s.update(auto_import=True, auto_parts={'runes': True})
        app.draft['locked'] = True
        fetch = app.lola_build
        app.lola_build = lambda *args: None
        app.auto_import_locked(app.draft)
        self.assertEqual(app.calls, [])
        self.assertIn('ждёт', app.messages[-1])
        app.lola_build = fetch
        app.auto_import_locked(app.draft)
        callbacks.get(timeout=2)()
        app.auto_import_locked(app.draft)
        self.assertEqual(len(app.calls), 1)
        self.assertEqual(app.applied_runes[2], [8214])

    def test_missing_win_build_preserves_only_popular_variant(self):
        from core import parse_lola_full, lola_item_sets, restore_lola_styles
        pick = {'runes': {'set': {'pri': [8437, 8446, 8444, 8451], 'sec': [8410, 8345]}},
                'items': {'start': {'set': [1056]}, 'core': {'set': [3118]}}}
        build = parse_lola_full({'summary': {'pick': pick}})
        self.assertIsNone(build['win'])
        app, _, _, _ = self.app()
        app.lola_build = lambda *args: build
        app.do_import(('items',))
        self.assertFalse(app.calls)
        self.assertIn('недоступен', app.messages[-1])
        self.assertEqual(len(lola_item_sets(build, 'Ари')), 1)
        self.assertIsNone(app.draft_build_variant(build['pick'], 'ARAM'))
        old = dict(pick=build['pick'], win=dict(build['pick']))
        self.assertIsNone(restore_lola_styles(old)['win'])
        confirmed = parse_lola_full({'summary': {'pick': pick, 'win': pick}})
        self.assertIsNotNone(restore_lola_styles(confirmed)['win'])

    def test_aram_import_uses_current_map_or_all_maps(self):
        for map_id in (12, None):
            app, callbacks, _, _ = self.app()
            app.draft.update(aram=True, map_id=map_id)
            app.do_import(('items',))
            callbacks.get(timeout=2)()
            self.assertEqual(app.calls[0][1][-1], map_id)

    def test_variant_or_role_change_cancels_remaining_operations(self):
        for change in ('variant', 'role'):
            with self.subTest(change=change):
                app, callbacks, entered, release = self.app(blocked=True)
                app.do_import(('runes', 'items'))
                self.assertTrue(entered.wait(2))
                if change == 'variant': app.s['rune_pick'] = 'pick'
                else: app.role_override = 'TOP'
                release.set()
                callbacks.get(timeout=2)()
                self.assertEqual([call[0] for call in app.calls], ['runes'])
                self.assertIsNone(app.imported)
                self.assertIsNone(app._import_pending)

    def test_duplicate_pending_export_does_not_write_twice(self):
        app, callbacks, entered, release = self.app(blocked=True)
        app.do_import(('runes', 'items'))
        self.assertTrue(entered.wait(2))
        app.do_import(('runes', 'items'))
        release.set()
        callbacks.get(timeout=2)()
        self.assertEqual([call[0] for call in app.calls], ['runes', 'items'])

    def test_matchup_selection_exports_matchup_runes_and_items(self):
        app, callbacks, _, _ = self.app()
        app.s['draft_build_context'] = 'matchup'
        app.draft_opponent = lambda cs, role: 'Viktor'
        specific = app.lola_build('Ahri','MIDDLE')
        specific['win'] = dict(specific['win'], perks=[8369], core=[3089])
        app.lola_matchup = lambda champion, role, opponent: specific
        app.do_import(('runes','items'))
        callbacks.get(timeout=2)()
        self.assertEqual(app.calls[0][1][3], [8369])
        self.assertIn('против Viktor', app.calls[0][1][0])
        self.assertEqual(app.calls[1][1][2][0][1][1][1], [3089])

    def test_missing_matchup_never_exports_general_build_as_a_fallback(self):
        app, _, _, _ = self.app()
        app.s['draft_build_context'] = 'matchup'
        app.draft_opponent = lambda cs, role: 'Viktor'
        app.lola_matchup = lambda champion, role, opponent: None
        app.do_import(('runes','items'))
        self.assertEqual(app.calls, [])
        self.assertIn('Экспорт не выполнен', app.messages[-1])

    def test_opponent_change_cancels_remaining_matchup_export(self):
        app, callbacks, entered, release = self.app(blocked=True)
        app.s['draft_build_context'] = 'matchup'
        app.draft['opponent'] = 'Viktor'
        app.draft_opponent = lambda cs, role: cs['opponent']
        app.lola_matchup = lambda champion, role, opponent: app.lola_build(champion,role)
        app.do_import(('runes','items'))
        self.assertTrue(entered.wait(2))
        app.draft['opponent'] = 'Lux'
        release.set()
        callbacks.get(timeout=2)()
        self.assertEqual([call[0] for call in app.calls], ['runes'])
        self.assertIsNone(app.imported)

    def test_external_build_exports_exact_runes_and_items(self):
        for context in ('offmeta','player:42'):
            with self.subTest(context=context):
                app,callbacks,_,_=self.app()
                app.s.update(draft_build_context=context,rune_pick='pick')
                variant=dict(app.lola_build('Ahri','MIDDLE')['pick'],perks=[8369],core=[3089])
                row={'id':'42','champion':'Ahri','role':'MIDDLE','variant':variant,'patch':'16.21','source':'Mobalytics'}
                app.offmeta_build=lambda c,r:row
                app.player_builds=lambda c,r:{'champion':'Ahri','role':'MIDDLE','groups':{'OTP':[row]}}
                app.do_import(('runes','items'));callbacks.get(timeout=2)()
                self.assertEqual(app.calls[0][1][3],[8369])
                self.assertEqual(app.calls[1][1][2][0][1][1][1],[3089])
                self.assertIn('Mobalytics',app.calls[1][1][2][0][0])

    def test_external_player_change_cancels_remaining_export(self):
        app,callbacks,entered,release=self.app(blocked=True)
        app.s.update(draft_build_context='offmeta',rune_pick='pick')
        row={'champion':'Ahri','role':'MIDDLE','variant':app.lola_build('Ahri','MIDDLE')['pick']}
        app.offmeta_build=lambda c,r:row
        app.do_import(('runes','items'));self.assertTrue(entered.wait(2))
        app.s['draft_build_context']='player:42';release.set();callbacks.get(timeout=2)()
        self.assertEqual([call[0] for call in app.calls],['runes'])


class QtServiceSourceTests(unittest.TestCase):
    def test_lolalytics_retries_after_temporary_failure(self):
        service = services.ApplicationServices()
        service.lola, service.lola_state = {}, {}
        service.cp_sel = None
        callbacks = queue.Queue()
        service.root = SimpleNamespace(after=lambda delay, fn:callbacks.put((delay,fn)))
        target = ('counter','Ahri','MIDDLE')
        service.redraw_draft = lambda:service.lola_fetch(*target)
        with tempfile.TemporaryDirectory() as home, patch.object(services,'log_error'):
            service.home = home
            with patch.object(services.urllib.request,'urlopen',side_effect=OSError) as net:
                service.lola_fetch(*target)
                _, done = callbacks.get(timeout=2)
                done()
                service.lola_fetch(*target)
                self.assertEqual(net.call_count,1)
            self.assertEqual(service.lola_state[target],'fail')
            delay, retry = callbacks.get(timeout=2)
            self.assertGreaterEqual(delay,30000)
            with patch.object(services.urllib.request,'urlopen',
                              return_value=io.BytesIO(b'{"counters":[{"cid":112}]}')) as net:
                retry()
                _, done = callbacks.get(timeout=2)
                done()
                self.assertEqual(net.call_count,1)
            self.assertEqual(service.lola_state[target],'ok')
            self.assertEqual(service.lola_fetch(*target),{'counters':[{'cid':112}]})


if __name__ == '__main__': unittest.main()
