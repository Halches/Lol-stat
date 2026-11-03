"""Current client ranks by queue. Arena's retired Gladiator rank is never reused."""
import time

QUEUES={'solo':'RANKED_SOLO_5x5','flex':'RANKED_FLEX_SR','tft':'RANKED_TFT'}
TIERS={'IRON','BRONZE','SILVER','GOLD','PLATINUM','EMERALD','DIAMOND','MASTER','GRANDMASTER','CHALLENGER'}
APEX={'MASTER','GRANDMASTER','CHALLENGER'}


def nonnegative_int(value):
    return type(value) is int and value>=0


def parse(raw,now=None):
    queue_map=raw.get('queueMap') if isinstance(raw,dict) else None
    if not isinstance(queue_map,dict):queue_map={}
    stamp=time.time() if now is None else now
    result={'attempted_at':stamp,'fetched_at':stamp if isinstance(raw,dict) and isinstance(raw.get('queueMap'),dict) else None,'source':'client'}
    for key,queue in QUEUES.items():
        entry=queue_map.get(queue)
        rank={'state':'unknown'}
        if isinstance(entry,dict) and entry.get('queueType',queue)==queue:
            tier=entry.get('tier')
            if tier=='NONE':
                rank={'state':'provisional' if entry.get('isProvisional') is True else 'unranked'}
            elif isinstance(tier,str) and tier in TIERS and nonnegative_int(entry.get('leaguePoints')):
                division=entry.get('division','')
                if tier in APEX or division in ('I','II','III','IV'):
                    rank={'state':'ranked','tier':tier,'div':'' if tier in APEX else division,'lp':entry['leaguePoints'],
                          'w':entry.get('wins') if nonnegative_int(entry.get('wins')) else None,
                          'l':entry.get('losses') if nonnegative_int(entry.get('losses')) else None}
        result[key]=rank
    # Arena has used Fame since 2025. Never reinterpret old CHERRY/ratedRating as Fame or LP.
    result['arena']={'state':'fame_unavailable'}
    return result


def legacy_solo(overview):
    rank=(overview or {}).get('solo') or {}
    if rank.get('state')!='ranked':return None
    return {k:(rank.get(k) or 0) if k in ('w','l') else rank[k] for k in ('tier','div','lp','w','l')}
