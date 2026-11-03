import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch,MagicMock
from offmeta_source import OffmetaSource

PAYLOAD=json.loads((Path(__file__).parent/'dev/fixtures/mobalytics-offmeta.json').read_text())['payload']
class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ready=threading.Event();self.callbacks=[];self.changed=[]
        def post(delay,callback):self.callbacks.append(callback);self.ready.set()
        self.source=OffmetaSource(self.temp.name,post,lambda *args:self.changed.append(args))
    def settle(self):
        self.assertTrue(self.ready.wait(3));self.callbacks.pop(0)()
    def cached(self,stamp):
        folder=Path(self.temp.name,'offmeta');folder.mkdir();(folder/'ahri_MIDDLE.json').write_text(json.dumps({'payload':PAYLOAD,'fetched_at':stamp}))
    def test_recent_cache_is_revalidated_and_does_not_request(self):
        self.cached(time.time()-10)
        with patch('urllib.request.urlopen',side_effect=AssertionError('unexpected network')):
            self.assertIsNone(self.source.get('Ahri','MIDDLE'));self.settle()
        self.assertEqual(self.source.get('Ahri','MIDDLE')['source_games'],6739);self.assertFalse(self.source.pending)
    def test_stale_cache_keeps_original_date_on_network_error(self):
        stamp=time.time()-90000;self.cached(stamp)
        with patch('urllib.request.urlopen',side_effect=OSError('offline')):
            self.source.get('Ahri','MIDDLE');self.settle()
        value=self.source.get('Ahri','MIDDLE');self.assertTrue(value['stale']);self.assertEqual(value['fetched_at'],stamp)
    def test_failed_context_does_not_substitute_another_role(self):
        html='<script>window.__PRELOADED_STATE__='+json.dumps({'lolState':{'apollo':{'dynamic':PAYLOAD}}})+';</script>'
        response=MagicMock();response.__enter__.return_value.read.return_value=html.encode()
        with patch('urllib.request.urlopen',return_value=response):
            self.source.get('Ahri','TOP');self.settle()
        self.assertIsNone(self.source.get('Ahri','TOP'));self.assertEqual(self.source.states[('Ahri','TOP')],'fail')
    def test_pending_limit(self):
        self.source.pending.update((str(i),'MIDDLE') for i in range(4))
        with patch('urllib.request.urlopen') as request:self.assertIsNone(self.source.get('Ahri','MIDDLE'));request.assert_not_called()
    def test_repeated_pending_request_is_not_duplicated(self):
        self.source.pending.add(('Ahri','MIDDLE'))
        with patch('threading.Thread') as thread:self.assertIsNone(self.source.get('Ahri','MIDDLE'));thread.assert_not_called()
if __name__=='__main__':unittest.main()
