"""Last confirmed public profile; never client credentials or authentication."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import time

FIELDS = {'profile','ranks','weekly','matches','historyAvailable','historyHasMore','historyInterrupted',
          '_accountKey','trend','range','assetVersion','month'}


class ProfileMemory:
    def __init__(self, path=None):
        local = Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/state')
        self.path = Path(path) if path is not None else local/'LoLHelper/last-profile.json'

    def load(self):
        try:
            if self.path.stat().st_size > 8_000_000:
                return None
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            data = saved['data']
            if (saved.get('version') != 1 or not isinstance(data,dict)
                    or not isinstance(data.get('_accountKey'),str) or not data['_accountKey']
                    or not isinstance(data.get('profile'),dict) or not data['profile'].get('riot')
                    or not isinstance(data.get('matches'),list)
                    or not all(isinstance(row,dict) and isinstance(row.get('id'),str)
                               and type(row.get('playedAt')) is int for row in data['matches'])
                    or not all(isinstance(data.get(k),dict) for k in ('ranks','weekly','trend','month'))):
                return None
            data = {key:value for key,value in data.items() if key in FIELDS}
            data['month']['days'] = {int(k):v for k,v in data['month'].get('days',{}).items()}
            return dict(data, savedAt=saved['savedAt'])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def save(self, data):
        pending = None
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with NamedTemporaryFile('w',encoding='utf-8',dir=self.path.parent,delete=False) as file:
                pending = Path(file.name)
                json.dump({'version':1,'savedAt':int(time()),
                           'data':{key:value for key,value in data.items() if key in FIELDS}},file,ensure_ascii=False)
            pending.replace(self.path)
        except (OSError, ValueError, TypeError):
            if pending:
                pending.unlink(missing_ok=True)
