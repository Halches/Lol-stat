import json,os,urllib.request,datetime,collections
K=os.environ.get('RIOT_API_KEY','').strip().strip('"')
from players import puuids,NAMES
try: P=[(NAMES[w],p) for w,p in puuids(K).items()]
except Exception as e: print('аккаунты не получены',e);P=[]
T={'IRON':'Железо','BRONZE':'Бронза','SILVER':'Серебро','GOLD':'Золото','PLATINUM':'Платина','EMERALD':'Изумруд','DIAMOND':'Алмаз','MASTER':'Мастер','GRANDMASTER':'Грандмастер','CHALLENGER':'Претендент'}
ranks=[];snap=[]
try:
 for n,p in P:
   r=json.load(urllib.request.urlopen(urllib.request.Request(f'https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{p}',headers={'X-Riot-Token':K,'User-Agent':'curl/8'})))
   qs=[]
   for e in sorted(r,key=lambda e:e['queueType']!='RANKED_SOLO_5x5'):
     if e['queueType'] not in('RANKED_SOLO_5x5','RANKED_FLEX_SR'):continue
     snap.append(dict(who=n.split('#')[0],q='solo' if e['queueType']=='RANKED_SOLO_5x5' else 'flex',tier=e['tier'],div=e['rank'],lp=e['leaguePoints'],w=e['wins'],l=e['losses']))
     qs.append(dict(t='Соло' if e['queueType']=='RANKED_SOLO_5x5' else 'Флекс',r=f"{T.get(e['tier'],e['tier'])} {e['rank']} · {e['leaguePoints']} LP",
       wl=f"{e['wins']}–{e['losses']} ({round(e['wins']/(e['wins']+e['losses'])*100)}%)"))
   ranks.append(dict(name=n,q=qs))
 json.dump(ranks,open('ranks.json','w'),ensure_ascii=False)
except Exception as e:
 print('ranks: не удалось обновить, беру сохранённые', e)
 ranks=json.load(open('ranks.json')) if os.path.exists('ranks.json') else []
games=json.load(open('games.json'))
# мастерство чемпионов
mastery={}
try:
  idmap={int(v['key']):v['id'] for v in json.load(open('dd/champion.json'))['data'].values()}
  for n,p in P:
    r=json.load(urllib.request.urlopen(urllib.request.Request(f'https://euw1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{p}',headers={'X-Riot-Token':K,'User-Agent':'curl/8'})))
    mastery['halch' if n.startswith('Halch') else 'drv']=[[idmap.get(x['championId'],str(x['championId'])),x['championLevel'],x['championPoints'],x['lastPlayTime']] for x in r]
  json.dump(mastery,open('mastery.json','w'),separators=(',',':'))
except Exception as e:
  print('mastery: не удалось обновить, беру сохранённое', e)
  mastery=json.load(open('mastery.json')) if os.path.exists('mastery.json') else {}
patch=games[0]['ver']
msk=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=3)
lp=json.load(open('lp_history.json')) if os.path.exists('lp_history.json') else []
for x in snap:
  last=next((h for h in reversed(lp) if h['who']==x['who'] and h['q']==x['q']),None)
  if not last or any(last[k]!=x[k] for k in ('tier','div','lp','w','l')): lp.append({'t':int(datetime.datetime.now().timestamp()*1000),**x})
json.dump(lp,open('lp_history.json','w'),ensure_ascii=False,separators=(',',':'))
meta=dict(ranks=ranks,updated=msk.strftime('%d.%m %H:%M')+' МСК',patch=patch,dd=open('dd/ver').read().strip(),lp=lp,mastery=mastery,lola=json.load(open('lola.json')) if os.path.exists('lola.json') else {})
OUT=os.environ.get('OUT','..')
os.makedirs(f'{OUT}/data',exist_ok=True)
for f in os.listdir(f'{OUT}/data'):
  if f.startswith('d-') and f.endswith('.json'): os.remove(f'{OUT}/data/{f}')
LITE=('c','n','t','team','pos','me','share','tr')
DET=('parts','gd','xd','kev','obev','obj','ppos','kall','win100')
CH=50
summary=[];chunks={}
for i,g in enumerate(games):
  ck=(len(games)-1-i)//CH
  summary.append({**{k:v for k,v in g.items() if k not in DET},'ck':ck,'parts':[{k:p.get(k) for k in LITE} for p in g['parts']]})
  chunks.setdefault(ck,[]).append({'id':g['id'],**{k:g[k] for k in DET if k in g}})
dump=lambda o,p:json.dump(o,open(p,'w'),ensure_ascii=False,separators=(',',':'))
dump(summary,f'{OUT}/data/summary.json')
for ck,arr in chunks.items(): dump(arr,f'{OUT}/data/d-{ck}.json')
meta['n']=len(games);meta['chunks']=len(chunks)
h=open('template.html').read().replace('/*ICONS*/',open('icons.json').read()).replace('/*META*/',json.dumps(meta,ensure_ascii=False))
page='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head><body>'+h+'</body></html>'
open(f'{OUT}/index.html','w').write(page)
print('index',os.path.getsize(f'{OUT}/index.html'),'summary',os.path.getsize(f'{OUT}/data/summary.json'),'chunks',len(chunks))
