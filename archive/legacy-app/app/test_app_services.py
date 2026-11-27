import io
import itertools
import json
import os
import queue
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app_services as services


class LolaCacheTests(unittest.TestCase):
    def test_memory_refresh_uses_source_age_and_keeps_last_good_build(self):
        matchup = {'champion': 'Ahri', 'role': 'MIDDLE', 'opponent': 'Lux', 'region': 'all'}
        for kind in ('general', 'matchup'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as home:
                app = services.ApplicationServices()
                app.lola, app.lola_state = {}, {}
                app.redraw_draft = lambda: None
                app.home, app.data = home, None
                callbacks = queue.Queue()
                app.root = SimpleNamespace(after=lambda delay, fn: callbacks.put((delay, fn)))
                clock = time.time()
                fetched_at = clock - 11 * 3600
                old, new = {'pick': {'marker': 'old'}}, {'pick': {'marker': 'new'}}
                if kind == 'general':
                    key, name = ('Ahri', 'MIDDLE'), 'full_Ahri_MIDDLE.json'
                    fetch = lambda: app.lola_build(*key)
                    parser = patch.object(services.core, 'parse_lola_full', return_value=new)
                else:
                    key, name = ('matchup', 'Ahri', 'MIDDLE', 'Lux'), 'matchup_v1_Ahri_MIDDLE_Lux.json'
                    old.update(matchup=matchup, fetched_at=fetched_at)
                    new.update(matchup=matchup)
                    fetch = lambda: app.lola_matchup(*key[1:])
                    parser = patch('matchup_data.parse', return_value=new)
                path = Path(home, 'lola', name)
                path.parent.mkdir()
                path.write_text(json.dumps(old), encoding='utf-8')
                os.utime(path, (fetched_at, fetched_at))

                started, release = threading.Event(), threading.Event()

                def fail_refresh(*args, **kwargs):
                    started.set()
                    release.wait(5)
                    raise OSError('offline')

                with (parser, patch.object(services, 'log_error'),
                      patch.object(services, 'time', SimpleNamespace(time=lambda: clock, monotonic=lambda: clock)),
                      patch.object(services.urllib.request, 'urlopen', side_effect=fail_refresh) as net):
                    self.assertIsNone(fetch())
                    _, done = callbacks.get(timeout=2)
                    done()
                    self.assertEqual(fetch(), old)
                    net.assert_not_called()
                    clock += 3601
                    try:
                        self.assertEqual(fetch()['pick'], old['pick'])
                        self.assertTrue(started.wait(2), 'expired memory hit did not start a refresh')
                        self.assertEqual(fetch()['pick'], old['pick'])
                        self.assertEqual(net.call_count, 1)
                    finally:
                        release.set()

                    _, done = callbacks.get(timeout=2)
                    done()
                    self.assertEqual(app.lola_state[key], 'stale')
                    self.assertEqual(fetch(), dict(old, stale=True))
                    refresh_calls = net.call_count
                    self.assertEqual(fetch(), dict(old, stale=True))
                    self.assertEqual(net.call_count, refresh_calls)
                    delay, _ = callbacks.get(timeout=2)
                    self.assertGreaterEqual(delay, 30_000)

                    clock += 31
                    net.side_effect = None
                    net.return_value = io.BytesIO(b'{}')
                    self.assertEqual(fetch(), dict(old, stale=True))
                    _, done = callbacks.get(timeout=2)
                    done()
                    self.assertEqual(app.lola_state[key], 'ok')
                    self.assertEqual(fetch(), new)
                    self.assertEqual(net.call_count, refresh_calls + 1)


class LivePollTests(unittest.TestCase):
    @contextmanager
    def run_poll(self, *, blocked_operation):
        app = services.ApplicationServices()
        app.account, app.draft, app.player = None, None, None
        app.q, samples = queue.Queue(), queue.Queue()
        app.stopping = threading.Event()
        app.stopping.wait = lambda _: app.stopping.is_set()
        app.data = SimpleNamespace(ids={'64': 'LeeSin'})
        app.pus, app.hraw, app.rank_pu, app.jg_cache = {}, {}, {}, {}
        app.evidence_region, app.evidence_region_at = None, 0
        app.prep_engine = Mock()
        app.hint_flags = lambda role: {}
        app.player_history = Mock(return_value={'n': 1})
        app.client = SimpleNamespace(
            live_match_context=Mock(return_value=(102, 420)),
            puuid=Mock(return_value='jungler'), rank=Mock(return_value={'tier': 'GOLD'}),
            history=Mock(return_value=[{'lane': 'JUNGLE', 'gid': 10}]),
            timeline=Mock(return_value={}), game=Mock(return_value={}),
            loading=Mock(return_value=[]),
            phase=Mock(return_value='Lobby'), me=Mock(return_value=None),
        )
        app.fetch_scout = Mock(return_value={'Enemy#EUW': 'scouted'})

        def engine(*args, **kwargs):
            return SimpleNamespace(player=app.player, prepped=True, jg_plan=None,
                                   tick=lambda g: [(g.t, threading.current_thread().name)])

        jungler = {'riot': 'Enemy#EUW', 'c': 'LeeSin', 'pos': 'JUNGLE'}

        def game(raw, data):
            return SimpleNamespace(t=raw['gameData']['gameTime'], events=raw['events'], arena=False,
                                   role='MIDDLE', me={'c': 'Ahri'}, data=data, players=[jungler], ejg=jungler)

        if blocked_operation == 'scout':
            operation = app.fetch_scout
        else:
            operation = getattr(app.client, blocked_operation)
        started, release, returned = threading.Event(), threading.Event(), threading.Event()

        def block_once(*args, **kwargs):
            value = operation.return_value
            if not started.is_set():
                started.set()
                release.wait(6)
                returned.set()
            return value

        operation.side_effect = block_once
        with ExitStack() as stack:
            stack.enter_context(patch.object(services.lcu, 'live_data', side_effect=lambda: samples.get(timeout=6)))
            stack.enter_context(patch.object(services.core, 'Game', side_effect=game))
            stack.enter_context(patch.object(services.core, 'Engine', side_effect=engine))
            stack.enter_context(patch.object(services, 'log_error'))
            poller = threading.Thread(target=app.poll, name='test-live-poll', daemon=True)
            poller.start()
            try:
                yield app, samples, started, release, returned, operation
            finally:
                release.set()
                app.stopping.set()
                samples.put(None)
                poller.join(timeout=2)

    def sample(self, samples, game_time, *, end=False):
        events = [{'EventName': 'GameEnd', 'Result': 'Win'}] if end else []
        samples.put({'gameData': {'gameTime': game_time}, 'events': events})

    def event(self, app, kind):
        deadline = time.monotonic() + 2
        while True:
            try:
                event = app.q.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                self.fail(f'{kind} was blocked by live enrichment')
            if event[0] == kind:
                return event[1:]

    def test_live_samples_and_hints_continue_while_enrichment_waits(self):
        for operation in ('live_match_context', 'scout', 'history', 'timeline'):
            with self.subTest(operation=operation), self.run_poll(blocked_operation=operation) as harness:
                app, samples, started, _, returned, blocked = harness
                for game_time in range(10, 40):
                    self.sample(samples, game_time)
                    self.event(app, 'game')
                    if started.wait(.02):
                        break
                else:
                    self.fail(f'poll did not start {operation}')
                self.assertFalse(returned.is_set())
                self.sample(samples, game_time + 1)
                game, hints, _ = self.event(app, 'game')
                self.assertEqual(hints, [(game.t, 'test-live-poll')])
                self.assertFalse(returned.is_set())
                self.assertEqual(blocked.call_count, 1)

    def test_live_samples_continue_while_loading_screen_waits(self):
        with self.run_poll(blocked_operation='loading') as harness:
            app, samples, started, release, returned, loading = harness
            app.client.phase.return_value = 'GameStart'
            loading.return_value = [{'pu': 'loading-only', 'team': 200, 'pos': 'jungle',
                                     'champ': 64, 'name': 'LoadingOnly'}]
            samples.put(None)
            self.assertTrue(started.wait(2))
            self.sample(samples, 10)
            game, hints, _ = self.event(app, 'game')
            self.assertEqual(game.t, 10)
            self.assertEqual(hints, [(10, 'test-live-poll')])
            self.assertFalse(returned.is_set())
            release.set()
            self.assertTrue(returned.wait(2))
            self.sample(samples, 11)
            self.event(app, 'game')
            self.assertNotIn('loading-only', app.hraw)

    def test_loading_result_is_discarded_after_phase_changes(self):
        with self.run_poll(blocked_operation='loading') as harness:
            app, samples, started, release, returned, loading = harness
            app.client.phase.return_value = 'GameStart'
            loading.return_value = [{'pu': 'old-loading', 'team': 200, 'pos': 'jungle',
                                     'champ': 64, 'name': 'OldLoading'}]
            clock = itertools.count(1000, 3)
            with patch.object(services, 'time', SimpleNamespace(time=lambda: next(clock))):
                samples.put(None)
                self.assertTrue(started.wait(2))
                app.client.phase.return_value = 'Lobby'
                release.set()
                self.assertTrue(returned.wait(2))
                time.sleep(.02)
                samples.put(None)
                time.sleep(.02)
                self.assertNotIn('old-loading', app.hraw)
                self.assertFalse(any(event[0] == 'load' for event in list(app.q.queue)))

    def test_scout_completion_from_ended_match_is_discarded(self):
        with self.run_poll(blocked_operation='scout') as harness:
            app, samples, started, release, returned, scout = harness
            scout.return_value = {'Enemy#EUW': 'previous match'}
            self.sample(samples, 310)
            self.event(app, 'game')
            self.assertTrue(started.wait(2))
            samples.put(None)
            self.event(app, 'end')

            current = {'Enemy#EUW': 'current match'}
            scout.return_value = current
            for game_time in range(10, 40):
                self.sample(samples, game_time)
                game, _, _ = self.event(app, 'game')
                if game.scouting[0]:
                    self.assertEqual(game.scouting[0], current)
                    break
                time.sleep(.01)
            else:
                self.fail('previous match prevented the current match from receiving scouting')
            self.assertFalse(returned.is_set())

            release.set()
            self.assertTrue(returned.wait(2))
            self.sample(samples, game_time + 1)
            game, _, _ = self.event(app, 'game')
            self.assertEqual(game.scouting[0], current)

    def test_clock_restart_replaces_match_without_waiting_for_old_scout(self):
        with self.run_poll(blocked_operation='scout') as harness:
            app, samples, started, release, returned, scout = harness
            scout.return_value = {'Enemy#EUW': 'previous match'}
            self.sample(samples, 310)
            self.event(app, 'game')
            self.assertTrue(started.wait(2))

            for game_time in range(311, 316):
                self.sample(samples, game_time)
                game, _, _ = self.event(app, 'game')
                if game.match_id == 102:
                    break
            else:
                self.fail('the first match never received its ID')

            current = {'Enemy#EUW': 'current match'}
            scout.return_value = current
            self.sample(samples, 20)
            game, _, _ = self.event(app, 'game')
            self.assertTrue(game.replaced_previous_match)

            for game_time in range(21, 31):
                self.sample(samples, game_time)
                game, _, _ = self.event(app, 'game')
                if game.scouting[0]:
                    self.assertEqual(game.scouting[0], current)
                    break
                time.sleep(.01)
            else:
                self.fail('the next match was blocked by the previous scout')
            self.assertFalse(returned.is_set())

            release.set()
            self.assertTrue(returned.wait(2))
            self.sample(samples, game_time + 1)
            game, _, _ = self.event(app, 'game')
            self.assertEqual(game.scouting[0], current)

    def test_old_context_result_cannot_hide_a_restarted_match(self):
        with self.run_poll(blocked_operation='scout') as harness:
            app, samples, started, _, _, _ = harness
            second_started, release_context, context_returned = (
                threading.Event(), threading.Event(), threading.Event())
            calls = itertools.count(1)

            def old_context():
                if next(calls) > 1:
                    second_started.set()
                    release_context.wait(2)
                    context_returned.set()
                return 102, 420

            app.client.live_match_context.side_effect = old_context
            clock = itertools.count(1000, 11)
            with patch.object(services, 'time', SimpleNamespace(time=lambda: next(clock))):
                try:
                    self.sample(samples, 310)
                    self.event(app, 'game')
                    self.assertTrue(started.wait(2))
                    for game_time in range(311, 316):
                        self.sample(samples, game_time)
                        game, _, _ = self.event(app, 'game')
                        if game.match_id == 102 and second_started.wait(.02):
                            break
                    else:
                        self.fail('the old match context was not established')

                    release_context.set()
                    self.assertTrue(context_returned.wait(2))
                    time.sleep(.02)
                    self.sample(samples, 20)
                    game, _, _ = self.event(app, 'game')
                    self.assertTrue(game.replaced_previous_match)
                    self.assertNotEqual(game.match_id, 102)
                finally:
                    release_context.set()
