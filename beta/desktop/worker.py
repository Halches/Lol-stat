"""Local, line-delimited JSON bridge for the Windows companion."""
import argparse
import ctypes
import json
import os
import re
import sys
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from ctypes import wintypes
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

if not getattr(sys, "frozen", False):
    project = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(project.parent / "app"), str(project)]

import core
import lcu
import rune_catalog

if __package__:
    from .draft_analysis import DraftProfiles, team_capabilities
    from .draft_stats import DraftStats, SUGGESTION_LIMIT
    from .extra_builds import SOURCE_ERRORS, lane_opponent, load_specials, situational_items, special_options, uncommon_build
    from .home_data import PAGE_SIZE, RankHistory, read_home
    from .profile_memory import ProfileMemory
else:
    from draft_analysis import DraftProfiles, team_capabilities
    from draft_stats import DraftStats, SUGGESTION_LIMIT
    from extra_builds import SOURCE_ERRORS, lane_opponent, load_specials, situational_items, special_options, uncommon_build
    from home_data import PAGE_SIZE, RankHistory, read_home
    from profile_memory import ProfileMemory


DDRAGON = "https://ddragon.leagueoflegends.com"
PLAYING = {"GameStart", "InProgress", "Reconnect"}
SUPPORTED_QUEUES = {420, 440}
LIVE_QUEUES = SUPPORTED_QUEUES | {3140}  # Multiplayer Practice Tool; no ranked draft/import.
ENDED = {"WaitingForStats", "PreEndOfGame", "EndOfGame"}
HOME_PHASES = {"None", "Lobby", "Matchmaking", "ReadyCheck", "idle", "offline"}
DRAFT_PHASES = {"pick", "loading", "no_build", "draft"}
FLOW_DISCONNECT_GRACE = 30
GAME_EXECUTABLE = "league of legends.exe"
ROLES = {"TOP": "Верх", "JUNGLE": "Лес", "MIDDLE": "Центр", "BOTTOM": "Низ", "UTILITY": "Поддержка"}


def get_json(url):
    with urlopen(Request(url, headers={"User-Agent": "LoL Helper Beta"}), timeout=6) as response:
        return json.load(response)


def public_catalog(path):
    with path.open(encoding="utf-8") as file:
        snapshot = json.load(file)
    return {key: snapshot[key] for key in ("patch", "ids", "names", "items", "champs")}


def read_catalog():
    if getattr(sys, "frozen", False):
        path = Path(sys._MEIPASS) / "catalog.json"
    else:
        path = Path(__file__).resolve().parents[2] / "app/data.json"
    return public_catalog(path)


def read_build_response(catalog, champion, role, cid):
    version = ".".join(catalog["patch"].split(".")[:2])
    url = core.lola_api("build-full", champion, role, "euw").replace("patch=30", "patch=" + version)
    if role is None:
        url = url.replace("&lane=top", "&lane=all")
    raw = get_json(url)
    header = raw.get("header") or {}
    lane = core.LOLA_LANE[role] if role is not None else header.get("defaultLane")
    if ((raw.get("response") or {}).get("valid") is not True
            or str(header.get("cid")) != str(cid) or header.get("patch") != version
            or not lane or header.get("lane") != lane or header.get("queue") != 420):
        return None
    return raw


def load_build(catalog, champion, role, cid):
    raw = read_build_response(catalog, champion, role, cid)
    if raw is None:
        return None
    version = raw["header"]["patch"]
    parsed = core.parse_lola_full(raw)
    if not parsed:
        return None
    keys = [key for key in ("pick", "win") if parsed[key]]
    builds = {}
    for key, item_set in zip(keys, core.lola_item_sets(parsed, champion)):
        build = parsed[key]
        if not build["core"] or not rune_catalog.valid_page(build["prim"], build["sec"], build["perks"], build["shards"]):
            continue
        spells = [core.SPELL_ID.get(spell) for spell in build["spells"]]
        spell_names = [core.SPELL_RU.get(spell, spell) for spell in build["spells"]]
        valid_spells = len(spells) == 2 and all(spells) and spells[0] != spells[1]
        items = []
        for item_id in core.lola_build_items(build):
            item = catalog["items"].get(str(item_id), {})
            items.append({"id": item_id, "name": item.get("n") or item.get("name") or str(item_id)})
        builds[key] = {
            "champion": catalog["names"].get(champion, champion), "role": core.ROLE_RU[role],
            "championKey": champion, "assetVersion": catalog["patch"],
            "patch": version, "source": "Lolalytics · EUW · Изумруд+",
            "sample": build["n_core"], "winRate": build["wr_core"],
            "items": items,
            "runes": build["perks"], "shards": build["shards"],
            "spellNames": spell_names if valid_spells else [], "spellIds": spells if valid_spells else [],
            "spells": spells, "variant": build, "sets": [item_set],
        }
    if unusual := uncommon_build(catalog, champion, role, raw, parsed):
        builds["unusual"] = unusual
    return builds


def draft_roster(session, catalog):
    locked_picks = {action.get("actorCellId"): action.get("championId")
                    for group in session.get("actions") or [] for action in group
                    if action.get("type") == "pick" and action.get("completed")
                    and type(action.get("actorCellId")) is int}
    roster = {}
    for side, key in (("allies", "myTeam"), ("enemies", "theirTeam")):
        allies = side == "allies"
        cards = []
        members = (session.get(key) or [])[:5]
        team_picks = {locked_picks.get(member.get("cellId")) for member in members}
        for member in members:
            cell = member.get("cellId")
            champ = member.get("championId")
            locked = bool(champ and cell in locked_picks and (allies or champ in team_picks))
            visible = (champ or member.get("championPickIntent")) if allies else (champ if locked else None)
            champion = catalog["ids"].get(str(visible))
            slot = (cell if type(cell) is int else None) if allies else champion
            cards.append({"championKey": champion, "name": catalog["names"].get(champion, champion),
                          "role": core.LCU_ROLE.get((member.get("assignedPosition") or "").lower()) if allies else None,
                          "roleSlot": slot,
                          "locked": locked and bool(champion),
                          "local": allies and cell is not None and cell == session.get("localPlayerCellId")})
        roster[side] = cards
    timer = (session.get("timer") or {}).get("adjustedTimeLeftInPhase")
    roster["seconds"] = max(0, timer // 1000) if type(timer) is int else None
    roster["assetVersion"] = catalog["patch"]
    profile = SimpleNamespace(champs=catalog.get("champs", {}))
    roster["damage"] = {side: core.team_comp(profile, [card["championKey"] for card in roster[side]])
                        for side in ("allies", "enemies")}
    roster["composition"] = {side: team_capabilities(roster[side], catalog) for side in ("allies", "enemies")}
    return roster


def allied_role_slots(members):
    slots = dict.fromkeys(ROLES)
    other = []
    for member in sorted(members, key=lambda member: not member.get("manualRole")):
        role = member.get("manualRole") or member.get("role")
        if role in slots and slots[role] is None:
            slots[role] = member
        else:
            other.append(member)
    unassigned = iter(other)
    return [member if member is not None else next(unassigned, {}) for member in slots.values()]


def unavailable_draft_champions(session, roster, catalog):
    bans = session.get("bans") or {}
    ids = set((bans.get("myTeamBans") or []) + (bans.get("theirTeamBans") or []))
    ids.update(action.get("championId") for group in session.get("actions") or [] for action in group
               if action.get("type") == "ban" and action.get("completed"))
    unavailable = {catalog["ids"].get(str(cid)) for cid in ids}
    unavailable.update(card["championKey"] for side in ("allies", "enemies") for card in roster[side] if card["locked"])
    unavailable.discard(None)
    return unavailable


def foreground_game():
    if os.name != "nt":
        return None
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user.IsIconic.argtypes = (wintypes.HWND,)
    user.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    hwnd = user.GetForegroundWindow()
    pid = wintypes.DWORD()
    if (not hwnd or user.IsIconic(hwnd) or not user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            or not is_game_process(pid.value)):
        return None

    set_dpi = getattr(user, "SetThreadDpiAwarenessContext", None)
    previous_dpi = None
    if set_dpi:
        set_dpi.argtypes = (ctypes.c_void_p,)
        set_dpi.restype = ctypes.c_void_p
        previous_dpi = set_dpi(ctypes.c_void_p(-4))  # Per-monitor aware v2, physical pixels.
    try:
        rect, origin = wintypes.RECT(), wintypes.POINT()
        if (not user.GetClientRect(hwnd, ctypes.byref(rect)) or not user.ClientToScreen(hwnd, ctypes.byref(origin))
                or rect.right <= 0 or rect.bottom <= 0 or user.GetForegroundWindow() != hwnd):
            return None
        return {"x": origin.x, "y": origin.y, "width": rect.right, "height": rect.bottom}
    finally:
        if previous_dpi:
            set_dpi(previous_dpi)


def is_game_process(pid):
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    )
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        length = wintypes.DWORD(32768)
        name = ctypes.create_unicode_buffer(length.value)
        return bool(kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length))
                    and Path(name.value).name.casefold() == GAME_EXECUTABLE)
    finally:
        kernel.CloseHandle(handle)


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                ("heap_id", ctypes.c_size_t), ("module_id", wintypes.DWORD), ("threads", wintypes.DWORD),
                ("parent_pid", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                ("name", wintypes.WCHAR * 260)]


def game_process_running():
    if os.name != "nt":
        return False
    kernel = ctypes.windll.kernel32
    snapshot = kernel.CreateToolhelp32Snapshot
    snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    snapshot.restype = wintypes.HANDLE
    for read_process in (kernel.Process32FirstW, kernel.Process32NextW):
        read_process.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
        read_process.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if handle == ctypes.c_void_p(-1).value:
        return False
    try:
        entry = ProcessEntry(size=ctypes.sizeof(ProcessEntry))
        found = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while found:
            if entry.name.casefold() == GAME_EXECUTABLE:
                return True
            found = kernel.Process32NextW(handle, ctypes.byref(entry))
        return False
    finally:
        kernel.CloseHandle(handle)


class Companion:
    def __init__(self, client=None, *, profile_memory=None):
        self.lcu = client or lcu.LCU()
        self.voice_context = {}
        self.voice_current_read = False
        self.catalog = read_catalog()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.locked_executor = ThreadPoolExecutor(max_workers=2)
        self.context_executor = ThreadPoolExecutor(max_workers=1)
        self.special_executor = ThreadPoolExecutor(max_workers=2)
        self.card_stats = DraftStats(read_build_response, get_json)
        self.draft_profiles = DraftProfiles()
        self.build_key = None
        self.build_job = None
        self.build = None
        self.build_roster = None
        self.build_patch = None
        self.draft_flow_binding = None
        self.build_locked = False
        self.special_job = None
        self.special_cache = OrderedDict()
        self.special_builds = {}
        self.role_draft_id = None
        self.draft_seen = 0
        self.role_overrides = {}
        self.retry_at = 0
        self.next_discovery = 0
        self.last_read = 0
        self.game = None
        self.flow_connection = None
        self.flow_missing_since = None
        self.flow_generation = 0
        self.finished = None
        self.euw = False
        self.platform = None
        self.region_after = 0
        self.client_phase = "offline"
        self.queue_id = None
        self.latest_match = None
        self.profile_memory = profile_memory if profile_memory is not None else ProfileMemory() if client is None else None
        self.home_profile = self.profile_memory.load() if self.profile_memory else None
        self.profile_cached = bool(self.home_profile)
        if self.home_profile:
            self.latest_match = next((row for row in self.home_profile['matches'] if row.get('queue') in SUPPORTED_QUEUES),None)
        self.rank_history = RankHistory()
        self.history_limit = PAGE_SIZE
        self.history_after = 0
        self.history_connection = None
        self.history_job = None
        self.history_failed = False
        self.catalog_after = 0
        self.catalog_job = self.executor.submit(self.update_catalog, self.catalog)
        self.status = {"phase": "offline", "build": None, "matchId": None}

    @staticmethod
    def update_catalog(fallback):
        try:
            latest = get_json(DDRAGON + "/api/versions.json")[0]
            if not isinstance(latest, str) or not re.fullmatch(r"\d+\.\d+\.\d+", latest):
                return fallback
            if latest == fallback.get("patch") and fallback.get("ids") and fallback.get("items"):
                return fallback
            base = f"{DDRAGON}/cdn/{latest}/data/ru_RU/"
            names = get_json(base + "champion.json")["data"]
            if not isinstance(names, dict) or not names:
                return fallback
            ids = {data["key"]: champ for champ, data in names.items()}
            if (len(ids) != len(names) or not all(isinstance(cid, str) and cid.isdecimal() for cid in ids)
                    or not set(fallback.get("ids", {})).issubset(ids)):
                return fallback
            items = get_json(base + "item.json")["data"]
            previous_items = set(fallback.get("items", {}))
            if (not isinstance(items, dict) or not items or len(previous_items.intersection(items)) * 4 < len(previous_items) * 3
                    or not all(isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]
                               for item in items.values())):
                return fallback
            return {
                "patch": latest, "names": {champ: data["name"] for champ, data in names.items()},
                "ids": ids,
                "items": items,
                "champs": {champ: {"tags": data["tags"], "mag": data["info"]["magic"],
                                   "atk": data["info"]["attack"], "def": data["info"]["defense"]}
                           for champ, data in names.items()},
            }
        except SOURCE_ERRORS:
            return fallback

    def query_session(self):
        try:
            session = self.lcu.call("/lol-gameflow/v1/session")
        except SOURCE_ERRORS:
            session = None
        game = session.get("gameData") if isinstance(session, dict) else None
        queue = game.get("queue") if isinstance(game, dict) else None
        if (not isinstance(session, dict) or not isinstance(session.get("phase"), str)
                or game is not None and not isinstance(game, dict) or queue is not None and not isinstance(queue, dict)):
            session = {}
        if not session and not self.lcu.port:
            self.next_discovery = time.monotonic() + 4
            self.euw = False
        return session

    def query_draft(self):
        try:
            draft = self.lcu.champ_select()
        except SOURCE_ERRORS:
            return None
        return draft if isinstance(draft, dict) and draft.get("myTeam") else None

    def draft_target(self, session=None, *, game_id=None, roster=None):
        if session is None:
            session = self.query_draft() or {}
        own = next((p for p in session.get("myTeam", [])
                    if p.get("cellId") == session.get("localPlayerCellId")), {})
        draft = core.parse_champ_select(session, SimpleNamespace(ids=self.catalog["ids"]))
        cid = own.get("championId") or own.get("championPickIntent")
        game_id = session.get("gameId") or game_id
        role = draft["role"]
        if game_id == self.role_draft_id and self.role_overrides:
            if roster is None:
                roster = draft_roster(session, self.catalog)
                self.annotate_roles(roster)
            card = next((card for card in roster["allies"] if card["local"]), {})
            role = card.get("manualRole") or card.get("effectiveRole") or role
        if not draft["me"] or not role or not cid:
            return None
        return (draft["me"], role, cid, game_id), draft["locked"]

    def snapshot(self, *, home=False, role_change=None, history_limit=None, refresh_connection=False):
        now = time.monotonic()
        if refresh_connection:
            self.lcu.find()
            self.last_read = self.next_discovery = self.region_after = self.history_after = 0
        if role_change is not None or now >= max(self.next_discovery, self.last_read + 0.9):
            self.last_read = now
            self.status = self.read_status(now, role_change)
            self.voice_context = {
                "active": (self.status.get("phase") == "game" and self.client_phase in PLAYING
                           and self.flow_missing_since is None and self.euw and self.game is not None
                           and self.voice_current_read),
                "gameId": self.game, "generation": self.flow_generation, "observedAt": now,
                "role": self.build_key[1] if self.build_key and self.build_key[3] == self.game else "",
            }
        snapshot = dict(self.status, flowGeneration=self.flow_generation, queueId=self.queue_id)
        if home:
            is_home = self.client_phase in HOME_PHASES
            if history_limit is not None and history_limit > self.history_limit:
                self.history_limit = history_limit
                self.history_after = 0
            self.update_latest_match(now, is_home)
            profile = self.home_profile if is_home else None
            if profile is not None:
                profile = {key: value for key, value in profile.items() if key != "_accountKey"}
            snapshot.update(home=is_home, latestMatch=self.latest_match if is_home else None,
                            homeProfile=profile, connection=self.connection_state())
        else:
            snapshot["bounds"] = foreground_game()
        return snapshot

    def update_latest_match(self, now, is_home):
        connection = (self.lcu.port, self.lcu.token) if self.euw and self.lcu.port else None
        if connection != self.history_connection:
            self.history_connection = connection
            self.profile_cached = bool(self.home_profile)
            self.history_after = 0
            self.history_failed = False
        if self.history_job and self.history_job[1].done():
            requested, job = self.history_job
            self.history_job = None
            if requested == connection:
                profile = job.result()
                self.history_failed = profile is None
                if profile is not None:
                    self.apply_home_profile(profile)
        if connection and is_home and self.history_job is None and now >= self.history_after:
            self.history_after = now + 30
            self.history_job = connection, self.context_executor.submit(self.read_home_profile, copy(self.lcu),
                                                                        self.history_limit)

    def connection_state(self):
        has_profile = bool(self.home_profile and self.home_profile.get("profile"))
        loading = self.history_job is not None
        if not self.lcu.port:
            state = "offline"
        elif not self.euw:
            state = "unsupported_region" if self.platform else "connecting"
        elif has_profile and not self.profile_cached:
            state = "ready"
        elif loading:
            state = "loading_profile"
        elif self.history_failed:
            state = "profile_error"
        elif self.client_phase not in HOME_PHASES:
            state = "in_match"
        else:
            state = "connecting"
        history = ("cached" if self.home_profile and (self.profile_cached or self.home_profile.get("historyInterrupted"))
                   and self.home_profile.get("matches") else "available" if self.home_profile
                   and self.home_profile.get("historyAvailable") else "loading" if loading else "unavailable")
        return {"state": state, "clientDetected": bool(self.lcu.port), "region": self.platform if self.lcu.port else None,
                "profileAvailable": has_profile, "refreshing": loading, "history": history,
                "profileCached": self.profile_cached, "savedAt": (self.home_profile or {}).get('savedAt')}

    def apply_home_profile(self, profile):
        previous = self.home_profile
        if profile["historyInterrupted"] and previous and previous["_accountKey"] == profile["_accountKey"]:
            matches = {row["id"]: row for row in profile["matches"]}
            for row in previous["matches"]:
                matches.setdefault(row["id"], row)
            profile = dict(profile, matches=sorted(matches.values(), key=lambda row: row["playedAt"], reverse=True),
                           historyAvailable=profile["historyAvailable"] or previous["historyAvailable"],
                           historyHasMore=profile["historyHasMore"] or previous["historyHasMore"])
        self.home_profile = profile
        self.profile_cached = False
        self.home_profile = dict(profile,savedAt=int(time.time()))
        if self.profile_memory:
            self.profile_memory.save(self.home_profile)
        self.latest_match = next((row for row in profile["matches"] if row["queue"] in SUPPORTED_QUEUES), None)

    def preview_build(self, champion_id, role, *, include_specials=False):
        catalog = self.catalog
        champion = catalog["ids"].get(str(champion_id))
        if champion and role in ROLES:
            if not include_specials:
                return public_builds(load_build(catalog, champion, role, champion_id))
            unavailable = None
            try:
                builds = load_build(catalog, champion, role, champion_id) or {}
            except SOURCE_ERRORS as error:
                unavailable = error
                builds = {}
            tournaments, personal, specialists = load_specials(catalog, champion, role, champion_id, copy(self.lcu))
            options = {**builds, **specialists, **special_options(tournaments, personal, None, catalog["names"])}
            if not options and unavailable:
                raise unavailable
            return public_builds(options)
        return {}

    def read_home_profile(self, client, history_limit):
        try:
            return read_home(client, self.catalog, self.rank_history, history_limit=history_limit)
        except SOURCE_ERRORS:
            return None

    def close(self):
        self.card_stats.close()
        self.draft_profiles.clear()
        self.context_executor.shutdown(wait=False, cancel_futures=True)
        self.special_executor.shutdown(wait=False, cancel_futures=True)
        self.locked_executor.shutdown(wait=False, cancel_futures=True)
        self.executor.shutdown(wait=False, cancel_futures=True)

    def update_special_builds(self, key, roster, now, *, fetch=True):
        champion, role, cid, _ = key
        source_key = self.catalog["patch"], champion, role, self.lcu.port, self.lcu.token
        if self.special_job and self.special_job[1].done():
            finished_key, job = self.special_job
            self.special_job = None
            try:
                tournaments, personal, specialists = job.result()
            except SOURCE_ERRORS:
                tournaments, personal, specialists = [], None, {}
            _, previous_tournaments, _, previous_specialists = self.special_cache.get(finished_key, (0, [], None, {}))
            self.special_cache[finished_key] = (
                now + (300 if tournaments or personal or specialists else 45),
                tournaments or previous_tournaments, personal, specialists or previous_specialists,
            )
            self.special_cache.move_to_end(finished_key)
            if len(self.special_cache) > 20:
                self.special_cache.popitem(last=False)
        expires, tournaments, personal, specialists = self.special_cache.get(source_key, (0, [], None, {}))
        if fetch and self.special_job and self.special_job[0] != source_key:
            self.special_job[1].cancel()
            self.special_job = None
        if fetch and now >= expires and self.special_job is None:
            self.special_job = source_key, self.special_executor.submit(
                load_specials, self.catalog, champion, role, cid, copy(self.lcu)
            )
        self.special_builds = {**specialists, **special_options(tournaments, personal, lane_opponent(roster, role), self.catalog["names"])}

    def clear_build(self):
        if self.build_job:
            self.build_job[1].cancel()
            self.build_job = None
        self.build = self.build_key = self.build_roster = self.build_patch = None
        self.build_locked = False
        self.special_builds = {}

    def paused_draft(self, now, draft_id=None):
        if (self.lcu.port and self.status.get("phase") in DRAFT_PHASES and now - self.draft_seen <= 5
                and (self.build_patch is None or self.build_patch == self.catalog.get("patch"))
                and (not draft_id or draft_id == self.role_draft_id)):
            return dict(self.status, locked=False, draftInterrupted=True)
        return None

    def finish_build(self, now):
        if self.build_job and self.build_job[1].done():
            key, job = self.build_job
            self.build_job = None
            if key == self.build_key:
                self.retry_at = now + 30
                try:
                    self.build = job.result()
                except SOURCE_ERRORS:
                    self.build = None

    def apply_draft_roles(self, roster, draft_id, role_change):
        if draft_id != self.role_draft_id:
            self.role_draft_id = draft_id
            self.role_overrides.clear()
        roster["gameId"] = draft_id
        if role_change is not None and draft_id is not None:
            requested_id, side, slot, role = role_change
            cards = roster.get(side, [])
            if (requested_id == draft_id and slot is not None
                    and any(card["roleSlot"] == slot for card in cards)):
                key = side, slot
                if role == "auto":
                    self.role_overrides.pop(key, None)
                elif role in ROLES:
                    if side == "allies":
                        previous = next((other for other, assigned in self.role_overrides.items()
                                         if other[0] == side and other != key and assigned == role), None)
                        if previous:
                            self.role_overrides.pop(previous)
                    self.role_overrides[key] = role
        self.annotate_roles(roster)

    def annotate_roles(self, roster):
        for side in ("allies", "enemies"):
            for card in roster[side]:
                card.pop("manualRole", None)
                card.pop("effectiveRole", None)
                if manual_role := self.role_overrides.get((side, card["roleSlot"])):
                    card["manualRole"] = manual_role
        allies = roster["allies"]
        if any(card.get("manualRole") for card in allies):
            for role, card in zip(ROLES, allied_role_slots(allies)):
                if card.get("role") and card["role"] != role and not card.get("manualRole"):
                    card["effectiveRole"] = role

    def refresh_catalog(self, now):
        if self.catalog_job and self.catalog_job.done():
            job, self.catalog_job = self.catalog_job, None
            self.catalog_after = now + 900
            try:
                self.catalog = job.result()
            except SOURCE_ERRORS:
                self.catalog_after = now + 30
        if self.catalog_job is None and now >= self.catalog_after:
            self.catalog_job = self.executor.submit(self.update_catalog, self.catalog)

    def read_status(self, now, role_change=None):
        self.voice_current_read = False
        self.refresh_catalog(now)
        previous = self.flow_connection
        before = self.lcu.port, self.lcu.token
        session = self.query_session()
        connection = self.lcu.port, self.lcu.token
        # A missing endpoint can be a temporary failure in the same match.
        if previous and any((port and (port, token) != previous) or (token and token != previous[1])
                            for port, token in (before, connection)):
            self.clear_build()
            self.game = self.finished = self.role_draft_id = self.flow_connection = None
            self.role_overrides.clear()
            self.draft_profiles.clear()
            self.euw = False
            self.platform = None
            self.region_after = 0
            self.flow_generation += 1
            self.status = {"phase": "offline", "build": None, "matchId": None}
        if self.lcu.port and self.lcu.token:
            self.flow_connection = connection
        phase = session.get("phase") or ("idle" if self.lcu.port else "offline")
        if session.get("phase"):
            self.flow_missing_since = None
        if not session.get("phase"):
            if self.game is not None:
                if self.flow_missing_since is None:
                    self.flow_missing_since = now
                if now - self.flow_missing_since < FLOW_DISCONNECT_GRACE or game_process_running():
                    return self.status
                phase = "offline"
                self.finished = self.flow_connection = self.flow_missing_since = None
                self.euw = False
                self.flow_generation += 1
            if paused := self.paused_draft(now):
                return paused
        self.client_phase = phase
        game = session.get("gameData") or {}
        queue = (game.get("queue") or {}).get("id")
        self.queue_id = queue
        if self.lcu.port and not self.euw and now >= self.region_after:
            region = self.lcu.region()
            self.platform = region.upper() if isinstance(region, str) and re.fullmatch(r"[A-Za-z0-9]{2,10}", region) else None
            self.euw = self.platform in {"EUW", "EUW1"}
            self.region_after = now + 5
        if phase == "ChampSelect" and queue in SUPPORTED_QUEUES and self.euw:
            return self.read_draft(now, game.get("gameId"), role_change)
        self.draft_profiles.clear()
        self.role_draft_id = None
        self.role_overrides.clear()
        match_id = game.get("gameId")
        tracked_game = (self.game is not None and queue in {None, *LIVE_QUEUES}
                        and (match_id is None or type(match_id) is int and match_id in (0, self.game)))
        if phase in PLAYING | ENDED and ((self.euw and queue in LIVE_QUEUES) or tracked_game):
            return self.read_game(now, phase, match_id, tracked_game)
        if phase in {"None", "Lobby"} and self.game and not self.finished and getattr(self,"reviewable_game",False):
            self.finished = f"EUW1_{self.game}"
        if self.game is not None:
            self.history_after = 0
        self.game = None
        self.clear_build()
        return {"phase": "ended" if self.finished else phase, "build": None, "matchId": self.finished,
                "postGameReady": phase in {"None", "Lobby"}}

    def read_draft(self, now, game_id, role_change):
        self.finished = None
        self.game = None
        draft = self.query_draft()
        if not draft:
            if paused := self.paused_draft(now, game_id):
                return paused
            self.clear_build()
            return {"phase": "pick", "build": None, "matchId": None, "draftInterrupted": True}
        self.draft_seen = now
        roster = draft_roster(draft, self.catalog)
        draft_id = draft.get("gameId") or game_id
        binding_key = (self.flow_generation, draft_id)
        if self.draft_flow_binding is None or self.draft_flow_binding[0] != binding_key:
            self.draft_flow_binding = (binding_key, game_id)
        self.apply_draft_roles(roster, draft_id, role_change)
        self.card_stats.apply(roster, self.catalog, unavailable_draft_champions(draft, roster, self.catalog), now)
        ids = {key: cid for cid, key in self.catalog["ids"].items()}
        self.draft_profiles.apply(roster, draft, self.lcu, self.context_executor, now, ids)
        target = self.draft_target(draft, game_id=draft_id, roster=roster)
        if not target:
            self.clear_build()
            return {"phase": "pick", "build": None, "matchId": None, "draft": roster}
        key, locked = target
        if key != self.build_key or self.build_patch != self.catalog["patch"]:
            self.clear_build()
            self.build_key, self.retry_at = key, 0
            self.build_patch = self.catalog["patch"]
        self.build_roster = roster
        self.finish_build(now)
        if locked and not self.build_locked:
            if self.build_job and self.build_job[1].cancel():
                self.build_job = None
            if self.special_job and self.special_job[1].cancel():
                self.special_job = None
        self.build_locked = locked
        if not self.build and not self.build_job and now >= self.retry_at:
            executor = self.locked_executor if locked else self.executor
            self.build_job = key, executor.submit(load_build, self.catalog, *key[:3])
        self.update_special_builds(key, roster, now)
        options = self.visible_builds()
        if options:
            phase = "draft"
        elif self.build_job or self.special_job:
            phase = "loading"
        else:
            phase = "no_build"
        return {"phase": phase,
                "build": next(iter(options.values()), None), "buildOptions": options, "locked": locked,
                "draftKey": list(key), "matchId": None, "draft": roster,
                "situationalItems": situational_items(self.catalog, key[0], roster["enemies"])}

    def read_game(self, now, phase, match_id, tracked_game):
        self.voice_current_read = type(match_id) is int and match_id > 0
        if type(match_id) is int and match_id > 0:
            if match_id != self.game:
                self.reviewable_game = self.queue_id in SUPPORTED_QUEUES
            if self.build_key and self.build_key[3] != match_id:
                self.clear_build()
            self.game = match_id
        if phase in ENDED and self.game is not None and getattr(self,"reviewable_game",False):
            self.finished = f"EUW1_{self.game}"
        elif phase not in ENDED:
            self.finished = None
        same_match = (self.build_locked and self.game is not None and self.build_key and self.build_key[3] == self.game
                      and ((type(match_id) is int and match_id == self.game) or tracked_game))
        if same_match:
            self.finish_build(now)
            if self.build_roster is not None and self.build_patch == self.catalog.get("patch"):
                self.update_special_builds(self.build_key, self.build_roster, now, fetch=False)
        options = self.visible_builds() if same_match else {}
        return {"phase": "ended" if phase in ENDED else "game",
                "build": next(iter(options.values()), None), "buildOptions": options, "matchId": self.finished,
                "draftKey": list(self.build_key) if same_match else None,
                "postGameReady": phase in {"PreEndOfGame", "EndOfGame"}}

    def available_builds(self):
        return {**(self.build or {}), **self.special_builds}

    def visible_builds(self):
        return public_builds(self.available_builds(), revisions=True)

    def export(self, supplied, choice=None, spells_only=False, *, revision=None):
        builds = self.available_builds()
        if not builds or not self.build_key or supplied != list(self.build_key):
            return {"results": ["Сборка уже сменилась. Проверьте драфт."]}
        build = builds.get(choice) if choice is not None else next(iter(builds.values()))
        if not build:
            return {"results": ["Выбранная сборка недоступна."]}
        if revision is not None and revision != build_revision(build):
            return {"results": ["Сборка обновилась. Проверьте новый вариант и нажмите импорт ещё раз."]}
        current = self.query_session()
        if not current:
            return {"results": ["Клиент LoL временно недоступен."]}
        if (current.get("phase") != "ChampSelect"
                or ((current.get("gameData") or {}).get("queue") or {}).get("id") not in SUPPORTED_QUEUES
                or str(self.lcu.region()).upper() not in {"EUW", "EUW1"}):
            return {"results": ["Драфт Solo/Duo EUW завершён."]}
        key = self.build_key
        connection = self.lcu.port, self.lcu.token
        if self.flow_connection is not None and connection != self.flow_connection:
            return {"results": ["Подключение к клиенту LoL изменилось. Проверьте текущий драфт."]}

        def pick(flow):
            game = flow.get("gameData") or {}
            game_id = game.get("gameId")
            if (flow.get("phase") != "ChampSelect" or (game.get("queue") or {}).get("id") not in SUPPORTED_QUEUES
                    or type(key[3]) is not int or key[3] <= 0):
                return None, False
            draft = self.query_draft() or {}
            current_id = draft.get("gameId")
            # Champ-select is authoritative here: gameflow can retain the last
            # match ID until the next game starts. Missing IDs still use the
            # conservative gameflow fallback; another explicit draft is refused.
            if current_id not in (None, 0):
                if current_id != key[3]:
                    return None, False
                binding = self.draft_flow_binding
                observed_flow = binding[1] if binding and binding[0] == (self.flow_generation, key[3]) else None
                if game_id not in (None, 0, key[3], observed_flow):
                    return None, False
            elif game_id not in (None, 0, key[3]):
                return None, False
            if (self.lcu.port, self.lcu.token) != connection:
                return None, False
            target = self.draft_target(draft, game_id=game_id)
            if not target or target[0] != key:
                return None, False
            return draft, target[1]

        def confirmed_draft():
            draft, locked = pick(self.query_session())
            return draft if locked else None

        draft, locked = pick(current)
        if draft is None:
            return {"results": ["Не удалось подтвердить исходный драфт. Проверьте клиент LoL."]}
        if not locked:
            return {"results": ["Сначала зафиксируйте этого чемпиона."]}
        if spells_only:
            if not build["spellNames"]:
                return {"results": ["Источнику не удалось подтвердить пару заклинаний."]}
            try:
                applied = self.lcu.set_spells(*build["spells"], draft_session=confirmed_draft)
            except SOURCE_ERRORS:
                applied = False
            return {"results": ["Заклинания применены" if applied else "Заклинания не применены"]}
        variant = build["variant"]
        results = []
        if build.get("canImportRunes", True):
            try:
                runes = self.lcu.set_runes(key[0], variant["prim"], variant["sec"], variant["perks"],
                                          variant["shards"], draft_session=confirmed_draft)
            except SOURCE_ERRORS:
                runes = False
            results.append("Руны применены" if runes else "Руны не применены")
        if not confirmed_draft():
            return {"results": [*results, "Подтверждение драфта потеряно. Набор предметов не добавлен."]}
        try:
            items = self.lcu.set_items(None, key[2], build["sets"], None, 11, draft_session=confirmed_draft)
        except SOURCE_ERRORS:
            items = False
        results.append("Набор предметов добавлен" if items else "Набор предметов не добавлен")
        return {"results": results}


def build_revision(build):
    return sha256(json.dumps(build, sort_keys=True).encode()).hexdigest()


def public_builds(builds, *, revisions=False):
    return {key: {**{name: value for name, value in build.items() if name not in {"variant", "sets", "spells"}},
                  **({"revision": build_revision(build)} if revisions else {})}
            for key, build in (builds or {}).items()}


def serve():
    companion = Companion()
    for line in sys.stdin.buffer:
        request = {}
        try:
            request = json.loads(line)
            if request["action"] == "snapshot":
                result = companion.snapshot()
            elif request["action"] == "export":
                result = companion.export(request.get("draftKey"))
            else:
                result = {"error": "Неизвестное действие."}
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            result = {"error": "Клиент LoL временно недоступен."}
        sys.stdout.buffer.write((json.dumps({"id": request.get("id"), **result}, ensure_ascii=False) + "\n").encode())
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args()
    if args.catalog:
        args.catalog.write_text(json.dumps(read_catalog(), ensure_ascii=False), encoding="utf-8")
    else:
        serve()
