import os,json,time,urllib.request,urllib.error,sys
K=os.environ['RIOT_API_KEY']; D='data'
P={'Halch#9200':'rGwU8TiuBiNSHqzSURckHNSy4h3eqNCkE7jmS30dYYFe8Qnx6IXOEttr8cz4SHa35xwCrweFXfcFeA',
   'DrVoldemar#EUW':'8p5ZvbhGJkcwxL_F0wKmjeb0keVOtltH7esKs1_gV8AZxaHIeC-S0eV7B78iINgvIVzNsJMR2i57DQ'}
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
B='https://europe.api.riotgames.com/lol/match/v5/matches/'
ids=set()
for n,p in P.items():
  l=get(B+f'by-puuid/{p}/ids?start=0&count=60')
  json.dump(l,open(f'{D}/ids_{n.split("#")[0]}.json','w')); ids|=set(l)
print(len(ids),file=sys.stderr)
for m in sorted(ids):
  f=f'{D}/{m}.json'
  if not os.path.exists(f):
    x=get(B+m)
    json.dump(x,open(f,'w'))
  else: x=json.load(open(f))
  if x and x['info'].get('queueId') in (400,420,430,440,490,480) and x['info']['gameDuration']>600:
    t=f'{D}/{m}_tl.json'
    if not os.path.exists(t): json.dump(get(B+m+'/timeline'),open(t,'w'))
print('done',file=sys.stderr)
