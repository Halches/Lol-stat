"""Player-card comments: stable IDs for review, factual wording and three colour groups."""
import re

# All comment types produced by summarize_history/history_patterns, without duplicate aliases.
CATALOG = [
    ('G1','good','Серия побед: N'),
    ('G2','good','Редко умирает (X за игру)'),
    ('G3','good','KDA X'),
    ('G4','good','Хорошо фармит (X CS/мин)'),
    ('G5','good','Много урона (X/мин)'),
    ('G6','good','Хороший обзор (X/мин)'),
    ('G7','good','Мейнер · N/M недавних игр'),
    ('G8','good','Высокое участие в убийствах · X%'),
    ('G9','good','Редко умирает до 14 минуты · X за игру'),
    ('G10','good','Топ-1000 · №N в мире · Lolalytics'),
    ('N4','neutral','Непривычная роль · N/M недавних игр'),
    ('R9','bad','Низкое участие в убийствах · X%'),
    ('R10','bad','Часто умирает до 14 минуты · X за игру'),
    ('N1','neutral','Играет почти только на этом чемпионе'),
    ('N2','neutral','Не играл на этом чемпионе недавно'),
    ('N3','neutral','История игрока недоступна'),
    ('R1','bad','Серия поражений: N'),
    ('R2','bad','N из 5 последних матчей проиграны'),
    ('R3','bad','Смертей всё больше: X за игру против Y раньше'),
    ('R4','bad','Часто умирает (X за игру)'),
    ('R5','bad','KDA X'),
    ('R6','bad','Мало фарма (X CS/мин)'),
    ('R7','bad','Мало урона (X/мин)'),
    ('R8','bad','Мало обзора (X/мин)'),
]


TEMPLATES = {key:text for key,_,text in CATALOG}


def palette(dark):
    """Comment colours are green/yellow/red in every theme: (background, foreground)."""
    return ({'good':('#11362f','#78d8b8'), 'neutral':('#363024','#e6c26b'), 'bad':('#39252e','#f49394')}
            if dark else {'good':('#d8edec','#0b8f70'), 'neutral':('#f4e8d9','#8a6a2b'), 'bad':('#f4e1e0','#b8433b')})

def comments(history):
    if not history: return [('N3','История игрока недоступна','neutral')]
    result, seen = [], set()
    def add(key, text, tone):
        if key not in seen:
            seen.add(key); result.append((key, text[:1].upper()+text[1:], tone))
    for key, text, tone in history.get('extra_comments') or []:
        if key in TEMPLATES: add(key,text,tone)
    if not history.get('n'): add('N3',TEMPLATES['N3'],'neutral')
    streak = history.get('streak',0)
    if streak >= 3: add('G1',f'Серия побед: {streak}','good')
    elif streak <= -3: add('R1',f'Серия поражений: {-streak}','bad')
    for text in history.get('good') or []:
        if text.startswith('в форме,'):
            if streak < 3:
                count = re.search(r'\d+',text)
                if count: add('G1','Серия побед: '+count[0],'good')
            continue
        prefixes = [('редко умирает','G2'),('KDA','G3'),('хорошо фармит','G4'),('много урона','G5'),('сильный обзор','G6')]
        key = next((key for prefix,key in prefixes if text.startswith(prefix)), 'good_other')
        add(key,text.replace('сильный обзор','хороший обзор'),'good')
    tags = history.get('tags') or []
    if 'G7' not in seen and any('почти только' in text for text in tags): add('N1',TEMPLATES['N1'],'neutral')
    if any('не играл' in text for text in tags): add('N2',TEMPLATES['N2'],'neutral')
    for text in history.get('bad') or []:
        prefixes = [('часто умирает','R4'),('KDA','R5'),('слабый фарм','R6'),('мало урона','R7'),('мало обзора','R8')]
        key = next((key for prefix,key in prefixes if text.startswith(prefix)), 'bad_other')
        add(key,text.replace('слабый фарм','мало фарма'),'bad')
    for text in history.get('tilt') or []:
        if re.match(r'\d+ поражени\w* подряд',text):
            if streak > -3: add('R1','Серия поражений: '+re.match(r'\d+',text)[0],'bad')
        elif 'из 5 последних' in text: add('R2',text.replace('последних проиграны','последних матчей проиграны'),'bad')
        else: add('R3',text,'bad')
    return grouped(result)


def grouped(rows):
    order = {'good':0, 'neutral':1, 'bad':2}
    return sorted(rows, key=lambda row: order.get(row[2],3))


def preview(history, limit=4):
    """Keep each available colour visible; the history drawer contains the complete list."""
    all_comments = sorted(comments(history), key=lambda row: {'G10':0,'G7':1}.get(row[0],2))
    groups = [[row for row in all_comments if row[2] == tone] for tone in ('good','bad','neutral')]
    result = []
    while any(groups) and len(result) < limit:
        for group in groups:
            if group and len(result) < limit: result.append(group.pop(0))
    return grouped(result)
