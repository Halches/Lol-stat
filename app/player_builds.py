"""Mobalytics player records: strict OTP/Pro categories, identity and same-record loadouts."""
import json
import re
import offmeta_data as data


def context(cache,champion,role):
    if not isinstance(cache,dict) or role not in data.ROLES:return None
    for entity in cache.values():
        if not isinstance(entity,dict) or entity.get('__typename')!='LolChampion':continue
        f=entity.get('activeFilters')
        if not isinstance(f,dict):continue
        if (f.get('slug'),f.get('role'),f.get('queue'),f.get('rank'),f.get('region'))!=(data.slug(champion),data.ROLES[role],'RANKED_SOLO','EmeraldPlus','ALL'):continue
        if isinstance(f.get('patch'),str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?',f['patch']):return entity,f
    return None


def record(build,champion,role,patch):
    if not isinstance(build,dict) or build.get('type')!='PRO_PLAYERS':return None
    if (build.get('championSlug'),build.get('role'),build.get('queue'))!=(data.slug(champion),data.ROLES.get(role),'RANKED_SOLO'):return None
    if build.get('vsChampionSlug') or build.get('patch',patch)!=patch:return None
    player=build.get('topPlayer');stats=build.get('stats');bid=build.get('id')
    if not isinstance(player,dict) or player.get('type') not in ('OTP','Pro') or not isinstance(stats,dict):return None
    name=player.get('name')
    if not isinstance(name,str) or not name.strip() or len(name)>120 or not name.isprintable():return None
    if not isinstance(bid,str) or not re.fullmatch(r'\d{1,20}',bid):return None
    n,w=stats.get('matchCount'),stats.get('wins')
    if type(n) is not int or type(w) is not int or n<=0 or not 0<=w<=n:return None
    perks=build.get('perks') or {};runes=perks.get('IDs',[]) if isinstance(perks,dict) else []
    runes=runes[:6] if data.ids(runes,9) else []
    decoded=data.equipment(build) if build.get('patch')==patch else None
    variant,situ=decoded if decoded else (None,[])
    return {'id':bid,'name':name.strip(),'kind':player['type'],'champion':champion,'role':role,'patch':patch,
            'games':n,'winrate':w/n*100,'perks':runes,'variant':variant,'situ':situ,
            'source':'Mobalytics','source_url':detail_url(champion,bid),'region':'ALL','tier':'EmeraldPlus'}


def listing(cache,champion,role):
    ctx=context(cache,champion,role)
    if not ctx:return None
    entity,filters=ctx;opts=entity.get('buildsOptions')
    if not isinstance(opts,dict) or not isinstance(opts.get('options'),list):return None
    groups={'OTP':[],'Pro':[]};seen=set()
    for ref in opts['options']:
        row=record(cache.get(ref.get('__ref')),champion,role,filters['patch']) if isinstance(ref,dict) and isinstance(ref.get('__ref'),str) else None
        if row and (row['kind'],row['name'].casefold()) not in seen:
            seen.add((row['kind'],row['name'].casefold()));groups[row['kind']].append(row)
    for kind in groups:groups[kind]=sorted(groups[kind],key=lambda r:(-r['games'],-r['winrate'],r['id']))[:3]
    return {'champion':champion,'role':role,'patch':filters['patch'],'groups':groups}


def detail_url(champion,bid):
    if not isinstance(bid,str) or not re.fullmatch(r'\d{1,20}',bid):raise ValueError('Некорректная сборка')
    return data.url(champion)+'?buildID='+bid


def detail(cache,expected):
    ctx=context(cache,expected['champion'],expected['role'])
    if not ctx or ctx[1]['patch']!=expected['patch']:return None
    entity,filters=ctx
    for key,value in entity.items():
        if not key.startswith('build(') or not key.endswith(')'):continue
        try:bid=json.loads(key[6:-1])['filters']['buildId']
        except (ValueError,KeyError,TypeError):continue
        if str(bid)!=expected['id'] or not isinstance(value,dict):continue
        build=cache.get(value.get('__ref')) if isinstance(value.get('__ref'),str) else None
        row=record(build,expected['champion'],expected['role'],expected['patch'])
        if row and row['id']==expected['id'] and row['name']==expected['name'] and row['kind']==expected['kind'] and row['variant']:return row
    return None


def compact(cache):
    out={}
    if not isinstance(cache,dict):return out
    for key,entity in cache.items():
        if not isinstance(entity,dict) or entity.get('__typename')!='LolChampion':continue
        mini={'__typename':'LolChampion','activeFilters':entity.get('activeFilters')}
        opts=entity.get('buildsOptions') or {};refs=[]
        for ref in opts.get('options',[]) if isinstance(opts,dict) and isinstance(opts.get('options'),list) else []:
            target=cache.get(ref.get('__ref')) if isinstance(ref,dict) and isinstance(ref.get('__ref'),str) else None
            if isinstance(target,dict) and target.get('type')=='PRO_PLAYERS':refs.append(ref)
        chosen=[]
        for kind in ('OTP','Pro'):
            candidates=[ref for ref in refs if isinstance(cache[ref['__ref']].get('topPlayer'),dict) and cache[ref['__ref']]['topPlayer'].get('type')==kind]
            def sample(ref):
                n=(cache[ref['__ref']].get('stats') or {}).get('matchCount')
                return n if type(n) is int else 0
            chosen.extend(sorted(candidates,key=sample,reverse=True)[:3])
        refs=chosen
        for ref in refs:out[ref['__ref']]=cache[ref['__ref']]
        mini['buildsOptions']={'options':refs}
        for k,v in entity.items():
            if k.startswith('build(') and isinstance(v,dict) and isinstance(v.get('__ref'),str):
                target=cache.get(v['__ref'])
                if isinstance(target,dict) and target.get('type')=='PRO_PLAYERS':mini[k]=v;out[v['__ref']]=target
        out[key]=mini
    return out
