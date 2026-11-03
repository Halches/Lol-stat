import copy
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import champion_pool as pool
import core
import ui

class PoolTests(unittest.TestCase):
    def setUp(self):
        with open(__import__('pathlib').Path(__file__).with_name('data.json'),encoding='utf-8') as source:
            self.data=core.Data(json.load(source))
        self.rows,self.source=pool.load_catalog(self.data)

    def test_all_champions_and_missing_lore_are_retained(self):
        self.assertEqual({r['id'] for r in self.rows},set(self.data.ids.values()))
        self.assertEqual(len(self.rows),len({r['id'] for r in self.rows}))
        with tempfile.TemporaryDirectory() as directory:
            rows,_=pool.load_catalog(self.data,directory+'/missing.json')
        self.assertEqual(len(rows),len(self.rows))
        self.assertFalse(any(r.get('year') is not None and r['year']<2009 for r in self.rows))
        self.assertTrue(all(not r['species'] for r in rows))
        unknown=pool.filtered(rows,{},'MIDDLE',filters={'species':'?'})
        self.assertEqual(len(unknown),len(rows))

    def test_search_russian_english_spacing_and_filters_intersect(self):
        ahri=pool.filtered(self.rows,{},'MIDDLE',query='Ари')
        self.assertIn('Ahri',[r['id'] for r in ahri])
        self.assertEqual([r['id'] for r in pool.filtered(self.rows,{},'MIDDLE',query='  aHri ')],['Ahri'])
        self.assertEqual([r['id'] for r in pool.filtered(self.rows,{},'MIDDLE',query='Ahri',filters={'gender':'FEMALE','regions':'Ionia','species':'Vesani'})],['Ahri'])
        self.assertEqual(pool.filtered(self.rows,{},'MIDDLE',query='Ahri',filters={'gender':'MALE'}),[])
        self.assertEqual(pool.norm('Ё НУ-НУ'),pool.norm('енуну'))

    def test_multiple_positions_are_preserved_and_pool_mode_is_independent(self):
        rows=[{'id':'Flex','name':'Флекс','roles':['TOP','MIDDLE'],'year':2020},{'id':'Other','name':'Другой','roles':['JUNGLE'],'year':2024}]
        for role in ('TOP','MIDDLE'):self.assertEqual([r['id'] for r in pool.filtered(rows,{},role,mode='role')],['Flex'])
        self.assertEqual([r['id'] for r in pool.filtered(rows,{'TOP':['Other']},'TOP',mode='pool')],['Other'])
        self.assertEqual([r['id'] for r in pool.filtered(rows,{'TOP':['Other']},'TOP',sort='selected')],['Other','Flex'])
        self.assertEqual(pool.filtered(rows,{},'TOP',sort='year')[0]['id'],'Other')

    def test_empty_saved_role_does_not_restore_defaults_or_modify_other_profile(self):
        defaults={'MIDDLE':['Ahri','Fizz'],'TOP':['Malphite']}
        settings={'champion_pools':{'a':{'MIDDLE':[]}}}
        result=pool.saved_pool(settings,'a',defaults,set(self.data.ids.values()))
        self.assertEqual(result['MIDDLE'],[])
        self.assertEqual(pool.saved_pool(settings,'b',defaults,set(self.data.ids.values()))['MIDDLE'],['Ahri','Fizz'])
        result['MIDDLE'].append('Ahri')
        self.assertEqual(settings['champion_pools']['a']['MIDDLE'],[])
        self.assertEqual(defaults['MIDDLE'],['Ahri','Fizz'])
        self.assertEqual(pool.clean_pool({'TOP':['Ahri','Ahri',{},'not-real'],'MIDDLE':'Ahri'},set(self.data.ids.values()))['TOP'],['Ahri'])

    def test_toggle_save_restart_role_isolation_and_failure_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            settings=ui.Settings(directory)
            app=SimpleNamespace(s=settings,data=self.data,who='halch',player=SimpleNamespace(pool={}),dash=None,draft_sig='old')
            app.current_pool=lambda:ui.App.current_pool(app)
            before=copy.deepcopy(self.data.d['pools'])
            initial=app.current_pool()
            champion='Ahri';had=champion in initial['MIDDLE']
            ui.App.toggle_pool(app,champion,'MIDDLE')
            self.assertEqual(champion in app.player.pool['MIDDLE'],not had)
            self.assertEqual(app.player.pool['TOP'],initial['TOP'])
            self.assertEqual(app.player.pool,pool.saved_pool(ui.Settings(directory),'halch',{},set(self.data.ids.values())))
            with patch.object(settings,'save',side_effect=OSError('disk full')):
                saved=copy.deepcopy(settings['champion_pools'])
                with self.assertRaises(OSError):ui.App.toggle_pool(app,champion,'MIDDLE')
                self.assertEqual(settings['champion_pools'],saved)
                self.assertEqual(app.player.pool,pool.saved_pool(settings,'halch',{},set(self.data.ids.values())))
            ui.App.toggle_pool(app,champion,'MIDDLE')
            self.assertEqual(app.current_pool(),initial)
            self.assertEqual(self.data.d['pools'],before)

if __name__=='__main__':unittest.main()
