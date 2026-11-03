import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from player_build_source import PlayerBuildSource

FIXTURE=json.loads((Path(__file__).parent/'dev/fixtures/mobalytics-players.json').read_text())
class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.callbacks=[]
        self.source=PlayerBuildSource(self.tmp.name,lambda delay,fn:self.callbacks.append(fn),lambda *args:None)
        self.thread=patch('threading.Thread',side_effect=lambda target,**kw:SimpleNamespace(start=target));self.thread.start();self.addCleanup(self.thread.stop)
    def finish(self):
        while self.callbacks:self.callbacks.pop(0)()
        return self.source.values.get(('Ahri','MIDDLE'))
    def read(self,url):return copy.deepcopy(FIXTURE['pages'][url.split('=')[-1]] if 'buildID=' in url else FIXTURE['index'])
    def test_complete_background_result_and_incremental_updates(self):
        with patch.object(self.source,'read',side_effect=self.read) as request:self.source.get('Ahri','MIDDLE')
        self.assertEqual(request.call_count,6);self.assertGreater(len(self.callbacks),2)
        packet=self.finish();self.assertFalse(packet['partial']);self.assertEqual(len(packet['groups']['Pro']),2)
        self.assertTrue(all(row['variant'] for group in packet['groups'].values() for row in group))
        self.assertFalse(self.source.pending)
    def test_valid_disk_cache_avoids_download(self):
        with patch.object(self.source,'read',side_effect=self.read):self.source.get('Ahri','MIDDLE');self.finish()
        self.source.values.clear();self.source.attempts.clear()
        with patch.object(self.source,'read',side_effect=AssertionError('network')) as request:self.source.get('Ahri','MIDDLE');packet=self.finish()
        request.assert_not_called();self.assertFalse(packet['partial'])
    def test_ignored_detail_query_never_applies_popular_build(self):
        with patch.object(self.source,'read',return_value=FIXTURE['index']):self.source.get('Ahri','MIDDLE');packet=self.finish()
        self.assertTrue(packet['partial']);self.assertTrue(all(row.get('error') and row['variant'] is None for group in packet['groups'].values() for row in group))
    def test_stale_disk_fallback_keeps_dates_and_full_variants(self):
        with patch.object(self.source,'read',side_effect=self.read):self.source.get('Ahri','MIDDLE');self.finish()
        path=Path(self.tmp.name,'players/ahri_MIDDLE.json');saved=json.loads(path.read_text());old=time.time()-90000;saved['fetched_at']=old;saved['dates']={bid:old for bid in saved['dates']};path.write_text(json.dumps(saved))
        self.source.values.clear();self.source.attempts.clear()
        with patch.object(self.source,'read',side_effect=OSError('offline')):self.source.get('Ahri','MIDDLE');packet=self.finish()
        self.assertTrue(packet['stale']);self.assertEqual(packet['fetched_at'],old)
        self.assertTrue(all(row['variant'] and row['stale'] and row['fetched_at']==old for group in packet['groups'].values() for row in group))
    def test_pending_is_bounded(self):
        self.source.pending={('Lux','MIDDLE'),('Viktor','MIDDLE')}
        with patch.object(self.source,'read') as request:self.assertIsNone(self.source.get('Ahri','MIDDLE'));request.assert_not_called()
if __name__=='__main__':unittest.main()
