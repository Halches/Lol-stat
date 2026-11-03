"""Подключённые внешние сборки драфта; никогда не подменяют отсутствующий вариант."""
def selected(context,champion,role,offmeta=None,players=None):
    if context=='offmeta':
        row=offmeta
        if not row or row.get('champion')!=champion or row.get('role')!=role:return None
    elif context.startswith('player:'):
        if not players or players.get('champion')!=champion or players.get('role')!=role:return None
        row=next((p for rows in players.get('groups',{}).values() for p in rows if 'player:'+p['id']==context),None)
        if not row or row.get('champion')!=champion or row.get('role')!=role:return None
    else:return None
    if not row.get('variant'):return None
    return {'pick':row['variant'],'situ':row.get('situ',[]),'external':row.get('source','Mobalytics'),
            'external_name':row.get('name','Оффметовая'),'patch':row.get('patch'),'source_url':row.get('source_url'),'stale':bool(row.get('stale') or (players or {}).get('stale'))}


def option(title,variant,winrate,games):
    return {'key':'pick','title':title,'variant':variant,'rune_winrate':winrate,'rune_games':games,
            'item_winrate':None,'item_games':None}
