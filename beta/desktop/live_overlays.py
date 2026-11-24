"""Read-only live cards. No demonstration values are used in a match."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from PySide6.QtCore import QObject, Signal, QTimer
from .voice_assistant import read_live
from .voice_rules import Catalog, game_snapshot
from .quick_buy import QuickBuyReader, remaining_price
from .worker import foreground_game


def live_cards(raw, catalog, role="", build=None, quick_buy=None):
    game = game_snapshot(raw, Catalog(catalog), role)
    if game is None:
        return {}
    me = game.me
    cs = "—" if me["cs"] is None else str(me["cs"])
    cards = {"metrics": {"title": "Показатели матча", "lines": [
        f"Фарм: {cs} · уровень {me['lvl']}", f"KDA: {me['k']} / {me['d']} / {me['a']}",
        f"Наличные: {game.gold:.0f}"]}}
    version = catalog.get("patch")
    cards["metrics"]["visual"] = {"version": version, "champion": me["c"],
        "name": catalog.get("names", {}).get(me["c"], me["c"]), "cs": cs,
        "csMinute": round(me["cs"] / (game.t / 60), 1) if me["cs"] is not None and game.t > 0 else None,
        "gold": round(game.gold), "level": me["lvl"], "kda": [me["k"],me["d"],me["a"]]}
    events = [event for event in game.events if event.get("EventName") in {"DragonKill", "BaronKill", "HeraldKill", "HordeKill"}]
    names = {"DragonKill": "Дракон", "BaronKill": "Барон", "HeraldKill": "Герольд", "HordeKill": "Личинки"}
    cards["objectives"] = {"title": "Объекты · события", "lines": [
        f"{names[event['EventName']]}: {max(0, int(game.t - event['EventTime']))} с назад"
        for event in events[-3:]] or ["Событий объектов пока нет"]}
    cards["objectives"]["visual"] = {"events": [{"kind": e["EventName"], "elapsed": max(0,int(game.t-e["EventTime"]))}
                                                for e in events]}
    items = catalog.get("items", {})
    def value(player):
        # Incomplete item costs must not look like zero inventory value.
        return None if any(str(i) not in items for i in player["items"]) else player["igold"]
    if all(value(p) is not None for p in game.players):
        cards["standings"] = {"title": "Стоимость предметов", "lines": [
            f"{catalog.get('names', {}).get(p['c'], p['c'])}: {p['igold']:.0f}"
            for p in sorted(game.players, key=lambda p: p["igold"], reverse=True)]}
        cards["standings"]["visual"] = {"version": version, "rows": [
            [p["c"], catalog.get("names", {}).get(p["c"], p["c"]), p["igold"], p["team"] == game.my_team]
            for p in sorted(game.players, key=lambda p: p["igold"], reverse=True)]}
        cards["tab"] = {"title": "Предметы команд · Tab", "lines": [f"Перевес: {game.gold_diff():+.0f}"]}
        differences = []
        for role_key in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
            ours = [p for p in game.allies if p["pos"] == role_key]
            theirs = [p for p in game.enemies if p["pos"] == role_key]
            differences.append(ours[0]["igold"]-theirs[0]["igold"] if len(ours)==len(theirs)==1 else None)
        cards["tab"]["visual"] = {"gold": [sum(p["igold"] for p in game.allies),sum(p["igold"] for p in game.enemies)],
                                   "differences": differences, "version": version, "myTeam": game.my_team,
                                   "players": [{"c": p["c"], "team": p["team"], "gold": p["igold"]} for p in game.players]}
        if game.opp:
            cards["lane"] = {"title": "Предметы на линии", "lines": [f"Разница: {game.lane_diff():+.0f}"]}
            cards["lane"]["visual"] = {"version": version, "champion": game.opp["c"],
                "name": catalog.get("names", {}).get(game.opp["c"],game.opp["c"]), "difference": game.lane_diff()}
    if quick_buy and quick_buy.get("state") == "ready":
        item_id = quick_buy.get("item")
        entry = items.get(str(item_id), {})
        cost = remaining_price(item_id, me["items"], items)
        if entry and cost is not None:
            missing = max(0, cost-game.gold)
            name = entry.get("n") or entry.get("name") or str(item_id)
            cards["purchase"] = {"title": "Выбрано в магазине", "lines": [name,
                f"Осталось заплатить: {cost:.0f} · не хватает: {missing:.0f}", "Источник: иконка быстрого закупа"]}
            cards["purchase"]["visual"] = {"version": version, "item": item_id, "name": name,
                "price": missing, "remaining": cost, "gold": game.gold, "source": "quick_buy",
                "confidence": quick_buy.get("confidence")}
    return cards


class LiveFeed(QObject):
    changed = Signal(dict)

    def __init__(self, companion, parent=None):
        super().__init__(parent)
        self.companion = companion
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="overlay-live")
        self.job = None
        self.closed = False
        self.contents = {}
        self.observed = 0
        self.build = None
        self.quick_buy = QuickBuyReader()
        self.purchase_enabled = lambda: False
        self.purchase_status = {"state": "inactive", "source": "screen"}
        self.session = None
        self.clock = None
        self.clock_at = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(1000)

    def poll(self):
        context = self.companion.voice_context or {}
        active = context.get("active") and monotonic() - context.get("observedAt", 0) < 4
        session = (context.get("generation"), context.get("gameId"))
        bounds = foreground_game() if active and self.purchase_enabled() else None
        rect = tuple(bounds[key] for key in ("x","y","width","height")) if bounds else None
        self.purchase_status = self.quick_buy.poll(rect, session, self.companion.catalog)
        if session != self.session:
            self.session = session
            self.contents = {}
            self.clock = None
        if not active or monotonic() - self.observed > 3:
            self.contents = {}
        if self.job and self.job[1].done():
            requested, job = self.job
            self.job = None
            try:
                if active and requested == session:
                    raw = job.result()
                    clock = (raw.get("gameData") or {}).get("gameTime") if isinstance(raw, dict) else None
                    if clock != self.clock:
                        self.clock, self.clock_at = clock, monotonic()
                    self.contents = (live_cards(raw, self.companion.catalog, context.get("role", ""), self.build, self.purchase_status)
                                     if monotonic() - self.clock_at < 3 else {})
                    self.observed = monotonic()
                    if self.contents.get("tab"):
                        self.contents["tab"]["visual"]["session"] = session
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                self.contents = {}
        if active and self.job is None and not self.closed:
            self.job = session, self.executor.submit(read_live)
        self.changed.emit(self.contents)

    def close(self):
        self.closed = True
        self.timer.stop()
        self.quick_buy.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
