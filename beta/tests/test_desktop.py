import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, mock_open, patch
from urllib.error import HTTPError

from desktop.worker import Companion, allied_role_slots, draft_roster, load_build, unavailable_draft_champions
from lcu import LCU
from desktop.draft_analysis import DraftProfiles, describe_profile
from desktop.draft_stats import available_suggestions, fetch_champion_statistics
from desktop.extra_builds import (
    add_pro_ranks, lane_opponent, personal_build, special_options, specialist_builds,
    situational_items, tournament_builds, uncommon_build,
)
from desktop.home_data import RankHistory, read_home


def gameflow(phase, game_id=None, queue=None):
    return {"phase": phase, "gameData": {"gameId": game_id, "queue": {"id": queue}}}


class GameflowTests(unittest.TestCase):
    def snapshots(self, *events, home=False):
        client = Mock(port=1234)
        client.region.side_effect = ["EUW", None]
        responses = iter(events)

        def read(_path):
            response = next(responses)
            if isinstance(response, OSError):
                raise response
            client.port = 1234 if response else None
            return response

        client.call.side_effect = read
        seconds = count(100, 10)
        clock = SimpleNamespace(monotonic=lambda: next(seconds))
        with (patch("desktop.worker.read_catalog", return_value={}),
              patch.object(Companion, "update_catalog", return_value={}),
              patch("desktop.worker.foreground_game", return_value=None),
              patch("desktop.worker.time", clock)):
            companion = Companion(client)
            companion.build_key = ("Viktor", "MIDDLE", 112, events[0]["gameData"]["gameId"])
            companion.build_locked = True
            companion.build = {"pick": {"champion": "Viktor"}}
            try:
                return [companion.snapshot(home=home) for _ in events]
            finally:
                companion.close()

    def test_disconnect_before_lobby_keeps_match_for_automatic_review(self):
        playing, disconnected, lobby = self.snapshots(
            gameflow("InProgress", 203, 420), None, gameflow("Lobby"),
        )
        self.assertEqual(playing["phase"], "game")
        self.assertEqual(disconnected, playing)
        self.assertEqual(lobby["matchId"], "EUW1_203")
        self.assertTrue(lobby["postGameReady"])

    def test_gameflow_error_during_stats_keeps_pending_match_until_scoreboard(self):
        unavailable = HTTPError("https://127.0.0.1", 503, "Unavailable", {}, None)
        playing, waiting, disconnected, unavailable_stats, scoreboard = self.snapshots(
            gameflow("InProgress", 204, 420), gameflow("WaitingForStats"), None,
            unavailable, gameflow("EndOfGame"),
        )
        self.assertEqual(playing["build"]["champion"], "Viktor")
        self.assertEqual(waiting["matchId"], "EUW1_204")
        self.assertFalse(waiting["postGameReady"])
        self.assertEqual(disconnected, waiting)
        self.assertEqual(unavailable_stats, waiting)
        self.assertEqual(scoreboard["matchId"], "EUW1_204")
        self.assertTrue(scoreboard["postGameReady"])

    def test_client_loss_keeps_background_game_until_game_process_exits(self):
        with patch("desktop.worker.game_process_running", side_effect=[True, False]):
            playing, brief, interrupted, background, closed = self.snapshots(
                gameflow("InProgress", 205, 420), None, None, None, None, home=True,
            )
        self.assertFalse(playing["home"])
        game_state = lambda snapshot: {key: value for key, value in snapshot.items() if key != "connection"}
        self.assertEqual(tuple(map(game_state, (brief, interrupted, background))), (game_state(playing),) * 3)
        self.assertFalse(brief["connection"]["clientDetected"])
        self.assertTrue(closed["home"])
        self.assertEqual(closed["phase"], "offline")
        self.assertIsNone(closed["build"])
        self.assertIsNone(closed["matchId"])
        self.assertEqual(closed["flowGeneration"], playing["flowGeneration"] + 1)

    def test_late_build_reaches_only_the_game_from_its_draft(self):
        client = Mock(port=1234)
        client.region.return_value = "EUW"
        key = ("Viktor", "MIDDLE", 112, 15)
        with (patch("desktop.worker.read_catalog", return_value={}),
              patch.object(Companion, "update_catalog", return_value={})):
            companion = Companion(client)
        self.addCleanup(companion.close)
        companion.build_key = key
        companion.build_locked = True
        waiting = Future()
        companion.build_job = key, waiting
        client.call.return_value = gameflow("GameStart", None, 420)
        self.assertFalse(companion.read_status(100)["buildOptions"])
        client.call.return_value = gameflow("InProgress", 15, 420)
        self.assertFalse(companion.read_status(101)["buildOptions"])
        waiting.set_result({"pick": {"champion": "Viktor"}})
        ready = companion.read_status(102)
        self.assertEqual(ready["draftKey"], list(key))
        self.assertEqual(ready["build"]["champion"], "Viktor")
        client.call.return_value = gameflow("Reconnect")
        self.assertEqual(companion.read_status(102.5)["build"]["champion"], "Viktor")
        client.call.return_value = gameflow("GameStart")
        self.assertEqual(companion.read_status(102.6)["build"]["champion"], "Viktor")
        companion.build_locked = False
        self.assertFalse(companion.read_status(102.7)["buildOptions"])
        companion.build_locked = True
        # Also simulate skipping the whole first game after champ select.
        companion.game = None
        client.call.return_value = gameflow("InProgress", 16, 420)
        next_match = companion.read_status(103)
        self.assertFalse(next_match["buildOptions"])
        self.assertIsNone(next_match["draftKey"])

    def test_new_lcu_connection_cannot_inherit_overlay_for_an_unknown_match(self):
        client = Mock(port=1234, token="first")
        client.region.return_value = "EUW"
        with (patch("desktop.worker.read_catalog", return_value={}),
              patch.object(Companion, "update_catalog", return_value={})):
            companion = Companion(client)
        self.addCleanup(companion.close)
        companion.build_key = ("Viktor", "MIDDLE", 112, 15)
        companion.build_locked = True
        companion.build = {"pick": {"champion": "Viktor"}}
        client.call.return_value = gameflow("InProgress", 15, 420)
        self.assertEqual(companion.read_status(100)["build"]["champion"], "Viktor")
        client.port, client.token = 5678, "second"
        client.call.return_value = gameflow("Reconnect")
        self.assertIsNone(companion.read_status(101)["build"])
        self.assertIsNone(companion.build_key)

    def test_failed_read_from_new_lcu_connection_discards_old_match_and_advances_generation(self):
        playing = gameflow("InProgress", 15, 420)
        client = Mock(port=1234, token="first")
        client.region.return_value = "EUW"
        client.call.return_value = playing
        with (patch("desktop.worker.read_catalog", return_value={}),
              patch.object(Companion, "update_catalog", return_value={})):
            companion = Companion(client)
        self.addCleanup(companion.close)
        companion.build_key = ("Viktor", "MIDDLE", 112, 15)
        companion.build_locked = True
        companion.build = {"pick": {"champion": "Viktor"}}
        companion.status = companion.read_status(100)
        self.assertEqual(companion.status["build"]["champion"], "Viktor")

        def failed_request(_path):
            client.port = None
            return None

        client.port, client.token = 5678, "second"
        client.call.side_effect = failed_request
        self.assertIsNone(companion.read_status(101)["build"])
        self.assertEqual(companion.flow_generation, 1)
        self.assertIsNone(companion.game)

        client.port = 5678
        client.call.side_effect = None
        self.assertIsNone(companion.read_status(102)["build"])
        self.assertEqual(companion.flow_generation, 1)

    def test_new_pick_is_requested_during_old_request_and_draft_recovers_after_missing_read(self):
        client = Mock(port=1234, token="test")
        client.region.return_value = "EUW"
        client.call.return_value = gameflow("ChampSelect", 15, 420)
        draft = {"gameId": 15, "localPlayerCellId": 0, "myTeam": [
            {"cellId": 0, "championId": 112, "assignedPosition": "middle"}], "actions": [[
            {"actorCellId": 0, "type": "pick", "championId": 112, "completed": True}]]}
        client.champ_select.return_value = draft
        catalog = DraftRosterTests.catalog
        with (patch("desktop.worker.read_catalog", return_value=catalog),
              patch.object(Companion, "update_catalog", return_value=catalog)):
            companion = Companion(client)
        self.addCleanup(companion.close)
        old, new = Future(), Future()
        old.set_running_or_notify_cancel()

        def read(now):
            companion.status = companion.read_status(now)
            return companion.status

        with (patch.object(companion.card_stats, "apply"), patch.object(companion.draft_profiles, "apply"),
              patch.object(companion, "update_special_builds"),
              patch.object(companion.locked_executor, "submit", side_effect=[old, new]) as submit):
            self.assertEqual(read(100)["phase"], "loading")
            draft["myTeam"][0]["championId"] = draft["actions"][0][0]["championId"] = 103
            self.assertEqual(read(101)["phase"], "loading")
            self.assertEqual(submit.call_args.args[-3:], ("Ahri", "MIDDLE", 103))
            new.set_result({"pick": {"champion": "Ahri"}})
            old.set_result({"pick": {"champion": "Viktor"}})
            self.assertEqual(read(102)["build"]["champion"], "Ahri")
            client.champ_select.return_value = None
            held = read(103)
            self.assertEqual(held["build"]["champion"], "Ahri")
            self.assertFalse(held["locked"])
            client.champ_select.return_value = draft
            self.assertTrue(read(104)["locked"])
            client.call.return_value = None
            client.port = None
            offline = read(105)
            self.assertEqual(offline["phase"], "offline")
            self.assertIsNone(offline["build"])

    def test_confirmed_pick_starts_while_both_hover_workers_are_busy(self):
        catalog = DraftRosterTests.catalog
        client = Mock(port=1234, token="test")
        client.region.return_value = "EUW"
        client.call.return_value = gameflow("ChampSelect", 15, 420)
        with (patch("desktop.worker.read_catalog", return_value=catalog),
              patch.object(Companion, "update_catalog", return_value=catalog)):
            companion = Companion(client)
        self.addCleanup(companion.close)
        companion.catalog_job.result(timeout=2)
        release = Event()
        started = {name: Event() for name in ("Viktor", "Ahri", "Zed")}

        def fetch(_catalog, champion, *_args):
            started[champion].set()
            if champion != "Zed":
                release.wait(3)
            return {"pick": {"champion": champion}}

        try:
            with (patch.object(companion.card_stats, "apply"), patch.object(companion.draft_profiles, "apply"),
                  patch.object(companion, "update_special_builds"), patch("desktop.worker.load_build", side_effect=fetch)):
                for now, cid, champion in ((100, 112, "Viktor"), (101, 103, "Ahri"), (102, 238, "Zed")):
                    locked = champion == "Zed"
                    client.champ_select.return_value = {"gameId": 15, "localPlayerCellId": 0, "myTeam": [
                        {"cellId": 0, "championId": cid if locked else 0, "championPickIntent": cid, "assignedPosition": "middle"}],
                        "actions": [[{"actorCellId": 0, "type": "pick", "championId": cid, "completed": locked}]]}
                    companion.read_status(now)
                    self.assertTrue(started[champion].wait(1))
                companion.build_job[1].result(timeout=1)
                self.assertEqual(companion.read_status(103)["build"]["champion"], "Zed")
        finally:
            release.set()

    def test_patch_changes_discard_build_before_requesting_same_target_again(self):
        key = ("Viktor", "MIDDLE", 112, 15)
        client = Mock(port=1234, token="test")
        client.region.return_value = "EUW"
        client.call.return_value = gameflow("ChampSelect", 15, 420)
        client.champ_select.return_value = {"gameId": 15, "localPlayerCellId": 0,
            "myTeam": [{"cellId": 0, "championId": 112, "assignedPosition": "middle"}]}
        previous = DraftRosterTests.catalog
        latest = dict(previous, patch="16.24.1")
        with (patch("desktop.worker.read_catalog", return_value=previous),
              patch.object(Companion, "update_catalog", return_value=latest)):
            companion = Companion(client)
        self.addCleanup(companion.close)
        companion.catalog_job.result(timeout=2)
        companion.build_key = key
        companion.build_patch = previous["patch"]
        companion.build = {"pick": {"assetVersion": previous["patch"]}}
        waiting = Future()
        with (patch.object(companion.card_stats, "apply"), patch.object(companion.draft_profiles, "apply"),
              patch.object(companion, "update_special_builds"),
              patch.object(companion.executor, "submit", return_value=waiting) as submit):
            snapshot = companion.read_status(100)
            self.assertEqual(snapshot["phase"], "loading")
            self.assertFalse(snapshot["buildOptions"])
            self.assertIs(submit.call_args.args[1], latest)
            waiting.set_result({"pick": {"assetVersion": latest["patch"]}})
            self.assertEqual(companion.read_status(101)["build"]["assetVersion"], latest["patch"])


class HomeTests(unittest.TestCase):
    def test_profile_loads_without_gameflow_session_and_new_connection_advances_generation(self):
        self.client.call.return_value = None  # Expected 404 outside a lobby.
        self.client.region.return_value = "EUW"
        self.client.me.return_value = {"puuid": "local-test-account", "riot": "Player#EUW", "level": 50}
        self.client.history_page.return_value = ([], False)
        self.companion.rank_history = Mock(record=Mock(return_value={}))
        with patch("desktop.worker.foreground_game", return_value=None):
            first = self.companion.snapshot(home=True)
            self.assertTrue(first["home"])
            self.assertTrue(self.companion.euw)
            self.assertIsNotNone(self.companion.history_job)
            self.companion.history_job[1].result(timeout=2)
            ready = self.companion.snapshot(home=True)
            self.assertEqual(ready["homeProfile"]["profile"]["riot"], "Player#EUW")
            self.client.token = "new-test-connection"
            self.companion.last_read = 0
            changed = self.companion.snapshot(home=True)
            self.assertEqual(changed["flowGeneration"], first["flowGeneration"] + 1)

    def setUp(self):
        self.catalog = {"ids": {"112": "Viktor"}, "names": {"Viktor": "Виктор"}, "patch": "16.23.1"}
        self.client = Mock(port=1234, token="test")
        with (patch("desktop.worker.read_catalog", return_value=self.catalog),
              patch.object(Companion, "update_catalog", return_value=self.catalog)):
            self.companion = Companion(self.client)
        self.addCleanup(self.companion.close)

    def test_preview_reuses_provider_with_no_import_or_live_build_state(self):
        build = {"champion": "Виктор", "sets": ["items"], "variant": {"perks": []}, "spells": [4, 12]}
        with patch("desktop.worker.load_build", return_value={"pick": build}) as fetch:
            self.assertEqual(self.companion.preview_build(112, "MIDDLE"), {"pick": {"champion": "Виктор"}})
            self.assertEqual(self.companion.preview_build(999, "MIDDLE"), {})
            fetch.assert_called_once_with(self.catalog, "Viktor", "MIDDLE", 112)
        self.assertIsNone(self.companion.build)
        self.client.set_runes.assert_not_called()

    def test_latest_card_uses_solo_duo_and_clears_on_client_disconnect(self):
        self.client.me.return_value = {"puuid": "local-profile"}
        self.client.history_page.return_value = ([
            {"q": 440, "gid": 7, "t": 2000}, {"q": 420, "gid": 6, "champ": 112, "win": True,
                                              "k": 5, "d": 2, "a": 8, "t": 1000},
        ], False)
        self.companion.euw = True
        self.companion.update_latest_match(100, True)
        self.companion.history_job[1].result(timeout=2)
        self.companion.update_latest_match(101, True)
        self.assertEqual(self.companion.latest_match["id"], "EUW1_6")
        self.assertEqual(self.companion.latest_match["champion"], "Виктор")
        self.assertEqual(self.companion.latest_match["kda"], [5, 2, 8])
        self.client.port = None
        self.companion.update_latest_match(102, True)
        self.assertIsNone(self.companion.latest_match)
        self.assertIsNone(self.companion.home_profile)

    def test_home_separates_weekly_queues_and_records_rank_for_each_account(self):
        now = datetime(2026, 11, 23, 12).astimezone()
        stamp = lambda days: int((now - timedelta(days=days)).timestamp() * 1000)
        self.client.me.return_value = {"puuid": "account-a", "riot": "Player#EUW", "icon": 29}
        solo = {"state": "ranked", "tier": "EMERALD", "div": "II", "lp": 68, "w": 168, "l": 143}
        flex = {"state": "ranked", "tier": "PLATINUM", "div": "I", "lp": 24, "w": 3, "l": 2}
        self.client.ranked_overview.return_value = {"solo": solo, "flex": flex}
        games = [{"gid": index, "q": queue, "win": won, "t": stamp(age), "champ": 112}
                 for index, (queue, won, age) in enumerate(((420, True, 1), (440, False, 2), (450, True, 4),
                                                            (420, False, 8), (440, True, 30)), 1)]
        with TemporaryDirectory() as directory:
            history = RankHistory(Path(directory) / "rank", Path(directory) / "legacy")
            self.client.history_page.side_effect = [(games[:2], True), (games[2:], False)]
            snapshot = read_home(self.client, self.catalog, history, now)
            self.assertEqual(snapshot["weekly"], {
                "solo": {"wins": 1, "games": 1, "complete": True},
                "flex": {"wins": 0, "games": 1, "complete": True},
            })
            self.assertEqual(snapshot["month"]["days"], {22: 1, 21: 1, 19: 1, 15: 1})
            self.assertEqual([entry["queue"] for entry in snapshot["matches"]], [420, 440, 450, 420, 440])
            self.assertNotIn("puuid", snapshot["profile"])
            self.assertEqual(set(snapshot["trend"]), {"solo", "flex"})
            self.client.history_page.side_effect = None
            self.client.history_page.return_value = (games, False)
            solo["lp"] = 88
            later = read_home(self.client, self.catalog, history, now + timedelta(hours=1))
            self.assertEqual([lp for _, lp in later["trend"]["solo"]], [2268, 2288])
            self.assertEqual(len(later["trend"]["flex"]), 1)
            self.client.me.return_value = {"puuid": "account-b", "riot": "Other#EUW"}
            other = read_home(self.client, self.catalog, history, now + timedelta(hours=2))
            self.assertEqual([lp for _, lp in other["trend"]["solo"]], [2288])

    def test_home_marks_truncated_history_as_partial(self):
        now = datetime(2026, 11, 23, 12).astimezone()
        self.client.me.return_value = {"puuid": "account", "riot": "Player#EUW"}
        self.client.ranked_overview.return_value = {}
        self.client.history_page.side_effect = [
            ([{"gid": 2, "q": 420, "win": True, "t": int(now.timestamp() * 1000)}], True),
            None,
        ]
        snapshot = read_home(self.client, self.catalog, Mock(record=Mock(return_value={})), now)
        self.assertEqual(snapshot["weekly"]["solo"], {"wins": 1, "games": 1, "complete": False})
        self.assertTrue(snapshot["month"]["available"])
        self.assertFalse(snapshot["month"]["complete"])

    def test_home_loads_requested_history_beyond_analytics_window(self):
        now = datetime(2026, 11, 23, 12).astimezone()
        self.client.me.return_value = {"puuid": "account"}
        self.client.ranked_overview.return_value = {}
        games = [{"gid": 1000 - index, "q": 420, "win": True,
                  "t": int((now - timedelta(days=31 + index)).timestamp() * 1000)} for index in range(45)]
        self.client.history_page.side_effect = lambda puuid, n, offset: (games[offset:offset + n], offset + n < len(games))
        history = Mock(record=Mock(return_value={}))
        initial = read_home(self.client, self.catalog, history, now)
        self.assertEqual(len(initial["matches"]), 20)
        self.assertTrue(initial["historyHasMore"])
        self.assertFalse(initial["historyInterrupted"])
        self.client.history_page.assert_called_once_with("account", n=20, offset=0)
        self.client.history_page.reset_mock()

        expanded = read_home(self.client, self.catalog, history, now, history_limit=48)
        self.assertEqual([row["id"] for row in expanded["matches"]], [f"EUW1_{row['gid']}" for row in games])
        self.assertFalse(expanded["historyHasMore"])
        self.assertEqual(expanded["weekly"], initial["weekly"])
        self.assertEqual(expanded["month"], initial["month"])
        self.assertEqual(self.client.history_page.call_args_list,
                         [call("account", n=20, offset=offset) for offset in (0, 20, 40)])

    def test_interrupted_history_keeps_only_the_same_accounts_confirmed_matches(self):
        now = datetime(2026, 11, 23, 12).astimezone()
        self.client.me.return_value = {"puuid": "account-a", "level": 100}
        self.client.ranked_overview.return_value = {}
        games = [{"gid": gid, "q": 420, "win": True, "t": int(now.timestamp() * 1000) + gid}
                 for gid in (2, 1)]
        history = Mock(record=Mock(return_value={}))
        self.client.history_page.return_value = (games, False)
        original = read_home(self.client, self.catalog, history, now)
        self.companion.apply_home_profile(original)

        self.client.me.return_value = {"puuid": "account-a", "level": 101}
        self.client.history_page.return_value = None
        unavailable = read_home(self.client, self.catalog, history, now)
        self.companion.apply_home_profile(unavailable)
        self.assertEqual(self.companion.home_profile["profile"]["level"], 101)
        self.assertEqual(self.companion.home_profile["matches"], original["matches"])
        self.assertEqual(self.companion.latest_match["id"], "EUW1_2")

        new_game = dict(games[0], gid=3, t=games[0]["t"] + 1)
        self.client.history_page.side_effect = [([new_game, dict(games[0], win=False)], True), None]
        partial = read_home(self.client, self.catalog, history, now, history_limit=48)
        self.assertTrue(partial["historyInterrupted"])
        self.companion.apply_home_profile(partial)
        self.assertEqual([(row["id"], row["win"]) for row in self.companion.home_profile["matches"]],
                         [("EUW1_3", True), ("EUW1_2", False), ("EUW1_1", True)])
        self.assertEqual(self.companion.latest_match["id"], "EUW1_3")

        self.client.history_page.side_effect = None
        self.client.history_page.return_value = ([], False)
        empty = read_home(self.client, self.catalog, history, now)
        self.companion.apply_home_profile(empty)
        self.assertTrue(self.companion.home_profile["historyAvailable"])
        self.assertEqual(self.companion.home_profile["matches"], [])
        self.assertIsNone(self.companion.latest_match)

        self.companion.apply_home_profile(original)
        self.client.me.return_value = {"puuid": "account-b", "level": 50}
        self.client.history_page.return_value = None
        other = read_home(self.client, self.catalog, history, now)
        self.companion.apply_home_profile(other)
        self.assertEqual(self.companion.home_profile["profile"]["level"], 50)
        self.assertFalse(self.companion.home_profile["historyAvailable"])
        self.assertEqual(self.companion.home_profile["matches"], [])
        self.assertIsNone(self.companion.latest_match)

    def test_preview_distinguishes_provider_timeout_from_missing_build(self):
        with (patch("desktop.worker.load_specials", return_value=([], None, {})),
              patch("desktop.worker.load_build", side_effect=[TimeoutError("timeout"), None])):
            with self.assertRaises(TimeoutError):
                self.companion.preview_build(112, "MIDDLE", include_specials=True)
            self.assertEqual(self.companion.preview_build(112, "MIDDLE", include_specials=True), {})

    def test_catalog_rejects_empty_feeds_and_can_recover_same_version(self):
        for data in ([], {}):
            with patch("desktop.worker.get_json", side_effect=[["16.24.1"], {"data": data}]):
                self.assertIs(Companion.update_catalog(self.catalog), self.catalog)
        teemo = {"key": "17", "name": "Тимо", "tags": [], "info": {"magic": 6, "attack": 6, "defense": 3}}
        with patch("desktop.worker.get_json", side_effect=[["16.24.1"], {"data": {"Teemo": teemo}}]):
            self.assertIs(Companion.update_catalog(self.catalog), self.catalog)
        champion = {"key": "112", "name": "Виктор", "tags": [], "info": {"magic": 9, "attack": 2, "defense": 4}}
        with patch("desktop.worker.get_json", side_effect=[
            ["16.24.1"], {"data": {"Viktor": champion}}, {"data": {"3157": {"name": "Жоня"}}},
        ]):
            recovered = Companion.update_catalog({"patch": "16.24.1", "ids": {}, "items": {}})
        self.assertEqual(recovered["ids"], {"112": "Viktor"})

    def test_failed_catalog_job_is_consumed_and_next_refresh_can_finish(self):
        self.companion.catalog_job.result(timeout=2)
        broken, recovered = Future(), Future()
        broken.set_exception(AttributeError("Malformed catalog"))
        recovered.set_result(dict(self.catalog, patch="16.24.1"))
        self.companion.catalog_job = broken
        self.client.call.return_value = gameflow("Lobby")
        self.client.region.return_value = "EUW"
        self.assertEqual(self.companion.read_status(100)["phase"], "Lobby")
        self.assertIsNone(self.companion.catalog_job)
        self.assertIs(self.companion.catalog, self.catalog)
        with patch.object(self.companion.executor, "submit", return_value=recovered):
            self.companion.read_status(130)
            self.companion.read_status(131)
        self.assertEqual(self.companion.catalog["patch"], "16.24.1")


class DraftRosterTests(unittest.TestCase):
    catalog = {"patch": "16.23.1", "ids": {"112": "Viktor", "103": "Ahri", "238": "Zed"},
               "names": {"Viktor": "Виктор", "Ahri": "Ари", "Zed": "Зед"},
               "champs": {"Viktor": {"atk": 2, "mag": 8}, "Ahri": {"atk": 2, "mag": 8}}}

    def test_draft_shows_local_intent_and_only_confirmed_enemy_picks(self):
        data = {"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championPickIntent": 112, "assignedPosition": "middle",
                                                    "puuid": "hidden"}],
                "theirTeam": [{"cellId": 5, "championId": 103}, {"cellId": 6, "championId": 238}],
                "actions": [[{"actorCellId": 5, "type": "pick", "championId": 103, "completed": True},
                             {"actorCellId": 6, "type": "pick", "championId": 238, "completed": False}]],
                "timer": {"adjustedTimeLeftInPhase": 21500}}
        roster = draft_roster(data, self.catalog)
        self.assertEqual(roster["allies"], [{"championKey": "Viktor", "name": "Виктор", "role": "MIDDLE",
                                            "roleSlot": 0, "locked": False, "local": True}])
        self.assertEqual([card["championKey"] for card in roster["enemies"]], ["Ahri", None])
        self.assertEqual([card["roleSlot"] for card in roster["enemies"]], ["Ahri", None])
        self.assertEqual(roster["damage"]["enemies"]["n"], 1)
        self.assertEqual(roster["seconds"], 21)

    def test_composition_uses_open_picks_and_does_not_call_partial_team_weak(self):
        draft = {"myTeam": [{"cellId": 0, "championPickIntent": 112}],
                 "theirTeam": [{"cellId": 6, "championId": 238}]}
        roster = draft_roster(draft, self.catalog)
        self.assertEqual(roster["composition"]["allies"], [
            {"label": "Зачистка волн", "champions": ["Виктор"], "tone": "good"}])
        self.assertFalse(roster["composition"]["enemies"])

    def test_role_columns_preserve_known_positions_and_unassigned_cards(self):
        support = {"championKey": "Lux", "role": "UTILITY"}
        middle = {"championKey": "Viktor", "role": "MIDDLE", "local": True}
        pending = {"championKey": "Ornn", "role": None}
        top = {"championKey": "Renekton", "role": "TOP"}
        self.assertEqual(allied_role_slots([support, middle, pending, top]), [top, pending, middle, {}, support])

    def test_draft_options_exclude_locked_picks_and_completed_bans(self):
        session = {"bans": {"myTeamBans": [238]}, "actions": [[{"type": "ban", "championId": 103, "completed": False}]]}
        roster = {"allies": [{"championKey": "Viktor", "locked": True}], "enemies": []}
        unavailable = unavailable_draft_champions(session, roster, self.catalog)
        rows = [("MIDDLE", "Zed", 53, 2, 900), ("BOTTOM", "Sivir", 53, 2, 850),
                ("MIDDLE", "Viktor", 53, 2, 800), ("MIDDLE", "Ahri", 53, 2, 700)]
        self.assertEqual([choice["championKey"] for choice in
                          available_suggestions(rows, self.catalog["names"], unavailable, "MIDDLE")], ["Ahri"])

    def test_at_most_five_unique_available_champions(self):
        keys = ["Viktor", "Ahri", "Ahri", "Zed", "Lux", "Annie", "Fizz", "Karma", "Akali"]
        rows = [("MIDDLE", key, 53, 2, 900) for key in keys]
        result = available_suggestions(rows, self.catalog["names"], {"Viktor"}, "MIDDLE")
        self.assertEqual([option["championKey"] for option in result], ["Ahri", "Zed", "Lux", "Annie", "Fizz"])

    def test_enemy_counter_uses_validated_lane_and_opposing_win_rate(self):
        build = Mock(return_value={"header": {"lane": "middle", "damage": {"physical": 1300, "magic": 19000, "true": 150}, "n": 900}})
        source = {"response": {"valid": True}, "stats": {"cid": 112, "lane": "middle", "vsLane": "middle"},
                  "counters": [{"cid": 103, "n": 450, "vsWr": 48, "d2": -1.5},
                               {"cid": 238, "n": 420, "vsWr": 55, "d2": 2.5}]}
        request = Mock(return_value=source)
        result = fetch_champion_statistics(self.catalog, "enemies", "Viktor", 112, None, build, request)
        self.assertEqual(result["damage"], [1300, 19000, 150])
        self.assertEqual(result["suggestions"], [("MIDDLE", "Ahri", 52, 1.5, 450)])
        self.assertIn("&vslane=middle", request.call_args.args[0])
        source["stats"]["vsLane"] = "top"
        self.assertIsNone(fetch_champion_statistics(self.catalog, "enemies", "Viktor", 112, None, build, request)["suggestions"])


class ManualDraftRoleTests(unittest.TestCase):
    def test_guarded_import_cancels_rune_activation_and_item_write(self):
        adapter = LCU()
        selection = Mock(side_effect=[{"gameId": 15}, None])
        with patch.object(adapter, "call", side_effect=[[], {"id": 1}]) as transport:
            self.assertFalse(adapter.set_runes("Viktor", 8200, 8300, [8214, 8226, 8210, 8237, 8306, 8352],
                                               [5005, 5008, 5001], draft_session=selection))
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(transport.call_args.args[1], "POST")
        self.assertFalse(transport.call_args.args[2]["current"])
        with patch.object(adapter, "call", return_value={"itemSets": []}) as transport:
            self.assertFalse(adapter.set_items(1, 112, "Viktor", [("Core", [3157])], draft_session=lambda: None))
        transport.assert_called_once_with("/lol-item-sets/v1/item-sets/1/sets")

    def test_adapter_rejects_different_pick_and_confirms_spell_readback(self):
        adapter = LCU()
        own = {"cellId": 0, "championId": 112, "spell1Id": 14, "spell2Id": 4}
        draft = {"gameId": 15, "localPlayerCellId": 0, "myTeam": [own],
                 "actions": [[{"actorCellId": 0, "type": "pick", "completed": True}]]}
        for session in (None, [], dict(draft, gameId=16), dict(draft, myTeam=[dict(own, championId=99)])):
            with patch.object(adapter, "call", return_value=session) as call:
                self.assertFalse(adapter.set_spells(4, 12, expected_pick=(15, 112)))
            self.assertEqual(call.call_count, 1)
        for readback, applied in ((draft, False), (dict(draft, myTeam=[dict(own, spell1Id=12)]), True)):
            with patch.object(adapter, "call", side_effect=[draft, None, readback]) as call:
                self.assertEqual(adapter.set_spells(4, 12, expected_pick=(15, 112)), applied)
            self.assertEqual(call.call_args_list[1].args[-2:], ("PATCH", {"spell1Id": 12, "spell2Id": 4}))

    def test_import_reports_applied_runes_if_draft_vanishes_before_items(self):
        client = Mock()
        client.region.return_value = "EUW"
        client.call.return_value = gameflow("ChampSelect", 15, 420)
        draft = {"gameId": 15, "localPlayerCellId": 0,
                 "myTeam": [{"cellId": 0, "championId": 112, "assignedPosition": "middle"}],
                 "actions": [[{"actorCellId": 0, "type": "pick", "championId": 112, "completed": True}]]}
        client.champ_select.side_effect = [draft, OSError("Client disconnected")]
        client.set_runes.return_value = True
        catalog = DraftRosterTests.catalog
        with (patch("desktop.worker.read_catalog", return_value=catalog),
              patch.object(Companion, "update_catalog", return_value=catalog)):
            companion = Companion(client)
        self.addCleanup(companion.close)
        companion.build_key = ("Viktor", "MIDDLE", 112, 15)
        build = {"variant": {"prim": 8200, "sec": 8000, "perks": [], "shards": []}, "sets": []}
        companion.build = {"pick": build}
        shown = companion.visible_builds()["pick"]["revision"]
        result = companion.export(list(companion.build_key), "pick", revision=shown)
        self.assertEqual(result["results"][0], "Руны применены")
        self.assertIn("Набор предметов не добавлен", result["results"][1])
        client.set_items.assert_not_called()

    def test_import_never_applies_a_replacement_under_the_same_key(self):
        client = Mock()
        client.region.return_value = "EUW"
        key = ("Viktor", "MIDDLE", 112, 15)
        with (patch("desktop.worker.read_catalog", return_value={}),
              patch.object(Companion, "update_catalog", return_value={})):
            companion = Companion(client)
        self.addCleanup(companion.close)
        companion.build_key = key
        original = {"spellNames": ["Скачок", "Телепорт"], "spells": [4, 12]}
        companion.special_builds = {"matchup": original}
        shown = companion.visible_builds()["matchup"]["revision"]
        companion.special_builds["matchup"] = {"spellNames": ["Скачок", "Очищение"], "spells": [4, 1]}
        with (patch.object(companion, "query_session", return_value=gameflow("ChampSelect", 15, 420)),
              patch.object(companion, "draft_target", return_value=(key, True))):
            result = companion.export(list(key), "matchup", True, revision=shown)
            self.assertIn("Сборка обновилась", result["results"][0])
            client.set_spells.assert_not_called()
            current = companion.visible_builds()["matchup"]["revision"]
            companion.export(list(key), "matchup", True, revision=current)
            client.set_spells.assert_called_once_with(4, 1, draft_session=ANY)

    def test_roles_use_the_current_draft_and_auto_restores_the_original(self):
        session = {"gameId": 15, "localPlayerCellId": 0,
                   "myTeam": [{"cellId": 0, "championId": 112, "assignedPosition": "middle"}],
                   "theirTeam": [{"cellId": 5, "championId": 103}, {"cellId": 6, "championId": 238}],
                   "actions": [[{"actorCellId": 0, "type": "pick", "championId": 112, "completed": True},
                                {"actorCellId": 5, "type": "pick", "championId": 103, "completed": True}]]}
        catalog = DraftRosterTests.catalog
        client = Mock()
        client.region.return_value = "EUW"
        client.call.return_value = gameflow("ChampSelect", 15, 420)
        client.champ_select.return_value = session
        with (patch("desktop.worker.read_catalog", return_value=catalog),
              patch.object(Companion, "update_catalog", return_value=catalog)):
            companion = Companion(client)
        self.addCleanup(companion.close)

        roster = draft_roster(session, catalog)
        companion.apply_draft_roles(roster, 15, (15, "enemies", "Zed", "TOP"))
        self.assertFalse(companion.role_overrides)
        companion.apply_draft_roles(roster, 15, (15, "enemies", "Ahri", "UTILITY"))
        companion.apply_draft_roles(roster, 15, (15, "allies", 0, "TOP"))
        self.assertEqual(roster["enemies"][0]["manualRole"], "UTILITY")
        self.assertEqual(roster["allies"][0]["role"], "MIDDLE")
        self.assertEqual(companion.draft_target(session), (("Viktor", "TOP", 112, 15), True))
        companion.build_key = ("Viktor", "TOP", 112, 15)
        companion.build = {"pick": {"spellNames": ["Скачок", "Телепорт"], "spells": [4, 12]}}
        companion.export(["Viktor", "MIDDLE", 112, 15], spells_only=True)
        client.set_spells.assert_not_called()
        companion.export(list(companion.build_key), spells_only=True)
        client.set_spells.assert_called_once_with(4, 12, draft_session=ANY)

        roster = draft_roster(session, catalog)
        companion.apply_draft_roles(roster, 15, (15, "allies", 0, "auto"))
        self.assertEqual(companion.draft_target(session)[0][1], "MIDDLE")
        self.assertEqual(roster["enemies"][0]["manualRole"], "UTILITY")
        roster = draft_roster(session, catalog)
        companion.apply_draft_roles(roster, 16, (15, "enemies", "Ahri", "TOP"))
        self.assertFalse(companion.role_overrides)
        self.assertNotIn("manualRole", roster["enemies"][0])


class DraftProfilesTests(unittest.TestCase):
    def test_swapped_roles_move_cards_and_recalculate_on_role_tag(self):
        game = {"q": 420, "dur": 1800, "win": True, "k": 4, "d": 2, "a": 8, "cs": 200,
                "vis": 20, "dmg": 24000, "champ": 112, "lane": "TOP", "role": "SOLO"}
        draft = {"gameId": 10, "localPlayerCellId": 0, "myTeam": [
            {"cellId": 0, "championId": 112, "assignedPosition": "middle"},
            {"cellId": 1, "championId": 103, "assignedPosition": "top"}]}
        roster = draft_roster(draft, DraftRosterTests.catalog)
        local, ally = roster["allies"]
        local["manualRole"], ally["manualRole"] = "TOP", "MIDDLE"
        self.assertIs(allied_role_slots(roster["allies"])[0], local)
        self.assertIs(allied_role_slots(roster["allies"])[2], ally)
        profiles = DraftProfiles()
        client = Mock(port=1234, token="test")
        profiles.session = (1234, "test", 10, 0)
        profiles.cache[None] = 200, ("Self#EUW", [game, game], None)
        profiles.apply(roster, draft, client, Mock(), 100, {"Viktor": 112})
        tag = next(tag for tag in local["profile"]["tags"] if tag["label"].startswith("На роли"))
        self.assertIn("2 из 2", tag["detail"])

    def test_profiles_use_solo_duo_and_keep_real_tag_evidence(self):
        game = {"q": 420, "dur": 1800, "win": True, "k": 4, "d": 2, "a": 8, "cs": 240,
                "vis": 20, "dmg": 24000, "champ": 112, "lane": "MID", "role": "SOLO"}
        profile = describe_profile(("Player#EUW", [dict(game, q=440), game, game, game], None), "112", "MIDDLE")
        self.assertEqual((profile["w"], profile["n"], profile["on"]), (3, 3, 3))
        labels = [tag["label"] for tag in profile["tags"]]
        self.assertEqual(labels, ["Серия побед", "Редко умирает", "Высокий KDA", "Хороший фарм"])
        self.assertEqual(describe_profile(("", None, None), None, None)["status"], "unavailable")

    def test_only_self_and_explicitly_visible_ally_are_read_even_when_old_result_finishes(self):
        team = [{"cellId": 0, "puuid": "slot-self"},
                {"cellId": 1, "puuid": "hidden", "gameName": "Hidden", "tagLine": "EUW", "nameVisibilityType": "HIDDEN"},
                {"cellId": 2, "puuid": "duo", "gameName": "Duo", "tagLine": "EUW", "nameVisibilityType": "VISIBLE"}]
        enemy = {"cellId": 5, "puuid": "enemy", "gameName": "Enemy", "tagLine": "EUW", "nameVisibilityType": "VISIBLE"}
        draft = {"gameId": 100, "localPlayerCellId": 0, "myTeam": team, "theirTeam": [enemy]}
        client = Mock(port=1234, token="test")
        client.__copy__ = Mock(return_value=client)
        client.me.return_value = {"puuid": "self", "riot": "Self#EUW"}
        client.history.return_value = []
        client.rank.return_value = None
        profiles = DraftProfiles()
        with ThreadPoolExecutor(max_workers=1) as executor:
            catalog = DraftRosterTests.catalog
            roster = draft_roster(draft, catalog)
            profiles.apply(roster, draft, client, executor, 100, {})
            profiles.pending[2].result(timeout=2)
            profiles.apply(roster, draft, client, executor, 101, {})
            self.assertEqual(roster["allies"][0]["profile"]["name"], "Self#EUW")
            self.assertEqual(roster["allies"][2]["profile"]["name"], "Duo#EUW")
            profiles.pending[2].result(timeout=2)
            team[2]["nameVisibilityType"] = "HIDDEN"
            roster = draft_roster(draft, catalog)
            profiles.apply(roster, draft, client, executor, 102, {})
            self.assertEqual([bool(card.get("profile")) for card in roster["allies"]], [True, False, False])
            self.assertNotIn("profile", roster["enemies"][0])
        self.assertEqual([call.args[0] for call in client.history.call_args_list], ["self", "duo"])


class ExtraBuildTests(unittest.TestCase):
    catalog = {"patch": "16.23.1", "names": {"Viktor": "Виктор", "Ryze": "Райз"},
               "items": {"4637": {"n": "Создатель Разломов"}, "3165": {"n": "Мореллономикон"},
                         "3102": {"n": "Завеса банши"}},
               "champs": {"Viktor": {"tags": ["Mage"]}}}
    perks = [8992, 8226, 8234, 8237, 9103, 8014]

    def test_malformed_optional_build_does_not_discard_popular_build(self):
        pick = {"runes": {"set": {"pri": self.perks[:4], "sec": self.perks[4:], "mod": [5005, 5008, 5011]}},
                "sums": {"ids": [4, 14]}, "items": {"core": {"set": [4637], "wr": 54, "n": 100}}}
        raw = {"header": {"patch": "16.23"}, "summary": {"pick": pick, "win": ["unexpected"]},
               "boots": [[1]], "popularItem": [None]}
        with patch("desktop.worker.read_build_response", return_value=raw):
            builds = load_build(self.catalog, "Viktor", "MIDDLE", 112)
        self.assertEqual(list(builds), ["pick"])
        self.assertEqual(builds["pick"]["spellIds"], [4, 14])

    def test_tournament_loadout_and_opponent_share_the_same_game(self):
        names = "Deathfire Touch,Manaflow Band,Celerity,Gathering Storm,Legend: Haste,Cut Down"
        english = ({"Viktor": "Viktor", "Ryze": "Ryze"}, {"riftmaker": 4637},
                   {"Sorcery": 8200, "Precision": 8000}, dict(zip(names.lower().split(","), self.perks)))
        row = {"Player": "buda", "Champion": "Viktor", "Role": "Mid", "Patch": "26.23", "Match": "cup_2_1",
               "Event": "Cup", "Runes": names + ",Attack Speed,Move Speed,Health", "PlayedAt": "2026-11-21",
               "Items": "Riftmaker", "PrimaryTree": "Sorcery", "SecondaryTree": "Precision",
               "SummonerSpells": "Flash,Ignite"}
        opponent = {"Player": "buda", "Match": "cup_2_1", "EnemyMatch": "cup_2_1", "Opponent": "Ryze", "EnemyRole": "Mid"}
        with (patch("desktop.extra_builds.english_catalog", return_value=english),
              patch("desktop.extra_builds.read_json", side_effect=[
                  {"cargoquery": [{"title": dict(row, Patch="26.22")}, {"title": row}]},
                  {"cargoquery": [{"title": dict(opponent, EnemyMatch="different")}, {"title": opponent}]},
              ])):
            builds = tournament_builds(self.catalog, "Viktor", "MIDDLE")
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0]["spellIds"], [4, 14])
        self.assertTrue(builds[0]["canImportRunes"])
        options = special_options(builds, None, "Ryze", self.catalog["names"])
        self.assertEqual(options["matchup"]["title"], "VS · Райз")
        self.assertEqual(options["pro:buda"]["items"][0]["id"], 4637)
        self.assertNotIn("matchup", special_options(builds, None, "Ahri", self.catalog["names"]))

    def test_personal_recipe_does_not_fill_in_missing_shards_or_claim_buy_order(self):
        stats = {f"perk{i}": perk for i, perk in enumerate(self.perks)}
        stats.update(perkPrimaryStyle=8200, perkSubStyle=8000, item0=4637)
        client = Mock()
        client.region.return_value = "EUW"
        client.me.return_value = {"puuid": "self"}
        client.history.return_value = [{"q": 420, "champ": 112, "dur": 1300, "lane": "MID", "gid": 1}]
        client.game.return_value = {
            "gameVersion": "16.23.839.9929",
            "participantIdentities": [{"participantId": 1, "player": {"puuid": "self"}}],
            "participants": [{"participantId": 1, "championId": 112, "spell1Id": 4, "spell2Id": 12, "stats": stats}],
        }
        build = personal_build(self.catalog, "Viktor", "MIDDLE", 112, client)
        self.assertEqual(build["runes"], self.perks)
        self.assertEqual(build["shards"], [])
        self.assertFalse(build["canImportRunes"])
        self.assertEqual(build["itemHeading"], "Предметы на конец матча")
        self.assertIsNone(personal_build(self.catalog, "Viktor", "TOP", 112, client))

    def test_pro_rank_comes_from_exact_euw_profile(self):
        builds = [{"player": "Nick", "playerProfile": "Nick (EU Player)"},
                  {"player": "Unknown", "playerProfile": "Unknown"},
                  {"player": "Linked", "playerProfile": "Linked"}]
        client = Mock()
        client.region.return_value = "EUW"
        client.puuid.return_value = "confirmed-puuid"
        client.rank.return_value = {"tier": "MASTER", "div": "NA", "lp": 527}
        rows = [{"Page": "Nick", "SoloqueueIds": "EUW: Another Nick#EUW"},
                {"Page": "Nick (EU Player)", "SoloqueueIds": "NA: Nick#NA1<br>'''EUW:''' His Name#1234"},
                {"Page": "Unknown", "SoloqueueIds": "EUW: Untagged<br>KR: Other#KR1"},
                {"Page": "Linked", "Lolpros": "https://lolpros.gg/player/linked"}]
        page = b'<a href="//op.gg/lol/summoners/euw/Linked%20Account-LNK" class="--opgg">'
        with (patch("desktop.extra_builds.read_json", return_value={"cargoquery": [{"title": row} for row in rows]}),
              patch("desktop.extra_builds.urlopen", mock_open(read_data=page))):
            add_pro_ranks(builds, client)
        self.assertEqual([call.args[0] for call in client.puuid.call_args_list], ["His Name#1234", "Linked Account#LNK"])
        self.assertEqual(client.rank.call_count, 2)
        self.assertEqual(builds[0]["proRank"], {"tier": "MASTER", "label": "Мастер", "lp": 527})
        self.assertNotIn("proRank", builds[1])
        self.assertEqual(builds[2]["proRank"], builds[0]["proRank"])

    def test_situational_items_and_manual_opponent(self):
        enemies = [{"championKey": "Vladimir", "name": "Владимир", "manualRole": "MIDDLE", "insights": {"damage": [1, 9, 0]}},
                   {"championKey": "Ryze", "name": "Райз", "insights": {"role": "MIDDLE", "damage": [1, 9, 0]}},
                   {"championKey": "Lux", "name": "Люкс", "insights": {"role": "MIDDLE", "damage": [2, 8, 0]}}]
        self.assertEqual(lane_opponent({"enemies": enemies}, "MIDDLE"), "Vladimir")
        self.assertEqual([row["id"] for row in situational_items(self.catalog, "Viktor", enemies)], [3165, 3102])

    def test_specialists_are_distinct_and_uncommon_build_needs_evidence(self):
        catalog = dict(self.catalog, items={**self.catalog["items"], **{
            str(number): {"name": str(number), "tags": ["Boots"] if number in (3020, 3111) else []}
            for number in (3020, 3111, 2503, 3152, 3100)
        }})
        summary = {"runes": {"set": {"pri": self.perks[:4], "sec": self.perks[4:], "mod": [5005, 5008, 5011]}},
                   "sums": {"ids": [4, 14]}, "items": {"core": {"set": [2503, 3020, 3100], "wr": 54}}}
        raw = {"summary": {"pick": summary}, "header": {"n": 10_000}, "builtBootSet3": [
            ["2503_3020_3100", 54, 14, 1400], ["3020_2503_3100", 55, 10, 1000],
            ["2503_3111_3100", 80, 4, 400], ["3152_3111_2503", 65, 1, 100],
            ["4637_3111_2503", 100, .01, 1],
        ]}
        with patch("desktop.extra_builds.specialist_build_data", return_value=raw):
            options = specialist_builds(catalog, "Viktor", "MIDDLE", 112)
        self.assertEqual([build["sample"] for build in options.values()], [1400, 400, 100])
        parsed = {"pick": options["otp:1"]["variant"] | {"core": [2503, 3020, 3100], "wr_core": 54,
                  "spells": ["SummonerFlash", "SummonerDot"], "start": []}, "win": None}
        unusual = uncommon_build(catalog, "Viktor", "MIDDLE", raw, parsed)
        self.assertEqual((unusual["sample"], unusual["winRate"]), (100, 65))
        self.assertEqual([item["id"] for item in unusual["items"]], [3152, 3111, 2503])
