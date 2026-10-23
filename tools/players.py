# PUUID шифруется под каждый ключ Riot, поэтому берём его по Riot ID при каждом запуске.
import json,urllib.request,urllib.parse
IDS={'halch':('Halch','9200'),'drv':('DrVoldemar','EUW')}
NAMES={'halch':'Halch#9200','drv':'DrVoldemar#EUW'}
def puuids(K):
  out={}
  for who,(n,t) in IDS.items():
    u=f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{urllib.parse.quote(n)}/{t}'
    out[who]=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'X-Riot-Token':K,'User-Agent':'curl/8'}),timeout=20))['puuid']
  return out
