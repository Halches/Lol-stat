"""Обновить только игровые поля по сохранённому модулю вики. Lua не исполняется."""
import argparse
import hashlib
import json
from pathlib import Path
import re

URL='https://wiki.leagueoflegends.com/en-us/Module:ChampionData/data?action=raw'


def records(text):
    starts=list(re.finditer(r'^  \["[^"\n]+"\]\s*=\s*\{',text,re.M));result={}
    for i,start in enumerate(starts):
        block=text[start.end():starts[i+1].start() if i+1<len(starts) else len(text)]
        ident=re.search(r'^[ \t]+\["id"\]\s*=\s*(\d+)\s*,',block,re.M)
        if not ident:continue
        cid=ident[1]
        if cid in result:raise ValueError('Повтор ID')
        def string(key):
            match=re.search(r'^[ \t]+\["'+key+r'"\]\s*=\s*("[^"\n]*")\s*,',block,re.M)
            return json.loads(match[1]) if match else None
        positions=re.search(r'^[ \t]+\["external_positions"\]\s*=\s*\{([^{}\n]*)\}\s*,',block,re.M)
        role_names=re.findall(r'"([A-Za-z]+)"',positions[1]) if positions else []
        resource,attack,date=string('resource'),string('rangetype'),string('date')
        if not resource or attack not in ('Melee','Ranged') or not date or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) or not role_names:
            continue
        result[cid]={'resource':resource,'attackType':[attack],'releaseYear':int(date[:4]),'positions':[name.upper() for name in role_names]}
    return result


def refresh(catalog,ids,text,date):
    rows=records(text)
    missing=set(ids)-set(rows)
    if missing:raise ValueError('Нет полных данных для ID: '+', '.join(sorted(missing)))
    result=json.loads(json.dumps(catalog))
    for cid,name in ids.items():result['champions'].setdefault(name,{}).update(rows[cid])
    result['source'].update(gameplay_snapshot_date=date,gameplay_url=URL,
                            gameplay_sha256=hashlib.sha256(text.encode()).hexdigest(),
                            note='Ресурс, тип атаки, роли и год обновлены напрямую из модуля вики; пол, вид и происхождение остаются в исходном снимке.')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',type=Path,required=True);parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True);parser.add_argument('--date',required=True)
    args=parser.parse_args()
    result=refresh(json.loads(args.catalog.read_text()),json.loads(args.data.read_text())['ids'],args.module.read_text(),args.date)
    args.catalog.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print('Обновлены игровые поля:',len(json.loads(args.data.read_text())['ids']))
