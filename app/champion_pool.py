"""Champion catalogue, filtering and per-profile pool settings; independent of Tk."""
import json
import unicodedata
from pathlib import Path
import core

ROLE_MAP = {'TOP':'TOP','JUNGLE':'JUNGLE','MID':'MIDDLE','MIDDLE':'MIDDLE','ADC':'BOTTOM','BOT':'BOTTOM','BOTTOM':'BOTTOM','SUPPORT':'UTILITY','UTILITY':'UTILITY'}
LABELS = {
 "Xer'Sai":"Ксер'Сай", 'Crimson Rush':'Кровавый прилив',
 'MALE':'Мужской','FEMALE':'Женский','OTHER':'Другое / несколько',
 'Melee':'Ближний бой','Ranged':'Дальний бой','MELEE':'Ближний бой','RANGED':'Дальний бой',
 'Fighter':'Воин','Tank':'Танк','Mage':'Маг','Assassin':'Убийца','Marksman':'Стрелок','Support':'Поддержка',
 'Mana':'Мана','Energy':'Энергия','Manaless':'Без ресурса','None':'Без ресурса','Fury':'Ярость','Rage':'Ярость','Heat':'Перегрев','Blood Well':'Кровавый колодец','Flow':'Поток','Grit':'Решимость','Ferocity':'Свирепость','Courage':'Храбрость','Shield':'Щит',
 'Ionia':'Иония','Noxus':'Ноксус','Demacia':'Демасия','Freljord':'Фрельйорд','Piltover':'Пилтовер','Zaun':'Заун','Shurima':'Шурима','Targon':'Таргон','Ixtal':'Ишталь','Bilgewater':'Билджвотер','Bandle City':'Бандл Сити','Shadow Isles':'Сумрачные острова','Blessed Isles':'Благословенные острова','Void':'Бездна','Runeterra':'Рунтерра','Spirit Realm':'Мир духов','Camavor':'Камавор','Icathia':'Икатия','Kathkan':'Каткан',
 'Human':'Человек','Yordle':'Йордл','Darkin':'Даркин','Demon':'Демон','Vesani':'Весани','Kiilash':'Киилаш','Lhotlan':'Лотлан','Marai':'Марай','Shimon':'Шимон','Oovi-Kat':'Оови-Кат','Voidborn':'Порождение Бездны','Ascended':'Вознесшийся','God-Warrior':'Бог-воин','Celestial':'Небожитель','Celestial Dragon':'Небесный дракон','Dragon':'Дракон','Terrestrial Dragon':'Земной дракон','Spirit God':'Дух-бог','Spirit Gods':'Духи-боги','Spirit Tree':'Древо духов','Treant':'Энт','Troll':'Тролль','Minotaur':'Минотавр','Cat':'Кошка','Wraith':'Призрак','Revenant':'Восставший','Brackern':'Бракерн','Baccai':'Бакай','Aspect Host':'Носитель Аспекта','Blood Golem':'Голем крови','Elemental Golem':'Стихийный голем','Petricite Golem':'Петрицитовый голем','Ooze Golem':'Голем слизи','Techmaturgical Golem':'Техномагический голем','Chemical beast':'Химический зверь','Plague Rat':'Чумная крыса','Reincarnated Spirit':'Перерождённый дух','Human Demon':'Человек-демон','Evolved being':'Изменённое существо','Dune Hounds':'Дюнные гончие','Fae Fawn':'Волшебный оленёнок','Drakalops':'Дракалопс','Bryni':'Брини', 'Unknown':'Неизвестно',
}
FIELDS = [('gender','Пол'),('regions','Происхождение'),('species','Вид / раса'),('resource','Ресурс'),('attack','Тип атаки'),('year','Год выхода')]


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',str(text)).casefold().replace('ё','е') if c.isalnum())


def clean_pool(value, champions):
    if not isinstance(value,dict): return {r:[] for r in core.ROLES}
    return {r:list(dict.fromkeys(c for c in value.get(r,[]) if isinstance(c,str) and c in champions))
            if isinstance(value.get(r,[]),list) else [] for r in core.ROLES}


def saved_pool(settings, profile, defaults, champions):
    saved=settings.get('champion_pools',{})
    value=saved[profile] if isinstance(saved,dict) and profile in saved else defaults
    return clean_pool(value,champions)


def load_catalog(data, path=None):
    path=path or Path(__file__).with_name('champion_catalog.json')
    try: metadata=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError): metadata={}
    if not isinstance(metadata,dict): metadata={}
    lore=metadata.get('champions',{})
    if not isinstance(lore,dict): lore={}
    rows=[]
    for champion in set(data.ids.values()):
        m=lore.get(champion,{})
        if not isinstance(m,dict): m={}
        roles=[ROLE_MAP[r] for r in m.get('positions',[]) if r in ROLE_MAP]
        if not roles:
            role=data.role_of_champ(champion)
            if role: roles=[role]
        rows.append({'id':champion,'name':data.cn(champion),'roles':list(dict.fromkeys(roles)),
                     'classes':(data.d.get('champs',{}).get(champion) or {}).get('tags',[]),
                     'gender':m.get('gender'),'regions':m.get('regions',[]),'species':m.get('species',[]),
                     'resource':m.get('resource'),'attack':m.get('attackType',[]),'year':m.get('releaseYear') if type(m.get('releaseYear')) is int and m['releaseYear']>=2009 else None})
    return rows,metadata.get('source',{})


def values(row,field):
    raw=row.get(field)
    return [str(x) for x in (raw if isinstance(raw,list) else [raw]) if x not in (None,'','Unknown')]


def options(rows,field):
    return sorted({v for row in rows for v in values(row,field)},key=lambda x:LABELS.get(x,x))


def filtered(rows, pool, role, query='', mode='all', filters=None, sort='name'):
    q=norm(query)
    selected=set(pool.get(role,[]))
    result=[]
    for row in rows:
        if q and q not in norm(row['name']) and q not in norm(row['id']): continue
        if mode=='role' and role not in row['roles']: continue
        if mode=='pool' and row['id'] not in selected: continue
        if any(v and v not in values(row,k) and not(v=='?' and not values(row,k)) for k,v in (filters or {}).items()):continue
        result.append(row)
    key=lambda row:(norm(row['name']),row['id'])
    if sort=='selected':key=lambda row:(row['id'] not in selected,norm(row['name']),row['id'])
    elif sort=='year':key=lambda row:(-(row.get('year') or 0),norm(row['name']),row['id'])
    return sorted(result,key=key)
