"""Aggregate damage and draft options for champions visible in champion select."""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from math import isfinite
from types import SimpleNamespace

import core


LANE_ROLES = {lane: role for role, lane in core.LOLA_LANE.items()}
DAMAGE_TYPES = ("physical", "magic", "true")
SUGGESTION_LIMIT = 5
SOURCE_ERRORS = (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError)


def fetch_champion_statistics(catalog, side, champion, cid, role, fetch_build, fetch_json):
    raw = fetch_build(catalog, champion, role, cid)
    if raw is None:
        return None
    header = raw["header"]
    lane = LANE_ROLES.get(header.get("lane"))
    damage = header.get("damage") or {}
    values = [damage.get(kind) for kind in DAMAGE_TYPES]
    if not all(type(v) in (float, int) and isfinite(v) and v >= 0 for v in values) or not any(values):
        values = []
    result = {"damage": values, "games": header.get("n"), "role": lane, "suggestions": None}
    if not lane:
        return result
    endpoint = "counter" if side == "enemies" else "build-team"
    version = ".".join(catalog["patch"].split(".")[:2])
    url = core.lola_api(endpoint, champion, lane, "euw").replace("patch=30", "patch=" + version)
    if side == "enemies":
        url += "&vslane=" + core.LOLA_LANE[lane]
    try:
        response = fetch_json(url)
        if (response.get("response") or {}).get("valid") is not True:
            return result
        expected = core.LOLA_LANE[lane]
        for context in (response.get("stats"), response.get("header")):
            if context is not None and (not isinstance(context, dict)
                    or ("cid" in context and str(context["cid"]) != str(cid))
                    or ("lane" in context and context["lane"] != expected)
                    or ("patch" in context and context["patch"] != version)):
                return result
        data = SimpleNamespace(ids=catalog["ids"])
        if side == "enemies":
            context = response.get("stats") or {}
            if (str(context.get("cid")), context.get("lane"), context.get("vsLane")) != (str(cid), expected, expected):
                return result
            pairs = ((lane, opponent, 100 - rate, -edge, games) for opponent, (rate, edge, games)
                     in core.lola_counters(response, data).items())
        else:
            pairs = ((other_role, partner, rate, edge, games) for (other_role, partner), (rate, edge, games)
                     in core.lola_team(response, data).items())
        result["suggestions"] = sorted((item for item in pairs if item[3] > 0),
                                       key=lambda item: (item[3], item[4]), reverse=True)
    except SOURCE_ERRORS:
        pass
    return result


def available_suggestions(rows, names, unavailable, own_role=None):
    options = []
    seen = set(unavailable)
    for role, key, rate, edge, games in rows:
        if key in seen or (own_role and role != own_role):
            continue
        seen.add(key)
        options.append({"championKey": key, "name": names.get(key, key), "role": role,
                        "winRate": rate, "edge": edge, "games": games})
        if len(options) == SUGGESTION_LIMIT:
            break
    return options


class DraftStats:
    def __init__(self, fetch_build, fetch_json):
        self.fetch_build = fetch_build
        self.fetch_json = fetch_json
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.jobs = {}
        self.cache = OrderedDict()

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)

    def apply(self, roster, catalog, unavailable, now):
        ids = {key: cid for cid, key in catalog["ids"].items()}
        cards = {(catalog["patch"], side, card["championKey"], card.get("manualRole") or card.get("effectiveRole") or card["role"]): card
                 for side in ("allies", "enemies") for card in roster[side] if card["championKey"] in ids}
        own_role = next((card.get("manualRole") or card.get("effectiveRole") or card["role"]
                         for card in roster["allies"] if card["local"]), None)
        for key, job in tuple(self.jobs.items()):
            if job.done():
                del self.jobs[key]
                try:
                    result = job.result()
                except SOURCE_ERRORS:
                    result = None
                lifetime = 1800 if result and result["suggestions"] is not None else 30
                self.cache[key] = now + lifetime, result
                self.cache.move_to_end(key)
                if len(self.cache) > 144:
                    self.cache.popitem(last=False)
            elif key not in cards and job.cancel():
                del self.jobs[key]

        for key, card in cards.items():
            _, side, champion, role = key
            expires, data = self.cache.get(key, (0, None))
            if now >= expires and key not in self.jobs and len(self.jobs) < 4:
                self.jobs[key] = self.executor.submit(fetch_champion_statistics, catalog, side, champion,
                                                      ids[champion], role, self.fetch_build, self.fetch_json)
            if not data:
                card["insights"] = {"status": "loading" if now >= expires else "unavailable"}
                continue
            partner_role = own_role if side == "allies" and own_role != data["role"] else None
            choices = available_suggestions(data["suggestions"] or [], catalog["names"], unavailable | {champion}, partner_role)
            card["insights"] = {"status": "ready" if data["suggestions"] is not None else "unavailable",
                                "damage": data["damage"], "games": data["games"], "role": data["role"],
                                "suggestions": choices, "partnerRole": partner_role}
