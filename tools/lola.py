# Средние Изумруд+ с lolalytics по чемпионам и ролям, на которых мы сыграли 3+ игры.
import json,os,re,time,urllib.request,collections
LANE={'TOP':'top','JUNGLE':'jungle','MIDDLE':'middle','BOTTOM':'bottom','UTILITY':'support'}
FIX={'MonkeyKing':'wukong'}
num=lambda s:float(s.replace(',',''))
def get(c,lane):
  u=f'https://lolalytics.com/lol/{FIX.get(c,c.lower())}/build/?lane={lane}&tier=emerald_plus'
  h=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read().decode('utf-8','ignore')
  t=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',h))
  f=lambda p:num(re.search(p,t).group(1))
  return dict(wr=f(r'([\d.]+) ?% Win Rate'),n=int(f(r'([\d,]+) Games')),avg=f(r'Average Emerald\+ Win Rate: ([\d.]+)'),
    dmg=f(r'Total Damage: ([\d,]+)'),taken=f(r'Damage Taken: ([\d,]+)'),k=f(r'Kills: ([\d.]+)'),d=f(r'Deaths: ([\d.]+)'),
    a=f(r'Assists: ([\d.]+)'),g=f(r'Gold: ([\d,]+)'),cs=f(r'Minions Killed: ([\d.]+)')+f(r'Jungle CS: ([\d.]+)'),
    patch=re.search(r'Patch ([\d.]+)',t).group(1))
games=json.load(open('games.json'))
cnt=collections.Counter((m['c'],m['pos']) for g in games for m in g['me'] if m['pos'] in LANE)
old=json.load(open('lola.json')) if os.path.exists('lola.json') else {}
out={}
for (c,pos),n in cnt.most_common():
  if n<3: continue
  k=f'{c}|{pos}'
  try: out[k]=get(c,LANE[pos]); print(k,out[k]['wr'],out[k]['n'])
  except Exception as e:
    print(k,'не получилось',e)
    if k in old: out[k]=old[k]
  time.sleep(1.5)
out['_t']=time.strftime('%Y-%m-%d')
json.dump(out,open('lola.json','w'),ensure_ascii=False,separators=(',',':'))
