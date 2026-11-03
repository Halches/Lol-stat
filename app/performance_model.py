"""Сопоставимые показатели: неизвестные величины не заменяются оценками."""
import math


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def benchmark(record):
    record=record or {}
    result={key:record[key] for key in ('csm','gpm','kda') if number(record.get(key))}
    if 'kda' not in result and all(number(record.get(key)) for key in ('k','d','a')):
        result['kda']=(record['k']+record['a'])/max(1,record['d'])
    return result


def personal(player,champion,role):
    if not player or len(player.on(champion,role))<3:return {}
    return player.norm(champion,role)


def live_values(game):
    me=game.me;minutes=max(1,game.t/60)
    team_kills=sum(p['k'] for p in game.allies)
    # Live API даёт оставшиеся деньги и инвентарь, но не всё заработанное золото.
    # Продажи, расходники и скидки делают inventory + currentGold несопоставимым.
    return {'csm':me['cs']/minutes,'gpm':None,
            'kda':(me['k']+me['a'])/max(1,me['d']),
            'kp':min(100,(me['k']+me['a'])/team_kills*100) if team_kills else None,
            'vsm':me['ward']/minutes if me.get('ward_known',False) else None}
