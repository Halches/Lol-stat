"""Named Lolalytics champion leaderboard. Absence in its partial list is unknown."""
import json
import re
import time
import unicodedata
import core

REGIONS = {'BR':'br','BR1':'br','EUN':'eune','EUNE':'eune','EUN1':'eune','EUW':'euw','EUW1':'euw',
           'JP':'jp','JP1':'jp','KR':'kr','LA1':'lan','LAN':'lan','LA2':'las','LAS':'las',
           'NA':'na','NA1':'na','OC1':'oce','OCE':'oce','RU':'ru','TR':'tr','TR1':'tr',
           'SG':'sg','SG2':'sg','TW':'tw','TW2':'tw','VN':'vn','VN2':'vn','PH':'ph','PH2':'ph','TH':'th','TH2':'th','ME':'me','ME1':'me'}


def region(value): return REGIONS.get(str(value or '').upper())


def url(champion):
    slug = core.LOLA_FIX.get(champion, champion.lower())
    if not re.fullmatch(r'[a-z0-9]+', slug): raise ValueError('Invalid champion')
    return f'https://lolalytics.com/lol/{slug}/leaderboard/'


def identity(value):
    if not isinstance(value, str): return None
    name, sep, tag = value.partition('#')
    if not sep or not name.strip() or not tag.strip(): return None
    return unicodedata.normalize('NFC', value.strip()).casefold()


def parse(html, champion_id, champion, now=None):
    for match in re.finditer(r'<script\b[^>]*\btype=[\"\']qwik/json[\"\'][^>]*>(.*?)</script>', html, re.S):
        try: objects = json.loads(match[1])['objs']
        except (ValueError, KeyError, TypeError): continue
        if not isinstance(objects, list): continue
        def deref(ref, seen=()):
            if not isinstance(ref, str) or not re.fullmatch(r'[a-z0-9]+!?', ref): raise ValueError('Reference')
            i = int(ref.rstrip('!'), 36)
            if i >= len(objects) or i in seen or len(seen) > 20: raise ValueError('Reference graph')
            obj = objects[i]
            if isinstance(obj, dict): return {k:deref(v,seen+(i,)) for k,v in obj.items()}
            if isinstance(obj, list): return [deref(v,seen+(i,)) for v in obj]
            return obj
        # Validate global scope and champion separately; regional rank is not global rank.
        nav = None
        for obj in objects:
            if isinstance(obj,dict) and all(k in obj for k in ('cid','page','region','champion')):
                try: candidate = {k:deref(obj[k]) for k in ('cid','page','region','champion')}
                except (ValueError,TypeError,IndexError): continue
                if candidate == {'cid':int(champion_id),'page':'leaderboard','region':'all',
                                 'champion':core.LOLA_FIX.get(champion,champion.lower())}: nav=candidate; break
        if not nav: continue
        for obj in objects:
            if not isinstance(obj,dict) or not all(k in obj for k in ('header','toplist','response')): continue
            try: raw = {k:deref(obj[k]) for k in ('header','toplist','response')}
            except (ValueError,TypeError,IndexError): continue
            if raw['header'].get('cid') != int(champion_id) or raw['response'].get('valid') is not True: continue
            records = []
            for row in raw['toplist'] if isinstance(raw['toplist'],list) else []:
                if not isinstance(row,list) or len(row)<3: continue
                rank, riot, reg = row[:3]
                if type(rank) is int and 1 <= rank <= 1000 and identity(riot) and region(reg):
                    records.append({'rank':rank,'riot':riot,'region':region(reg)})
            return {'champion':champion,'rows':records,'source':'Lolalytics','url':url(champion),
                    'scope':'global','fetched_at':time.time() if now is None else now,
                    'coverage':len(records)}
    return None


def lookup(board, champion, riot, platform, now=None):
    now = time.time() if now is None else now
    if not board or board.get('champion') != champion or board.get('scope') != 'global': return None
    age = now - board.get('fetched_at',0)
    if age < 0 or age > 21600 or not identity(riot) or not region(platform): return None
    found = [r for r in board.get('rows',[]) if identity(r.get('riot')) == identity(riot) and r.get('region') == region(platform)]
    if len(found) != 1 or type(found[0].get('rank')) is not int or not 1 <= found[0]['rank'] <= 1000: return None
    return dict(found[0], source=board.get('source','Lolalytics'), url=board['url'], fetched_at=board['fetched_at'], scope='global')
