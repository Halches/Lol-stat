import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock,patch
from desktop.profile_memory import ProfileMemory
from desktop.worker import Companion
from desktop.connection import connection_view


def profile(key='one', matches=None):
    return dict(_accountKey=key,profile={'riot':key+'#EUW','level':100},ranks={},weekly={},trend={},
                month={'days':{1:2}},matches=matches or [],historyAvailable=True,
                historyInterrupted=False,historyHasMore=False,assetVersion='16.23.1',range=[1,2])


class MemoryTests(unittest.TestCase):
    def companion(self,memory):
        with patch('desktop.worker.read_catalog',return_value={}),patch.object(Companion,'update_catalog',return_value={}):
            c=Companion(Mock(port=None,token=None),profile_memory=memory)
        self.addCleanup(c.close)
        return c

    def test_restart_offline_preserves_profile_and_account_switch_does_not_mix_history(self):
        with TemporaryDirectory() as folder:
            memory=ProfileMemory(Path(folder)/'profile.json')
            first=self.companion(memory)
            row={'id':'EUW1_1','playedAt':100,'queue':420}
            first.apply_home_profile(profile(matches=[row]))
            second=self.companion(memory)
            second.update_latest_match(10,True)
            self.assertEqual(second.home_profile['profile']['riot'],'one#EUW')
            self.assertEqual(second.latest_match,row)
            self.assertEqual(second.home_profile['month']['days'][1],2)
            state=second.connection_state()
            self.assertTrue(state['profileCached']);self.assertEqual(state['state'],'offline')
            self.assertIn('Сохранённый',connection_view({'connection':state})['title'])
            second.apply_home_profile(dict(profile('two'),historyInterrupted=True))
            self.assertEqual(second.home_profile['matches'],[])
            self.assertFalse(second.connection_state()['profileCached'])
            self.assertEqual(memory.load()['profile']['riot'],'two#EUW')

    def test_corrupt_cache_is_ignored_and_session_secrets_are_not_written(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'profile.json';memory=ProfileMemory(path)
            memory.save(dict(profile(),token='secret',password='secret',port=123))
            self.assertNotIn('secret',path.read_text(encoding='utf-8'))
            path.write_text('{broken',encoding='utf-8');self.assertIsNone(memory.load())
            path.write_text(json.dumps({'version':1,'data':{'profile':{}}}),encoding='utf-8')
            self.assertIsNone(memory.load())
