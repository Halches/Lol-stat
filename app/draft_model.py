"""Presentation models for the native draft, independent of Tk and the client."""
import math


def role_slots(players, roles):
    """Keep each role's row reserved, including missing picks and unknown roles."""
    assigned, waiting = {}, []
    for player in players:
        role = player.get('pos')
        if role in roles and role not in assigned:
            assigned[role] = player
        else:
            waiting.append(player)
    return [assigned[role] if role in assigned else waiting.pop(0) if waiting else {'pos': role}
            for role in roles]


def recommendations(data, champion, lane, side, my_role, counters, teammates,
                    pools=None, scope='pool', unavailable=(), limit=3):
    """Verified pair win rates; enemy counter data is inverted once, never guessed across roles."""
    if not champion or not lane:
        return []
    rows = []
    role = lane if side == 'enemy' else my_role
    if not role:
        return []
    for key, values in (counters if side == 'enemy' else teammates).items():
        if side == 'enemy':
            candidate = key
        else:
            candidate_role, candidate = key
            if candidate_role != role:
                continue
        if candidate == champion or candidate in unavailable:
            continue
        if scope == 'pool' and candidate not in (pools or {}).get(role, ()):
            continue
        wr, delta, n = values
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (wr, delta, n)):
            continue
        if not 0 <= wr <= 100 or n < 150:
            continue
        rows.append({'champion': candidate, 'role': role,
                     'winrate': 100 - wr if side == 'enemy' else wr,
                     'delta': -delta if side == 'enemy' else delta, 'games': int(n)})
    rows.sort(key=lambda row: (-row['delta'], -row['games'], row['champion']))
    return rows[:limit]


def build_options(full):
    """Keep source rune/item statistics separate until a joint sample is actually supplied."""
    options = []
    if full:
        for key, title in (('pick', 'Популярная'), ('win', 'По винрейту')):
            variant = full.get(key) or (full if key == 'pick' else None)
            if not variant:
                continue
            options.append({'key': key, 'title': title, 'variant': variant,
                            'joint_winrate': None, 'joint_games': None,
                            'rune_winrate': variant.get('wr_runes'),
                            'rune_games': variant.get('n_runes'),
                            'item_winrate': variant.get('wr_core'),
                            'item_games': variant.get('n_core')})
    return options
