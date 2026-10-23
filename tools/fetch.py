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
SEASON=int(os.environ.get('SEASON_START','1767830400'))
for n,p in P.items():
  allids=[]
  for typ in ('ranked','normal'):
    st=0
    while True:
      l=get(B+f'by-puuid/{p}/ids?type={typ}&startTime={SEASON}&start={st}&count=100')
      allids+=l; st+=100
      if len(l)<100: break
  json.dump(allids,open(f'{D}/ids_{n.split("#")[0]}.json','w')); ids|=set(allids)
  print(n,len(allids),file=sys.stderr,flush=True)
print(len(ids),file=sys.stderr,flush=True)
n_done=0
for m in sorted(ids):
  f=f'{D}/{m}.json'
  if not os.path.exists(f):
    x=get(B+m)
    json.dump(x,open(f,'w'))
  else: x=json.load(open(f))
  if x and x['info'].get('queueId') in (400,420,430,440,490,480) and x['info']['gameDuration']>600:
    t=f'{D}/{m}_tl.json'
    if not os.path.exists(t): json.dump(get(B+m+'/timeline'),open(t,'w'))
  n_done+=1
  if n_done%50==0: print('progress',n_done,file=sys.stderr,flush=True)
print('done',file=sys.stderr)
