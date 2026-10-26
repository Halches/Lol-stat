# Игры Арены (очередь 1700) за сезон: место, чемпион, напарник, счёт и урон. Копится в arena.json.
# Винрейты аугментов и предметов Арены Riot показывать запрещает, поэтому их не собираем.
import os,json,time,urllib.request,urllib.error,sys
from players import puuids,NAMES
K=os.environ.get('RIOT_API_KEY','').strip().strip('"')
SEASON=int(os.environ.get('SEASON_START','1767830400'))
B='https://europe.api.riotgames.com/lol/match/v5/matches/'
def get(url):
  for i in range(6):
    try:
      r=urllib.request.urlopen(urllib.request.Request(url,headers={'X-Riot-Token':K,'User-Agent':'curl/8'}),timeout=30)
      time.sleep(1.25); return json.load(r)
    except urllib.error.HTTPError as e:
      if e.code==429: time.sleep(int(e.headers.get('Retry-After','10'))+1); continue
      if e.code==404: return None
      raise
  raise Exception('fail '+url)
out=json.load(open('arena.json')) if os.path.exists('arena.json') else []
have={g['id'] for g in out}
try: pu=puuids(K)
except Exception as e: print('arena: аккаунты не получены',e); sys.exit(0)
ids=set()
for w,p in pu.items():
  st=0
  while True:
    l=get(B+f'by-puuid/{p}/ids?queue=1700&startTime={SEASON}&start={st}&count=100') or []
    ids|=set(l); st+=100
    if len(l)<100: break
new=sorted(ids-have)
print('arena new',len(new),file=sys.stderr)
if os.environ.get('GITHUB_OUTPUT'): open(os.environ['GITHUB_OUTPUT'],'a').write(f'arena={len(new)}\n')
mine={p:w for w,p in pu.items()}
for m in new:
  x=get(B+m)
  if not x or x['info'].get('queueId')!=1700: continue
  i=x['info'];ps=i['participants']
  for p in ps:
    w=mine.get(p['puuid'])
    if not w: continue
    mate=next((q for q in ps if q['puuid']!=p['puuid'] and q.get('playerSubteamId')==p.get('playerSubteamId')),{})
    out.append({'id':m,'who':w,'t':i['gameStartTimestamp']//1000,'dur':round(i['gameDuration']/60,1),'c':p['championName'],
      'place':p.get('placement') or p.get('subteamPlacement'),'k':p['kills'],'d':p['deaths'],'a':p['assists'],
      'dmg':p['totalDamageDealtToChampions'],'pc':mate.get('championName'),
      'pn':f"{mate.get('riotIdGameName','')}#{mate.get('riotIdTagline','')}" if mate else ''})
out.sort(key=lambda g:-g['t'])
json.dump(out,open('arena.json','w'),ensure_ascii=False,separators=(',',':'))
print('arena total',len(out),file=sys.stderr)
