"""Saved match details must come from exact historical records, including offline use."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import history_archive as archive
import history_model
import lolhelper


def fixture(mid='EUW1_1000'):
    champs=['Aatrox','LeeSin','Ahri','Jinx','Thresh','Malphite','Sejuani','Viktor','Caitlyn','Lux']
    roles=['TOP','JUNGLE','MIDDLE','BOTTOM','UTILITY']*2
    return {'id':mid,'q':420,'start':1700000000000,'dur':30,'win100':True,
        'parts':[{'c':c,'n':f'Player{i}','t':'TEST','team':100 if i<5 else 200,'pos':roles[i],
            'k':i,'d':3,'a':8,'cs':180,'dmg':24000+i,'g':12000+i,'vs':25,'items':[1056,3020,0],
            'me':'halch' if i==2 else 'drv' if i==7 else None} for i,c in enumerate(champs)],
        'me':[{'who':'halch','c':'Ahri','pos':'MIDDLE','sums':[4,14],'keystone':8112,'lvl':16,
            'k':2,'d':3,'a':8,'cs':180,'dmg':24002,'g':12002,'vs':25},
            {'who':'drv','c':'Viktor','pos':'MIDDLE','sums':[4,12],'keystone':8229,'lvl':15}]}


def old_data():
    return {'players':{'halch':{'g':[{'c':'Ahri','q':420,'t':1700000000,'dur':30,'csm':6.1,'k':2,'d':3,'a':8,'w':1}]},
        'drv':{'g':[{'c':'Viktor','q':420,'t':1700000000,'dur':30}]}}}


class HistoryArchive(unittest.TestCase):
    def test_exact_join_and_both_profiles_keep_their_own_participant(self):
        matches=archive.build([fixture()]);data=old_data();before=copy.deepcopy(data)
        archive.attach(data,matches)
        for who,champ in [('halch','Ahri'),('drv','Viktor')]:
            record=history_model.saved(data['players'][who]['g'],None,who)[0]
            review=history_model.saved_details(matches[record['match_id']],who,record['match_id'])
            self.assertEqual(len(review['rows']),10);self.assertEqual(review['me']['c'],champ)
            self.assertEqual(sum(row['me'] for row in review['rows']),1)
            self.assertEqual(record['gid'],1000)
        for who,player in before['players'].items():
            for key,value in player['g'][0].items():self.assertEqual(data['players'][who]['g'][0][key],value)
        focus=archive.review(matches['EUW1_1000'],'halch','EUW1_1000')['me']
        self.assertEqual(focus['dmg'],24002);self.assertEqual(focus['gold'],12002)
        self.assertEqual(data['players']['halch']['g'][0]['spells'],[4,14])

    def test_ambiguous_time_or_conflicting_id_does_not_guess(self):
        data=old_data();matches=archive.build([fixture(),fixture('EUW1_2000')])
        archive.attach(data,matches);self.assertNotIn('id',data['players']['halch']['g'][0])
        data=old_data();data['players']['halch']['g'][0]['id']='RU_123'
        archive.attach(data,archive.build([fixture()]));self.assertEqual(data['players']['halch']['g'][0]['id'],'RU_123')

    def test_missing_time_does_not_join_by_champion_alone(self):
        game=fixture();game.pop('start');data=old_data();data['players']['halch']['g'][0].pop('t')
        archive.attach(data,archive.build([game]));self.assertNotIn('id',data['players']['halch']['g'][0])

    def test_wrong_match_unknown_profile_and_missing_values_are_retained(self):
        game=fixture();game['parts'][0].pop('dmg');matches=archive.build([game]);snapshot=matches['EUW1_1000']
        self.assertIsNone(archive.review(snapshot,'halch','EUW1_9999'))
        review=archive.review(snapshot,'unknown','EUW1_1000')
        self.assertIsNone(review['me']);self.assertIsNone(review['rows'][0]['dmg'])
        self.assertFalse(review['analysis_available'])

    def test_views_do_not_mutate_the_shared_archive(self):
        matches=archive.build([fixture()]);before=copy.deepcopy(matches)
        review=archive.review(matches['EUW1_1000'],'halch','EUW1_1000');review['rows'][0]['items'].append(999)
        archive.review(matches['EUW1_1000'],'drv','EUW1_1000')
        self.assertEqual(matches,before)
        with self.assertRaises(ValueError):archive.build([fixture(),fixture()])

    def test_newer_legacy_cache_uses_bundled_details_without_losing_history(self):
        base=json.loads(Path(__file__).with_name('data.json').read_text(encoding='utf-8'))
        base['players']['halch']['g']=old_data()['players']['halch']['g'];base['t']='2020-01-01 00:00'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);bundle=root/'bundle';cache=root/'cache';bundle.mkdir();cache.mkdir()
            (bundle/'data.json').write_text(json.dumps(base),encoding='utf-8')
            newer=copy.deepcopy(base);newer['t']='2021-01-01 00:00';newer['cached_only']=True
            (cache/'data.json').write_text(json.dumps(newer),encoding='utf-8')
            (bundle/'history-details.json').write_text(json.dumps({'version':1,'matches':archive.build([fixture()])}),encoding='utf-8')
            before=(cache/'data.json').read_bytes()
            with patch.object(lolhelper,'HERE',str(bundle)),patch.object(lolhelper,'home',return_value=str(cache)):
                data=lolhelper.load_data().d
            self.assertTrue(data['cached_only']);self.assertEqual(data['t'],newer['t'])
            self.assertEqual(data['players']['halch']['g'][0]['id'],'EUW1_1000')
            self.assertEqual((cache/'data.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
