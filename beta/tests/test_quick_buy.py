import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import Mock, patch

from desktop.quick_buy import QuickBuyReader, detect_item, remaining_price
from desktop.live_overlays import live_cards
import test_voice as voice


class QuickBuyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cv2
        import numpy as np
        from PIL import Image
        cls.root=Path(__file__).parent/'fixtures/quick-buy'
        cls.templates={int(p.stem):cv2.cvtColor(np.asarray(Image.open(p).convert('RGB')),cv2.COLOR_RGB2GRAY)
                       for p in cls.root.glob('*.png') if p.stem.isdigit()}

    def image(self,name,w=3440,h=1440):
        from PIL import Image
        image=Image.new('RGB',(w,h));scale=h/1440
        with Image.open(self.root/(name+'-hud.png')) as source:
            hud=source.resize((round(source.width*scale),round(source.height*scale)))
        image.paste(hud,(round(w/2+180*scale),round(1280*scale)))
        return image

    def test_real_hud_item_changes_and_standard_screen_sizes(self):
        for name,expected in [('collector',6676),('phantom-dancer',3046)]:
            for w,h in [(3440,1440),(1920,1080),(1920,1440)]:
                with self.subTest(name=name,size=(w,h)):
                    result=detect_item(self.image(name,w,h),self.templates)
                    self.assertEqual(result['item'],expected)
                    self.assertGreaterEqual(result['confidence'],.78)

    def test_blank_or_ambiguous_face_never_becomes_a_purchase_hint(self):
        from PIL import Image,ImageDraw
        self.assertIsNone(detect_item(Image.new('RGB',(1920,1080)),self.templates))
        image=self.image('collector')
        ImageDraw.Draw(image).rectangle((2095,1390,2141,1438),fill='black')
        self.assertIsNone(detect_item(image,self.templates))
        duplicated=dict(self.templates);duplicated[9999]=duplicated[6676]
        self.assertIsNone(detect_item(self.image('collector'),duplicated))

    def test_reader_requires_confirmation_discards_old_match_and_clears_missing_item(self):
        reader=QuickBuyReader();reader.executor.shutdown(wait=True)
        reader.executor=Mock();reader.executor.submit.side_effect=lambda *a:Future();self.addCleanup(reader.close)
        reader.templates=self.templates;reader.version='16.23.1'
        catalog={'patch':'16.23.1','items':{}}
        context=(0,0,3440,1440),(0,1),'16.23.1'
        result={'item':6676,'confidence':.9,'source':'screen'}
        def complete(value,stamp=10):
            done=Future();done.set_result(value);reader.job=context,'capture',done
            with patch('desktop.quick_buy.monotonic',return_value=stamp):
                return reader.poll(context[0],context[1],catalog)
        self.assertNotEqual(complete(result)['state'],'ready')
        self.assertEqual(complete(result,11)['item'],6676)
        with patch('desktop.quick_buy.monotonic',return_value=12):
            self.assertNotEqual(reader.poll(context[0],(0,2),catalog)['state'],'ready')
        self.assertNotEqual(complete(None,13)['state'],'ready')

    def test_component_credit_is_counted_once_and_unknown_recipe_is_hidden(self):
        items={'1':{'g':100},'2':{'g':250,'from':['1','1']},'3':{'g':600,'from':['2','2']}}
        self.assertEqual(remaining_price(3,[1],items),500)
        self.assertEqual(remaining_price(3,[2,1],items),250)
        self.assertEqual(remaining_price(3,[2,2],items),100)
        self.assertEqual(remaining_price(3,[3],items),600) # Buying an additional copy.
        self.assertIsNone(remaining_price(3,[],{'3':{'g':600,'from':['missing']}}))
        self.assertIsNone(remaining_price(3,[],{'3':{'g':600,'from':['3']}}))

    def test_loader_merges_only_truly_equivalent_internal_item_ids(self):
        import json,tempfile
        from PIL import Image
        from desktop.quick_buy import load_templates
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'16.23.1';root.mkdir()
            with Image.open(self.root/'6676.png') as icon:icon.save(root/'item0.png')
            item={'name':'Сборщик долгов','gold':{'total':3000},'from':['1037'],
                  'image':{'sprite':'item0.png','x':0,'y':0,'w':48,'h':48}}
            data={'6676':item,'667666':item,'9999':{**item,'gold':{'total':4000}}}
            (root/'items.json').write_text(json.dumps({'version':'16.23.1','data':data}),encoding='utf-8')
            result=load_templates('16.23.1',tuple(data),folder)
            self.assertEqual(set(result),{6676,9999})
            self.assertIsNone(detect_item(self.image('collector'),result))

    def test_purchase_uses_queued_item_without_fallback_to_build(self):
        catalog={**voice.CATALOG,'items':{'6676':{'g':3000,'n':'Сборщик долгов','from':['1037']},'1037':{'g':875}}}
        raw=voice.snapshot(gold=500,items=(1037,))
        build={'items':[{'id':3046,'name':'Другой предмет сборки'}]}
        self.assertNotIn('purchase',live_cards(raw,catalog,'TOP',build))
        cards=live_cards(raw,catalog,'TOP',build,{'state':'ready','item':6676,'confidence':.9})
        self.assertEqual(cards['purchase']['visual']['item'],6676)
        self.assertEqual(cards['purchase']['visual']['remaining'],2125)
        self.assertEqual(cards['purchase']['visual']['price'],1625)
        self.assertEqual(cards['purchase']['visual']['source'],'quick_buy')


if __name__=='__main__':unittest.main()
