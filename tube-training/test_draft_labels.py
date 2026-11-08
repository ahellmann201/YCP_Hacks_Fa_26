import tempfile
import unittest
from pathlib import Path
from PIL import Image
from dataset import write, load
from draft_labels import approve


class DraftTests(unittest.TestCase):
    def fixture(self, root):
        identifier = 'a' * 32
        write(root / 'manifest.json', [{'image_id':'photo','tube_id':'tube_001'}])
        write(root / 'tube_meta.json', {'tube_001':{
            'label_type':'small','group_id':'tube_001','split':'train'}})
        write(root / 'annotations.json', [
            {'id':'old','tube_id':'tube_001','image_id':'photo','field':'machine',
             'text':'OLD','status':'verified'},
            {'id':'keep','tube_id':'tube_001','image_id':'photo','field':'date_sampled',
             'text':'9-26','status':'verified'},
        ])
        write(root / 'draft_annotations.json', [{
            'id':identifier,'tube_id':'tube_001','image_id':'photo','field':'machine',
            'rotation':0,'box':[0,0,100,40],'review_status':'needs_review',
        }])
        (root / 'draft-crops').mkdir()
        Image.new('RGB',(100,40),'white').save(root / 'draft-crops' / (identifier+'.png'))
        return identifier

    def test_explicit_review_required(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root=Path(temporary)
            identifier=self.fixture(root)
            with self.assertRaisesRegex(ValueError,'Check the full crop'):
                approve(root,{'id':identifier,'status':'verified','text':'UP123'})
            self.assertEqual(len(load(root / 'annotations.json',[])),2)

    def test_replace_and_archive_without_duplication(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root=Path(temporary)
            identifier=self.fixture(root)
            request={'id':identifier,'status':'verified','text':'UP123','human_checked':True}
            approve(root,request)
            approve(root,request)
            rows=load(root / 'annotations.json',[])
            self.assertEqual(len(rows),2)
            self.assertEqual(sum(r['field']=='machine' for r in rows),1)
            self.assertEqual(len(load(root / 'annotation_history.json',[])),1)
            self.assertTrue((root / 'crops' / (identifier+'.png')).is_file())

    def test_uncertain_stays_uncertain(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root=Path(temporary)
            identifier=self.fixture(root)
            result=approve(root,{'id':identifier,'status':'uncertain','text':'UP???'})
            self.assertEqual(result['status'],'uncertain')


if __name__=='__main__':
    unittest.main()
