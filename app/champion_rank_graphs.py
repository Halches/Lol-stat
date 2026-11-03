"""Публичные глобальные рейтинги LeagueOfGraphs; только подтверждённые места."""
import html
import re
import time
import urllib.request
import champion_rank
import core


def url(champion,page=1):
    slug=core.LOLA_FIX.get(champion,champion.lower())
    if not re.fullmatch(r'[a-z0-9]+',slug) or not 1<=page<=10:raise ValueError('Контекст рейтинга')
    return 'https://www.leagueofgraphs.com/rankings/summoners/'+slug+(f'/page-{page}' if page>1 else '')


def parse(text,champion_id,champion,page=1,now=None):
    expected=url(champion,page).partition('.com')[2]
    canonical=re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"',text)
    base=url(champion).partition('.com')[2]
    if not canonical or canonical[1] not in (expected,base,'https://www.leagueofgraphs.com'+expected,'https://www.leagueofgraphs.com'+base):return None
    if not re.search(r'On all regions|Rankings\s*·\s*All regions',html.unescape(text)):return None
    if not re.search(r'champion-icons/[\d.]+/\d+/'+re.escape(str(champion_id))+r'\.png',text):return None
    rows=[];slots=[]
    for block in text.split('<div class="lolg-rk__row">')[1:]:
        rank=re.search(r'class="lolg-rk__num">\s*(\d+)\.',block)
        who=re.search(r'<a class="lolg-rk-who" href="/summoner/([a-z0-9]+)/[^"<>]*">(.*?)</a>',block,re.S)
        if not rank or not who:return None
        slots.append(int(rank[1]))
        name=re.search(r'<img\b[^>]*\balt="([^"]+)"',who[2])
        reg=re.search(r'class="lolg-rk-who__region">\s*([^<\s]+)',who[2])
        riot=html.unescape(name[1]) if name else ''
        if not riot:continue  # Source withheld the identity; keep its slot unknown.
        region=('sg' if reg and reg[1]=='SEA' and who[1]=='sg' else champion_rank.region(reg[1])) if reg else None
        if not champion_rank.identity(riot) or not riot.isprintable() or len(riot)>160 or not region or region!=champion_rank.region(who[1]):return None
        rows.append({'rank':int(rank[1]),'riot':riot,'region':region})
    start=(page-1)*100+1
    if not slots or len(slots)>100 or slots!=list(range(start,start+len(slots))):return None
    if len({(champion_rank.identity(r['riot']),r['region']) for r in rows})!=len(rows):return None
    return {'champion':champion,'rows':rows,'scope':'global','source':'LeagueOfGraphs','url':url(champion),
            'fetched_at':time.time() if now is None else now,'coverage':len(rows),'partial':True,'scanned_to':slots[-1],'entries':len(slots)}


def fetch(champion_id,champion,publish=lambda board:None,read=None):
    def download(page_url):
        request=urllib.request.Request(page_url,headers={'User-Agent':'LoLHelper/1.0'})
        with urllib.request.urlopen(request,timeout=8) as response:
            if response.geturl()!=page_url:raise ValueError('Другой адрес рейтинга')
            raw=response.read(1_000_001)
        if len(raw)>1_000_000:raise ValueError('Ответ слишком большой')
        return raw.decode('utf-8')
    read=read or download;result=None;deadline=time.monotonic()+60
    for page in range(1,11):
        if time.monotonic()>deadline:break
        try:chunk=parse(read(url(champion,page)),champion_id,champion,page)
        except Exception:break
        if not chunk:break
        rows=(result['rows'] if result else [])+chunk['rows']
        if len({(champion_rank.identity(r['riot']),r['region']) for r in rows})!=len(rows):break
        result=dict(chunk,rows=rows,coverage=len(rows),partial=chunk['scanned_to']<1000)
        publish(result)
        if chunk['entries']<100:break
    return result
