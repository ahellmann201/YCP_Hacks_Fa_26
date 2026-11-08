import json
import tempfile
import unittest
from pathlib import Path
from tools.benchmark_threads import select_tubes, summarize


class BenchmarkTests(unittest.TestCase):
    def test_selection_varies_groups_and_excludes_duplicate_photos(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, kind, photos, sample_id in [
                ('a','small',[b'a'],'1'), ('b','large',[b'b',b'c'],'2'),
                ('c','small',[b'd',b'e'],'3'), ('duplicate','small',[b'a'],'1')]:
                folder = root/'uploads'/name
                folder.mkdir(parents=True)
                images = []
                for number, content in enumerate(photos):
                    filename = f'image_{number}.jpg'
                    (folder/filename).write_bytes(content)
                    images.append({'filename':filename})
                (folder/'sample.json').write_text(json.dumps({'images':images}))
                (folder/'ocr.json').write_text(json.dumps({'label_type':kind,'suggestions':{'sample_id':sample_id}}))
            chosen = select_tubes(root, 10)
            self.assertEqual(len(chosen), 3)
            self.assertIn(root/'uploads/b', chosen)
            self.assertIn(root/'uploads/c', chosen)
            self.assertEqual(len({p.name for p in chosen}&{'a','duplicate'}), 1)

    def test_summary_compares_outputs_within_each_tube(self):
        runs = []
        for tube, values in [('a',[20,22]), ('b',[38,40])]:
            for seconds in values:
                runs.append({'tube':tube,'threads':3,'seconds':seconds,'ocr_worker_peak_mib':310,
                             'label_type':'small','suggestions':{'sample_id':tube},'photo_errors':[None]})
        summary, same = summarize(runs, [3])
        self.assertEqual(summary['3']['mean_seconds'], 30)
        self.assertEqual(summary['3']['slowest_tube_mean_seconds'], 39)
        self.assertEqual(summary['3']['tubes_with_mean_under_30s'], 1)
        self.assertTrue(same)
        runs[-1]['suggestions']={'sample_id':'changed'}
        self.assertFalse(summarize(runs, [3])[1])
        self.assertIsNone(summarize(runs[:1], [3])[1])


if __name__ == '__main__':
    unittest.main()
