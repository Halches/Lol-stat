import copy
import json
from pathlib import Path
import unittest
import champion_rank
import player_traits
import player_comments
import player_evidence
import ui
from types import SimpleNamespace


def history(n=20, on=16, role='MIDDLE'):
    return [dict(q=420,dur=1800,gid=i,champ=103 if i<on else 1,lane=role,role='SOLO') for i in range(n)]


def qwik(data, nav):
    objects=[]
    def encode(value):
        i=len(objects);objects.append(None)
        if isinstance(value,dict):objects[i]={k:encode(v) for k,v in value.items()}
        elif isinstance(value,list):objects[i]=[encode(v) for v in value]
        else:objects[i]=value
        digits='0123456789abcdefghijklmnopqrstuvwxyz';r='';j=i
        while True:
            r=digits[j%36]+r;j//=36
            if not j:return r
    encode(nav);encode(data)
    return '<script type="qwik/json">'+json.dumps({'objs':objects})+'</script>'


class TraitsTests(unittest.TestCase):
    def test_main_is_recent_frequency_with_sufficient_sample(self):
        self.assertIn('G7',[r[0] for r in player_traits.traits(history(),103,'MIDDLE')])
        for h in (history(n=9), history(on=9), [dict(h,q=450) for h in history()]):
            self.assertNotIn('G7',[r[0] for r in player_traits.traits(h,103,'MIDDLE')])
        self.assertNotIn('G7',[r[0] for r in player_traits.traits(history(),1,'MIDDLE')])

    def test_role_is_neutral_and_not_inferred_from_unknown_history(self):
        self.assertIn(('N4','Непривычная роль · 0/20 игр','neutral'),player_traits.traits(history(),103,'TOP'))
        self.assertFalse(any(r[0]=='N4' for r in player_traits.traits(history(role=''),103,'TOP')))

    def test_team_and_timeline_evidence_are_required_independently(self):
        game={'gameDuration':1800,'participantIdentities':[{'participantId':1,'player':{'puuid':'p'}}],
              'participants':[{'participantId':i,'teamId':100,'stats':{'kills':2,'assists':5}} for i in range(1,6)]}
        tl={'frames':[{'timestamp':t,'events':[]} for t in range(0,840001,60000)]}
        tl['frames'][-1]['events']=[{'type':'CHAMPION_KILL','victimId':1,'timestamp':839999},
                                    {'type':'CHAMPION_KILL','victimId':1,'timestamp':840000}]
        self.assertEqual(player_traits.detail_metrics(game,tl,'p'),{'kp':70,'d14':1})
        self.assertEqual(player_traits.detail_metrics(game,None,'p'),{'kp':70})
        self.assertEqual(player_traits.detail_metrics(game,tl,'hidden'),{})
        incomplete=copy.deepcopy(game);incomplete['participants'].pop()
        self.assertEqual(player_traits.detail_metrics(incomplete,tl,'p'),{'d14':1})
        short=copy.deepcopy(tl);short['frames'][-1]['timestamp']=839999
        self.assertNotIn('d14',player_traits.detail_metrics(game,short,'p'))
        gap=copy.deepcopy(tl);gap['frames'].pop(5)
        self.assertNotIn('d14',player_traits.detail_metrics(game,gap,'p'))
        self.assertNotIn('d14',player_traits.detail_metrics(game,{'frames':[tl['frames'][-1]]},'p'))
        zero=copy.deepcopy(game)
        for p in zero['participants']:p['stats']['kills']=0
        self.assertNotIn('kp',player_traits.detail_metrics(zero,tl,'p'))

    def test_metrics_need_five_games_in_current_role_and_missing_is_not_zero(self):
        good={i:{'kp':70,'d14':1} for i in range(5)}
        rows=player_traits.traits(history(),103,'MIDDLE',good)
        self.assertEqual({r[0] for r in rows},{'G7','G8','G9'})
        self.assertEqual({r[0] for r in player_traits.traits(history(),103,'MIDDLE',{i:good[i] for i in range(4)})},{'G7'})
        bad={i:{'kp':20,'d14':3} for i in range(5)}
        self.assertTrue({'R9','R10'} <= {r[0] for r in player_traits.traits(history(),103,'MIDDLE',bad)})
        self.assertFalse({'R9','R10','G8','G9'} & {r[0] for r in player_traits.traits(history(),103,'TOP',good)})

    def test_both_badges_visible_and_colours_grouped_in_four_slots(self):
        h={'n':20,'tags':['почти только'],'streak':4,'good':['KDA 5'],'bad':['мало обзора'],
           'extra_comments':[('G7','Мейнер · 16/20 игр','good'),('G10','Топ-1000 · №42 в мире · Lolalytics','good'),('N4','Непривычная роль','neutral')]}
        rows=player_comments.preview(h)
        self.assertEqual([r[0] for r in rows],['G10','G7','N4','R8'])
        self.assertNotIn('N1',[r[0] for r in player_comments.comments(h)])

    def test_hidden_draft_player_never_requests_evidence_or_client(self):
        app=SimpleNamespace(data=SimpleNamespace(ids={'103':'Ahri'}),account=None,hraw={},ranks={},rank_pu={})
        app.player_history=lambda pu,*args: self.assertIsNone(pu)
        rows=ui.App.draft_allies(app,{'localPlayerCellId':0,'myTeam':[{'nameVisibilityType':'HIDDEN','cellId':1,'puuid':'secret','championId':103,'gameName':'hidden','tagLine':'one'}]})
        self.assertIsNone(rows[0]['pu'])


class EvidenceTests(unittest.TestCase):
    def test_background_fetches_five_games_once_and_keeps_missing_timeline_unknown(self):
        calls=[]
        class Client:
            def game(self,gid):
                calls.append(gid)
                return {'gameId':gid,'gameDuration':1800,
                        'participantIdentities':[{'participantId':1,'player':{'puuid':'p'}}],
                        'participants':[{'participantId':i,'teamId':100,'stats':{'kills':2,'assists':5}} for i in range(1,6)]}
            def timeline(self,gid):return None
        service=player_evidence.Evidence()
        for _ in range(2):service.request(Client(),'p',history(),'Ahri',103,'MIDDLE','')
        service.jobs.join()
        metrics,board=service.snapshot('p','Ahri')
        self.assertEqual(sorted(calls),list(range(1,6)))
        self.assertEqual(len(metrics),5)
        self.assertTrue(all(v=={'kp':70} for v in metrics.values()))
        self.assertIsNone(board)
        service.request(Client(),'p',history(),'Ahri',103,'MIDDLE','')
        service.jobs.join()
        self.assertEqual(len(calls),5)
        service.request(None,None,history(),'Ahri',103,'MIDDLE','Hidden#TAG')
        self.assertEqual(len(calls),5)

    def test_verified_rank_can_coexist_with_unavailable_history(self):
        board={'champion':'Ahri','scope':'global','fetched_at':100,'url':champion_rank.url('Ahri'),
               'rows':[{'rank':42,'riot':'Player#TAG','region':'euw'}]}
        app=SimpleNamespace(hraw={},data=SimpleNamespace(ids={'103':'Ahri'}),
            evidence=SimpleNamespace(request=lambda *a:None,snapshot=lambda *a:({},board)),
            evidence_region='EUW',evidence_region_at=100,client=SimpleNamespace(region=lambda:'EUW'))
        from unittest.mock import patch
        with patch('ui.time.time',return_value=101):
            summary=ui.App.player_history(app,'p',103,'MIDDLE','Player#TAG')
        self.assertEqual(summary['n'],0)
        text,tags=ui.hist_tags(summary)
        self.assertEqual(text,'История игрока недоступна')
        self.assertIn('N3',[r[0] for r in player_comments.comments(summary)])
        self.assertEqual(summary['champion_rank']['rank'],42)


class ChampionRankTests(unittest.TestCase):
    def board(self, rank=1000, reg='all', champion=103, valid=True):
        nav={'cid':champion,'page':'leaderboard','region':reg,'champion':'ahri'}
        data={'header':{'cid':champion},'response':{'valid':valid},'toplist':[[rank,'Player#TAG','euw']]}
        return champion_rank.parse(qwik(data,nav),103,'Ahri',now=100)

    def test_rank_boundary_identity_champion_region_and_expiry(self):
        board=self.board()
        self.assertEqual(champion_rank.lookup(board,'Ahri','player#tag','EUW1',now=101)['rank'],1000)
        for champ,riot,region,now in [('Ahri','Player','EUW1',101),('Ahri','Player#WRONG','EUW1',101),('Ahri','Player#TAG','NA1',101),('Annie','Player#TAG','EUW1',101),('Ahri','Player#TAG','EUW1',21701)]:
            self.assertIsNone(champion_rank.lookup(board,champ,riot,region,now))
        for rank in (0,1001,True,1.5):self.assertEqual(self.board(rank)['rows'],[])
        self.assertIsNone(self.board(reg='euw'))
        self.assertIsNone(self.board(champion=1))
        self.assertIsNone(self.board(valid=False))

    def test_real_public_page_has_only_fifty_entries_not_a_full_top_thousand(self):
        fixture=Path(__file__).parent/'dev/fixtures/lolalytics-leaderboard.html'
        board=champion_rank.parse(fixture.read_text(encoding='utf-8'),103,'Ahri',now=100)
        self.assertEqual(board['coverage'],50)
        self.assertEqual(board['rows'][0]['rank'],1)
        self.assertEqual(board['rows'][-1]['rank'],50)
        self.assertIsNone(champion_rank.lookup(board,'Ahri','Unknown#TAG','EUW',101))

if __name__=='__main__': unittest.main()
