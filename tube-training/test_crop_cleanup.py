import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from clean_training_crops import build


class CleanupTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source';(source/'crops').mkdir(parents=True)
        rows=[]
        for name,split,color in [('a','train','blue'),('b','train','green'),('c','val','red')]:
            Image.new('RGB',(30,12),color).save(source/'crops'/f'{name}.png')
            rows.append({'id':name,'crop':f'crops/{name}.png','split':split,'task':'recognition',
                'text':name,'group_id':name,'source_sha256':name})
        (source/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        (source/'val.txt').write_bytes(b'crops/c.png\tc\n')
        return source

    def test_validation_bytes_and_labels_cannot_be_changed_by_recipe(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=self.fixture(root);original=(source/'crops/a.png').read_bytes()
            result=build(source,root/'out',{'a':{'trim':[0,0,.5,1]},'c':{'exclude':'should be ignored'}})
            self.assertEqual(result['validation_crops'],1)
            self.assertEqual((source/'val.txt').read_bytes(),(root/'out/val.txt').read_bytes())
            self.assertEqual((source/'crops/c.png').read_bytes(),(root/'out/crops/c.png').read_bytes())
            self.assertEqual((source/'crops/a.png').read_bytes(),original)

    def test_exclusions_are_audited_and_do_not_delete_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=self.fixture(root)
            result=build(source,root/'out',{'a':{'exclude':'clipped character'}})
            self.assertEqual(result['training_crops'],1)
            self.assertEqual(result['audit'][0]['reason'],'clipped character')
            self.assertTrue((source/'crops/a.png').exists())

    def test_rejects_group_overlap(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=self.fixture(root);file=source/'manifest.jsonl'
            rows=[json.loads(s) for s in file.read_text().splitlines()];rows[-1]['group_id']='a'
            file.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'overlap'):build(source,root/'out',{})


if __name__=='__main__':unittest.main()
