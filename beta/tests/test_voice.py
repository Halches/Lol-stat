"""Voice integration checks: fixtures never pretend to be a live match."""
from concurrent.futures import Future
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

# worker sets up shared classic modules for the desktop package.
from desktop import worker
from desktop.voice_audio import ClipPlayer, VoicePack
from desktop.voice_catalog import PHRASES, TOPICS, setting_key
from desktop.voice_rules import Catalog, VoiceRules, game_snapshot


CATALOG = {"names": {"Sett": "Сетт", "Darius": "Дариус", "LeeSin": "Ли Син"}, "ids": {},
           "items": {"3340": {"n": "Тотем", "g": 0, "tags": ["Trinket"]},
                     "1001": {"n": "Ботинки", "g": 300, "done": False},
                     "3000": {"n": "Предмет", "g": 3000, "done": True}}}


def snapshot(t=301, gold=500, level=1, enemy_level=1, role="TOP", dead=False, items=()):
    def player(identity, champ, team, lane, lvl, its):
        return {"riotId": identity, "rawChampionName": "game_character_displayname_" + champ,
                "championName": champ, "team": team, "position": lane, "level": lvl, "isDead": False,
                "items": [{"itemID": i, "count": 1} for i in its],
                "scores": {"creepScore": 10, "kills": 0, "deaths": 0, "assists": 0},
                "summonerSpells": {"summonerSpellOne": {"rawDisplayName": "SummonerSmite" if lane == "JUNGLE" else "SummonerFlash"}}}
    me = player("Player#EUW", "Sett", "ORDER", role, level, items)
    me["isDead"] = dead
    return {"activePlayer": {"riotId": "Player#EUW", "currentGold": gold,
                             "abilities": {key: {"abilityLevel": level if key == "Q" else 0} for key in "QWER"}},
            "gameData": {"gameTime": t, "gameMode": "CLASSIC", "mapNumber": 11},
            "allPlayers": [me, player("Enemy#EUW", "Darius", "CHAOS", "TOP", enemy_level, ()),
                           player("Jungler#EUW", "LeeSin", "CHAOS", "JUNGLE", 1, ())],
            "events": {"Events": []}}


def selected(*topics):
    return lambda topic, role: topic.key in topics


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = VoiceRules(CATALOG)

    def test_gold_threshold_cooldown_and_purchase_invalidates_queued_reminder(self):
        on = selected("hoard")
        self.assertEqual(self.rules.tick(snapshot(gold=1999), "TOP", on), [])
        self.assertEqual(self.rules.tick(snapshot(302, gold=2000), "TOP", on), ["hoard"])
        self.assertEqual(self.rules.tick(snapshot(350, gold=2400), "TOP", on), [])
        self.rules.tick(snapshot(351, gold=700), "TOP", on)
        self.assertNotIn("hoard", self.rules.valid_phrases)
        self.assertEqual(self.rules.tick(snapshot(423, gold=2400), "TOP", on), ["hoard"])

    def test_disabled_topics_and_dead_player_are_silent(self):
        self.assertEqual(self.rules.tick(snapshot(gold=2500), "TOP", selected()), [])
        self.assertEqual(self.rules.tick(snapshot(302, gold=2500, dead=True), "TOP", selected("hoard")), [])
        self.assertEqual(self.rules.valid_phrases, set())

    def test_unknown_identity_or_incomplete_data_does_not_become_a_game(self):
        for raw in (None, {}, {"gameData": {"gameTime": 301}}, snapshot()):
            raw = deepcopy(raw)
            if raw and "activePlayer" in raw:
                raw["activePlayer"]["riotId"] = "Spectator#EUW"
            self.assertEqual(self.rules.tick(raw, "TOP", selected("hoard")), [])
            self.assertFalse(self.rules.accepted)

    def test_wrong_map_and_game_end_do_not_produce_hints(self):
        raw = snapshot(gold=2500)
        raw["gameData"]["mapNumber"] = 12
        self.assertEqual(self.rules.tick(raw, "TOP", selected("hoard")), [])
        raw = snapshot(gold=2500)
        raw["events"]["Events"] = [{"EventName": "GameEnd", "EventTime": 301}]
        self.assertEqual(self.rules.tick(raw, "TOP", selected("hoard")), [])

    def test_roles_are_explicit_not_guessed_from_champion(self):
        raw = snapshot(role="")
        for p in raw["allPlayers"]:
            p["position"] = ""
        game = game_snapshot(raw, self.rules.data)
        self.assertEqual(game.role, "")
        self.assertIsNone(game.opp)
        self.assertEqual(self.rules.tick(raw, "", selected("ganks", "levels")), [])

    def test_role_specific_ward_is_used_and_only_in_its_window(self):
        for role, phrase in (("TOP", "ward_lane"), ("JUNGLE", "ward_jungle"), ("UTILITY", "ward_support")):
            rules = VoiceRules(CATALOG)
            self.assertEqual(rules.tick(snapshot(25, role=role), role, selected("early_ward")), [phrase])
            self.assertEqual(rules.tick(snapshot(26, role=role), role, selected("early_ward")), [])
        self.assertEqual(self.rules.tick(snapshot(100), "TOP", selected("early_ward")), [])

    def test_level_advantage_uses_confirmed_opponent(self):
        on = selected("levels")
        self.rules.tick(snapshot(90), "TOP", on)
        self.assertEqual(self.rules.tick(snapshot(91, level=2), "TOP", on), ["level_2"])
        self.rules.tick(snapshot(92, level=2, enemy_level=2), "TOP", on)
        self.assertEqual(self.rules.tick(snapshot(93, level=2, enemy_level=3), "TOP", on), ["enemy_level_3"])
        self.assertNotIn("level_2", self.rules.valid_phrases)

    def test_spent_skill_points_are_silent_and_no_backlog_on_late_connection(self):
        on = selected("skills")
        self.assertEqual(self.rules.tick(snapshot(level=10), "TOP", on), [])
        raw = snapshot(302, level=11)
        raw["activePlayer"]["abilities"]["Q"]["abilityLevel"] = 10
        self.assertEqual(self.rules.tick(raw, "TOP", on), ["skills"])
        self.assertEqual(self.rules.tick(raw, "TOP", on), [])

    def test_three_gank_windows_do_not_repeat_the_same_phrase_immediately(self):
        on = selected("ganks")
        self.assertEqual(self.rules.tick(snapshot(130), "TOP", on), ["gank"])
        self.assertEqual(self.rules.tick(snapshot(150), "TOP", on), [])
        self.assertEqual(self.rules.tick(snapshot(180), "TOP", on), ["gank"])

    def test_objective_leads_and_no_late_misleading_recording(self):
        on = selected("objectives")
        self.assertEqual(self.rules.tick(snapshot(240), "TOP", on), ["dragon_60"])
        self.assertEqual(self.rules.tick(snapshot(270), "TOP", on), ["dragon_30"])
        late = VoiceRules(CATALOG)
        self.assertEqual(late.tick(snapshot(246), "TOP", on), [])
        normal_polling = VoiceRules(CATALOG)
        self.assertEqual(normal_polling.tick(snapshot(240.9), "TOP", on), ["dragon_60"])

    def test_inhibitor_reminder_accepts_normal_polling_delay(self):
        raw = snapshot(840.7)
        raw["events"]["Events"] = [{"EventName": "InhibKilled", "EventTime": 600, "EventID": 1}]
        self.assertEqual(self.rules.tick(raw, "TOP", selected("inhib")), ["inhib"])

    def test_new_match_clock_clears_one_shot_and_cooldown(self):
        on = selected("hoard", "early_ward")
        self.assertEqual(self.rules.tick(snapshot(gold=2500), "TOP", on), ["hoard"])
        self.assertEqual(self.rules.tick(snapshot(25), "TOP", on), ["ward_lane"])
        self.assertTrue(self.rules.reset_detected)

    def test_raw_and_compact_item_catalogs_both_detect_completed_item(self):
        for catalog in (CATALOG, {**CATALOG, "items": {"3000": {"name": "Предмет", "gold": {"total": 3000}, "from": ["1001"]}}}):
            rules = VoiceRules(catalog)
            on = selected("powerspike")
            rules.tick(snapshot(301), "TOP", on)
            self.assertEqual(rules.tick(snapshot(302, items=(3000,)), "TOP", on), ["item"])

    def test_cs_goal_is_explicit_and_silent_for_support(self):
        on = selected("cs_norm")
        self.assertEqual(self.rules.tick(snapshot(300), "TOP", on, 7), ["cs"])
        other = VoiceRules(CATALOG)
        self.assertEqual(other.tick(snapshot(300, role="UTILITY"), "UTILITY", on, 7), [])


class PlaybackTests(unittest.TestCase):
    def test_stop_cancels_active_and_discards_pending(self):
        started, cancelled = Event(), Event()
        played = []
        class Backend:
            def play(self, path, volume, stop):
                played.append(path.name)
                started.set()
                if stop.wait(2):
                    cancelled.set()
        player = ClipPlayer(Backend)
        try:
            player.submit("one.wav", "one", 70)
            self.assertTrue(started.wait(1))
            player.submit("two.wav", "two", 70)
            player.stop()
            self.assertTrue(cancelled.wait(1))
        finally:
            player.close()
        self.assertEqual(played, ["one.wav"])
        self.assertFalse(player.thread.is_alive())

    def test_queue_is_bounded_prioritized_and_deduplicated(self):
        started = Event()
        class Backend:
            def play(self, path, volume, stop):
                started.set()
                stop.wait(2)
        player = ClipPlayer(Backend)
        try:
            player.submit("active.wav", "active", 70)
            self.assertTrue(started.wait(1))
            for i in range(12):
                player.submit(f"{i}.wav", str(i), 70, priority=i)
            player.submit("same.wav", "11", 70, priority=100)
            with player.condition:
                self.assertEqual([p.phrase for p in player.pending], ["11", "10"])
            player.retain({"10"})
            with player.condition:
                self.assertLessEqual(len(player.pending), 1)
        finally:
            player.close()

    def test_expired_message_is_not_played(self):
        delivered = Event()
        backend = Mock()
        backend.play.side_effect = lambda *args: delivered.set()
        player = ClipPlayer(lambda: backend)
        try:
            player.submit("old.wav", "old", 70, ttl=-1)
            player.submit("new.wav", "new", 70)
            self.assertTrue(delivered.wait(1))
            self.assertEqual(backend.play.call_args.args[0], Path("new.wav"))
            self.assertEqual(backend.play.call_count, 1)
        finally:
            player.close()

    def test_missing_or_broken_pack_is_not_advertised_as_ready(self):
        with TemporaryDirectory() as folder:
            self.assertEqual(VoicePack(folder).voices, {})
            Path(folder, "manifest.json").write_text("bad json")
            self.assertEqual(VoicePack(folder).voices, {})

    def test_every_topic_has_an_actual_finite_phrase(self):
        for topic in TOPICS:
            self.assertTrue(topic.phrases)
            self.assertTrue(all(p in PHRASES for p in topic.phrases))


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        from PySide6.QtCore import QSettings
        from desktop.voice_assistant import Assistant
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = QSettings(str(Path(self.temp.name) / "settings.ini"), QSettings.Format.IniFormat)
        self.context = SimpleNamespace(catalog=CATALOG, voice_context={})
        self.player = Mock()
        pack = SimpleNamespace(voices={"svetlana": {"name": "Голос"}}, clip=lambda *args: Path("clip.mp3"))
        self.assistant = Assistant(settings, self.context, running=False, pack=pack, player=self.player)
        self.addCleanup(self.assistant.close)
        self.assistant.executor.shutdown(wait=True)
        self.assistant.executor = Mock()
        self.assistant.executor.submit.side_effect = lambda *args: Future()
        settings.setValue("assistant/enabled", True)

    def enter(self, game=1):
        self.context.voice_context = {"gameId": game, "active": True, "generation": 0,
                                      "observedAt": time.monotonic(), "role": "TOP"}
        self.assistant.poll()

    def deliver(self, raw):
        self.assistant.job[1].set_result(raw)
        self.assistant.poll()

    def test_late_live_response_cannot_speak_in_a_different_match(self):
        self.enter(1)
        old = self.assistant.job[1]
        self.enter(2)
        old.set_result(snapshot(gold=2500))
        self.assistant.poll()
        self.player.submit.assert_not_called()

    def test_disconnect_stops_speech_without_rearming_match_hints(self):
        self.enter()
        self.deliver(snapshot(gold=2500))
        self.assertTrue(self.player.submit.called)
        rules = self.assistant.rules
        self.context.voice_context["active"] = False
        self.assistant.poll()
        self.assertIs(self.assistant.rules, rules)
        self.assertIsNone(self.assistant.rules.engine.prev)
        self.assertIn("hoard", rules.last_phrase)

    def test_disabling_and_changing_voice_cancel_in_flight_read(self):
        self.enter()
        job = self.assistant.job[1]
        self.assistant.configure("assistant/enabled", False)
        job.set_result(snapshot(gold=2500))
        self.assistant.poll()
        self.player.submit.assert_not_called()
        self.player.stop.assert_called()

    def test_settings_for_each_lane_and_common_are_independent(self):
        topic = next(t for t in TOPICS if t.key == "ganks")
        self.assistant.configure(setting_key("ganks", "TOP"), False)
        self.assertFalse(self.assistant.enabled(topic, "TOP"))
        self.assertTrue(self.assistant.enabled(topic, "MIDDLE"))
        self.assertFalse(self.assistant.enabled(topic, "JUNGLE"))
        common = next(t for t in TOPICS if t.key == "hoard")
        self.assistant.configure(setting_key("hoard"), False)
        self.assertFalse(self.assistant.enabled(common, "TOP"))
        self.assertFalse(self.assistant.enabled(common, "UTILITY"))

    def test_removed_voice_in_saved_settings_falls_back_to_svetlana(self):
        for removed in ("eugene", "dmitry"):
            with self.subTest(voice=removed):
                self.assistant.settings.setValue("assistant/voice", removed)
                self.assertEqual(self.assistant.voice, "svetlana")
                self.player.reset_mock()
                self.assistant.preview()
                self.player.submit.assert_called_once()

    def test_invalid_or_finished_live_data_stops_current_speech(self):
        self.enter()
        self.deliver(snapshot(gold=2500))
        self.assistant.after = 0
        self.assistant.poll()
        self.player.reset_mock()
        self.deliver({"gameData": {}})
        self.player.stop.assert_called()
        self.player.submit.assert_not_called()

    def test_changing_voice_rejects_an_already_running_live_request(self):
        self.enter()
        request = self.assistant.job[1]
        self.assistant.configure("assistant/voice", "svetlana")
        request.set_result(snapshot(gold=2500))
        self.assistant.poll()
        self.player.submit.assert_not_called()

    def test_frozen_game_clock_stops_speech_even_when_endpoint_responds(self):
        clock = [100.0]
        with patch("desktop.voice_assistant.monotonic", side_effect=lambda: clock[0]):
            self.enter()
            self.context.voice_context["observedAt"] = clock[0]
            self.deliver(snapshot(gold=2500))
            for second in range(1, 5):
                clock[0] = 100.0 + second
                self.context.voice_context["observedAt"] = clock[0]
                self.assistant.after = 0
                self.assistant.poll()
                self.deliver(snapshot(gold=2500))
            self.assertFalse(self.assistant.watching)
            self.player.stop.assert_called()


class ContextTests(unittest.TestCase):
    def test_gameflow_must_confirm_id_and_disconnect_cannot_reuse_old_permission(self):
        from test_desktop import gameflow
        client = Mock(port=1234)
        client.region.return_value = "EUW"
        with patch.object(worker, "read_catalog", return_value=CATALOG), patch.object(worker.Companion, "update_catalog", return_value=CATALOG):
            companion = worker.Companion(client)
        self.addCleanup(companion.close)
        now = [100.0]
        with patch.object(worker.time, "monotonic", side_effect=lambda: now[0]):
            client.call.return_value = gameflow("InProgress", 123, 420)
            companion.snapshot()
            self.assertTrue(companion.voice_context["active"])
            self.assertEqual(companion.voice_context["gameId"], 123)
            now[0] += 2
            client.call.return_value = gameflow("GameStart", None, 420)
            companion.snapshot()
            self.assertFalse(companion.voice_context["active"])
            now[0] += 2
            client.call.return_value = None
            companion.snapshot()
            self.assertFalse(companion.voice_context["active"])


if __name__ == "__main__":
    unittest.main()
