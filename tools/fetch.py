"""Download matches and keep eligible IDs pending until analysis includes them."""
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from players import NAMES, puuids

MATCH_API = 'https://europe.api.riotgames.com/lol/match/v5/matches/'
QUEUES = {400, 420, 430, 440, 480, 490}
SEEN = Path('seen.json')
PENDING = Path('pending_matches.json')
ARCHIVE = Path('games.json')
DATA = Path('data')


def save(path, value):
    temp = tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False)
    try:
        with temp:
            json.dump(value, temp)
        os.replace(temp.name, path)
    finally:
        Path(temp.name).unlink(missing_ok=True)


def get(url, key):
    for attempt in range(6):
        try:
            request = urllib.request.Request(url, headers={'X-Riot-Token': key, 'User-Agent': 'curl/8'})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            time.sleep(1.25)
            return payload
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(int(error.headers.get('Retry-After') or 10) + 1)


def listed_ids(accounts, key, start_time, incremental, known):
    ids = set()
    count = 20 if incremental else 100
    for who, puuid in accounts.items():
        player_ids = set()
        for queue_type in ('ranked', 'normal'):
            start = 0
            while True:
                url = (f'{MATCH_API}by-puuid/{puuid}/ids?type={queue_type}'
                       f'&startTime={start_time}&start={start}&count={count}')
                page = get(url, key)
                if not isinstance(page, list):
                    raise ValueError(f'Riot не вернул список матчей для {NAMES[who]}')
                player_ids.update(page)
                if len(page) < count or (incremental and known.intersection(page)):
                    break
                start += count
        print(NAMES[who], len(player_ids), file=sys.stderr)
        ids.update(player_ids)
    return ids


def match_payload(mid, key, timeline=False):
    path = DATA / (mid + ('_tl.json' if timeline else '.json'))
    def valid(value):
        if not isinstance(value, dict) or (value.get('metadata') or {}).get('matchId') != mid:
            return False
        info = value.get('info')
        if not isinstance(info, dict):
            return False
        if timeline:
            return isinstance(info.get('frames'), list) and bool(info['frames'])
        return type(info.get('queueId')) is int and type(info.get('gameDuration')) is int

    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if valid(cached):
                return cached
        except ValueError:
            pass
    payload = get(MATCH_API + mid + ('/timeline' if timeline else ''), key)
    if not valid(payload):
        return None
    save(path, payload)
    return payload


def run(acknowledge=False):
    archived = {g['id'] for g in json.loads(ARCHIVE.read_text())} if ARCHIVE.exists() else set()
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    # Older versions also marked missing timelines as seen. Recheck legacy IDs
    # absent from the archive once, including any intentionally excluded queues.
    pending = set(json.loads(PENDING.read_text())) if PENDING.exists() else seen - archived
    seen.update(archived)
    pending.difference_update(archived)
    seen.difference_update(pending)
    if acknowledge:
        save(SEEN, sorted(seen))
        save(PENDING, sorted(pending))
        return

    key = os.environ.get('RIOT_API_KEY', '').strip().strip('"')
    incremental = os.environ.get('INCREMENTAL') == '1'
    ids = listed_ids(puuids(key), key, int(os.environ.get('SEASON_START', '1767830400')),
                     incremental, seen | pending)
    pending.update(ids - seen if incremental else ids)
    save(PENDING, sorted(pending))
    DATA.mkdir(exist_ok=True)
    ready = 0
    for mid in sorted(pending):
        match = match_payload(mid, key)
        if match is None:
            continue
        info = match['info']
        if info['queueId'] not in QUEUES or info['gameDuration'] < 600:
            pending.remove(mid)
            seen.add(mid)
        elif match_payload(mid, key, timeline=True) is not None:
            ready += 1

    save(SEEN, sorted(seen))
    save(PENDING, sorted(pending))
    print(f'Готово к анализу: {ready}. Ожидают данных: {len(pending) - ready}', file=sys.stderr)
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a') as stream:
            print(f'new={ready}', file=stream)


if __name__ == '__main__':
    run(acknowledge=sys.argv[1:] == ['--acknowledge'])
