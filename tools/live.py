# Текущая игра (spectator-v5) для обоих игроков -> ../data/live.json. Пишет файл, только если что-то поменялось.
import json,os,time,urllib.request,urllib.error
K=os.environ.get('RIOT_API_KEY','').strip().strip('"')
from players import puuids
P=puuids(K)
T={'IRON':'Железо','BRONZE':'Бронза','SILVER':'Серебро','GOLD':'Золото','PLATINUM':'Платина','EMERALD':'Изумруд','DIAMOND':'Алмаз','MASTER':'Мастер','GRANDMASTER':'Грандмастер','CHALLENGER':'Претендент'}
def get(u,tries=3):
  try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'X-Riot-Token':K,'User-Agent':'curl/8'}),timeout=20))
  except urllib.error.HTTPError as e:
    if e.code==404: return None
    if e.code==429 and tries>0: time.sleep(int(e.headers.get('Retry-After') or 10)+1); return get(u,tries-1)
    raise
def scout(x,q):
  # разведка соперника: мастерство на его чемпионе и последние 10 рейтинговых игр
  sc={}
  try:
    m=get(f"https://euw1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{x['puuid']}/by-champion/{x['championId']}")
    if m: sc['m']=[m['championLevel'],m['championPoints']]
  except Exception: pass
  try:
    ids=get(f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{x['puuid']}/ids?queue={q if q in (420,440) else 420}&count=10") or []
    res=[]
    for i in ids:
      g=get(f'https://europe.api.riotgames.com/lol/match/v5/matches/{i}')
      if not g or g['info']['gameDuration']<300: continue
      me=next((p for p in g['info']['participants'] if p['puuid']==x['puuid']),None)
      if me: res.append((me['win'],me['championId']==x['championId'],me['kills'],me['deaths'],me['assists'],me.get('teamPosition','')))
    if res:
      st=0
      for r in res:
        if st==0 or (st>0)==r[0]: st+=1 if r[0] else -1
        else: break
      on=[r for r in res if r[1]]
      pos={};[pos.__setitem__(r[5],pos.get(r[5],0)+1) for r in res if r[5]]
      sc.update(r=[sum(r[0] for r in res),sum(not r[0] for r in res)],st=st,cn=[len(on),sum(r[0] for r in on)],
        kda=round(sum(r[2]+r[4] for r in on)/max(1,sum(r[3] for r in on)),2) if on else None,pos=max(pos,key=pos.get) if pos else '')
  except Exception as e: print('scout',e)
  return sc
OUT='../data/live.json'
if not os.path.exists('champ_ids.json'):
  v=get('https://ddragon.leagueoflegends.com/api/versions.json')[0]
  d=get(f'https://ddragon.leagueoflegends.com/cdn/{v}/data/en_US/champion.json')['data']
  json.dump({x['key']:x['id'] for x in d.values()},open('champ_ids.json','w'))
CID=json.load(open('champ_ids.json'))
old=json.load(open(OUT)) if os.path.exists(OUT) else {'games':[]}
games={}
for who,p in P.items():
  g=get(f'https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{p}')
  if not g: continue
  gid=g['gameId']
  if gid in games: games[gid]['who'].append(who); continue
  prev=next((x for x in old['games'] if x['id']==gid),None)
  if prev: prev['who']=[who]; games[gid]=prev; continue
  pl=[]
  for x in g['participants']:
    rk=''
    try:
      for e in get(f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{x['puuid']}") or []:
        if e['queueType']=='RANKED_SOLO_5x5': rk=f"{T.get(e['tier'],e['tier'])} {e['rank']} · {e['leaguePoints']} LP · {round(e['wins']/max(1,e['wins']+e['losses'])*100)}% из {e['wins']+e['losses']}"
    except Exception: pass
    pl.append(dict(c=CID.get(str(x['championId']),str(x['championId'])),n=x.get('riotId','').split('#')[0],team=x['teamId'],me=next((k for k,v in P.items() if v==x['puuid']),None),
      s=[x['spell1Id'],x['spell2Id']],k=(x.get('perks') or {}).get('perkIds',[None])[0],sub=(x.get('perks') or {}).get('perkSubStyle'),rk=rk))
  ours={x['teamId'] for x in g['participants'] if x['puuid']==p}
  for x,d in zip(g['participants'],pl):
    if x['teamId'] not in ours and x.get('puuid'): d['sc']=scout(x,g.get('gameQueueConfigId'))
  games[gid]=dict(id=gid,who=[who],q=g.get('gameQueueConfigId'),start=g.get('gameStartTime'),players=pl,
    bans=[[CID.get(str(b['championId']),None),b['teamId']] for b in g.get('bannedChampions',[]) if b['championId']>0])
new={'games':list(games.values())}
if [x['id'] for x in new['games']]!=[x['id'] for x in old['games']] or [x['who'] for x in new['games']]!=[x['who'] for x in old['games']]:
  new['t']=int(time.time()*1000)
  json.dump(new,open(OUT,'w'),ensure_ascii=False,separators=(',',':'))
  print('changed',len(new['games']))
else: print('same',len(new['games']))
