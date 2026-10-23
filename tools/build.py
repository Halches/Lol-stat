import json,os,urllib.request,datetime,collections
K=os.environ['RIOT_API_KEY']
P=[('Halch#9200','rGwU8TiuBiNSHqzSURckHNSy4h3eqNCkE7jmS30dYYFe8Qnx6IXOEttr8cz4SHa35xwCrweFXfcFeA'),
   ('DrVoldemar#EUW','8p5ZvbhGJkcwxL_F0wKmjeb0keVOtltH7esKs1_gV8AZxaHIeC-S0eV7B78iINgvIVzNsJMR2i57DQ')]
T={'IRON':'Железо','BRONZE':'Бронза','SILVER':'Серебро','GOLD':'Золото','PLATINUM':'Платина','EMERALD':'Изумруд','DIAMOND':'Алмаз','MASTER':'Мастер','GRANDMASTER':'Грандмастер','CHALLENGER':'Претендент'}
ranks=[]
try:
 for n,p in P:
   r=json.load(urllib.request.urlopen(urllib.request.Request(f'https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{p}',headers={'X-Riot-Token':K,'User-Agent':'curl/8'})))
   qs=[]
   for e in sorted(r,key=lambda e:e['queueType']!='RANKED_SOLO_5x5'):
     if e['queueType'] not in('RANKED_SOLO_5x5','RANKED_FLEX_SR'):continue
     qs.append(dict(t='Соло' if e['queueType']=='RANKED_SOLO_5x5' else 'Флекс',r=f"{T.get(e['tier'],e['tier'])} {e['rank']} · {e['leaguePoints']} LP",
       wl=f"{e['wins']}–{e['losses']} ({round(e['wins']/(e['wins']+e['losses'])*100)}%)"))
   ranks.append(dict(name=n,q=qs))
 json.dump(ranks,open('ranks.json','w'),ensure_ascii=False)
except Exception as e:
 print('ranks: не удалось обновить, беру сохранённые', e)
 ranks=json.load(open('ranks.json')) if os.path.exists('ranks.json') else []
games=json.load(open('games.json'))
patch=games[0]['ver']
msk=datetime.datetime.utcnow()+datetime.timedelta(hours=3)
meta=dict(ranks=ranks,updated=msk.strftime('%d.%m %H:%M')+' МСК',patch=patch,dd=open('dd/ver').read().strip())
h=open('template.html').read().replace('/*DATA*/',json.dumps(games,ensure_ascii=False,separators=(',',':'))).replace('/*ICONS*/',open('icons.json').read()).replace('/*META*/',json.dumps(meta,ensure_ascii=False))
open('index.html','w').write(h); print(os.path.getsize('index.html'))
