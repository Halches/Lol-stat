# Текущая игра (spectator-v5) для обоих игроков -> ../data/live.json. Пишет файл, только если что-то поменялось.
import json,os,time,urllib.request,urllib.error
K=os.environ.get('RIOT_API_KEY','').strip().strip('"')
from players import puuids
P=puuids(K)
T={'IRON':'Железо','BRONZE':'Бронза','SILVER':'Серебро','GOLD':'Золото','PLATINUM':'Платина','EMERALD':'Изумруд','DIAMOND':'Алмаз','MASTER':'Мастер','GRANDMASTER':'Грандмастер','CHALLENGER':'Претендент'}
def get(u):
  try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'X-Riot-Token':K,'User-Agent':'curl/8'}),timeout=20))
  except urllib.error.HTTPError as e:
    if e.code==404: return None
    raise
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
  games[gid]=dict(id=gid,who=[who],q=g.get('gameQueueConfigId'),start=g.get('gameStartTime'),players=pl,
    bans=[[CID.get(str(b['championId']),None),b['teamId']] for b in g.get('bannedChampions',[]) if b['championId']>0])
new={'games':list(games.values())}
if [x['id'] for x in new['games']]!=[x['id'] for x in old['games']] or [x['who'] for x in new['games']]!=[x['who'] for x in old['games']]:
  new['t']=int(time.time()*1000)
  json.dump(new,open(OUT,'w'),ensure_ascii=False,separators=(',',':'))
  print('changed',len(new['games']))
else: print('same',len(new['games']))
