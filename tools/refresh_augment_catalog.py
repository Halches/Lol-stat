"""Rebuild the offline League card catalog. Supply a CommunityDragon patch, e.g. 16.23."""
import argparse
from datetime import date
import json
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parents[1] / 'app' / 'augment_data'
MAYHEM = 'https://arammayhem.com/data/v1/latest/'


def get(url):
    with urlopen(Request(url, headers={'User-Agent': 'LoLHelper/catalog'}), timeout=30) as response:
        return json.load(response)


def build(ru, en, arena, picks, combos):
    english = {row['id']: row for row in en}
    arena_keys = {row['apiName'] for row in arena['augments']}
    rates_by_name = {row['name']['en'].casefold(): row for row in picks['rows'] if not row['retiredPatch']}
    cards, rates, pairings = [], {}, {}
    for row in ru:
        if row['rarity'] == 'kEventChoice':
            continue
        local = english[row['id']]
        if row['augmentNameId'] != local['augmentNameId']:
            raise ValueError('Несогласованные английский и русский каталоги')
        key, name = row['augmentNameId'], local['nameTRA']
        if not name or not row['nameTRA']:
            continue
        cards.append(dict(key=key, ru=row['nameTRA'], en=name,
                          tags=[t.removeprefix('k') for t in row['augmentDisplayTags']],
                          arena=key in arena_keys or row['id'] < 1000))
        record = rates_by_name.get(name.casefold())
        if record and record['rarity'].casefold() == row['rarity'][1:].casefold():
            rate = record['pickRate']
            if type(rate) in (float, int) and 0 <= rate <= 100:
                rates[name] = rate
    available = {row['en'].casefold():row['en'] for row in cards}
    for row in combos['rows']:
        # A multi-augment combo is conditional on all its components being present.
        if len(row['augmentIds']) != 1 or len(row['augmentNames']) != 1:
            continue
        tags = set(row['types'])
        name = available.get(row['augmentNames'][0]['en'].casefold())
        if not name or 'bug' in tags:
            continue
        rating = 'trap' if 'trap' in tags else 'strong' if {'strong', 'god'} & tags else None
        if rating:
            pairings.setdefault(row['championId'], {}).setdefault(name, set()).add(rating)
    curated = {champ: {name: next(iter(values)) for name, values in names.items() if len(values) == 1}
               for champ, names in pairings.items()}
    if not cards or not rates or not curated:
        raise ValueError('Пустой набор данных аугментаций')
    return cards, dict(source=picks['source'], license=picks['licenseUrl'], patch=picks['meta']['patch'],
                       date=picks['meta']['statsDate'], rates=rates, champion_pairs=curated)


def save(patch, cards, mayhem):
    header = {'source': 'Riot game data via CommunityDragon', 'patch': patch, 'retrieved': date.today().isoformat()}
    catalog = json.dumps(header, ensure_ascii=False, indent=2)[:-2] + ',\n  "cards": [\n'
    catalog += ',\n'.join('    ' + json.dumps(card, ensure_ascii=False) for card in cards) + '\n  ]\n}\n'
    for name, value in [('catalog', catalog), ('mayhem_picks', json.dumps(mayhem, ensure_ascii=False, indent=2)+'\n')]:
        tmp = OUT / (name + '.tmp')
        tmp.write_text(value, encoding='utf-8')
        tmp.replace(OUT / (name + '.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch')
    patch = parser.parse_args().patch
    base = f'https://raw.communitydragon.org/{patch}/'
    client = base + 'plugins/rcp-be-lol-game-data/global/'
    save(patch, *build(get(client+'ru_ru/v1/cherry-augments.json'), get(client+'default/v1/cherry-augments.json'),
                       get(base+'cdragon/arena/en_us.json'), get(MAYHEM+'augments.json'), get(MAYHEM+'combos.json')))
