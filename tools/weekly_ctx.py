# Сводка для недельного отчёта тренера: последние 7 дней против 4 недель до них.
import json,time,collections,sys
games=json.load(open(sys.argv[1] if len(sys.argv)>1 else 'games.json'))
now=time.time()*1000;D=86400000
ROLE={'TOP':'топ','JUNGLE':'лес','MIDDLE':'мид','BOTTOM':'бот','UTILITY':'саппорт'}
def stats(ms):
  n=len(ms)
  if not n: return 'нет игр'
  w=sum(m['win'] for m in ms);avg=lambda f:(lambda a:sum(a)/len(a) if a else None)([f(m) for m in ms if f(m) is not None])
  kda=sum(m['k']+m['a'] for m in ms)/max(1,sum(m['d'] for m in ms))
  g15=avg(lambda m:m['diffs'].get('15',m['diffs'].get(15,{})).get('gold'));cs=avg(lambda m:None if m['pos']=='UTILITY' else m['csm'])
  f=lambda x,d=1:'—' if x is None else f'{x:.{d}f}'
  return f"{n} игр, {w}–{n-w} ({w/n*100:.0f}%), KDA {kda:.2f}, смертей {f(avg(lambda m:m['d']))}, до 14 мин {f(avg(lambda m:m['early_d']))}, CS/мин {f(cs)}, золото vs опп. на 15 {f(g15,0)}, обзор/мин {f(avg(lambda m:m['vsm']),2)}, KP {f(avg(lambda m:m['kp']),0)}%, вклад #{f(avg(lambda m:m['tr']))} в команде"
for who,name in (('halch','Halch'),('drv','DrVoldemar')):
  rows=[(g,m) for g in games for m in g['me'] if m['who']==who]
  wk=[m for g,m in rows if now-g['start']<7*D];pr=[m for g,m in rows if 7*D<=now-g['start']<35*D]
  print(f'## {name}\nЭта неделя: {stats(wk)}\nПрошлые 4 недели: {stats(pr)}')
  c=collections.defaultdict(list)
  for m in wk: c[(m['c'],m['pos'])].append(m)
  for (ch,pos),ms in sorted(c.items(),key=lambda x:-len(x[1])): print(f"- {ch} ({ROLE.get(pos,pos)}): {stats(ms)}")
  for g,m in sorted([(g,m) for g,m in rows if now-g['start']<7*D],key=lambda x:x[0]['start']):
    o=m.get('opp') or {}
    print(f"  · {time.strftime('%a %d.%m %H:%M',time.gmtime(g['start']/1000+3*3600))} {g['qn']} {'W' if m['win'] else 'L'} {m['c']} vs {o.get('c','?')} {m['k']}/{m['d']}/{m['a']}, @15 {(m['diffs'].get('15') or m['diffs'].get(15) or {}).get('gold')}, смерти до 14: {m['early_d']}")
  print()
