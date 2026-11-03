"""Read the public Lolalytics matchup page, validating champion, opponent and lane."""
import json
import re
from urllib.parse import urlencode
import core


def url(champion, role, opponent):
    lane = core.LOLA_LANE[role]
    champion = core.LOLA_FIX.get(champion, champion.lower())
    opponent = core.LOLA_FIX.get(opponent, opponent.lower())
    return f'https://lolalytics.com/lol/{champion}/vs/{opponent}/build/?' + urlencode({'lane':lane, 'vslane':lane})


def parse(html, champion, role, opponent, data):
    """Decode only JSON references, never JavaScript. An unverified fallback is not a matchup."""
    lane = core.LOLA_LANE.get(role)
    cid = next((int(k) for k,v in data.ids.items() if v == champion), None)
    oid = next((int(k) for k,v in data.ids.items() if v == opponent), None)
    if not lane or not cid or not oid: return None
    for match in re.finditer(r'<script\b[^>]*\btype=[\"\']qwik/json[\"\'][^>]*>(.*?)</script>', html, re.S):
        try: objects = json.loads(match[1])['objs']
        except (ValueError, KeyError, TypeError): continue
        if not isinstance(objects, list): continue
        def deref(ref, seen=()):
            if not isinstance(ref, str) or not re.fullmatch(r'[a-z0-9]+!?', ref): raise ValueError('Unsupported reference')
            i = int(ref.rstrip('!'), 36)
            if i >= len(objects) or i in seen or len(seen) > 24: raise ValueError('Invalid reference graph')
            obj = objects[i]
            if isinstance(obj, dict): return {k:deref(v, seen+(i,)) for k,v in obj.items()}
            if isinstance(obj, list): return [deref(v, seen+(i,)) for v in obj]
            if isinstance(obj, str) and obj.startswith(tuple(chr(i) for i in range(32))): raise ValueError('Unsupported serialized value')
            return obj
        def resolve(obj): return {k:deref(v) for k,v in obj.items()}
        params = None
        for obj in objects:
            if isinstance(obj, dict) and all(k in obj for k in ('champion','vsCid','vs','tier','region','page')):
                try: candidate = resolve(obj)
                except (ValueError, TypeError, KeyError, IndexError): continue
                if candidate.get('cid') == cid and candidate.get('vsCid') == oid:
                    params = candidate; break
        if not params or params.get('region') != 'all' or params.get('tier') != 'emerald_plus' or params.get('mode') != 'ranked': continue
        for obj in objects:
            if not isinstance(obj, dict) or not all(k in obj for k in ('header','summary','nav')): continue
            try:
                raw = {k:deref(obj[k]) for k in ('header','summary','nav','response','boots','popularItem') if k in obj}
                h = raw['header']
                if (h.get('cid'), h.get('vs'), h.get('lane'), h.get('vsLane'), h.get('queue')) != (cid, oid, lane, lane, 420): continue
                if raw.get('response',{}).get('valid') is not True: continue
                if not isinstance(h.get('n'), (int,float)) or h['n'] <= 0: continue
                full = core.parse_lola_full(raw, data)
                if not full: continue
                full['win'] = core._lola_variant(raw['summary'].get('win') or {})
                # The public page explicitly labels this statistic as the primary keystone,
                # not the full rune page or its joint distribution with items.
                for key in ('pick','win'):
                    if full.get(key): full[key]['rune_stat_kind'] = 'keystone'
                full['matchup'] = {'champion':champion, 'opponent':opponent, 'role':role,
                                   'patch':h.get('patch'), 'region':'all', 'tier':'emerald_plus', 'queue':420}
                return full
            except (ValueError, TypeError, KeyError, IndexError): continue
    return None
