"""Read-only game rules adapted from the classic app to a finite recording set."""
import math
import core

from .voice_catalog import PHRASES, ROLES, TOPICS


class Catalog(core.Data):
    def __init__(self, source):
        items = {}
        for key, item in source.get("items", {}).items():
            # Both the shipped compact catalog and freshly fetched Data Dragon work.
            items[key] = {**item, "n": item.get("n") or item.get("name", key),
                          "g": item.get("g", (item.get("gold") or {}).get("total", 0)),
                          "done": item.get("done", not item.get("into") and bool(item.get("from")))}
        super().__init__({**source, "names": source.get("names", {}), "ids": source.get("ids", {}),
                          "items": items, "lola": {}})

    def role_of_champ(self, champion):
        return ""  # A popular role does not identify this player's actual lane.


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def game_snapshot(raw, data, selected_role=""):
    if not isinstance(raw, dict):
        return None
    active, info = raw.get("activePlayer"), raw.get("gameData")
    players = raw.get("allPlayers")
    if (not isinstance(active, dict) or not isinstance(info, dict) or not isinstance(players, list)
            or not valid_number(info.get("gameTime")) or info["gameTime"] < 0
            or info.get("mapNumber") != 11 or info.get("gameMode") != "CLASSIC"
            or not valid_number(active.get("currentGold")) or active["currentGold"] < 0):
        return None
    if not all(isinstance(p, dict) and type(p.get("level")) is int and 1 <= p["level"] <= 30
               and type(p.get("isDead")) is bool and p.get("team") in ("ORDER", "CHAOS")
               and isinstance(p.get("items"), list) and all(isinstance(i, dict) for i in p["items"])
               for p in players):
        return None
    events = (raw.get("events") or {}).get("Events")
    if not isinstance(events, list) or not all(isinstance(e, dict) and valid_number(e.get("EventTime"))
                                             and 0 <= e["EventTime"] <= info["gameTime"] for e in events):
        return None
    if any(event.get("EventName") == "GameEnd" for event in events):
        return None
    game = core.Game(raw, data)
    if not game.me:
        return None
    role = selected_role if selected_role in ROLES else game.me["pos"]
    game.role = role if role in ROLES else ""
    game.me["pos"] = game.role
    opponents = [p for p in game.enemies if game.role and p["pos"] == game.role]
    game.opp = opponents[0] if len(opponents) == 1 else None
    return game


class VoiceRules:
    def __init__(self, catalog):
        self.data = Catalog(catalog)
        self.engine = core.Engine(self.data, None)
        self.last_phrase = {}
        self.last_time = None
        self.identity = None
        self.role = None
        self.accepted = False
        self.reset_detected = False
        self.valid_phrases = set()

    def tick(self, raw, role, enabled, cs_target=7.0):
        self.accepted = self.reset_detected = False
        self.valid_phrases = set()
        game = game_snapshot(raw, self.data, role)
        if game is None:
            self.engine.prev = None
            return []
        # Also guard clock resets and identity changes without relying on gameflow.
        if (self.last_time is not None and game.t < self.last_time - 2
                or self.identity is not None and game.my_riot != self.identity):
            self.__init__({"names": self.data.names, "ids": self.data.ids, "items": self.data.items})
            self.reset_detected = True
        self.accepted = True
        self.identity = game.my_riot
        if self.role != game.role:
            self.engine.prev = None
            self.role = game.role
        previous = self.engine.prev
        switches = {key: False for key in core.HINT_IDS}
        for topic in TOPICS:
            on = enabled(topic, game.role) and (not topic.roles or game.role in topic.roles)
            if topic.key == "ganks":
                switches.update({key: on for key in ("gank1", "gank2", "gank3")})
            else:
                switches[topic.key] = on
        # Skills and CS use explicit free points / the user's goal below.
        switches["skills"] = switches["cs_norm"] = False
        # Six-level announcements belong to the lane's level switch.
        switches["levels"] = False
        self.engine.enabled = switches
        out = []
        for hint in self.engine.tick(game):
            phrase = self.phrase(hint, game)
            if phrase:
                out.append(phrase)
        topics = {t.key: t for t in TOPICS}
        level_on = game.role in topics["levels"].roles and enabled(topics["levels"], game.role)
        if previous and previous.me and not game.me["dead"]:
            if level_on and game.opp and previous.opp:
                for level in (2, 3, 6):
                    if previous.me["lvl"] < level <= game.me["lvl"] and game.opp["lvl"] < level:
                        out.append(f"level_{level}")
                    if previous.opp["lvl"] < level <= game.opp["lvl"] and game.me["lvl"] < level:
                        out.append(f"enemy_level_{level}")
        abilities = (raw.get("activePlayer") or {}).get("abilities") or {}
        levels = [(abilities.get(key) or {}).get("abilityLevel") for key in "QWER"]
        if (enabled(topics["skills"], game.role) and not game.me["dead"]
                and all(type(v) is int and v >= 0 for v in levels)
                and sum(levels) < game.me["lvl"]
                and (previous is None or previous.me["lvl"] < game.me["lvl"])):
            out.append("skills")
        if (game.role in topics["cs_norm"].roles and enabled(topics["cs_norm"], game.role)
                and game.me["cs"] is not None and valid_number(cs_target) and cs_target > 0):
            for minute in (5, 10, 15):
                if (0 <= game.t - minute * 60 <= 3 and (self.last_time is None or self.last_time < minute * 60)
                        and game.me["cs"] < cs_target * minute * .85):
                    out.append("cs")
        self.last_time = game.t
        self.valid_phrases = self.still_relevant(game)
        result = []
        for phrase in out:
            # Three legacy gank windows can overlap. Never repeat a recording immediately.
            if game.t - self.last_phrase.get(phrase, -10000) >= (45 if phrase == "gank" else 20):
                self.last_phrase[phrase] = game.t
                result.append(phrase)
        return result if not game.me["dead"] else []

    @staticmethod
    def still_relevant(game):
        if game.me["dead"]:
            return set()
        valid = set(PHRASES)
        if game.gold < 2000:
            valid.discard("hoard")
        if any(item in (3330, 3340, 3363, 3364) for item in game.me["items"]):
            valid.discard("trinket")
        if 3340 not in game.me["items"]:
            valid.discard("lens")
        levels = [((game.raw.get("activePlayer") or {}).get("abilities", {}).get(k) or {}).get("abilityLevel") for k in "QWER"]
        if not all(type(v) is int and v >= 0 for v in levels) or sum(levels) >= game.me["lvl"]:
            valid.discard("skills")
        for level in (2, 3, 6):
            if not game.opp or game.me["lvl"] != level or game.opp["lvl"] >= level:
                valid.discard(f"level_{level}")
            if not game.opp or game.opp["lvl"] != level or game.me["lvl"] >= level:
                valid.discard(f"enemy_level_{level}")
        return valid

    @staticmethod
    def phrase(hint, game):
        key = hint.id
        if key == "jungler":
            champion = game.ejg["c"] if game.ejg else ""
            return "jungler_early" if champion in core.JG_EARLY else "jungler_farm" if champion in core.JG_FARM else "jungler_normal"
        if key == "early_ward":
            return "ward_jungle" if game.role == "JUNGLE" else "ward_support" if game.role == "UTILITY" else "ward_lane"
        if key in ("gank1", "gank2", "gank3"):
            return "gank"
        if key == "powerspike":
            return "item" if hint.say.startswith("Собран ") else None
        if key == "objectives":
            for obj, name in (("elder", "Древний дракон"), ("dragon", "Дракон"),
                              ("grubs", "Личинки"), ("herald", "Герольд"), ("baron", "Барон")):
                for lead in (60, 30):
                    # Don't play an inaccurate sixty-second recording after a long gap.
                    if (hint.say.startswith(f"{name} через ")
                            and lead - 2 <= int(hint.say.rsplit(" через ", 1)[1].split()[0]) <= lead):
                        return f"{obj}_{lead}"
            return None
        if key == "inhib":
            remaining = int(hint.text.rsplit("через ", 1)[1].split()[0])
            return "inhib" if 58 <= remaining <= 60 else None
        return key if key in PHRASES else None
