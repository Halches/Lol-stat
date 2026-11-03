"""Read factual OFF_META records from public Mobalytics SSR JSON, never execute scripts."""
import json
import re
from urllib.parse import quote
import core

ROLES={'TOP':'TOP','JUNGLE':'JUNGLE','MIDDLE':'MID','BOTTOM':'ADC','UTILITY':'SUPPORT'}
SLUGS={'MonkeyKing':'wukong','Nunu':'nunu','Renata':'renata','Chogath':'chogath','KogMaw':'kogmaw','KhaZix':'khazix','Velkoz':'velkoz'}

def slug(champion):
    if not isinstance(champion,str) or not re.fullmatch(r'[A-Za-z0-9]+',champion):raise ValueError('Некорректный чемпион')
    return SLUGS.get(champion,champion.lower())

def url(champion):return 'https://mobalytics.gg/lol/champions/'+quote(slug(champion))+'/build'

def ids(values,length=None):
    return isinstance(values,list) and (length is None or len(values)==length) and all(type(x) is int and x>0 for x in values)

def state(html):
    match=re.search(r'<script\b[^>]*>\s*window\.__PRELOADED_STATE__\s*=\s*(.*?)\s*;\s*</script>',html,re.S)
    if not match:return None
    try:cache=json.loads(match[1])['lolState']['apollo']['dynamic']
    except (ValueError,KeyError,TypeError):return None
    return cache if isinstance(cache,dict) else None

def parse(html,champion,role):return parse_state(state(html),champion,role)

def parse_state(cache,champion,role):
    if role not in ROLES or not isinstance(cache,dict):return None
    expected=slug(champion)
    for entity in cache.values():
        if not isinstance(entity,dict) or entity.get('__typename')!='LolChampion':continue
        filters=entity.get('activeFilters') or {}
        if not isinstance(filters,dict):continue
        if (filters.get('slug'),filters.get('role'),filters.get('queue'),filters.get('rank'),filters.get('region'))!=(expected,ROLES[role],'RANKED_SOLO','EmeraldPlus','ALL'):continue
        patch=filters.get('patch')
        if not isinstance(patch,str) or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?',patch):continue
        build_options=entity.get('buildsOptions')
        options=build_options.get('options') if isinstance(build_options,dict) else None
        if not isinstance(options,list):continue
        base={'champion':champion,'role':role,'patch':patch,'region':'ALL','tier':'EmeraldPlus','queue':'RANKED_SOLO','source':'Mobalytics','source_url':url(champion)}
        for ref in options:
            build=cache.get(ref.get('__ref')) if isinstance(ref,dict) and isinstance(ref.get('__ref'),str) else None
            if not isinstance(build,dict) or build.get('type')!='OFF_META':continue
            if (build.get('championSlug'),build.get('role'),build.get('queue'),build.get('patch'))!=(expected,ROLES[role],'RANKED_SOLO',patch):continue
            if build.get('vsChampionSlug') or build.get('topPlayer'):continue
            stats=build.get('stats') or {}
            if not isinstance(stats,dict):continue
            n,wins=stats.get('matchCount'),stats.get('wins')
            if type(n) is not int or type(wins) is not int or n<=0 or not 0<=wins<=n:continue
            decoded=equipment(build)
            if not decoded:continue
            variant,situ=decoded
            return dict(base,variant=variant,situ=situ,source_games=n,source_winrate=wins/n*100,status='ok')
        return dict(base,variant=None,status='absent')
    return None


def compact(cache):
    """Retain only champion filter context and OFF_META factual records for disk cache."""
    out={}
    if not isinstance(cache,dict):return out
    for key,entity in cache.items():
        if not isinstance(entity,dict):continue
        if entity.get('__typename')=='LolChampion':
            opts=entity.get('buildsOptions') or {}
            if not isinstance(opts,dict):continue
            if not isinstance(opts.get('options'),list):continue
            refs=[ref for ref in opts['options'] if isinstance(ref,dict) and isinstance(ref.get('__ref'),str) and isinstance(cache.get(ref['__ref']),dict) and cache[ref['__ref']].get('type')=='OFF_META']
            out[key]={'__typename':'LolChampion','activeFilters':entity.get('activeFilters'),'buildsOptions':{'options':refs}}
            for ref in refs:out[ref['__ref']]=cache[ref['__ref']]
    return out


def equipment(build):
    perks=build.get('perks') or {};spells=build.get('spells')
    if not isinstance(perks,dict) or not ids(perks.get('IDs'),9) or perks.get('style') not in (8000,8100,8200,8300,8400) or perks.get('subStyle') not in (8000,8100,8200,8300,8400) or perks['style']==perks['subStyle']:return None
    if not ids(spells,2) or any(s not in core.SPELL_KEY for s in spells):return None
    groups={}
    if not isinstance(build.get('items'),list):return None
    for row in build['items']:
        if isinstance(row,dict) and ids(row.get('items')):groups[row.get('type')]=row['items']
    if not groups.get('Core') or not groups.get('FullBuild') or not groups.get('Starter'):return None
    items=list(dict.fromkeys(groups['Core']+groups['FullBuild']))
    if len(items)!=6:return None
    order,priority=build.get('skillOrder'),build.get('skillMaxOrder')
    if not ids(order) or len(order)>18 or any(x>4 for x in order) or not ids(priority,3) or set(priority)!={1,2,3}:return None
    variant={'prim':perks['style'],'sec':perks['subStyle'],'perks':perks['IDs'][:6],'shards':perks['IDs'][6:],
             'spells':[core.SPELL_KEY[s] for s in spells],'start':groups['Starter'],'core':items[:3],
             'i4':[items[3]],'i5':[items[4]],'i6':[items[5]],'skills':''.join('QWER'[x-1] for x in order),'skill_prio':''.join('QWER'[x-1] for x in priority)}
    situ=[(iid,*core.SITU[iid]) for iid in groups.get('Situational',[]) if iid in core.SITU]
    return variant,situ
