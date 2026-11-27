"""Evidence-based player traits. Missing details never mean zero deaths or participation."""
import math
import core


def ranked_games(history):
    return [h for h in history or [] if h.get('q') in (420, 440) and h.get('dur', 0) >= 600]


def role_of(h):
    return core.lcu_pos({'timeline': {'lane': h.get('lane'), 'role': h.get('role')}})


def detail_metrics(game, timeline, puuid):
    """Only complete five-player team totals and a timeline covering minute 14 count."""
    out = {}
    pid = core.game_pid(game, puuid) if puuid else None
    if pid is None or not isinstance(game, dict): return out
    participants = game.get('participants') or []
    player = next((p for p in participants if p.get('participantId') == pid), None)
    if not player or player.get('teamId') not in (100, 200): return out
    team = [p for p in participants if p.get('teamId') == player['teamId']]
    stats = player.get('stats') or {}
    kills = [(p.get('stats') or {}).get('kills') for p in team]
    valid = lambda x: type(x) in (int, float) and math.isfinite(x) and x >= 0
    if len(team) == 5 and len({p.get('participantId') for p in team}) == 5 and all(valid(k) for k in kills):
        k, a = stats.get('kills'), stats.get('assists')
        if valid(k) and valid(a) and sum(kills) > 0:
            kp = (k + a) / sum(kills) * 100
            if 0 <= kp <= 100: out['kp'] = kp
    frames = (timeline or {}).get('frames') or []
    complete = isinstance(frames, list) and bool(frames) and all(
        isinstance(f, dict) and valid(f.get('timestamp')) and isinstance(f.get('events'), list)
        for f in frames)
    if complete:
        frames = sorted(frames, key=lambda f:f['timestamp'])
        # A final frame alone does not prove that earlier events are available.
        stamps = [f['timestamp'] for f in frames if f['timestamp'] < 840000]
        after = next((f['timestamp'] for f in frames if f['timestamp'] >= 840000), None)
        if after is not None: stamps.append(after)
        complete = bool(stamps) and stamps[0] <= 60000 and after is not None and all(
            0 < b-a <= 90000 for a,b in zip(stamps,stamps[1:]))
        complete = complete and all(isinstance(e,dict) and (e.get('type') != 'CHAMPION_KILL' or
            (valid(e.get('timestamp')) and type(e.get('victimId')) is int))
            for f in frames for e in f['events'])
    if game.get('gameDuration', 0) >= 840 and complete:
        out['d14'] = sum(e.get('type') == 'CHAMPION_KILL' and e.get('victimId') == pid and
                         0 <= e.get('timestamp', -1) < 840000 for f in frames for e in f['events'])
    return out


def traits(history, champion, role, metrics=None):
    """Recent-history heuristics; not a lifetime mastery or official skill rating."""
    rows = []
    games = ranked_games(history)[:20]
    on = [h for h in games if str(h.get('champ')) == str(champion)] if champion else []
    if len(games) >= 10 and len(on) >= 10 and len(on) / len(games) >= .7:
        rows.append(('G7', f'Мейнер · {len(on)}/{len(games)} игр', 'good'))
    known = [h for h in games if role_of(h)]
    same = [h for h in known if role_of(h) == role]
    if role in core.ROLES and len(known) >= 10 and len(same) / len(known) <= .2:
        rows.append(('N4', f'Непривычная роль · {len(same)}/{len(known)} игр', 'neutral'))
    sampled = [(metrics or {}).get(h.get('gid'), {}) for h in same[:5]]
    kp = [m['kp'] for m in sampled if type(m.get('kp')) in (float,int) and math.isfinite(m['kp']) and 0 <= m['kp'] <= 100]
    if len(kp) >= 5:
        avg = sum(kp)/len(kp)
        high, low = (65, 40) if role in ('UTILITY','JUNGLE') else (60, 30)
        if avg >= high: rows.append(('G8', f'Участие в убийствах {avg:.0f}% · 5 игр', 'good'))
        elif avg <= low: rows.append(('R9', f'Участие в убийствах {avg:.0f}% · 5 игр', 'bad'))
    ds = [m['d14'] for m in sampled if type(m.get('d14')) is int and m['d14'] >= 0]
    if len(ds) >= 5:
        avg = sum(ds)/len(ds)
        if avg <= 1: rows.append(('G9', f'До 14 мин: {avg:.1f} смерти · 5 игр', 'good'))
        elif avg >= 3: rows.append(('R10', f'До 14 мин: {avg:.1f} смерти · 5 игр', 'bad'))
    return rows
