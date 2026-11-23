"""Composition from visible champions and recent Solo/Duo profiles."""

from copy import copy
from types import SimpleNamespace

import core
import player_comments
import player_traits
from app_config import TIER_RU


# Curated capabilities of champion kits. An omitted champion is not evidence of absence.
CAPABILITIES = {
    "Инициация": "Amumu Ashe Camille Galio Gnar JarvanIV Kled Leona Lissandra Malphite Maokai "
                 "MonkeyKing Nautilus Neeko Nocturne Ornn Rakan Rell Sejuani Sion Skarner Vi Yone Zac",
    "Дайв": "Akali Camille Diana Elise Fizz Hecarim Irelia JarvanIV Kaisa Katarina Kled LeeSin "
            "MonkeyKing Naafiri Nocturne Pantheon Renekton Rengar Talon Vi XinZhao Yone Zac Zed",
    "Ловля одиночек": "Ahri Bard Blitzcrank Elise Evelynn LeBlanc Lissandra Lux Morgana "
                      "Nautilus Pyke Rengar Skarner Taliyah Thresh TwistedFate",
    "Сплитпуш": "Camille Fiora Gwen Illaoi Jax Nasus Olaf Quinn Shen Singed Trundle "
                "Tryndamere TwistedFate Udyr Volibear Warwick Yorick",
    "Пок издалека": "Ashe Corki Ezreal Jayce Jhin Karma KogMaw Lux Nidalee Varus Velkoz Xerath Ziggs Zoe",
    "Защита керри": "Alistar Braum Galio Janna Karma Lulu Milio Morgana Poppy Renata "
                    "Shen TahmKench Taric Thresh Zilean",
    "Зачистка волн": "Anivia AurelionSol Azir Hwei Karthus Lissandra Malzahar Orianna "
                    "Sivir Taliyah Viktor Xayah Ziggs",
}
CAPABILITIES = {label: frozenset(keys.split()) for label, keys in CAPABILITIES.items()}
PLAYER_LABELS = {
    "G1": "Серия побед", "G2": "Редко умирает", "G3": "Высокий KDA", "G4": "Хороший фарм",
    "G5": "Много урона", "G6": "Хороший обзор", "G7": "Мейнер",
    "N4": "Непривычная роль",
    "R1": "Серия поражений", "R2": "Мало побед", "R3": "Рост смертей", "R4": "Часто умирает",
    "R5": "Низкий KDA", "R6": "Мало фарма", "R7": "Мало урона", "R8": "Мало обзора",
}


def team_capabilities(cards, catalog):
    data = SimpleNamespace(champs=catalog.get("champs", {}))
    by_style = {}
    known = 0
    for card in cards:
        champion = card["championKey"]
        if not champion:
            continue
        profile = core.champ_profile(data, champion)
        known += profile["known"]
        styles = ["Фронтлайн"] if profile["front"] else []
        styles += [label for label, members in CAPABILITIES.items() if champion in members]
        for style in styles:
            by_style.setdefault(style, []).append(card["name"])
    report = [{"label": style, "champions": by_style[style], "tone": "good"}
              for style in ("Фронтлайн", *CAPABILITIES) if style in by_style]
    if known == 5 and all(card["locked"] for card in cards) and "Фронтлайн" not in by_style:
        report.insert(0, {"label": "Без фронтлайна", "champions": [], "tone": "bad",
                          "detail": "В пяти подтверждённых пиках нет танка или бойца с высокой защитой."})
    return report


def visible_ally(member):
    """Only trust a Riot ID and real PUUID explicitly shared by champion select."""
    if member.get("nameVisibilityType") != "VISIBLE":
        return None
    info = member.get("summonerInfo") or {}
    if info.get("privacy") not in (None, "PUBLIC"):
        return None
    name = member.get("gameName") or info.get("gameName")
    tag = member.get("tagLine") or info.get("tagLine")
    puuid = member.get("puuid") or info.get("puuid")
    if name and tag and puuid and puuid != member.get("obfuscatedPuuid"):
        return puuid, f"{name}#{tag}"
    return None


def read_profile(client, identity):
    if identity is None:
        account = client.me() or {}
        puuid, name = account.get("puuid"), account.get("riot")
    else:
        puuid, name = identity
    if not puuid:
        return None
    history = client.history(puuid, n=20)
    rank = client.rank(puuid)
    return name, history, rank


def describe_profile(raw, champion_id, role):
    name, history, rank = raw
    games = [game for game in player_traits.ranked_games(history) if game["q"] == 420]
    result = {"name": name, "status": "ready", "tags": []}
    if rank:
        tier = TIER_RU.get(rank["tier"], rank["tier"])
        div = rank["div"] if rank["tier"] not in {"MASTER", "GRANDMASTER", "CHALLENGER"} else ""
        result["rank"] = f"{tier} {div}".strip() + f" · {rank['lp']} LP"
    if not games:
        result["status"] = "unavailable" if history is None else "insufficient"
        return result

    summary = core.summarize_history(games, champion_id, role)
    result.update({key: summary[key] for key in ("n", "w", "on", "on_w", "kda")})
    reviewed_role = [game for game in games if role and player_traits.role_of(game) == role]
    if len(games) >= 3:
        _, summary["good"], summary["bad"] = core.history_patterns(reviewed_role, role)
        summary["extra_comments"] = player_traits.traits(games, champion_id, role)
        # Present the existing preview first, then keep the full list for the popup.
        rows = player_comments.preview(summary, limit=2) + player_comments.comments(summary)
        by_key = {row[0]: row for row in rows}
        for key, detail, tone in by_key.values():
            if key in PLAYER_LABELS:
                result["tags"].append({"label": PLAYER_LABELS[key], "detail": detail, "tone": tone})
    if champion_id and len(result["tags"]) < 2 and not any(tag["label"] == PLAYER_LABELS["G7"] for tag in result["tags"]):
        result["tags"].append({"label": f"На пике · {summary['on']}", "tone": "champion",
                               "detail": f"На выбранном чемпионе сыграно {summary['on']} из {len(games)} матчей выборки."})
    if reviewed_role and len(result["tags"]) < 2 and not any(tag["label"] == PLAYER_LABELS["N4"] for tag in result["tags"]):
        result["tags"].append({"label": f"На роли · {len(reviewed_role)}", "tone": "champion",
                               "detail": f"На назначенной роли сыграно {len(reviewed_role)} из {len(games)} матчей выборки."})
    return result


class DraftProfiles:
    def __init__(self):
        self.session = None
        self.cache = {}
        self.pending = None

    def clear(self):
        self.session = None
        self.cache.clear()
        if self.pending:
            self.pending[2].cancel()
            self.pending = None

    def apply(self, roster, draft, client, executor, now, ids):
        session = client.port, client.token, draft.get("gameId"), draft.get("localPlayerCellId")
        if session != self.session:
            self.clear()
            self.session = session
        if self.pending and self.pending[2].done():
            requested, identity, job = self.pending
            self.pending = None
            if requested == session:
                try:
                    profile = job.result()
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    profile = None
                complete = profile and profile[1] is not None
                self.cache[identity] = now + (300 if complete else 20), profile

        for member, card in zip(draft.get("myTeam") or [], roster["allies"]):
            identity = None if card["local"] else visible_ally(member)
            if identity is None and not card["local"]:
                continue
            expires, profile = self.cache.get(identity, (0, None))
            if now >= expires and self.pending is None:
                self.pending = session, identity, executor.submit(read_profile, copy(client), identity)
            if profile:
                role = card.get("manualRole") or card.get("effectiveRole") or card["role"]
                card["profile"] = describe_profile(profile, ids.get(card["championKey"]), role)
            else:
                card["profile"] = {"name": identity[1] if identity else None,
                                   "status": "loading" if now >= expires else "unavailable"}
