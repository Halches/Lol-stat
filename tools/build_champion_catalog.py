"""Build the pool's factual metadata subset from a saved wiki-derived snapshot.

python tools/build_champion_catalog.py --input output.json --output app/champion_catalog.json
The input's provenance is fixed below. Updating it requires checking its source/date.
No wiki scraping, executable Lua or unverified fallback attributes are used.
"""
import argparse
import json
from pathlib import Path

SOURCE = {'name':'LoL Wiki через iEranDEV/loldle-data',
          'url':'https://github.com/iEranDEV/loldle-data/blob/a2994b6b3f047dc96744d1066908bd657185866c/output.json',
          'wiki':'https://wiki.leagueoflegends.com/en-us/','snapshot_date':'2026-03-04',
          'retrieved':'2026-11-03','commit':'a2994b6b3f047dc96744d1066908bd657185866c',
          'note':'Производная выгрузка, не проверена на соответствие текущему состоянию вики. Неизвестные значения не угадываются.'}
FIELDS=['gender','regions','species','releaseYear','resource','attackType','positions']

def build(raw):
    if not isinstance(raw,list):raise ValueError('Expected a champion list')
    records={}
    for row in raw:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str):raise ValueError('Invalid champion record')
        if row['id'] in records:raise ValueError('Duplicate champion')
        records[row['id']]={k:row.get(k) for k in FIELDS}
    return {'source':SOURCE,'champions':records}

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--input',required=True,type=Path);cli.add_argument('--output',required=True,type=Path)
    args=cli.parse_args()
    result=build(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print(f"Записано {len(result['champions'])} чемпионов")
