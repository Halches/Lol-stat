"""Bounded background enrichment; no network access from card rendering."""
import copy
import queue
import threading
import time
import urllib.request
import champion_rank
import champion_rank_graphs
import player_traits


class Evidence:
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs = queue.Queue(maxsize=32)
        self.pending, self.done, self.metrics, self.boards = set(), {}, {}, {}
        self.started = False

    def _submit(self, key, job, ttl=300):
        with self.lock:
            if key in self.pending or time.time() - self.done.get(key,0) < ttl: return
            if not self.started:
                self.started = True
                for _ in range(2): threading.Thread(target=self._worker, daemon=True).start()
            try: self.jobs.put_nowait((key,job))
            except queue.Full: return
            self.pending.add(key)

    def _worker(self):
        while True:
            key, job = self.jobs.get()
            try: job()
            except Exception: pass  # Unavailable evidence produces no badge; retry after cooldown.
            finally:
                with self.lock:
                    self.pending.discard(key); self.done[key] = time.time()
                    while len(self.done) > 2000: self.done.pop(next(iter(self.done)))
                self.jobs.task_done()

    def request(self, client, puuid, history, champion, champion_id, role, riot):
        if not puuid: return
        # A separate LCU handle prevents a failed enrichment request resetting the poller's port.
        client = copy.copy(client)
        games = [h for h in player_traits.ranked_games(history) if player_traits.role_of(h) == role and h.get('gid')][:5]
        ids = tuple(h['gid'] for h in games)
        if len(ids) == 5:
            def details():
                result = {}
                for gid in ids:
                    with self.lock: cached = self.metrics.get((puuid,gid))
                    if cached and 'kp' in cached and 'd14' in cached: continue
                    game = client.game(gid)
                    if not game or str(game.get('gameId')) != str(gid): continue
                    values = player_traits.detail_metrics(game, client.timeline(gid), puuid)
                    if values: result[(puuid,gid)] = values
                with self.lock:
                    self.metrics.update(result)
                    # Session-only cache, bounded even if the client stays open for days.
                    while len(self.metrics) > 2000: self.metrics.pop(next(iter(self.metrics)))
            self._submit(('metrics',puuid,role,ids), details)
        if champion and champion_id and champion_rank.identity(riot):
            def leaderboard():
                def publish(board):
                    with self.lock:self.boards[champion]=board
                board=champion_rank_graphs.fetch(champion_id,champion,publish)
                if board:return
                req = urllib.request.Request(champion_rank.url(champion), headers={'User-Agent':'LoLHelper/1.0'})
                with urllib.request.urlopen(req, timeout=8) as response:
                    html = response.read(4_000_001)
                if len(html)>4_000_000: return
                board = champion_rank.parse(html.decode('utf-8'), champion_id, champion)
                if board:
                    with self.lock: self.boards[champion] = board
            with self.lock: board = self.boards.get(champion)
            if not board or time.time() - board['fetched_at'] > (300 if board.get('partial') else 21600):
                self._submit(('board',champion), leaderboard)

    def snapshot(self, puuid, champion):
        with self.lock:
            metrics = {gid:dict(v) for (pu,gid),v in self.metrics.items() if pu == puuid}
            return metrics, self.boards.get(champion)
