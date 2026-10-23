import json,glob,os
D='data'
P={'rGwU8TiuBiNSHqzSURckHNSy4h3eqNCkE7jmS30dYYFe8Qnx6IXOEttr8cz4SHa35xwCrweFXfcFeA':'halch',
   '8p5ZvbhGJkcwxL_F0wKmjeb0keVOtltH7esKs1_gV8AZxaHIeC-S0eV7B78iINgvIVzNsJMR2i57DQ':'drv'}
Q={420:'Соло/дуо',440:'Флекс',400:'Обычная (драфт)',430:'Обычная (вслепую)',490:'Быстрая игра',480:'Быстрая игра'}
champ=json.load(open('dd/champion.json'))['data']
ITEMS=json.load(open('dd/item.json'))['data']
cid={int(v['key']):(k,v['name']) for k,v in champ.items()}
games=[]
for f in sorted(glob.glob(f'{D}/EUW1_*[0-9].json')):
  try: x=json.load(open(f))
  except Exception: continue
  if not x: continue
  i=x['info']
  if i['queueId'] not in Q or i['gameDuration']<600: continue
  tlf=f.replace('.json','_tl.json')
  try: tl=json.load(open(tlf)) if os.path.exists(tlf) else None
  except Exception: tl=None
  if not tl: continue
  dur=i['gameDuration']/60
  parts=i['participants']
  byid={p['participantId']:p for p in parts}
  frames=tl['info']['frames'] if tl else []
  def fr(minute,pid):
    if minute<len(frames): return frames[minute]['participantFrames'][str(pid)]
  # team gold diff per minute (team 100 minus 200)
  gd=[]
  for fm in frames:
    s=0
    for k,v in fm['participantFrames'].items():
      s+= v['totalGold']*(1 if byid[int(k)]['teamId']==100 else -1)
    gd.append(s)
  xd=[]
  for fm in frames:
    xd.append(sum(v['xp']*(1 if byid[int(k)]['teamId']==100 else -1) for k,v in fm['participantFrames'].items()))
  ser={}
  for k in byid:
    ser[k]=dict(gold=[fm['participantFrames'][str(k)]['totalGold'] for fm in frames],
      xp=[fm['participantFrames'][str(k)]['xp'] for fm in frames],
      cs=[fm['participantFrames'][str(k)]['minionsKilled']+fm['participantFrames'][str(k)]['jungleMinionsKilled'] for fm in frames])
  buys={k:[] for k in byid}
  for fm in frames:
    for e in fm['events']:
      if e['type']=='ITEM_PURCHASED' and e.get('participantId') in buys and str(e['itemId']) in ITEMS:
        it=ITEMS[str(e['itemId'])]
        if (it['gold']['total']>=2200 and not it.get('into')) or 'Boots' in it.get('tags',[]) and it['gold']['total']>=900:
          buys[e['participantId']].append([e['itemId'],round(e['timestamp']/60000,1)])
  kills=[e for fm in frames for e in fm['events'] if e['type']=='CHAMPION_KILL']
  obj=[e for fm in frames for e in fm['events'] if e['type'] in('ELITE_MONSTER_KILL','BUILDING_KILL')]
  teams={t['teamId']:t for t in i['teams']}
  plist=[]
  for p in parts:
    plist.append(dict(c=p['championName'],n=p['riotIdGameName'],t=p['riotIdTagline'],team=p['teamId'],pos=p['teamPosition'],
      k=p['kills'],d=p['deaths'],a=p['assists'],cs=p['totalMinionsKilled']+p['neutralMinionsKilled'],dmg=p['totalDamageDealtToChampions'],
      g=p['goldEarned'],items=[p[f'item{j}'] for j in range(7)],me=P.get(p['puuid']),
      taken=p['totalDamageTaken']+p['damageSelfMitigated'],vs=p['visionScore'],obj=p['damageDealtToBuildings']+0.3*p['damageDealtToEpicMonsters'],
      cc=p['timeCCingOthers'],heal=p['totalHealsOnTeammates']+p['totalDamageShieldedOnTeammates'],pid=p['participantId'],
      sg=ser[p['participantId']]['gold'],sx=ser[p['participantId']]['xp'],sc=ser[p['participantId']]['cs'],buys=buys[p['participantId']]))
  me_list=[]
  for p in parts:
    who=P.get(p['puuid'])
    if not who: continue
    pid=p['participantId']; team=p['teamId']; pos=p['teamPosition']
    opp=next((o for o in parts if o['teamId']!=team and o['teamPosition']==pos and pos),None)
    ch=p.get('challenges',{})
    teamk=sum(o['kills'] for o in parts if o['teamId']==team)
    diffs={}
    for m in (10,15):
      a=fr(m,pid); b=fr(m,opp['participantId']) if opp else None
      if a and b:
        csa=a['minionsKilled']+a['jungleMinionsKilled']; csb=b['minionsKilled']+b['jungleMinionsKilled']
        diffs[m]=dict(gold=a['totalGold']-b['totalGold'],xp=a['xp']-b['xp'],cs=csa-csb,mycs=csa,lvl=a['level']-b['level'])
    mydeaths=[e['timestamp']/60000 for e in kills if e.get('victimId')==pid]
    ejg=next((o['participantId'] for o in parts if o['teamId']!=team and o['teamPosition']=='JUNGLE'),None)
    dpos=[]
    for e in kills:
      if e.get('victimId')!=pid: continue
      kid=e.get('killerId',0); inv=set([kid]+(e.get('assistingParticipantIds') or []))-{0}
      if kid==0 or kid not in byid: typ='tower'
      elif len(inv)>=3: typ='fight'
      elif ejg in inv: typ='jungle'
      elif opp and opp['participantId'] in inv: typ='lane'
      else: typ='roam'
      xy=e.get('position',{})
      dpos.append([round(e['timestamp']/60000,1),xy.get('x',0),xy.get('y',0),typ,byid[kid]['championName'] if kid in byid else None])
    skills=''.join('QWER'[e['skillSlot']-1] for fm in frames for e in fm['events'] if e['type']=='SKILL_LEVEL_UP' and e.get('participantId')==pid and e.get('levelUpType')=='NORMAL' and 1<=e['skillSlot']<=4)
    mykills=[e for e in kills if e.get('killerId')==pid]
    solo=sum(1 for e in mykills if not e.get('assistingParticipantIds'))
    early_d=sum(1 for t in mydeaths if t<14)
    # deaths to lane opponent before 14
    lane_d=sum(1 for e in kills if e.get('victimId')==pid and e['timestamp']<14*60000 and opp and e.get('killerId')==opp['participantId'])
    ganked=sum(1 for e in kills if e.get('victimId')==pid and e['timestamp']<14*60000 and len(e.get('assistingParticipantIds') or [])>=1)
    perks=p['perks']['styles']
    me_list.append(dict(who=who,pid=pid,c=p['championName'],team=team,pos=pos or p['individualPosition'],win=p['win'],
      k=p['kills'],d=p['deaths'],a=p['assists'],cs=p['totalMinionsKilled']+p['neutralMinionsKilled'],
      csm=round((p['totalMinionsKilled']+p['neutralMinionsKilled'])/dur,2),g=p['goldEarned'],gpm=round(p['goldEarned']/dur),
      dmg=p['totalDamageDealtToChampions'],dpm=round(p['totalDamageDealtToChampions']/dur),
      dshare=round(ch.get('teamDamagePercentage',0)*100,1),kp=round(ch.get('killParticipation',0)*100) if teamk else 0,
      taken=round(ch.get('damageTakenOnTeamPercentage',0)*100,1),
      vs=p['visionScore'],vsm=round(p['visionScore']/dur,2),cw=p['visionWardsBoughtInGame'],wards=p['wardsPlaced'],wk=p['wardsKilled'],
      solo=ch.get('soloKills',solo),plates=ch.get('turretPlatesTaken',0),turret=p['damageDealtToTurrets'],
      dead=p['totalTimeSpentDead'],lvl=p['champLevel'],
      lm10=ch.get('laneMinionsFirst10Minutes'),maxcs=ch.get('maxCsAdvantageOnLaneOpponent'),
      opp=dict(c=opp['championName'],n=opp['riotIdGameName'],k=opp['kills'],d=opp['deaths'],a=opp['assists'],
               cs=opp['totalMinionsKilled']+opp['neutralMinionsKilled'],dmg=opp['totalDamageDealtToChampions']) if opp else None,
      diffs=diffs,deaths=[round(t,1) for t in mydeaths],early_d=early_d,lane_d=lane_d,ganked=ganked,
      items=[p[f'item{j}'] for j in range(7)],sums=[p['summoner1Id'],p['summoner2Id']],
      keystone=perks[0]['selections'][0]['perk'],prim=perks[0]['style'],sec=perks[1]['style'],
      ff=p['gameEndedInSurrender'],early_ff=p['gameEndedInEarlySurrender'],
      firstblood=p['firstBloodKill'] or p['firstBloodAssist'],
      dpos=dpos,skills=skills,first=[i for i,t in buys[pid] if 'Boots' not in ITEMS[str(i)].get('tags',[])][:2],
      perks=[sel['perk'] for st_ in perks for sel in st_['selections']]))
  W=dict(dmg=.28,kp=.20,g=.15,taken=.10,obj=.07,vs=.08,cc=.05,heal=.04)
  for tm in (100,200):
    T=[q for q in plist if q['team']==tm]
    tk=sum(q['k'] for q in T) or 1
    tot={k:sum(q[k] for q in T) for k in ('dmg','g','taken','vs','obj','cc','heal','d')}
    for q in T:
      rel=lambda k:min(2.5,q[k]*len(T)/tot[k]) if tot[k] else 1
      kp=(q['k']+q['a'])/tk
      raw=W['kp']*min(2.5,kp/0.5)+sum(W[k]*rel(k) for k in ('dmg','g','taken','vs','obj','cc','heal'))-0.10*rel('d')
      q['raw']=raw
  mx=max(q['raw'] for q in plist) or 1
  for tm in (100,200):
    T=sorted([q for q in plist if q['team']==tm],key=lambda q:-q['raw'])
    st_=sum(q['raw'] for q in T) or 1
    for j_,q in enumerate(T): q['tr']=j_+1; q['share']=round(q['raw']/st_*100,1)
  for j_,q in enumerate(sorted(plist,key=lambda q:-q['raw'])): q['ar']=j_+1
  mn=min(q['raw'] for q in plist)
  for q in plist: q['imp']=round(1+9*(q['raw']-mn)/((mx-mn) or 1),1); del q['raw']
  for m_ in me_list:
    q=next(q for q in plist if q['pid']==m_['pid']); m_['imp']=q['imp']; m_['tr']=q['tr']; m_['ar']=q['ar']; m_['share']=q['share']
  for q in plist:
    for k in ('taken','obj','cc','heal','pid'): q.pop(k,None)
  ppos=[[[round(fm['participantFrames'][str(k)].get('position',{}).get('x',0)/10),round(fm['participantFrames'][str(k)].get('position',{}).get('y',0)/10)] for fm in frames] for k in sorted(byid)]
  kall=[[round(e['timestamp']/60000,2),round(e.get('position',{}).get('x',0)/10),round(e.get('position',{}).get('y',0)/10),e.get('killerId',0)-1,e['victimId']-1,[a_-1 for a_ in (e.get('assistingParticipantIds') or [])]] for e in kills]
  games.append(dict(ppos=ppos,kall=kall,id=x['metadata']['matchId'],q=i['queueId'],qn=Q[i['queueId']],start=i['gameStartTimestamp'],dur=round(dur,1),
    ver='.'.join(i['gameVersion'].split('.')[:2]),win100=teams[100]['win'],
    obj={t:{k:v['kills'] for k,v in teams[t]['objectives'].items()} for t in teams},
    gd=gd,xd=xd,kev=[[round(e['timestamp']/60000,1),byid[e['killerId']]['teamId'] if e.get('killerId') in byid else 300-byid[e['victimId']]['teamId']] for e in kills],parts=plist,me=me_list,
    obev=[dict(t=round(e['timestamp']/60000,1),type=e.get('monsterType') or e.get('buildingType'),sub=e.get('monsterSubType') or e.get('towerType'),
      team=(e.get('killerTeamId') or (300-e['teamId'] if e.get('teamId') else None))) for e in obj]))
if os.path.exists('games.json'):
  new_ids={g['id'] for g in games}
  games+=[g for g in json.load(open('games.json')) if g['id'] not in new_ids]
games.sort(key=lambda g:-g['start'])
cnt={'halch':0,'drv':0}
for g in games:
  keep=False
  for m in g['me']:
    cnt[m['who']]+=1
    if cnt[m['who']]<=60: keep=True
  g['full']=keep
  if not keep:
    for p in g['parts']:
      for k in ('sg','sx','sc','buys'): p.pop(k,None)
    g.pop('ppos',None); g.pop('kall',None)
json.dump(games,open('games.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(games), os.path.getsize('games.json'))
