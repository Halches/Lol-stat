"""Home-page statistics over loaded matches, with explicit sample sizes and missing values."""
import math


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value >= 0


def ordered(games):
    return sorted((g for g in games or [] if isinstance(g,dict)),key=lambda g:g.get('t') if number(g.get('t')) else 0,reverse=True)


def stats(games):
    results=[g['w'] for g in games if g.get('w') in (0,1) and g.get('w') is not None]
    kda=[g for g in games if all(number(g.get(k)) for k in ('k','d','a'))]
    out={'n':len(games),'wins':sum(results),'results':len(results),'wr':sum(results)/len(results)*100 if results else None,
         'kda':sum(g['k']+g['a'] for g in kda)/max(1,sum(g['d'] for g in kda)) if kda else None,
         'kda_n':len(kda)}
    for key in ('csm','vsm'):
        values=[g[key] for g in games if number(g.get(key))]
        out[key]=sum(values)/len(values) if values else None
        out[key+'_n']=len(values)
    return out


def snapshot(games,period='season'):
    games=ordered(games)
    selected=games[:20] if period=='recent' else games
    by={}
    for g in selected:
        if not g.get('c'):continue
        by.setdefault(g['c'],[]).append(g)
    frequent=[]
    for champion,group in sorted(by.items(),key=lambda pair:(-len(pair[1]),pair[0]))[:4]:
        roles={}
        for g in group:
            if g.get('pos'):roles[g['pos']]=roles.get(g['pos'],0)+1
        frequent.append({'champion':champion,'stats':stats(group),'role':max(roles,key=roles.get) if roles else ''})
    return {'games':games,'selected':selected,'stats':stats(selected),'season':stats(games),
            'recent':stats(games[:20]),'frequent':frequent}


def live_profile(profile,account):
    """Full Riot ID only; selecting another stored profile must not display the client's rank."""
    if not account:return False
    if not profile:return True
    return bool(profile.get('riot')) and str(profile['riot']).casefold()==str(account.get('riot','')).casefold()
