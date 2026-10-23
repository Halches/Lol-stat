import json,os,io,base64,urllib.request
from PIL import Image
V=open('dd/ver').read().strip()
os.makedirs('img',exist_ok=True)
games=json.load(open('games.json'))
champ=json.load(open('dd/champion.json'))['data']
lower={k.lower():k for k in champ}
def fetch(url,path):
  if not os.path.exists(path):
    try:
      urllib.request.urlretrieve(url,path)
    except Exception as e:
      print('miss',url,e); return None
  return path
def enc(path,size):
  im=Image.open(path).convert('RGBA').resize((size,size),Image.LANCZOS)
  b=io.BytesIO(); im.save(b,'WEBP',quality=80); return 'data:image/webp;base64,'+base64.b64encode(b.getvalue()).decode()
out={'c':{},'i':{},'s':{},'r':{},'names':{}}
if os.path.exists('icons.json'):
  out.update(json.load(open('icons.json')))
  for k in ('c','i','s','r','inames','snames','rnames'): out[k]={(int(x) if k!='c' and str(x).lstrip('-').isdigit() else x):v for x,v in out[k].items()}
champs={p['c'] for g in games for p in g['parts']}
for c in champs:
  if c in out['c']: continue
  k=lower.get(c.lower(),c)
  out['names'][c]=champ[k]['name'] if k in champ else c
  p=fetch(f'https://ddragon.leagueoflegends.com/cdn/{V}/img/champion/{k}.png',f'img/c_{k}.png')
  if p: out['c'][c]=enc(p,48)
items=json.load(open('dd/item.json'))['data']
iset={i for g in games for p in g['parts'] for i in p['items']+[b[0] for b in p.get('buys',[])] if i}
out.setdefault('inames',{})
for i in iset:
  if i in out['i']: continue
  p=fetch(f'https://ddragon.leagueoflegends.com/cdn/{V}/img/item/{i}.png',f'img/i_{i}.png')
  if p: out['i'][i]=enc(p,32)
  if str(i) in items: out['inames'][i]=items[str(i)]['name']
summ=json.load(open('dd/summoner.json'))['data']
skey={int(v['key']):v for v in summ.values()}
out.setdefault('snames',{})
for s in {s for g in games for m in g['me'] for s in m['sums']}:
  if s in skey:
    p=fetch(f'https://ddragon.leagueoflegends.com/cdn/{V}/img/spell/{skey[s]["id"]}.png',f'img/s_{s}.png')
    if p: out['s'][s]=enc(p,28); out['snames'][s]=skey[s]['name']
runes=json.load(open('dd/runes.json'))
perk={}
for st in runes:
  perk[st['id']]=st
  for sl in st['slots']:
    for r in sl['runes']: perk[r['id']]=r
out.setdefault('rnames',{})
for r in {x for g in games for m in g['me'] for x in (m['keystone'],m['sec'])}:
  if r in perk:
    p=fetch('https://ddragon.leagueoflegends.com/cdn/img/'+perk[r]['icon'],f'img/r_{r}.png')
    if p: out['r'][r]=enc(p,28); out['rnames'][r]=perk[r]['name']
p=fetch(f'https://ddragon.leagueoflegends.com/cdn/{V}/img/map/map11.png','img/map11.png')
if p:
  im=Image.open(p).convert('RGB').resize((420,420),Image.LANCZOS); b=io.BytesIO(); im.save(b,'WEBP',quality=70)
  out['map']='data:image/webp;base64,'+base64.b64encode(b.getvalue()).decode()
for r in {x for g in games for m in g['me'] for x in m.get('perks',[])[:1]}:
  if r in perk and r not in out['r']:
    p=fetch('https://ddragon.leagueoflegends.com/cdn/img/'+perk[r]['icon'],f'img/r_{r}.png')
    if p: out['r'][r]=enc(p,28); out['rnames'][r]=perk[r]['name']
json.dump(out,open('icons.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(out['c']),len(out['i']),os.path.getsize('icons.json'))
