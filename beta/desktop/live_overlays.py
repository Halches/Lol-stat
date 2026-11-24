"""Read-only live cards. No demonstration values are used in a match."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from PySide6.QtCore import QObject, Signal, QTimer
from .voice_assistant import read_live
from .voice_rules import Catalog, game_snapshot


def live_cards(raw, catalog, role="", build=None):
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
                                   "differences": differences}
        if game.opp:
            cards["lane"] = {"title": "Предметы на линии", "lines": [f"Разница: {game.lane_diff():+.0f}"]}
            cards["lane"]["visual"] = {"version": version, "champion": game.opp["c"],
                "name": catalog.get("names", {}).get(game.opp["c"],game.opp["c"]), "difference": game.lane_diff()}
    # The build's full purchase price is explicit; do not pretend unknown recipe
    # component credit or a game's quick-buy selection is available.
    for item in (build or {}).get("items", []):
        if item.get("id") not in me["items"]:
            entry = items.get(str(item.get("id")), {})
            cost = entry.get("g", (entry.get("gold") or {}).get("total"))
            if type(cost) in (int, float) and cost > 0:
                cards["purchase"] = {"title": "Следующий предмет сборки", "lines": [item["name"],
                    f"Полная цена: {cost:.0f} · наличные: {game.gold:.0f}", "Компоненты в цене не вычтены"]}
                cards["purchase"]["visual"] = {"version": version, "item": item["id"], "price": cost, "gold": game.gold}
            break
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
                    self.contents = (live_cards(raw, self.companion.catalog, context.get("role", ""), self.build)
                                     if monotonic() - self.clock_at < 3 else {})
                    self.observed = monotonic()
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                self.contents = {}
        if active and self.job is None and not self.closed:
            self.job = session, self.executor.submit(read_live)
        self.changed.emit(self.contents)

    def close(self):
        self.closed = True
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
