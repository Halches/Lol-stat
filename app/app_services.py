"""Сервисы приложения, перенесённые из ui.App; интерфейс и планировщик предоставляет Qt.
Расчёты, ограничения скрытых профилей и валидация импорта сохранены.
"""
import json,os,platform,queue,threading,time,urllib.request
from collections import Counter
import core,lcu,tab_detect,player_comments,player_traits,player_evidence,champion_rank,champion_pool,profile_ranks,performance_model
from app_config import *

def show_postgame(app,res,result): app.show_postgame(res,result)

AFTER_GAME_PHASES = {
    'WaitingForStats', 'PreEndOfGame', 'EndOfGame', 'Lobby',
    'Matchmaking', 'ReadyCheck', 'ChampSelect', 'None',
}

class ApplicationServices:
    def layout(self):
        return self.s['layout'].setdefault(screens()[0], {})

    def sync_voice(self):
        v, s = self.voice, self.s
        v.voice, v.volume, v.rate, v.master, v.beep_volume = s['voice'], s['volume'], s['rate'], s['master'], s['beep_volume']
        v.sound = s['sound']
        v.warm()

    def set_who(self, who):
        if who not in self.data.d['players']: who = None
        self.player = core.Player(self.data, who) if who else None
        self.who = who
        if self.player: self.player.pool = self.current_pool()
        view = getattr(self, 'pool_view', None)
        if view: view.refresh()
        history=getattr(self,'history_view',None)
        if history: history.profile_changed()
        champion=getattr(self,'champion_view',None)
        if champion: champion.refresh()
        self.engine = None

    def current_pool(self):
        defaults = self.data.d.get('pools',{}).get(self.who or '',{})
        return champion_pool.saved_pool(self.s,self.who or 'local',defaults,set(self.data.ids.values()))

    def toggle_pool(self, champion, role):
        if champion not in self.data.ids.values() or role not in core.ROLES: raise ValueError('Неизвестный чемпион или роль')
        pool = self.current_pool()
        if champion in pool[role]: pool[role].remove(champion)
        else: pool[role].append(champion)
        old = self.s.get('champion_pools',{})
        self.s['champion_pools'] = {**(old if isinstance(old,dict) else {}), self.who or 'local':pool}
        try: self.s.save()
        except Exception:
            self.s['champion_pools'] = old
            raise
        if self.player: self.player.pool = pool
        self.draft_sig = None
        if self.dash: self.dash.draft_sig = None

    def new_engine(self):
        self.engine = core.Engine(self.data, self.player, enabled=self.hint_flags(''))

    def cached_build(self, champ, role):
        """Сборка по Европе из памяти или с диска (любой давности): в игре важнее быстро, чем свежо."""
        b = self.lola.get((champ, role))
        if b: return b
        try:
            with open(os.path.join(self.home, 'lola', f'full_{champ}_{role}.json'), encoding='utf-8') as source:
                return core.restore_lola_styles(json.load(source))
        except Exception: return None

    def prep_engine(self, g):
        """В начале игры: порядок умений, ситуативные предметы и темп Изумруда+ для подсказок."""
        self.engine.prepped = True
        chosen=getattr(self,'_chosen_draft_build',None)
        context=self.s.get('draft_build_context','general')
        b=chosen[3] if chosen and chosen[:3]==(g.me['c'],g.role,context) else None
        if context == 'matchup' and b and (b.get('matchup') or {}).get('opponent') != (g.opp or {}).get('c'):
            b = None
        if not b and context == 'general':b=self.cached_build(g.me['c'],g.role)
        if not b and g.role and context == 'general': self.root.after(0, lambda: self.lola_fetch('build', g.me['c'], g.role)); self.engine.prepped = False
        v = self.draft_build_variant(b, g.role) or {}
        self.engine.skills, self.engine.skill_prio = v.get('skills', ''), v.get('skill_prio', '')
        self.engine.situ = (b or {}).get('situ') or []
        lo = self.data.lola.get(f"{g.me['c']}|{g.role}")
        self.engine.bench={'csm':lo['csm']} if lo and type(lo.get('csm')) in (int,float) and lo['csm']<float('inf') and lo['csm']>=0 else None

    def hint_mode(self, hid, role=None):
        """Режим подсказки: общие — один на все роли, ролевые — свой у каждой роли."""
        if hid not in core.HINT_ROLES: return self.s['hints'].get(hid, 'off')
        role = role or self.s['hint_preset']
        if role not in core.HINT_ROLES[hid]: return 'off'
        dflt = next(h[3] for h in core.HINTS if h[0] == hid)
        return self.s['hints_role'].get(role, {}).get(hid, dflt)

    def hint_flags(self, role):
        return {h: self.hint_mode(h, role) != 'off' for h in core.HINT_IDS}

    SR_ONLY = ('lane', 'timers', 'perf', 'item')   # виджеты только для Ущелья: в Арене их нет

    def apply_visibility(self):
        arena = bool(self.last_game and self.last_game.arena)
        no_player=bool(self.last_game and not self.last_game.me)
        non_sr=bool(self.last_game and not getattr(self.last_game,'sr',not arena))
        demo=bool(getattr(self,'demo_on',False) and not self.hidden)
        for k,w in self.ov.items():
            enabled=self.s['widgets'].get(k)
            if demo:
                if enabled and w.unlocked:w.deiconify()
                else:w.withdraw()
                continue
            if k=='hints':
                if self.hidden or no_player or not enabled:w.withdraw()
                continue
            if self.hidden or no_player or not enabled or not self.last_game or (non_sr and k in self.SR_ONLY) or (k=='arena' and not arena):w.withdraw()
            else:w.deiconify()
        if self.hidden or no_player or not self.s.get('scoreboard') or (not demo and (not self.last_game or arena)):
            for w in self.tab.values():w.withdraw()

    def arena_tick(self, g):
        """Арена: напоминание о покупке, когда скопилось 1000+ золота (раз в минуту, режим как у подсказки «Следующий предмет»)."""
        mode = self.hint_mode('next_item')
        if mode == 'off' or g.gold < 1000 or time.time() - getattr(self, '_arena_buy', 0) < 60: return
        self._arena_buy = time.time()
        self.ov['hints'].push(f'Есть {int(g.gold)} золота: купи предмет до начала раунда'); self.ov['hints'].show()
        if mode == 'beep': self.voice.beep()
        elif mode == 'voice': self.voice.say('Есть золото, купи предмет')

    def toast(self, text, color='gold'):
        self.ov['hints'].push(text, color); self.ov['hints'].show()

    def poll(self):
        last_lcu, last_me, last_scout, in_game = 0, 0, 0, False
        game_ended = live_missing = False
        while not self.stopping.is_set():
            try:
                raw = lcu.live_data()
                now = time.time()
                if raw and (raw.get('gameData') or {}).get('gameTime', 0) > 0:
                    if not in_game:
                        self.ranks, self.hists, self.scout = {}, {}, {}
                        last_scout, game_ended = 0, False
                        match_id, queue_id, next_id_check = None, None, 0
                    in_game = True
                    live_missing = False
                    g = core.Game(raw, self.data)
                    if (match_id is None or queue_id is None) and now >= next_id_check:
                        gid, qid = self.client.live_match_context()
                        if gid and gid != match_id:
                            match_id, queue_id = gid, qid
                        elif qid is not None:
                            queue_id = qid
                        next_id_check = now + 10
                    g.match_id = match_id
                    g.queue_id = queue_id
                    if self.engine is None: self.new_engine()
                    if g.me and not getattr(self.engine, 'prepped', False): self.prep_engine(g)
                    self.engine.enabled = self.hint_flags(g.role)
                    hints = [] if g.arena else self.engine.tick(g)   # подсказки Ущелья в Арене не имеют смысла
                    end_event = next((e for e in g.events if e.get('EventName') == 'GameEnd'), None)
                    game_ended = game_ended or end_event is not None
                    res = end_event.get('Result') if end_event else None
                    if now - last_scout > 90:
                        last_scout = now
                        self.scout = self.fetch_scout(g)
                    if len(self.ranks) < len(g.players): self.fetch_people(g)
                    elif g.ejg and not g.arena and self.engine.jg_plan is None and g.t < 240: self.scout_jungler(g)
                    self.q.put(('game', g, hints, res))
                elif in_game:
                    if game_ended or self.client.phase() in AFTER_GAME_PHASES:
                        in_game = False
                        self.q.put(('end', None, None, None))
                    elif not live_missing:
                        live_missing = True
                        self.q.put(('game_stale', None, None, None))
                else:
                    if now - last_me > 60:
                        last_me = now
                        me = self.client.me()
                        if me:
                            me['ranks'] = self.client.ranked_overview()
                            me['rank'] = profile_ranks.legacy_solo(me['ranks'])
                            self.q.put(('me', me, None, None))
                        elif self.account:
                            self.q.put(('me', None, None, None))
                    if now - last_lcu > 2:
                        last_lcu = now
                        ph = self.client.phase()
                        if ph == 'ChampSelect':
                            sess = self.client.champ_select()
                            if sess:
                                observed_at = time.monotonic()
                                cs = core.parse_champ_select(sess, self.data)
                                cs['observed_at'] = observed_at
                                cs['allies'] = self.draft_allies(sess)
                                queue_id, map_id = self.client.queue_and_map()
                                cs['arena'] = queue_id == 1700
                                cs['map_id'] = map_id or cs.get('map_id')
                                self.q.put(('draft', cs, None, None))
                        elif ph is not None:
                            if self.draft is not None: self.q.put(('draft', None, None, None))
                            if ph in ('GameStart', 'InProgress'): self.load_scout()
            except Exception as e:
                log_error('опрос клиента', e)
                self.q.put(('error', str(e), None, None))
            self.stopping.wait(1)

    def scout_jungler(self, g):
        """Лесник врагов: как он начинал 2–3 последние игры в лесу (для окна ганка и подсказки)."""
        pu = self.pus.get(g.ejg['riot'])
        if not pu or pu not in self.hraw: self.engine.jg_plan = {}; return
        try: self.engine.jg_plan = self.jg_plan_for(pu) or {}
        except Exception as e: log_error('разведка лесника', e); self.engine.jg_plan = {}

    def jg_plan_for(self, pu):
        if pu in self.jg_cache: return self.jg_cache[pu]
        games = [h for h in (self.hraw.get(pu) or []) if h.get('lane') == 'JUNGLE' and h.get('gid')][:3]
        plan = core.jungle_plan([core.jungle_game(self.client.timeline(h['gid']), self.client.game(h['gid']), pu) for h in games])
        self.jg_cache[pu] = plan
        return plan

    def cid(self, key):
        return next((i for i, c in self.data.ids.items() if c == key), None)

    def player_history(self, pu, champion_id, pos, riot=''):
        """Вызывается фоновым опросом: готовые данные сразу, подробности догружаются."""
        if not pu: return None
        raw = self.hraw.get(pu)
        champion = self.data.ids.get(str(champion_id))
        self.evidence.request(self.client, pu, raw, champion, champion_id, pos, riot)
        metrics, board = self.evidence.snapshot(pu, champion)
        out = core.summarize_history(raw, champion_id, pos)
        extras = player_traits.traits(raw, champion_id, pos, metrics)
        if board and champion_rank.identity(riot):
            if time.time() - self.evidence_region_at > 300:
                self.evidence_region = self.client.region()
                self.evidence_region_at = time.time()
            rank = champion_rank.lookup(board, champion, riot, self.evidence_region)
            if rank:
                extras.insert(0, ('G10', f"Топ-1000 · №{rank['rank']} в мире · {rank['source']}", 'good'))
                if out is None: out = {'n':0,'w':0,'streak':0,'on':0,'on_w':0,'kda':0,'tags':[], 'good':[], 'bad':[], 'tilt':[]}
                out['champion_rank'] = rank
        if out is not None: out['extra_comments'] = extras
        return out

    def fetch_people(self, g):
        """Звание и история последних игр каждого из десяти через клиент (как в профиле). По одному за проход."""
        for p in g.players:
            if p['riot'] in self.ranks:
                pu = self.pus.get(p['riot'])
                self.hists[p['riot']] = self.player_history(pu, self.cid(p['c']), p['pos'], p['riot'])
                continue
            pu = self.pus.get(p['riot']) or self.client.puuid(p['riot'])
            if pu and pu in self.hraw: raw, self.ranks[p['riot']] = self.hraw[pu], self.rank_pu.get(pu)   # уже скачано на экране загрузки
            else:
                self.ranks[p['riot']] = self.rank_pu[pu] = self.client.rank(pu) if pu else None
                raw = self.client.history(pu) if pu else None
            if pu: self.hraw[pu], self.pus[p['riot']] = raw, pu
            self.hists[p['riot']] = self.player_history(pu, self.cid(p['c']), p['pos'], p['riot'])
            return

    def draft_allies(self, sess):
        """Союзники в драфте: чемпион (или наведённый), роль, звание и история игр."""
        out = []
        for p in sess.get('myTeam') or []:
            # Riot запрещает раскрывать игроков, которых игра скрыла: у скрытых союзников не берём ни звание, ни историю
            hidden = p.get('nameVisibilityType') == 'HIDDEN' and p.get('cellId') != sess.get('localPlayerCellId')
            pu = None if hidden else p.get('puuid')
            if pu and pu not in self.hraw:
                self.ranks[pu] = self.rank_pu[pu] = self.client.rank(pu)
                self.hraw[pu] = self.client.history(pu)
            champ_id = p.get('championId') or p.get('championPickIntent') or 0
            riot = (p['gameName']+'#'+p['tagLine']) if not hidden and p.get('gameName') and p.get('tagLine') else ''
            if not riot and pu and pu == (self.account or {}).get('puuid'): riot = self.account.get('riot','')
            out.append({'c': self.data.ids.get(str(champ_id)), 'pos': core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), ''),
                        'rank': self.ranks.get(pu), 'hist': self.player_history(pu, champ_id, core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), ''), riot),
                        'me': p.get('cellId') == sess.get('localPlayerCellId'), 'pu': pu})
        return out

    def load_scout(self):
        """Экран загрузки: все десять из клиента. Звание и история — по одному игроку за проход, как в игре."""
        ps = self.client.loading()
        if not ps: return
        mine = (self.account or {}).get('puuid')
        my_team = next((p['team'] for p in ps if p['pu'] and p['pu'] == mine), 100)
        todo = next((p['pu'] for p in ps if p['pu'] and p['pu'] not in self.hraw), None)
        if todo:
            self.rank_pu[todo] = self.client.rank(todo)
            self.hraw[todo] = self.client.history(todo)
        else:   # все истории есть: заранее смотрим, как начинает лесник врагов
            jg = next((p['pu'] for p in ps if p['pu'] and p['team'] != my_team and p['pos'] == 'jungle'), None)
            if jg and jg not in self.jg_cache:
                try: self.jg_plan_for(jg)
                except Exception as e: log_error('разведка лесника', e); self.jg_cache[jg] = None
        out = []
        for p in ps:
            pu, pos = p['pu'], core.LCU_ROLE.get(p['pos'], '')
            out.append({'c': self.data.ids.get(str(p['champ'])), 'pos': pos, 'col': 0 if p['team'] == my_team else 1, 'pu': pu,
                        'me': bool(pu) and pu == mine, 'name': p['name'], 'ok': not pu or pu in self.hraw, 'rank': self.rank_pu.get(pu),
                        'hist': self.player_history(pu, p['champ'], pos, p['name'])})
        self.q.put(('load', out, None, None))

    def on_loading(self, ps):
        if self.last_game is not None: return
        dash = self.dashboard_for_events()
        if dash:
            try: dash.show_loading(ps)
            except Exception as e: log_error('второе окно: загрузка', e)
        self.status.configure(text='Экран загрузки')

    def dashboard_for_events(self, *, new_draft=False):
        if not self.s['dashboard']:
            return self.dash if self.dash and self.dash.opened_manually and not self.dash._manual_hidden else None
        if not self.dash or (new_draft and self.dash._manual_hidden):
            self.open_dash(manual=False)
        return self.dash

    def fetch_scout(self, g):
        try:
            with urllib.request.urlopen(RAW + 'data/live.json', timeout=8) as r:
                live = json.load(r)
        except Exception:
            return self.scout
        mine = Counter(p['c'] for p in g.players)
        for gm in live.get('games', []):
            if Counter(p['c'] for p in gm['players']) != mine:
                continue
            matched = {}
            for player in g.players:
                name = player['riot'].partition('#')[0].casefold()
                team = {'ORDER': 100, 'CHAOS': 200}.get(player['team'])
                candidates = [
                    p for p in gm['players'] if p['c'] == player['c']
                    and (not p.get('n') or p['n'].casefold() == name)
                    and (team is None or p.get('team', team) == team)
                ]
                if len(candidates) == 1:
                    matched[player['riot']] = scout_text(candidates[0])
            if matched:
                return matched
        return self.scout

    def drain(self):
        deadline = time.perf_counter() + .008
        delay = 300
        try:
            for _ in range(32):
                kind, a, b, c = self.q.get_nowait()
                try:
                    if kind == 'game': self.on_game(a, b, c)
                    elif kind == 'game_stale': self.on_game_stale()
                    elif kind == 'end': self.on_end()
                    elif kind == 'me': self.on_me(a)
                    elif kind == 'draft': self.on_draft(a)
                    elif kind == 'load': self.on_loading(a)
                    elif kind == 'error': self.status.configure(text=f'Ошибка: {a}')
                except Exception as error:
                    log_error('событие интерфейса ' + str(kind), error)
                if time.perf_counter() >= deadline:
                    delay = 1
                    break
            else:
                delay = 1
        except queue.Empty:
            pass
        finally:
            try: self.root.after(delay, self.drain)
            except (RuntimeError, RuntimeError): pass

    def on_me(self, me):
        self.account, self.my_rank = me, (me or {}).get('rank')
        history=getattr(self,'history_view',None)
        if history: history.account_changed(me)
        if not me:
            self.panel_sync(); return
        who = self.data.who_by_riot(me['riot'])
        if who and who != self.who:
            self.s['who'] = who; self.s.save(); self.set_who(who)
        self.panel_sync()

    def on_game(self, g, hints, result):
        first = self.last_game is None
        self._arena_result_id = None
        self.last_game, self.result = g, result or self.result
        self.live_stale = False
        if self.draft is not None:
            self.on_draft(None)
        self.apply_visibility()
        if not g.me:
            self.status.configure(text='Ожидаю данные твоего игрока из клиента')
            return
        dash = self.dashboard_for_events()
        if first:
            if not self.account:
                who = self.data.who_by_riot(g.my_riot)
                if who and who != self.who: self.set_who(who); self.new_engine()
            self.apply_visibility()
            if dash: dash.reset()
        for h in hints:
            mode = self.hint_mode(h.id, g.role)
            if mode == 'off': continue
            self.apply_text(h)
            self.ov['hints'].push(h.text)
            if dash: dash.add_log(g.t, h.text)
            if mode == 'beep': self.voice.beep()
            elif mode == 'voice': self.voice.say(h.say)
        if hints: self.ov['hints'].show()
        if g.arena: self.arena_tick(g)
        for k in ('perf', 'lane', 'item', 'timers', 'arena', 'inventory'):
            if not self.s['widgets'].get(k) or (not getattr(g,'sr',not g.arena) and k in self.SR_ONLY) or (k == 'arena' and not g.arena): continue
            try: self.ov[k].show(g)
            except Exception as e: log_error(f'виджет {k}', e)
        if dash:
            try: dash.show(g, self.scout, self.ranks, self.hists)
            except Exception as e: log_error('второе окно: игра', e)
        self.status.configure(text=f'Игра: {core.mmss(g.t)} · {self.data.cn(g.me["c"]) if g.me else ""}')

    def on_game_stale(self):
        if not self.last_game:
            return
        self.live_stale = True
        text = 'Связь с игрой потеряна · последние данные в ' + core.mmss(self.last_game.t)
        self.status.configure(text=text)
        if self.dash:
            self.dash.mark_game_stale()

    def arena_games(self):
        return (self.data.d.get('arena') or {}).get(self.who or '', [])

    def arena_post(self, gid, puuid, attempt=0):
        def relevant():
            return (not self.stopping.is_set() and not self.last_game and not self.draft
                    and (self.account or {}).get('puuid') == puuid
                    and self._arena_result_id == gid)

        if not relevant():
            return
        def work():
            game = self.client.game(gid)
            if not game or game.get('gameId') != gid or game.get('queueId') != 1700:
                return None
            result = core.arena_result(game, puuid)
            return result if result and result.get('place') else None
        def done(result, error):
            if not relevant():
                return
            if result:
                self.show_arena_post(result)
            elif attempt < 6:
                self.root.after(20000, lambda: self.arena_post(gid, puuid, attempt + 1))
        self.background(work, done)

    def on_end(self):
        g = self.last_game
        gid = self._arena_result_id = getattr(g, 'match_id', None)
        if g and g.arena and gid and self.s['postgame'] and self.hint_mode('postgame') != 'off':
            puuid = (self.account or {}).get('puuid')
            if puuid:
                self.root.after(20000, lambda: self.arena_post(gid, puuid))
        if g and g.me and getattr(g,'sr',not g.arena) and self.engine and self.s['postgame'] and g.t > 300 and self.hint_mode('postgame') != 'off':
            res = core.postgame(self.engine, g, self.player)
            if res:
                res['match_id'] = getattr(g, 'match_id', None)
                show_postgame(self, res, self.result)
        self.last_game, self.result, self.engine, self.scout = None, None, None, {}
        self.live_stale = False
        self.hraw, self.rank_pu, self.jg_cache = {}, {}, {}   # к следующей игре история у всех уже другая
        if self.pending_data: self.reload_data(self.pending_data)
        self.apply_visibility()
        for w in self.tab.values(): w.withdraw()
        if self.dash: self.dash.idle()
        self.status.configure(text='Игра закончилась')
        self.root.after(30000, self.hist_refresh)   # LP и игра появляются в клиенте не сразу

    def on_draft(self, cs):
        """Драфт целиком во втором окне (дашборд): карточки, линия, импорт, кого взять и банить."""
        new_draft=self.draft is None and cs is not None
        if cs is not None and cs is not self.draft:
            observed_at = cs.get('observed_at', time.monotonic())
            self.draft_observed_at = observed_at
            left = cs.get('left')
            self.draft_deadline = observed_at + left if left is not None else None
        self.draft = cs
        if cs is None:
            self.role_override = None
            if self.dash and self.draft_sig not in (None, 'none'): self.dash.idle()
            self.draft_sig = 'none'
            self._import_generation = getattr(self, '_import_generation', 0) + 1
            self._import_pending = None
            self._auto_key = None
            self._draft_export_target = None
            self.applied_runes = None
            self.import_text = ''
            self.imported = None; return
        dash = self.dashboard_for_events(new_draft=new_draft)
        sig = json.dumps([cs['role'], self.role_override, self.s.get('draft_scope'), cs.get('locked'), cs['me'], cs['enemies'], sorted(cs['unavailable']), cs.get('arena'), cs.get('aram'), cs.get('bench'), len(self.lola), [(a['c'], bool(a['rank']), a.get('hist')) for a in cs.get('allies', [])]], default=str)
        if sig == self.draft_sig:
            if dash: dash.tick()
            self.auto_import_locked(cs)
            return
        self.draft_sig = sig
        p, d = self.player, self.data
        self.status.configure(text='Выбор чемпионов · второе окно' if dash else 'Выбор чемпионов')
        if not p:
            if dash:
                dash.clear('idle')
                dash.head.configure(text='Выбор чемпионов', fg=C['gold'])
                dash.sub.configure(text='Аккаунта нет в статистике сайта: выбери игрока на вкладке «Статус» основного окна')
            return
        if cs.get('arena'):
            if dash:
                try: dash.show_arena(cs)
                except Exception as e: log_error('второе окно: Арена', e)
            return
        role, how = self.draft_role(cs)
        export_target = self.draft_export_target(cs, role)
        if getattr(self, '_draft_export_target', None) != export_target:
            self._draft_export_target = export_target
            self.imported = None
            self.set_import_msg('')
        if role == 'ARAM':
            if dash:
                try: dash.show_aram(cs)
                except Exception as e: log_error('второе окно: ARAM', e)
            self.auto_import_locked(cs)
            return
        r = core.draft_suggest(p, role, cs['enemies'], cs['unavailable'], scope=self.s.get('draft_scope', 'pool'))
        r['role'], r['how'] = role, how
        for a in cs.get('allies') or []:
            if a.get('me') and (not a.get('pos') or a.get('auto')): a['pos'], a['auto'] = role, True
        pool = core.ban_pool(p, role)
        cnt = {m: core.lola_counters(self.lola_fetch('counter', m, role), d) for m in pool}
        bans = core.ban_suggest(p, cs['unavailable'], 3, role, {m: v for m, v in cnt.items() if v})
        if dash:
            try: dash.show_draft(cs, r, bans)
            except Exception as e: log_error('второе окно: драфт', e)
        self.auto_import_locked(cs)

    def draft_role(self, cs):
        """Линия для подсказок: выбранная вручную, назначенная клиентом или основная линия игрока."""
        if cs.get('aram'): return 'ARAM', 'ARAM'
        if self.role_override: return self.role_override, 'выбрана вручную'
        if cs['role']: return cs['role'], 'назначена клиентом'
        if cs['me'] and self.player:
            on = {r: len(self.player.on(cs['me'], r)) for r in core.ROLES}
            if max(on.values()) >= 3: return max(on, key=on.get), f'твоя линия на {self.data.cn(cs["me"])}'
        if self.player:
            cnt = {r: len(self.player.on(pos=r)) for r in core.ROLES}
            if max(cnt.values()): return max(cnt, key=cnt.get), 'твоя основная'
        return 'TOP', 'по умолчанию'

    TIERS = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']

    def next_tier(self):
        """Ранг на ступень выше твоего: (слаг lolalytics, название). Мастер и выше сравниваются с собой."""
        t = (self.my_rank or {}).get('tier')
        if not t:
            ru = tier_of((self.data.d['players'].get(self.who or '') or {}).get('rank'))
            t = next((k for k, v in TIER_RU.items() if v == ru), None)
        if t not in self.TIERS: return None, None
        i = self.TIERS.index(t)
        up = self.TIERS[i if i >= 7 else i + 1]
        return up.lower(), TIER_RU[up]

    def tier_bench(self, champ, role):
        """Подтверждённые средние ранга выше; длительность матча не угадывается."""
        slug, name = self.next_tier()
        if not slug or role not in core.ROLES: return None
        b = self.lola_fetch('tier_' + slug, champ, role)
        if not b: return None
        return {'tier':name,**performance_model.benchmark(b)}

    def draft_opponent(self, cs, role):
        roles = core.guess_enemy_roles(self.data, cs.get('enemies') or [])
        return next((champ for champ, lane in roles.items() if lane == role), None)

    def draft_export_target(self, cs, role):
        context = self.s.get('draft_build_context', 'general') if role in core.ROLES else 'general'
        opponent = self.draft_opponent(cs, role) if context == 'matchup' else None
        return cs.get('me'), role, context, opponent, self.s['rune_pick']

    def selected_draft_build(self, cs=None):
        cs = cs or self.draft
        if not cs or not cs.get('me'): return None
        role = self.draft_role(cs)[0]
        context=self.s.get('draft_build_context','general') if role in core.ROLES else 'general'
        if context=='matchup':return self.lola_matchup(cs['me'],role,self.draft_opponent(cs,role))
        if context=='offmeta' or context.startswith('player:'):
            from draft_external import selected
            return selected(context,cs['me'],role,self.offmeta_build(cs['me'],role) if context=='offmeta' else None,
                            self.player_builds(cs['me'],role) if context.startswith('player:') else None)
        return self.lola_build(cs['me'],role)

    def draft_build_variant(self, full, role):
        if not full:
            return None
        context = self.s.get('draft_build_context','general') if role in core.ROLES else 'general'
        if context == 'matchup' or 'pick' in full or 'win' in full:
            return full.get(self.s['rune_pick'])
        return full if self.s['rune_pick'] == 'pick' else None

    def set_draft_build(self, context, variant):
        if context not in ('general','matchup','offmeta') and not (context.startswith('player:') and context[7:].isdigit()):return
        if variant not in ('pick','win') or (context not in ('general','matchup') and variant!='pick'):return
        self.s['draft_build_context'] = context
        self.s['rune_pick']=variant
        if self.draft and self.draft.get('me'):
            role=self.draft_role(self.draft)[0]
            self._chosen_draft_build=(self.draft['me'],role,context,self.selected_draft_build(self.draft))
        self.set_rune_pick(variant)

    def lola_matchup(self, champion, role, opponent):
        """Public matchup page only. Cache includes both champions and the verified source context."""
        if not champion or not opponent or role not in core.ROLES: return None
        key = ('matchup', champion, role, opponent)
        cached = self.lola.get(key)
        if not self.begin_lola_request(key): return cached
        path = os.path.join(self.home, 'lola', f'matchup_v1_{champion}_{role}_{opponent}.json')
        def valid(value):
            meta = value.get('matchup') if isinstance(value, dict) else None
            if not isinstance(meta, dict):return False
            return (meta.get('champion'), meta.get('role'), meta.get('opponent'), meta.get('region')) == (champion, role, opponent, 'all')
        def job():
            import matchup_data
            value, saved = None, None
            try:
                try:
                    with open(path, encoding='utf-8') as source: saved = json.load(source)
                    saved = core.restore_lola_styles(saved) if valid(saved) else None
                except (OSError, ValueError): pass
                fetched_at = saved.get('fetched_at',0) if saved else 0
                if saved and type(fetched_at) in (int,float) and time.time()-fetched_at < 12*3600:
                    value = saved
                else:
                    def load_page(url):
                        request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
                        with urllib.request.urlopen(request, timeout=20) as response:
                            return matchup_data.parse(response.read().decode('utf-8'), champion, role, opponent, self.data)
                    url = matchup_data.url(champion, role, opponent)
                    value = load_page(url)
                    if value and not value.get('pick'):
                        try:
                            value = matchup_data.with_recent_build(value, load_page(url + '&patch=30'))
                        except (OSError, ValueError) as error:
                            log_error(f'сборка матчапа за 30 дней {champion} против {opponent}', error)
                    if value:
                        value['fetched_at'] = time.time()
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path+'.tmp', 'w', encoding='utf-8') as output: json.dump(value, output)
                        os.replace(path+'.tmp', path)
                    else: raise ValueError('Источник не подтвердил состав, роль или выборку матчапа')
            except Exception as error:
                log_error(f'сборка {champion} против {opponent}, {role}', error)
                if saved:
                    value = dict(saved, stale=True)
            def done():
                result = value or cached
                if result: self.lola[key] = result
                self.finish_lola_request(key, result, champion, role)
            try: self.root.after(0, done)
            except (RuntimeError, RuntimeError): pass
        threading.Thread(target=job, daemon=True, name='matchup-build').start()
        return cached

    def lola_build(self, champ, role):
        """Руны и сборка по Европе (lolalytics, EUW Изумруд+). Нет в памяти — грузим в фоне и перерисовываем драфт."""
        return self.lola_fetch('build', champ, role)

    def begin_lola_request(self, key):
        state = self.lola_state.get(key)
        cached = self.lola.get(key)
        retry_at = self.__dict__.setdefault('_lola_retry_at', {})
        if ((cached and not cached.get('stale')) or state == 'loading'
                or time.monotonic() < retry_at.get(key, 0)):
            return False
        self.lola_state[key] = 'loading'
        return True

    def finish_lola_request(self, key, value, champion, role):
        retry_at = self._lola_retry_at
        state = 'stale' if value and value.get('stale') else 'ok' if value else 'fail'
        self.lola_state[key] = state
        if state == 'ok':
            retry_at.pop(key, None)
        else:
            delay = 30
            deadline = retry_at[key] = time.monotonic() + delay

            def auto_retry():
                if self.lola_state.get(key) != state or retry_at.get(key) != deadline:
                    return
                retry_at.pop(key, None)
                self.refresh_lola_views(champion, role)

            self.root.after(delay * 1000 + 50, auto_retry)
        self.refresh_lola_views(champion, role)

    def refresh_lola_views(self, champion, role):
        self.redraw_draft()
        if getattr(self, 'cp_sel', None) == (champion, role):
            self.cp_show()

    def retry_lola(self, key, champion, role):
        if self.lola_state.get(key) == 'loading':
            return
        self.__dict__.setdefault('_lola_retry_at', {}).pop(key, None)
        self.refresh_lola_views(champion, role)

    def lola_fetch(self, kind, champ, role):
        """Данные lolalytics в фоне с кешем на 12 часов: kind='build' — руны и сборка, 'counter' — матчапы, 'build-team' — синергия.
        Пока грузится — None; по готовности драфт перерисуется."""
        if not champ or not role: return None
        k = (champ, role) if kind == 'build' else (kind, champ, role)
        cached = self.lola.get(k)
        if not self.begin_lola_request(k): return cached
        name = f'full_{champ}_{role}.json' if kind == 'build' else f'{kind}_{champ}_{role}.json'
        if role in ('ARAM', 'ARENA'):
            name = 'v2_' + name
        path = os.path.join(self.home, 'lola', name)

        def job():
            saved, modified = None, 0
            try:
                with open(path, encoding='utf-8') as source:
                    value = json.load(source)
                    if isinstance(value, dict) and value:
                        modified = os.fstat(source.fileno()).st_mtime
                        saved = core.restore_lola_styles(value) if kind == 'build' else value
            except (OSError, ValueError):
                pass
            b = saved if saved and time.time() - modified < 12 * 3600 else None
            try:
                if not b:
                    def get(url):
                        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(request, timeout=20) as response:
                            return response.read().decode('utf-8', 'ignore')
                    if kind == 'build' and role == 'ARAM':   # ARAM: в API нет, только страница сборки (все ранги)
                        html = get(core.lola_url(champ, role))
                        b = core.mode_build(html, champ, self.data, 'aram')
                    elif kind == 'arena':
                        slug = core.LOLA_FIX.get(champ, champ.lower())
                        html = get(f'https://lolalytics.com/lol/{slug}/arena/build/?patch=30')
                        b = core.mode_build(html, champ, self.data, 'arena')
                    elif kind.startswith('tier_'):   # средние ранга выше со страницы сборки
                        b = core.parse_lola_avg(get(core.lola_url(champ, role).replace('tier=emerald_plus', 'tier=' + kind[5:])))
                    elif kind == 'build':   # две сборки по Европе из API, иначе одна со страницы сборки
                        try: b = core.parse_lola_full(json.loads(get(core.lola_api('build-full', champ, role, 'euw'))), self.data)
                        except Exception as e: log_error(f'lolalytics build-full {champ} {role}', e); b = None
                        b = b or core.parse_lola_build(get(core.lola_url(champ, role)))
                    else: b = json.loads(get(core.lola_api(kind, champ, role)))
                    if kind == 'build-team': b = {'team': b.get('team')} if b.get('team') else None
                    if kind == 'counter':
                        b = {'counters': b['counters']} if isinstance(b.get('counters'), list) and (b.get('response') or {}).get('valid') is not False else None
                    if not isinstance(b, dict) or not b:
                        raise ValueError('Источник не вернул данные')
                    try:
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path+'.tmp', 'w', encoding='utf-8') as output:
                            json.dump(b, output)
                        os.replace(path+'.tmp', path)
                    except OSError as error:
                        log_error(f'кэш lolalytics {kind} {champ} {role}', error)
            except Exception as e:
                log_error(f'lolalytics {kind} {champ} {role}', e)
                b = dict(saved, stale=True) if saved else None
            def done():
                value = b or cached
                if value: self.lola[k] = value
                self.finish_lola_request(k, value, champ, role)
            self.root.after(0, done)
        threading.Thread(target=job, daemon=True).start()
        return cached

    def redraw_draft(self):
        """Перерисовать драфт один раз, даже если несколько загрузок lolalytics закончились подряд (иначе окно моргает)."""
        if getattr(self, '_redraw_job', None): return
        def go():
            self._redraw_job = None
            self.draft_sig = None
            if self.dash: self.dash.draft_sig = None
            if self.draft: self.on_draft(self.draft)
        self._redraw_job = self.root.after(400, go)

    def set_draft_scope(self, scope):
        self.s['draft_scope'] = scope
        self.s.save()
        self.draft_sig = None
        if self.dash: self.dash.draft_sig = None
        if self.draft: self.on_draft(self.draft)

    def set_draft_role(self, role):
        self.role_override = role
        self.imported = None
        self.draft_sig = None
        if self.dash: self.dash.draft_sig = None
        if self.draft: self.on_draft(self.draft)

    def set_rune_pick(self, val):
        self.s['rune_pick'] = val; self.s.save()
        self.imported = None
        if self.dash: self.dash.draft_sig = None
        self.draft_sig = None
        if self.draft: self.on_draft(self.draft)

    def draft_build_name(self, cs, role, full):
        context = self.s['draft_build_context'] if role in core.ROLES else 'general'
        if full and full.get('external'):
            return ' · '.join(filter(None, (full['external'], full.get('external_name'))))
        if context == 'offmeta':
            return 'Оффметовая · Mobalytics'
        if context.startswith('player:'):
            return 'Сборка игрока · Mobalytics'
        source = 'Общая'
        if context == 'matchup':
            opponent = self.draft_opponent(cs, role)
            source = 'Против ' + self.data.cn(opponent) if opponent else 'Против оппонента'
        variant = 'По винрейту' if self.s['rune_pick'] == 'win' else 'Популярная'
        return f'{source} · {variant.lower()}'

    def report_text(self):
        """Отчёт для Claude: версия, система, состояние клиента и последние строки журналов."""
        h = self.home
        try: ph = self.client.phase()
        except Exception: ph = '?'
        L = [f'LoL Helper {self.version} · {platform.platform()} · Python {platform.python_version()}',
             f"Экран: {screens()[0] if os.name == 'nt' else '?'} · масштаб {self.s['scale']}% · клиент {'найден' if self.client.port else 'не найден'}, фаза {ph}",
             f"Аккаунт: {(self.account or {}).get('riot', 'нет')} · статистика: {self.who}", '']
        L += [w.auto_status for w in self.tab.values()]
        for name, n in (('errors.log', 60), ('import.log', 15), ('update.log', 10), ('crash.txt', 40), ('site_error.txt', 20)):
            lines = tail(os.path.join(h, name), n)
            if lines: L += [f'--- {name} (последние {len(lines)} строк)'] + lines + ['']
        if len(L) == 4: L.append('Журналы пустые: ошибок не было.')
        return '\n'.join(L)

    def auto_import_locked(self, cs):
        if not self.s['auto_import'] or not cs.get('locked') or not cs.get('me') or cs.get('arena') or not self.player:
            return
        parts = tuple(k for k, enabled in self.s['auto_parts'].items() if enabled)
        role = self.draft_role(cs)[0]
        key = (*self.draft_export_target(cs, role), parts)
        if getattr(self, '_auto_key', None) != key:
            self._auto_key = key
            self._auto_done = set()
            self._auto_attempts = 0
            self._auto_after = 0
        pending = tuple(k for k in parts if k not in self._auto_done)
        if pending and not getattr(self, '_import_pending', None) and time.monotonic() >= self._auto_after:
            if not self.draft_build_variant(self.selected_draft_build(cs), role):
                self.set_import_msg('Автоимпорт ждёт выбранную сборку')
                return
            self._auto_attempts += 1
            self._auto_after = time.monotonic() + min(20, (self._auto_attempts - 1) * 3)
            self.do_import(pending, auto_key=key)

    def do_import(self, parts=None, *, auto_key=None):
        """Сохраняем выбор в потоке интерфейса и последовательно отправляем его в клиент."""
        cs, player = self.draft, self.player
        if not cs or not cs.get('me') or not player:
            self.set_import_msg('Сначала выбери чемпиона в драфте'); return
        follow_selection = parts is None or auto_key is not None
        if parts is None:
            parts = tuple(k for k, enabled in self.s['auto_parts'].items() if enabled)
        parts = tuple(k for k in parts if k in ('runes', 'items', 'spells'))
        if not parts:
            self.set_import_msg('Выбери, что экспортировать: руны, предметы или заклинания'); return
        target = self.draft_export_target(cs, self.draft_role(cs)[0])
        me, role, context, opponent, chosen = target
        full = self.selected_draft_build(cs)
        if not full and (context != 'general' or auto_key is not None):
            self.set_import_msg('Выбранная сборка ещё не подтверждена или не загружена. Экспорт не выполнен.');return
        variant = self.draft_build_variant(full, role)
        if full and not variant:
            self.set_import_msg('Выбранный вариант сборки недоступен. Экспорт не выполнен.'); return
        signature = (*target, parts)
        if getattr(self, '_import_pending', None) == signature: return
        self._import_pending = signature
        self._import_generation = getattr(self, '_import_generation', 0) + 1
        generation = self._import_generation
        if not hasattr(self, '_import_lock'): self._import_lock = threading.Lock()
        name, client = self.data.cn(me) + (' против ' + self.data.cn(opponent) if opponent else ''), self.client
        account = dict(self.account or {})
        cid = next((key for key, value in self.data.ids.items() if value == me), None)
        map_id = cs.get('map_id')
        if type(map_id) is not int or map_id <= 0:
            map_id = None if role == 'ARAM' else 11
        # Copy data before starting a worker; no Tk/settings calls in the worker.
        variant = json.loads(json.dumps(variant)) if variant else None
        personal_runes = player.best_runes(me) if not variant else None
        if full and full.get('external'):
            sets=core.lola_item_sets(dict(variant,situ=full.get('situ',[])),name)[:1]
            sets=[(name+': '+full['external']+' · '+full.get('external_name','выбранный вариант'),sets[0][1])]
        elif full:sets=core.lola_item_sets(full,name)
        else:sets=[(name,[('Сборка из твоих побед',player.best_build(me)),('Тотемы',[2055,3340,3364])])]
        if full and chosen == 'win': sets.reverse()
        sets = json.loads(json.dumps(sets))
        log_path = os.path.join(self.home, 'import.log') if getattr(self, 'home', None) else None
        source = ((('Против ' + self.data.cn(opponent) + ', все регионы') if opponent else 'Европа') + ', ' + ('лучший винрейт' if chosen == 'win' else 'популярная')) if full else 'из твоих игр'
        if full and full.get('build_period_days'):
            source += f", за {full['build_period_days']} дней"
        if full and role == 'ARAM':
            source = 'ARAM · ' + ('по винрейту' if chosen == 'win' else 'популярная')
        if full and full.get('external'):
            source = ' · '.join((full['external'], full.get('external_name') or 'выбранный вариант',
                                 'патч ' + str(full.get('patch') or '—')))
        runes = variant or personal_runes
        self.set_import_msg('Экспортирую выбранные данные…')

        def target_is_current(draft):
            return (bool(draft) and draft.get('me') == me and not self.last_game
                    and self.draft_export_target(draft, self.draft_role(draft)[0]) == target)

        def current():
            draft = self.draft
            return (self._import_generation == generation and target_is_current(draft)
                    and (not follow_selection or all(self.s['auto_parts'].get(k) for k in parts))
                    and (auto_key is None or (draft.get('locked') and self.s['auto_import'])))

        def job():
            results = []
            with self._import_lock:
                for part in parts:
                    if not current(): break
                    client.last_error = ''
                    try:
                        if part == 'runes':
                            ok = bool(runes) and client.set_runes(name, runes['prim'], runes['sec'], runes['perks'],
                                        runes.get('shards', []) if variant else None)
                        elif part == 'items':
                            acc = account or client.me() or {}
                            ok = bool(cid and sets and sets[0][1] and sets[0][1][0][1]) and client.set_items(acc.get('id'), cid, sets, None, map_id)
                        else:
                            spells = (variant or {}).get('spells') or []
                            ids = [core.SPELL_ID.get(spell) for spell in spells[:2]]
                            ok = len(ids) == 2 and None not in ids and client.set_spells(*ids)
                        error = client.last_error or ('нет подходящих данных' if not ok else '')
                    except Exception as exc:
                        ok, error = False, str(exc)
                    title = {'runes': 'Руны', 'items': 'Предметы', 'spells': 'Заклинания'}[part]
                    if part == 'runes':
                        status = 'применено' if ok else error
                    else:
                        status = 'готово' if ok else 'не получилось (' + error + ')'
                    results.append((ok, title + ': ' + status))
                    if not ok: log_error('импорт ' + title, error)
            def done():
                if self._import_generation != generation: return
                self._import_pending = None
                if not current():
                    if target_is_current(self.draft):
                        self.set_import_msg('Экспорт остановлен: настройки импорта изменились')
                    return
                success = len(results) == len(parts) and all(ok for ok, _ in results)
                if auto_key is not None and auto_key == getattr(self, '_auto_key', None):
                    self._auto_done.update(part for part, (ok, _) in zip(parts, results) if ok)
                for part, (ok, _) in zip(parts, results):
                    if part == 'runes':
                        self.applied_runes = None
                        if ok:
                            shards = runes.get('shards', []) if variant else [5008, 5008, 5011]
                            self.applied_runes = (name, source, list(runes['perks']), list(shards), target)
                        if getattr(self, 'dash', None):
                            self.redraw_draft()
                self.imported = me if success else None
                message = source + ' · ' + ' · '.join(text for _, text in results)
                self.set_import_msg(message)
                if log_path:
                    try:
                        with open(log_path, 'a', encoding='utf-8') as output:
                            output.write(time.strftime('%Y-%m-%d %H:%M:%S ') + me + ' ' + message + '\n')
                    except OSError: pass
            try: self.root.after(0, done)
            except (RuntimeError, RuntimeError): pass
        threading.Thread(target=job, daemon=True, name='draft-import').start()

    def keys(self):
        try:
            self._poll_keys()
        except Exception as error:
            self._recover_overlays(error)
        finally:
            try:self.root.after(40, self.keys)
            except (RuntimeError,RuntimeError):pass

    def _recover_overlays(self,error):
        log_error('клавиши и виджеты',error)
        self.demo_on=False
        self._demo_epoch=getattr(self,'_demo_epoch',0)+1
        self.keys_prev.update(tab=False,drag=False)
        for window in list(self.tab.values())+list(self.ov.values()):
            try:
                window.withdraw()
                window.unlocked=False
                window.unlock(False)
            except Exception:pass
        try:self.demo_btn.configure(text='Показать все виджеты для расстановки')
        except (AttributeError,RuntimeError):pass

    def _poll_keys(self):
        k = self.s['keys']
        for name in ('mute', 'hide'):
            down = combo_down(k.get(name))
            if down and not self.keys_prev.get(name):
                if name == 'mute':
                    self.voice.muted = not self.voice.muted
                    self.toast('Звук выключен' if self.voice.muted else 'Звук включён')
                else:
                    self.hidden = not self.hidden; self.apply_visibility()
            self.keys_prev[name] = down
        drag = bool(combo_down(k.get('drag')) and self.last_game and not self.hidden and game_focused()) or self.demo_on   # Alt двигает виджеты только в игре
        tab_down = combo_down(k.get('scoreboard'))
        focused = game_focused()
        tab = bool(self.s['scoreboard'] and self.last_game and self.last_game.me and not self.last_game.arena and not self.hidden and tab_down and focused)
        if not tab and not self.demo_on:
            for w in self.tab.values():
                if w.winfo_viewable():w.withdraw()
        for w in self.tab.values():
            if tab_down and self.s.get('tab_auto'):
                reason = ('включите оверлей таблицы Tab' if not self.s['scoreboard'] else
                          'ожидаю игровые данные от клиента LoL' if not self.last_game else
                          'таблица Арены пока не поддерживается' if self.last_game.arena else
                          'показ оверлеев скрыт горячей клавишей' if self.hidden else
                          'завершите расстановку виджетов' if self.demo_on else
                          'отпустите Alt для автоматического поиска' if drag else
                          'переключитесь в окно игры' if not focused else None)
                if reason: w._detection_status('Автоподгонка: ' + reason)
            w.auto_tick(bool(tab and not drag), self.last_game)
        if drag != self.keys_prev.get('drag'):
            self.set_unlocked(drag)
            self.keys_prev['drag'] = drag
        if self.demo_on:
            for w in self.tab.values():
                if not self.s['scoreboard']:w.withdraw()
                elif w.winfo_viewable():w.refresh_geometry()
            self.keys_prev['tab']=False
            return
        if tab:
            for w in self.tab.values():
                if w.unlocked!=drag:w.unlock(drag)
                w.refresh_geometry()
            if not self.keys_prev.get('tab') or time.time() - self.keys_prev.get('tab_t', 0) > 1:
                for w in self.tab.values():
                    try: w.show(self.last_game); w.deiconify()
                    except Exception as e: log_error('Tab', e)
                self.keys_prev['tab_t'] = time.time()
        else:
            for w in self.tab.values():
                if w.winfo_viewable():w.withdraw()
        self.keys_prev['tab'] = bool(tab)

    def set_unlocked(self, on, keys=None):
        """Расстановка виджетов; у Tab мышь принимает только отдельная ручка."""
        if on and self.hidden and not self.demo_on: return
        if not on:
            for w in self.tab.values():w.withdraw()
        wins=dict(self.tab,**self.ov)
        for key,w in wins.items():
            if keys is not None and key not in keys:continue
            enabled=self.s['scoreboard'] if key in self.tab else self.s['widgets'].get(key)
            if not enabled:
                w.withdraw();w.unlock(False);continue
            if on and key in self.tab and not self.demo_on and not combo_down(self.s['keys'].get('scoreboard')):
                w.withdraw();w.unlock(False);continue
            w.unlock(on)
            if not on:continue
            if self.last_game and self.last_game.me and key!='hints':w.show(self.last_game)
            else:w.demo()
            w.deiconify();w.lift()
        if not on:
            self.apply_visibility();self.ov['hints'].show()

    def stop_demo(self,event=None):
        if self.demo_on:
            self.toggle_demo()
            return 'break'

    def tick_ui(self):
        self.ov['hints'].show()
        self.root.after(1000, self.tick_ui)

    NAV = [('Главная', 'home'), ('История матчей', 'history'), ('Чемпион', 'search'), ('Подсказки', 'bulb'), ('Виджеты и окна', 'window'), ('Вид', 'look'),
           ('Звук', 'sound'), ('Клавиши', 'keys'), ('Таймеры', 'clock'), ('Обновления', 'update'), ('Мой пул', 'pool')]

    NAV_GROUPS = {0: 'Игра', 3: 'Настройки'}   # подписи групп перед пунктами меню

    def external_build_ready(self,champion,role):
        if self.cp_sel==(champion,role):self.cp_show()
        if self.draft and self.draft.get('me')==champion and self.draft_role(self.draft)[0]==role:
            self.draft_sig=None
            self._chosen_draft_build=(champion,role,self.s.get('draft_build_context','general'),self.selected_draft_build(self.draft))
            if self.dash:self.dash.draft_sig=None
            self.on_draft(self.draft)

    def offmeta_build(self,champion,role):
        from offmeta_source import OffmetaSource
        if not hasattr(self,'_offmeta_source'):
            self._offmeta_source=OffmetaSource(self.home,self.root.after,
                self.external_build_ready)
        return self._offmeta_source.get(champion,role)

    def player_builds(self,champion,role):
        from player_build_source import PlayerBuildSource
        if not hasattr(self,'_player_build_source'):
            self._player_build_source=PlayerBuildSource(self.home,self.root.after,
                self.external_build_ready)
        return self._player_build_source.get(champion,role)

    def lp_snaps(self, rank=None, puuid=None):
        """Снимки звания [время мс, ladder] в %APPDATA%/LoLHelper/lp.json; с rank — дописать новый, если LP изменились."""
        import hashlib
        name = 'lp-'+hashlib.sha256(puuid.encode()).hexdigest()[:16]+'.json' if puuid else 'lp.json'
        path = os.path.join(self.home,name)
        try:
            with open(path,encoding='utf-8') as source: snaps=json.load(source)
        except (OSError,ValueError): snaps=[]
        v = core.ladder(rank)
        if v is not None and (not snaps or snaps[-1][1] != v or time.time() * 1000 - snaps[-1][0] > 6 * 3600 * 1000):
            snaps.append([int(time.time() * 1000), v]); snaps = snaps[-400:]
            try:
                with open(path+'.tmp','w',encoding='utf-8') as output: json.dump(snaps,output)
                os.replace(path+'.tmp',path)
            except OSError: pass
        return snaps

    def apply_text(self, h):
        """Свой текст подсказки: {текст} заменяется исходным."""
        o = self.s['hint_text'].get(h.id)
        if not o: return
        orig_t, orig_s = h.text, h.say or h.text
        if o.get('text'): h.text = o['text'].replace('{текст}', orig_t)
        if o.get('say'): h.say = o['say'].replace('{текст}', orig_s)
        elif o.get('text'): h.say = o['text'].replace('{текст}', orig_s)

    def test_hint(self, hid, name):
        """Проверка подсказки: звучит так, как настроено (сигнал, голос или только текст)."""
        mode = self.hint_mode(hid)
        if mode == 'off': self.status.configure(text='Эта подсказка выключена'); return
        h = core.Hint(hid, name, None); self.apply_text(h)
        self.toast(h.text); self.status.configure(text=f'Проверка: {MODES[mode].lower()}')
        if mode == 'beep': self.voice.beep(force=True)
        elif mode == 'voice': self.voice.say(h.say or h.text, force=True)

    def load_lanes(self):
        """Частоты линий всех чемпионов (lolalytics, Изумруд+): по ним угадываются линии врагов в драфте. Кеш на 3 дня."""
        path = os.path.join(self.home, 'lola', 'lanes.json')
        lanes = None
        try:
            if time.time() - os.path.getmtime(path) < 3 * 86400: lanes = json.load(open(path, encoding='utf-8'))
        except Exception: pass
        if not lanes:
            try:
                lists = {}
                for r, lane in core.LOLA_LANE.items():
                    url = f'https://a1.lolalytics.com/mega/?ep=list&v=1&patch=30&lane={lane}&tier=emerald_plus&queue=ranked&region=all'
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    lists[r] = json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore'))
                lanes = core.lola_lanes(lists, self.data)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                json.dump(lanes, open(path, 'w', encoding='utf-8'))
            except Exception as e:
                log_error('таблица линий', e)
                try: lanes = json.load(open(path, encoding='utf-8'))
                except Exception: lanes = {}
        def done():
            self.data.lanes = lanes or {}
            self.redraw_draft()
        self.root.after(0, done)

    def reload_data(self, data):
        """Новая статистика скачалась: подменяем между играми, текущая игра доигрывается со старой."""
        if self.last_game:
            self.pending_data = data; return
        self.pending_data = None
        data.lanes = self.data.lanes
        self.data = data
        if getattr(self,'pool_view',None):
            self.pool_view.rows, self.pool_view.source = champion_pool.load_catalog(data)
        self.set_who(self.who)
        self.panel_sync()

    def matchup_lines(self, p, col, allies, r):
        """Строки под чемпионом в драфте: у врага — кто его контрит (и кто из твоего пула), у союзника — синергия с командой."""
        d, pl = self.data, self.player
        c, pos = p.get('c'), p.get('pos')
        if not c or not pos: return []
        myrole = r.get('role')
        if col == 1:
            cnt = core.lola_counters(self.lola_fetch('counter', c, pos), d)
            if not cnt:
                state = self.lola_state.get(('counter', c, pos))
                if state == 'loading':
                    return [('Контрпики: загружаю Lolalytics…', 'mute')]
                if state == 'ok':
                    return [('Мало игр для контрпиков на этой роли', 'mute')]
                return []
            pool = pl.pool.get(myrole, []) if pl and pos == myrole else []
            best, mine = core.counter_picks(cnt, 3, pool)
            out = []
            if best: out.append(('Контрпики', [(x, f'{wr:.0f}% (+{dd:.1f})', 'blue') for x, dd, wr in best]))
            if mine:
                mine.sort(key=lambda x: -x[1])
                out.append(('Из твоего пула', [(x, f'{wr:.0f}% ({dd:+.1f})', 'good' if dd > .5 else 'bad' if dd < -.5 else 'fg') for x, dd, wr in mine[:3]]))
            return out
        team = core.lola_team(self.lola_fetch('build-team', c, pos), d)
        if not team: return []
        out, parts = [], []
        for a in allies:
            if a is p or not a.get('c') or not a.get('pos'): continue
            v = team.get((a['pos'], a['c']))
            if v: parts.append((v[1], (a['c'], f"{v[0]:.0f}% ({v[1]:+.1f})", 'good' if v[1] > .5 else 'bad' if v[1] < -.5 else 'fg')))
        if parts:
            parts.sort(key=lambda x: -x[0])
            out.append(('Синергия', [t for _, t in parts]))
        me = next((a for a in allies if a.get('me')), None)
        if pl and me and not me.get('c') and not p.get('me') and myrole:
            pool = [(team[(myrole, x)][1], x) for x in pl.pool.get(myrole, []) if (myrole, x) in team]
            if pool:
                pool.sort(reverse=True)
                out.append(('Тебе с ним из пула', [(x, f'({v:+.1f})', 'good' if v > .5 else 'fg') for v, x in pool[:4]]))
        return out

    TIPS = {'csm': 'Фарм просел к сезону: добивай волну перед каждым возвращением на базу и забирай боковые линии в середине игры.',
            'vsm': 'Обзор просел к сезону: ставь контрольный вард при каждом возвращении на базу.',
            'kda': 'KDA просел к сезону: меньше заходов в туман без обзора, после линии держись ближе к команде.',
            'wr': 'Винрейт ниже сезона: играй меньше игр подряд после двух поражений и бери свой основной пул.'}
