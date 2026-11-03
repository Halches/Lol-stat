"""Compact, factual match details from the repository's existing analysed games."""
import json
import math
from pathlib import Path


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def build(games):
    matches={}
    for game in games:
        mid=game.get('id')
        if not isinstance(mid,str) or not mid or not game.get('parts'):continue
        if mid in matches:raise ValueError('Duplicate match ID: '+mid)
        profiles={}
        for me in game.get('me') or []:
            who=me.get('who')
            if not who:continue
            profiles[who]={'champion':me.get('c'),'role':me.get('pos'),'spells':list(me.get('sums') or [])[:2],
                'perk':me.get('keystone'),**{key:me.get(source) for key,source in
                    [('k','k'),('d','d'),('a','a'),('cs','cs'),('dmg','dmg'),('gold','g'),('vis','vs'),('lvl','lvl')]}}
        rows=[]
        for player in game['parts']:
            name=player.get('n') or 'Имя недоступно'
            if player.get('n') and player.get('t'):name+='#'+player['t']
            win=game.get('win100')
            outcome=(win if player.get('team')==100 else not win) if type(win) is bool and player.get('team') in (100,200) else None
            row={'c':player.get('c'),'pos':player.get('pos'),'team':player.get('team'),'name':name,
                'profile':player.get('me'),'win':outcome,'items':list(player.get('items') or [])[:7]}
            for key,source in [('k','k'),('d','d'),('a','a'),('cs','cs'),('dmg','dmg'),('gold','g'),('vis','vs')]:
                value=player.get(source);row[key]=value if number(value) else None
            row['lvl']=profiles.get(player.get('me'),{}).get('lvl')
            rows.append(row)
        matches[mid]={'id':mid,'timestamp':game['start']//1000 if number(game.get('start')) else None,
            'q':game.get('q'),'min':game.get('dur') if number(game.get('dur')) else None,'rows':rows,'profiles':profiles}
    return matches


def attach(data,matches):
    """Join old compact records by exact profile/champion/queue/time; never guess."""
    valid={mid:value for mid,value in matches.items() if isinstance(value,dict) and value.get('id')==mid
        and isinstance(value.get('profiles'),dict) and isinstance(value.get('rows'),list)}
    data['match_details']=valid
    index={}
    for mid,game in valid.items():
        if not number(game.get('timestamp')) or not game['timestamp']:continue
        for who,profile in (game.get('profiles') or {}).items():
            if not profile.get('champion'):continue
            key=(who,profile.get('champion'),game.get('q'),game.get('timestamp'))
            index.setdefault(key,[]).append((mid,profile))
    for who,player in data.get('players',{}).items():
        for record in player.get('g',[]):
            found=index.get((who,record.get('c'),record.get('q'),record.get('t')),[])
            if len(found)!=1:continue
            mid,profile=found[0]
            if record.get('id') and record['id']!=mid:continue
            record['id']=mid
            for field in ('spells','cs','dmg','gold','vis'):
                if field not in record and profile.get(field) is not None:record[field]=profile[field]
    return data


def review(snapshot,profile,match_id):
    if not isinstance(snapshot,dict) or snapshot.get('id')!=match_id:return None
    rows=[]
    for original in snapshot.get('rows') or []:
        if not isinstance(original,dict):continue
        row=dict(original);row['items']=list(row.get('items') or [])
        row['me']=bool(profile) and row.pop('profile',None)==profile
        rows.append(row)
    if not rows:return None
    return {'rows':rows,'me':next((row for row in rows if row['me']),None),'min':snapshot.get('min'),
        'q':snapshot.get('q'),'lines':[],'analysis_available':False,'team_grouping':'teams','source':'saved'}


def main():
    import argparse
    import os
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    games=json.loads(Path(args.source).read_text(encoding='utf-8'))
    matches=build(games)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.name+'.tmp')
    temporary.write_text(json.dumps({'version':1,'matches':matches},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    os.replace(temporary,output)
    print('Saved match archive:',len(matches),'matches,',output.stat().st_size,'bytes')


if __name__=='__main__':main()
