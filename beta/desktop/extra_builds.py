"""Builds from tournament scoreboards and the player's own recent games."""

import json
import re
from functools import lru_cache
from html import unescape
from math import sqrt
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen

import core
import rune_catalog
from rank_labels import TIER_RU


DDRAGON = "https://ddragon.leagueoflegends.com"
LEAGUEPEDIA = "https://lol.fandom.com"
LANE_NAMES = {"TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid", "BOTTOM": "Bot", "UTILITY": "Support"}
SHARD_NAMES = {
    "adaptive force": 5008, "attack speed": 5005, "ability haste": 5007, "move speed": 5010,
    "health scaling": 5001, "scaling health": 5001, "health": 5011, "tenacity and slow resist": 5013,
}
SPELL_ALIASES = {"cleanse": 1, "ghost": 6, "ignite": 14}
RIOT_ID = r"[^#<>\[\]\r\n]{1,32}#[a-z0-9]{2,5}"
HEALING_CHAMPIONS = frozenset((
    "Aatrox", "Briar", "DrMundo", "Illaoi", "Maokai", "Nami", "Soraka", "Swain", "Taric",
    "Vladimir", "Warwick", "Yuumi", "Zac",
))
SOURCE_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError)


def read_json(url):
    request = Request(url, headers={"User-Agent": "LoL Helper Beta (public tournament builds)"})
    with urlopen(request, timeout=4) as response:
        return json.load(response)


@lru_cache(maxsize=2)
def english_catalog(version):
    base = f"{DDRAGON}/cdn/{version}/data/en_US"
    champions = read_json(f"{base}/champion.json")["data"]
    trees = read_json(f"{base}/runesReforged.json")
    items = read_json(f"{base}/item.json")["data"]
    by_name = {}
    for item_id, item in items.items():
        if item["maps"].get("11"):
            name = item["name"].casefold()
            previous = by_name.get(name)
            if previous is None or (item.get("inStore") is not False and items[str(previous)].get("inStore") is False):
                by_name[name] = int(item_id)
    return (
        {key: info["name"] for key, info in champions.items()}, by_name,
        {tree["name"]: tree["id"] for tree in trees},
        {rune["name"].casefold(): rune["id"] for tree in trees for slot in tree["slots"] for rune in slot["runes"]},
    )


def patch_key(version):
    return ".".join((version or "").split(".")[:2])


def otp_url(champion, role):
    slug = core.LOLA_FIX.get(champion, champion.lower())
    filters = urlencode({"lane": core.LOLA_LANE[role], "tier": "1trick", "region": "euw"})
    return f"https://lolalytics.com/lol/{slug}/build/?{filters}"


def specialist_build_data(catalog, champion, role, cid):
    request = Request(otp_url(champion, role), headers={"User-Agent": "LoL Helper Beta"})
    with urlopen(request, timeout=4) as response:
        page = response.read(4_000_000).decode("utf-8")
    snapshot = re.search(r'<script type="qwik/json">(.+?)</script>', page, re.DOTALL)
    if not snapshot:
        return None
    objects = json.loads(snapshot[1])["objs"]

    # Resolve only the rendered page's build payload and selected filters.
    def value(ref, depth=0):
        if depth > 10:
            raise ValueError("Unexpected build page structure")
        element = objects[int(ref, 36)]
        if isinstance(element, dict):
            return {key: value(item, depth + 1) for key, item in element.items()}
        if isinstance(element, list):
            return [value(item, depth + 1) for item in element]
        return element

    filters = next((obj for obj in objects if isinstance(obj, dict) and {"champion", "tier", "region", "lane", "path"} <= obj.keys()), None)
    lane = core.LOLA_LANE[role]
    if not filters or [value(filters[key]) for key in ("tier", "region", "lane")] != ["1trick", "euw", lane]:
        return None
    fields = ("header", "response", "summary", "builtBootSet3")
    payload = next((obj for obj in objects if isinstance(obj, dict) and set(fields) <= obj.keys()), None)
    if not payload:
        return None
    header = value(payload["header"])
    if (value(payload["response"]).get("valid") is not True or str(header.get("cid")) != str(cid)
            or header.get("patch") != patch_key(catalog["patch"]) or header.get("lane") != lane or header.get("queue") != 420):
        return None
    return {key: value(payload[key]) for key in ("summary", "builtBootSet3")}


def observed_cores(catalog, raw):
    rows = raw.get("builtBootSet3")
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, list) or len(row) < 4:
            continue
        encoded, rate, share, matches = row[:4]
        if (not isinstance(encoded, str) or not re.fullmatch(r"[0-9]+_[0-9]+_[0-9]+", encoded)
                or type(matches) is not int or matches <= 0
                or type(rate) not in (int, float) or not 0 <= rate <= 100
                or type(share) not in (int, float) or not 0 < share <= 100):
            continue
        items = tuple(map(int, encoded.split("_")))
        if len(set(items)) == 3 and all(str(item) in catalog["items"] for item in items):
            yield items, rate, share, matches


def statistical_build(catalog, champion, role, baseline, observed, title, source):
    if not baseline:
        return None
    items, rate, share, matches = observed
    build = match_build(catalog, champion, role, title=title, source=source,
                        page=(baseline["prim"], baseline["sec"], baseline["perks"], baseline["shards"]),
                        spells=[core.SPELL_ID.get(spell) for spell in baseline["spells"]], items=items,
                        itemHeading="Основа сборки", sample=matches, winRate=rate, coreShare=share)
    if not build or not build["canImportRunes"]:
        return None
    start = [item for item in baseline["start"] if str(item) in catalog["items"]]
    blocks = ([('Старт', start)] if start else []) + [("Основа", list(items))]
    build["sets"] = [(f"{champion}: {title}", blocks)]
    return build


def specialist_builds(catalog, champion, role, cid):
    raw = specialist_build_data(catalog, champion, role, cid)
    if not raw or not (baseline := core.parse_lola_full(raw)):
        return {}
    builds = {}
    used = set()
    for row in sorted(observed_cores(catalog, raw), key=lambda row: -row[3]):
        identity = frozenset(row[0])
        if row[3] < 5 or identity in used:
            continue
        number = len(builds) + 1
        build = statistical_build(catalog, champion, role, baseline["pick"], row, f"Мейнеры · {number}",
                                  "Lolalytics · EUW · мейнеры · руны и заклинания из частой страницы выборки")
        if build:
            builds[f"otp:{number}"] = build
            used.add(identity)
        if len(builds) == 3:
            break
    return builds


def uncommon_build(catalog, champion, role, raw, parsed):
    def nonboots(items):
        return frozenset(item for item in items if "Boots" not in (catalog["items"].get(str(item)) or {}).get("tags", []))

    popular = parsed["pick"]
    mainstream = {nonboots(build["core"]) for build in (popular, parsed["win"]) if build}
    games = raw["header"].get("n")
    min_games = max(50, round((games if type(games) is int else 0) * .001))
    min_rate = max(53, (popular["wr_core"] or 0) + 1)
    candidates = (row for row in observed_cores(catalog, raw)
                  if row[1] >= min_rate and row[2] <= 5 and row[3] >= min_games and nonboots(row[0]) not in mainstream)
    # Wilson lower bound prefers evidence from more games over a noisy high point estimate.
    def confidence(row):
        p, n, z = row[1] / 100, row[3], 1.96
        return (p + z*z/(2*n) - z*sqrt((p*(1-p) + z*z/(4*n))/n)) / (1 + z*z/n)

    best = max(candidates, key=confidence, default=None)
    if best:
        return statistical_build(catalog, champion, role, popular, best, "Нестандартная",
                                 "Lolalytics · EUW · Изумруд+ · руны и заклинания от популярной сборки")
    return None


def item_record(catalog, item_id):
    item = catalog["items"].get(str(item_id)) or {}
    if name := item.get("n") or item.get("name"):
        return {"id": item_id, "name": name}
    return None


def match_build(catalog, champion, role, *, title, source, page, spells, items, **metadata):
    primary, secondary, runes, shards = page
    full_page = rune_catalog.valid_page(primary, secondary, runes, shards)
    names = [core.SPELL_RU.get(core.SPELL_KEY.get(spell)) for spell in spells]
    item_rows = [row for item_id in items if (row := item_record(catalog, item_id))]
    if not item_rows or len(names) != 2 or not all(names) or spells[0] == spells[1]:
        return None
    if not full_page and (shards or not rune_catalog.valid_page(primary, secondary, runes, [5008, 5008, 5011])):
        return None
    final_items = [item["id"] for item in item_rows]
    return {
        "champion": catalog["names"].get(champion, champion), "role": core.ROLE_RU[role],
        "championKey": champion, "assetVersion": catalog["patch"], "patch": patch_key(catalog["patch"]),
        "title": title, "source": source, "itemHeading": "Предметы на конец матча", "canImportRunes": full_page,
        "items": item_rows, "runes": runes, "shards": shards, "spells": spells, "spellIds": spells, "spellNames": names,
        "variant": {"prim": primary, "sec": secondary, "perks": runes, "shards": shards},
        "sets": [(f"{champion}: {title}", [("Предметы на конец матча", final_items)])],
        **metadata,
    }


def tournament_builds(catalog, champion, role):
    champions, items, trees, runes = english_catalog(catalog["patch"])
    name, lane = champions[champion], LANE_NAMES[role]
    patch = patch_key(catalog["patch"])
    major, minor = patch.split(".")
    labels = (patch, f"{int(major) + 10}.{minor}")
    params = {
        "action": "cargoquery", "format": "json", "tables": "ScoreboardPlayers=SP,ScoreboardGames=SG",
        "join_on": "SP.GameId=SG.GameId",
        "fields": ("SP.Link=Player,SP.Champion,SP.Role,SP.IngameRole,SP.OverviewPage=Event,SP.Runes,"
                   "SP.Items,SP.PrimaryTree,SP.SecondaryTree,SP.SummonerSpells,SP.DateTime_UTC=PlayedAt,"
                   "SG.Patch,SG.GameId=Match"),
        "where": (f'SP.Champion="{name}" AND SG.Patch IN ("{labels[0]}","{labels[1]}") '
                  f'AND (SP.IngameRole="{lane}" OR ((SP.IngameRole IS NULL OR SP.IngameRole="") AND SP.Role="{lane}"))'),
        "order_by": "SP.DateTime_UTC DESC", "limit": 25,
    }
    response = read_json(f"{LEAGUEPEDIA}/api.php?{urlencode(params)}")
    if "cargoquery" not in response:
        raise ValueError("Leaguepedia did not return tournament scoreboards.")
    spell_ids = {spell.removeprefix("Summoner").casefold(): value for value, spell in core.SPELL_KEY.items()}
    spell_ids.update(SPELL_ALIASES)
    rivals = tournament_opponents(params, lane, champions) if response["cargoquery"] else {}
    builds = []
    seen = set()
    for result in response["cargoquery"]:
        row = result.get("title") or {}
        if (row.get("Champion") != name or row.get("Patch") not in labels
                or (row.get("IngameRole") or row.get("Role")) != lane
                or not all(row.get(field) for field in ("Match", "Player", "Event", "PlayedAt"))):
            continue
        identity = row["Match"], row["Player"]
        if identity in seen:
            continue
        seen.add(identity)
        perk_names = [name.strip().casefold() for name in (row.get("Runes") or "").split(",")]
        if len(perk_names) != 9:
            continue
        page = (trees.get(row.get("PrimaryTree")), trees.get(row.get("SecondaryTree")),
                [runes.get(perk) for perk in perk_names[:6]], [SHARD_NAMES.get(perk) for perk in perk_names[6:]])
        spells = [spell_ids.get(spell.strip().casefold())
                  for spell in (row.get("SummonerSpells") or "").split(",")]
        final_items = [items.get(name.strip().casefold()) for name in (row.get("Items") or "").split(";") if name.strip()]
        if None in final_items:
            continue
        event_url = f"{LEAGUEPEDIA}/wiki/{quote(row['Event'].replace(' ', '_'))}"
        player = row["Player"].split(" (", 1)[0]
        event = row["Event"].split("/", 1)[0]
        opponent = rivals.get(identity)
        source = f"Leaguepedia · {event} · {player} · {row['PlayedAt'][:10]}"
        if opponent:
            source += f" · соперник {catalog['names'].get(opponent, opponent)}"
        build = match_build(catalog, champion, role, title=f"Про · {player}",
                            source=source,
                            page=page, spells=spells, items=final_items, player=player,
                            playerProfile=row["Player"], opponent=opponent, sourceUrl=event_url)
        if build and build["canImportRunes"] and len(build["items"]) == len(final_items):
            builds.append(build)
    return builds


def tournament_opponents(params, lane, champions):
    query = dict(params, tables=params["tables"] + ",ScoreboardPlayers=OP",
                 join_on=params["join_on"] + ",SP.UniqueLineVs=OP.UniqueLine",
                 fields=("SP.Link=Player,SG.GameId=Match,OP.GameId=EnemyMatch,"
                         "OP.Champion=Opponent,OP.Role=EnemyRole,OP.IngameRole=EnemyIngameRole"))
    try:
        response = read_json(f"{LEAGUEPEDIA}/api.php?{urlencode(query)}")
    except SOURCE_ERRORS:
        return {}
    keys = {name.casefold(): key for key, name in champions.items()}
    rivals = {}
    for result in response.get("cargoquery") or []:
        row = result.get("title") or {}
        if (row.get("Match") and row.get("EnemyMatch") == row["Match"] and row.get("Opponent")
                and (row.get("EnemyIngameRole") or row.get("EnemyRole")) == lane):
            rivals[(row["Match"], row.get("Player"))] = keys.get(row["Opponent"].casefold())
    return rivals


def featured_pro_builds(tournaments):
    distinct = {}
    for build in tournaments:
        distinct.setdefault(build["player"], build)
        if len(distinct) == 3:
            break
    return distinct


def linked_pro_account(profile):
    if not re.fullmatch(r"https://lolpros\.gg/player/[\w-]+/?", profile or "", re.ASCII):
        return None
    request = Request(profile, headers={"User-Agent": "LoL Helper Beta (public pro profile link)"})
    try:
        with urlopen(request, timeout=2) as response:
            page = response.read(1_000_000).decode("utf-8")
    except (OSError, UnicodeError):
        return None
    # This link belongs to the profile's Current Rank card.
    link = re.search(r'<a\s+href="(?:https:)?//(?:www\.)?op\.gg/(?:lol/)?summoners/euw/([^"/?]+)"[^>]*class="--opgg"', page)
    if link:
        account = unquote(unescape(link[1])).rpartition("-")
        riot_id = f"{account[0]}#{account[2]}"
        if re.fullmatch(RIOT_ID, riot_id, re.IGNORECASE):
            return riot_id
    return None


def profile_rank(client, accounts):
    for account in accounts:
        if account and (puuid := client.puuid(account)):
            rank = client.rank(puuid) or {}
            if tier := TIER_RU.get(rank.get("tier")):
                division = rank.get("div")
                label = f"{tier} {division}" if division in {"I", "II", "III", "IV"} else tier
                return {"tier": rank["tier"], "label": label, "lp": rank.get("lp")}
    return None


def add_pro_ranks(tournaments, client):
    if not tournaments or client.region() not in {"EUW", "EUW1"}:
        return
    profiles = {name.replace("_", " ").casefold(): build
                for build in featured_pro_builds(tournaments).values()
                if (name := build.get("playerProfile")) and re.fullmatch(r"[\w .'’()\-]{1,100}", name)}
    if not profiles:
        return
    pages = ",".join(json.dumps(build["playerProfile"].replace("_", " "), ensure_ascii=False) for build in profiles.values())
    query = {"action": "cargoquery", "format": "json", "tables": "Players",
             "fields": "Players._pageName=Page,Players.SoloqueueIds,Players.Lolpros", "where": f"Players._pageName IN ({pages})"}
    response = read_json(f"{LEAGUEPEDIA}/api.php?{urlencode(query)}")
    for result in response.get("cargoquery") or []:
        row = result.get("title") or {}
        build = profiles.get((row.get("Page") or "").replace("_", " ").casefold())
        if not build:
            continue
        # Leaguepedia entries can list accounts across regions and use wiki markup for the labels.
        accounts = re.sub(r"<br\s*/?>", "\n", unescape(row.get("SoloqueueIds") or ""), flags=re.IGNORECASE).replace("'''", "")
        tagged = re.findall(rf"^[ \t]*EUW1?[ \t]*:[ \t]*({RIOT_ID})[ \t]*$", accounts, re.IGNORECASE | re.MULTILINE)
        rank = profile_rank(client, (account.strip() for account in tagged))
        if not rank and (linked := linked_pro_account(row.get("Lolpros"))):
            rank = profile_rank(client, [linked])
        if rank:
            build["proRank"] = rank


def personal_build(catalog, champion, role, cid, client):
    if client.region() not in {"EUW", "EUW1"}:
        return None
    account = client.me() or {}
    puuid = account.get("puuid")
    if not puuid:
        return None
    for entry in client.history(puuid, n=20) or []:
        pos = core.lcu_pos({"timeline": {"lane": entry.get("lane"), "role": entry.get("role")}})
        if entry.get("q") != 420 or entry.get("dur", 0) < 600 or str(entry.get("champ")) != str(cid) or pos != role:
            continue
        game = client.game(entry["gid"]) or {}
        if patch_key(game.get("gameVersion")) != patch_key(catalog["patch"]):
            continue
        player_id = core.game_pid(game, puuid)
        participant = next((p for p in game.get("participants") or []
                            if p.get("participantId") == player_id and str(p.get("championId")) == str(cid)), {})
        stats = participant.get("stats") or {}
        shards = [stats.get(f"statPerk{index}") for index in range(3)]
        build = match_build(
            catalog, champion, role, title="Моя сборка", source="Клиент Riot · последний подходящий Solo/Duo",
            page=(stats.get("perkPrimaryStyle"), stats.get("perkSubStyle"),
                  [stats.get(f"perk{index}") for index in range(6)], [] if None in shards else shards),
            spells=[participant.get("spell1Id"), participant.get("spell2Id")],
            items=[stats.get(f"item{index}") for index in range(6) if stats.get(f"item{index}")],
        )
        if build:
            return build
    return None


def load_specials(catalog, champion, role, cid, client):
    try:
        tournaments = tournament_builds(catalog, champion, role)
    except SOURCE_ERRORS:
        tournaments = []
    try:
        add_pro_ranks(tournaments, client)
    except SOURCE_ERRORS:
        pass
    try:
        personal = personal_build(catalog, champion, role, cid, client)
    except SOURCE_ERRORS:
        personal = None
    try:
        specialists = specialist_builds(catalog, champion, role, cid)
    except SOURCE_ERRORS:
        specialists = {}
    return tournaments, personal, specialists


def special_options(tournaments, personal, opponent, names):
    options = {"personal": personal} if personal else {}
    if opponent:
        match = next((build for build in tournaments if build["opponent"] == opponent), None)
        if match:
            rival = names.get(opponent, opponent)
            options["matchup"] = dict(match, title=f"VS · {rival}", opponentName=rival)
    options.update({f"pro:{player}": build for player, build in featured_pro_builds(tournaments).items()})
    return options


def lane_opponent(roster, role):
    enemies = roster.get("enemies") or []
    manual = [card["championKey"] for card in enemies if card.get("manualRole") == role]
    if manual:
        return manual[0] if len(manual) == 1 else None
    inferred = [card["championKey"] for card in enemies if not card.get("manualRole")
                and (card.get("insights") or {}).get("role") == role]
    return inferred[0] if len(inferred) == 1 else None


def situational_items(catalog, champion, opponents):
    tags = (catalog.get("champs", {}).get(champion) or {}).get("tags") or []
    if not tags:
        return []
    antiheal, resistance = {
        "Mage": (3165, 3102), "Marksman": (3033, 3156), "Tank": (3075, 4401),
        "Fighter": (6609, 3156), "Assassin": (6609, 3156), "Support": (None, 3190),
    }.get(tags[0], (None, None))
    healing = [card["name"] for card in opponents if card.get("championKey") in HEALING_CHAMPIONS]
    mixes = [values for card in opponents if (values := (card.get("insights") or {}).get("damage"))]
    candidates = []
    if healing and antiheal:
        candidates.append((antiheal, f"Против лечения · {', '.join(healing)}"))
    total = sum(sum(values) for values in mixes)
    magic = sum(values[1] for values in mixes)
    if resistance and len(mixes) >= 3 and total and magic / total >= .65:
        candidates.append((resistance, f"Против магического урона · {magic / total:.0%} в выборке открытых пиков"))
    return [dict(row, reason=reason) for item_id, reason in candidates
            if (row := item_record(catalog, item_id))]
