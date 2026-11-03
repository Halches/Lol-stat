"""History view adapters. Saved data use seconds/minutes; LCU uses milliseconds/seconds."""
import core
import home_model
from champion_pool import norm


def number(value):return home_model.number(value)


def timestamp(value,scale=1):
    return value/scale if number(value) and 0<value/scale<253402300800 else None


def outcome(value):return bool(value) if type(value) in (int,bool) and value in (0,1) else None


def ratio(value,duration):
    return value/(duration/60) if number(value) and number(duration) and duration>0 else None


def saved(games,data,profile):
    result=[]
    for i,g in enumerate(games or []):
        if not isinstance(g,dict):continue
        duration=round(g['dur']*60) if number(g.get('dur')) else None
        result.append({'key':('saved',profile,i),'source':'saved','owner':None,'gid':None,'raw':g,
            'champion':g.get('c'),'role':g.get('pos') if g.get('pos') in core.ROLES else '',
            'win':outcome(g.get('w')),'queue':g.get('q'),'timestamp':timestamp(g.get('t')),
            'duration':duration,'k':g.get('k') if number(g.get('k')) else None,
            'd':g.get('d') if number(g.get('d')) else None,'a':g.get('a') if number(g.get('a')) else None,
            'csm':g.get('csm') if number(g.get('csm')) else None,'vsm':g.get('vsm') if number(g.get('vsm')) else None,
            'kp':g.get('kp') if number(g.get('kp')) and g['kp']<=100 else None,
            'items':list(g.get('it') or [])[:7],'spells':[],'perk':next(iter(g.get('pk') or []),None),
            'opp':g.get('opp'),'lp':None,'cs':None,'dmg':None,'gold':None,'vis':None})
    return sorted(result,key=lambda r:r['timestamp'] or 0,reverse=True)


def client(games,data,puuid,lp=None):
    result=[]
    for i,g in enumerate(games or []):
        if not isinstance(g,dict):continue
        dur=g.get('dur') if number(g.get('dur')) else None
        stamp=timestamp(g.get('t'),1000)
        row={'key':('client',puuid,g.get('gid') or i),'source':'client','owner':puuid,'gid':g.get('gid'),'raw':g,
             'champion':data.ids.get(str(g.get('champ'))),'role':core.lcu_pos({'timeline':{'lane':g.get('lane'),'role':g.get('role')}}),
             'win':outcome(g.get('win')),'queue':g.get('q'),'timestamp':stamp,'duration':dur,
             'csm':ratio(g.get('cs'),dur),'vsm':ratio(g.get('vis'),dur),'kp':None,
             'items':list(g.get('items') or [])[:7],'spells':list(g.get('spells') or [])[:2],
             'perk':g.get('perk'),'opp':None,'lp':(lp or {}).get(g.get('gid')) if g.get('q')==420 else None}
        for key in ('k','d','a','cs','dmg','gold','vis'):row[key]=g.get(key) if number(g.get(key)) else None
        result.append(row)
    return sorted(result,key=lambda r:r['timestamp'] or 0,reverse=True)


def filtered(rows,data,query='',role='',queue='',result='all'):
    q=norm(query)
    return [r for r in rows if (not q or any(q in norm(value) for value in (r['champion'] or '',data.cn(r['champion']),r.get('opp') or '',data.cn(r.get('opp')))))
            and (not role or role==r['role']) and (queue=='' or queue==r['queue'])
            and (result=='all' or result=='win' and r['win'] is True or result=='loss' and r['win'] is False)]


def stats(rows):
    return home_model.stats([{'w':int(r['win']) if r['win'] is not None else None,**{k:r.get(k) for k in ('k','d','a','csm','vsm')}} for r in rows])


def details(game,puuid,data):
    """Actual participants only, with missing stats retained. Existing analysis runs on complete SR data."""
    if not isinstance(game,dict):return None
    participants=game.get('participants')
    if not isinstance(participants,list) or not participants:return None
    identities={p.get('participantId'):p.get('player') or {} for p in game.get('participantIdentities') or [] if isinstance(p,dict)}
    duration=game.get('gameDuration') if number(game.get('gameDuration')) else None
    rows=[]
    keys={'k':'kills','d':'deaths','a':'assists','dmg':'totalDamageDealtToChampions','vis':'visionScore','gold':'goldEarned','lvl':'champLevel'}
    for p in participants:
        if not isinstance(p,dict):continue
        st=p.get('stats') or {};person=identities.get(p.get('participantId'),{})
        name=person.get('gameName') or person.get('summonerName') or 'Имя недоступно'
        if person.get('gameName') and person.get('tagLine'):name+='#'+person['tagLine']
        row={'team':p.get('teamId'),'c':data.ids.get(str(p.get('championId'))),'pos':core.lcu_pos(p),
             'name':name,'me':bool(puuid) and person.get('puuid')==puuid,'win':outcome(st.get('win')),
             'cs':st['totalMinionsKilled']+st['neutralMinionsKilled'] if all(number(st.get(k)) for k in ('totalMinionsKilled','neutralMinionsKilled')) else None,
             'items':[st.get(f'item{i}') for i in range(7)],'participantId':p.get('participantId')}
        row.update({key:st.get(value) if number(st.get(value)) else None for key,value in keys.items()})
        rows.append(row)
    if not rows:return None
    focus=next((r for r in rows if r['me']),None)
    complete=duration and duration>=600 and len(rows)==10 and len({r['participantId'] for r in rows})==10 and all(
        type(r['participantId']) is int and r['participantId']>0 and r['pos'] in core.ROLES and all(r.get(k) is not None for k in ('k','d','a','cs','dmg','vis','gold')) for r in rows)
    complete=complete and all(len([r for r in rows if r['team']==team])==5 and
        {r['pos'] for r in rows if r['team']==team}==set(core.ROLES) for team in (100,200))
    if focus:
        team=[r for r in rows if r['team']==focus['team']]
        complete=complete and sum(r.get('k') or 0 for r in team)>0 and sum(r.get('dmg') or 0 for r in team)>0
    analysis=[]
    if complete and focus and game.get('queueId') in (400,420,430,440,490):
        review=core.review_game(game,puuid,data)
        analysis=(review or {}).get('lines',[])
    return {'rows':rows,'me':focus,'min':duration/60 if duration and duration>0 else None,'q':game.get('queueId'),
            'lines':analysis,'team_grouping':'participants' if game.get('queueId')==1700 else 'teams','analysis_available':bool(complete and focus and game.get('queueId') in (400,420,430,440,490))}
