import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import core
import history_model as model
import ui


def game_fixture():
    roles=[('TOP','SOLO'),('JUNGLE','NONE'),('MIDDLE','SOLO'),('BOTTOM','DUO_CARRY'),('BOTTOM','DUO_SUPPORT')]*2
    return {'gameId':1000,'gameDuration':1800,'queueId':420,
        'participantIdentities':[{'participantId':i,'player':{'gameName':f'Игрок{i}','tagLine':'TEST','puuid':f'p{i}'}} for i in range(1,11)],
        'participants':[{'participantId':i,'teamId':100 if i<=5 else 200,'championId':c,'timeline':{'lane':lane,'role':role},
                        'stats':{'win':i<=5,'kills':5,'deaths':3,'assists':8,'totalMinionsKilled':150,'neutralMinionsKilled':30,
                                 'totalDamageDealtToChampions':24000,'visionScore':25,'goldEarned':12000,'champLevel':16,
                                 'item0':1056,'item1':3020,'item2':3118,'item3':3089,'item4':3135,'item5':3157,'item6':3340}}
            for i,(c,(lane,role)) in enumerate(zip([266,64,103,222,412,54,113,112,51,99],roles),1)]}


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with Path(__file__).with_name('data.json').open(encoding='utf-8') as source:cls.data=core.Data(json.load(source))

    def test_source_units_and_unknown_saved_totals_are_not_estimated(self):
        saved=model.saved([{'c':'Ahri','t':1700000000,'dur':31.5,'w':1,'k':5,'d':2,'a':7,'csm':6.2,'vsm':.6,'q':420,'pos':'MIDDLE'}],self.data,'x')[0]
        self.assertEqual(saved['duration'],1890);self.assertEqual(saved['timestamp'],1700000000)
        self.assertIsNone(saved['cs']);self.assertIsNone(saved['vis']);self.assertIsNone(saved['lp']);self.assertIsNone(saved['gid'])
        current=model.client([{'champ':103,'t':1700000000000,'dur':1800,'win':True,'cs':180,'vis':30,'gid':1,'q':420,'lane':'MIDDLE','role':'SOLO'}],self.data,'p',{1:0})[0]
        self.assertEqual(current['timestamp'],1700000000);self.assertEqual(current['duration'],1800)
        self.assertEqual(current['csm'],6);self.assertEqual(current['vsm'],1);self.assertEqual(current['lp'],0)
        self.assertIsNone(current['k'])

    def test_lp_solo_only_and_missing_values_are_not_losses_or_zero(self):
        rows=model.client([{'gid':1,'q':440,'dur':0},{'gid':2,'q':420,'t':float('nan')}],self.data,'p',{1:20})
        self.assertTrue(all(r['lp'] is None and r['win'] is None and r['csm'] is None for r in rows))
        self.assertEqual(model.stats(rows)['results'],0)
        self.assertIsNone(model.stats(rows)['wr'])
        self.assertIsNone(model.timestamp(10**20))

    def test_filters_intersect_and_do_not_mutate_records(self):
        raw=[{'c':'Ahri','opp':'Viktor','pos':'MIDDLE','q':420,'w':1,'t':2},
             {'c':'Ahri','pos':'TOP','q':440,'w':0,'t':1}]
        before=copy.deepcopy(raw);rows=model.saved(raw,self.data,'x')
        selected=model.filtered(rows,self.data,'Виктор','MIDDLE',420,'win')
        self.assertEqual(len(selected),1);self.assertEqual(selected[0]['champion'],'Ahri')
        self.assertEqual(model.filtered(rows,self.data,'Ahri','MIDDLE',440),[])
        self.assertEqual(raw,before)

    def test_full_detail_keeps_actual_teams_items_identity_and_analysis(self):
        review=model.details(game_fixture(),'p3',self.data)
        self.assertEqual(len(review['rows']),10);self.assertEqual(review['me']['c'],'Ahri')
        self.assertEqual(review['me']['name'],'Игрок3#TEST');self.assertEqual(len(review['me']['items']),7)
        self.assertTrue(review['analysis_available']);self.assertTrue(review['lines'])

    def test_incomplete_stats_unknown_focus_or_zero_team_totals_do_not_invent_analysis(self):
        partial=game_fixture();del partial['participants'][0]['stats']['kills']
        review=model.details(partial,'p3',self.data)
        self.assertIsNone(review['rows'][0]['k']);self.assertFalse(review['analysis_available'])
        for game in (dict(game_fixture(),gameDuration=300),dict(game_fixture(),queueId=450)):
            self.assertFalse(model.details(game,'p3',self.data)['analysis_available'])
        zero=game_fixture()
        for p in zero['participants']:p['stats']['kills']=0
        self.assertFalse(model.details(zero,'p3',self.data)['analysis_available'])
        unknown=model.details(game_fixture(),'not-in-match',self.data)
        self.assertIsNone(unknown['me']);self.assertFalse(unknown['lines'])
        self.assertIsNone(model.details(None,'p3',self.data))
        arena=model.details(dict(game_fixture(),queueId=1700),'p3',self.data)
        self.assertEqual(arena['team_grouping'],'participants')
        self.assertEqual(len(arena['rows']),10)

    def test_snapshots_are_separate_per_account_and_legacy_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as home:
            old=Path(home,'lp.json');old.write_text('[[1,9999]]')
            app=SimpleNamespace(home=home)
            rank={'tier':'EMERALD','div':'IV','lp':17}
            first=ui.App.lp_snaps(app,rank,puuid='one');second=ui.App.lp_snaps(app,None,puuid='two')
            self.assertTrue(first);self.assertEqual(second,[])
            self.assertEqual(old.read_text(),'[[1,9999]]')
            self.assertEqual(len(list(Path(home).glob('lp-*.json'))),1)

if __name__=='__main__':unittest.main()
