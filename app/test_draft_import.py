"""Client export snapshots, failures and cancellation, with no Tk display or network."""
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import ui


class DraftImportTests(unittest.TestCase):
    def app(self, fail_items=False, blocked=False):
        app = object.__new__(ui.App)
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
        with patch.object(ui, 'log_error'):
            app.do_import(('runes', 'items'))
            callbacks.get(timeout=2)()
        self.assertIsNone(app.imported)
        self.assertIn('Руны: готово', app.messages[-1])
        self.assertIn('Предметы: не получилось', app.messages[-1])

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


if __name__ == '__main__': unittest.main()
