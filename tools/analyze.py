import json,glob,os
D='data'
P={'rGwU8TiuBiNSHqzSURckHNSy4h3eqNCkE7jmS30dYYFe8Qnx6IXOEttr8cz4SHa35xwCrweFXfcFeA':'halch',
   '8p5ZvbhGJkcwxL_F0wKmjeb0keVOtltH7esKs1_gV8AZxaHIeC-S0eV7B78iINgvIVzNsJMR2i57DQ':'drv'}
Q={420:'Соло/дуо',440:'Флекс',400:'Обычная (драфт)',430:'Обычная (вслепую)',490:'Быстрая игра',480:'Быстрая игра'}
champ=json.load(open('dd/champion.json'))['data']
cid={int(v['key']):(k,v['name']) for k,v in champ.items()}
games=[]
for f in sorted(glob.glob(f'{D}/EUW1_*[0-9].json')):
  x=json.load(open(f))
  if not x: continue
  i=x['info']
  if i['queueId'] not in Q or i['gameDuration']<600: continue
  tlf=f.replace('.json','_tl.json')
  tl=json.load(open(tlf)) if os.path.exists(tlf) else None
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
  kills=[e for fm in frames for e in fm['events'] if e['type']=='CHAMPION_KILL']
  obj=[e for fm in frames for e in fm['events'] if e['type'] in('ELITE_MONSTER_KILL','BUILDING_KILL')]
  teams={t['teamId']:t for t in i['teams']}
  plist=[]
  for p in parts:
    plist.append(dict(c=p['championName'],n=p['riotIdGameName'],t=p['riotIdTagline'],team=p['teamId'],pos=p['teamPosition'],
      k=p['kills'],d=p['deaths'],a=p['assists'],cs=p['totalMinionsKilled']+p['neutralMinionsKilled'],dmg=p['totalDamageDealtToChampions'],
      g=p['goldEarned'],items=[p[f'item{j}'] for j in range(7)],me=P.get(p['puuid'])))
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
      firstblood=p['firstBloodKill'] or p['firstBloodAssist']))
  games.append(dict(id=x['metadata']['matchId'],q=i['queueId'],qn=Q[i['queueId']],start=i['gameStartTimestamp'],dur=round(dur,1),
    ver='.'.join(i['gameVersion'].split('.')[:2]),win100=teams[100]['win'],
    obj={t:{k:v['kills'] for k,v in teams[t]['objectives'].items()} for t in teams},
    gd=gd,parts=plist,me=me_list,
    obev=[dict(t=round(e['timestamp']/60000,1),type=e.get('monsterType') or e.get('buildingType'),sub=e.get('monsterSubType') or e.get('towerType'),
      team=(e.get('killerTeamId') or (300-e['teamId'] if e.get('teamId') else None))) for e in obj]))
games.sort(key=lambda g:-g['start'])
json.dump(games,open('games.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(games), os.path.getsize('games.json'))
