"""Profile statistics from the client and locally observed ranked progression."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from core import ladder


QUEUES = {"solo": 420, "flex": 440}
PAGE_SIZE = 20
MAX_PAGES = 10
SOURCE_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError)


def started_at(row):
    value = row.get("t")
    return value if type(value) is int and 0 < value < 4_102_444_800_000 else 0


def rank_season_start(now):
    # Riot reopened EUW ranked at 12:00 CET on 8 January 2026 (patch 26.1).
    if now.year == 2026:
        return datetime(2026, 1, 8, 11, tzinfo=timezone.utc)
    return datetime(now.year, 1, 1).astimezone()


def read_history(client, puuid, cutoff, history_limit):
    games = {}
    settled = False
    available = False
    analytics_covered = False
    history_has_more = False
    interrupted = False
    page_budget = MAX_PAGES + history_limit // PAGE_SIZE
    for page_index in range(page_budget):
        try:
            page = client.history_page(puuid, n=PAGE_SIZE, offset=page_index * PAGE_SIZE)
        except SOURCE_ERRORS:
            page = None
        if page is None:
            interrupted = True
            break
        available = True
        rows, history_has_more = page
        previous_size = len(games)
        for row in rows:
            game_id = row.get("gid")
            if type(game_id) is int and game_id > 0:
                games.setdefault(game_id, row)
        if not history_has_more:
            settled = True
            break
        if rows and len(games) == previous_size:
            history_has_more = False
            break
        analytics_covered |= any(0 < started_at(row) < cutoff for row in rows)
        if len(games) >= history_limit and (analytics_covered or page_index + 1 >= MAX_PAGES):
            break
    ordered = sorted(games.values(), key=started_at, reverse=True)
    oldest = min((started_at(row) for row in ordered if started_at(row)), default=None)
    return ordered, available, settled, oldest, history_has_more, interrupted


def read_points(path):
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    return [(stamp, lp) for row in rows
            if isinstance(row, list) and len(row) == 2
            for stamp, lp in (row,)
            if type(stamp) is int and type(lp) is int and stamp > 0 and lp >= 0]


class RankHistory:
    def __init__(self, directory=None, legacy=None):
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local/state")
        roaming = Path(os.environ.get("APPDATA") or Path.home())
        self.directory = Path(directory) if directory is not None else local / "LoLHelper" / "rank-history"
        self.legacy = Path(legacy) if legacy is not None else roaming / "LoLHelper"

    def record(self, puuid, ranks, now, start):
        key = hashlib.sha256(puuid.encode()).hexdigest()[:16]
        stamp = int(now.timestamp() * 1000)
        first = int(start.timestamp() * 1000)
        trends = {}
        for queue in QUEUES:
            path = self.directory / f"{key}-{queue}.json"
            recorded = sorted(set(read_points(path)))
            rank = ranks.get(queue) or {}
            lp = ladder(rank) if rank.get("state") == "ranked" else None
            if lp is not None and (not recorded or recorded[-1][1] != lp
                                   or stamp - recorded[-1][0] >= 86_400_000):
                recorded = [point for point in recorded if point[0] < stamp]
                recorded.append((stamp, lp))
                self.save(path, recorded[-800:])
            legacy = read_points(self.legacy / f"lp-{key}.json") if queue == "solo" else []
            combined = dict(legacy)
            combined.update(recorded)
            trends[queue] = sorted((point, score) for point, score in combined.items() if first <= point <= stamp)
        return trends

    def save(self, path, points):
        pending = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=self.directory, suffix=".tmp", delete=False, mode="w", encoding="utf-8") as file:
                pending = Path(file.name)
                json.dump(points, file, separators=(",", ":"))
            pending.replace(path)
        except OSError:
            if pending is not None:
                try:
                    pending.unlink(missing_ok=True)
                except OSError:
                    pass


def read_home(client, catalog, rank_history, now=None, *, history_limit=PAGE_SIZE):
    now = now or datetime.now().astimezone()
    account = client.me()
    if not isinstance(account, dict) or not isinstance(account.get("puuid"), str) or not account["puuid"]:
        return None
    profile = {key: account.get(key) for key in ("riot", "icon", "level")}
    ranks = client.ranked_overview()
    ranks = ranks if isinstance(ranks, dict) else {}
    ranks = {key: ranks.get(key) or {} for key in QUEUES}
    week = int((now - timedelta(days=7)).timestamp() * 1000)
    first_day = now.date().replace(day=1)
    month = int(datetime.combine(first_day, datetime.min.time()).astimezone().timestamp() * 1000)
    puuid = account["puuid"]
    games, available, settled, oldest, more, interrupted = read_history(client, puuid, min(week, month), history_limit)
    timestamp = int(now.timestamp() * 1000)
    weekly = {}
    for key, queue in QUEUES.items():
        results = [row["win"] for row in games
                   if row.get("q") == queue and week <= started_at(row) <= timestamp and type(row.get("win")) is bool]
        weekly[key] = {"wins": sum(results), "games": len(results),
                       "complete": available and (settled or oldest is not None and oldest < week)}

    activity = {}
    for row in games:
        stamp = started_at(row)
        if month <= stamp <= timestamp:
            day = datetime.fromtimestamp(stamp / 1000).date()
            if day.year == first_day.year and day.month == first_day.month:
                activity[day.day] = activity.get(day.day, 0) + 1
    matches = []
    for row in games:
        champion = catalog["ids"].get(str(row.get("champ")))
        matches.append({
            "id": f"EUW1_{row['gid']}", "champion": catalog["names"].get(champion, champion),
            "portrait": champion, "assetVersion": catalog["patch"], "win": row.get("win"),
            "kda": [row.get(stat) for stat in ("k", "d", "a")], "playedAt": started_at(row),
            "queue": row.get("q"), "duration": row.get("dur"), "cs": row.get("cs"), "damage": row.get("dmg"),
        })
    start = rank_season_start(now)
    month_complete = available and (settled or oldest is not None and oldest < month)
    first_known_day = 1 if month_complete else datetime.fromtimestamp(oldest / 1000).day if oldest else now.day + 1
    return {"profile": profile, "ranks": ranks, "weekly": weekly, "matches": matches,
            "historyAvailable": available, "historyHasMore": more, "historyInterrupted": interrupted,
            "_accountKey": hashlib.sha256(puuid.encode()).hexdigest(),
            "trend": rank_history.record(puuid, ranks, now, start),
            "range": (int(start.timestamp() * 1000), timestamp),
            "assetVersion": catalog["patch"],
            "month": {"year": first_day.year, "month": first_day.month, "today": now.day, "days": activity,
                      "available": available, "complete": month_complete, "firstKnownDay": first_known_day}}
