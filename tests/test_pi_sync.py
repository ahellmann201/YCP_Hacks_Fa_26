import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
BASH=str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Git/bin/bash.exe') if os.name=='nt' else shutil.which('bash')


@unittest.skipUnless(shutil.which('git') and BASH and Path(BASH).is_file(),'Git and Bash required')
class PiSyncTests(unittest.TestCase):
    def test_sync_preserves_runtime_state_and_backs_up_code(self):
        with tempfile.TemporaryDirectory(dir=BASE) as temporary:
            root=Path(temporary).resolve()
            self.assertEqual(root.parent,BASE)
            def git(*args):
                result=subprocess.run(['git','-c','user.name=Sync Test','-c','user.email=sync@example.invalid',*args],
                                      cwd=root,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                return result.stdout.strip()
            git('init','-b','Andrew')
            (root/'.gitignore').write_text('.venv*/\nuploads/\n')
            (root/'main.py').write_text('old source')
            git('add','.');git('commit','-m','old');git('switch','-c','training')
            (root/'main.py').write_text('new training source')
            (root/'crop_adjustments.py').write_text('new training helper')
            (root/'.gitignore').write_text((BASE/'.gitignore').read_text())
            git('add','.');git('commit','-m','training')
            git('update-ref','refs/remotes/origin/training','HEAD')
            git('remote','add','origin','https://github.com/ahellmann201/YCP_Hacks_Fa_26.git')
            git('switch','Andrew')
            (root/'main.py').write_text('local modified source');git('add','main.py')
            (root/'crop_adjustments.py').write_text('local untracked helper')
            (root/'benchmark_threads.py').write_text('old untracked benchmark')
            protected={'scanner.sqlite3':'db','scanner.sqlite3-wal':'wal','.env':'placeholder',
                'benchmark-results.json':'results','uploads/tube/image.jpg':'photo','.venv-ocr/bin/python':'environment'}
            for name,content in protected.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
            result=subprocess.run([BASH,str(BASE/'scripts/sync_pi.sh'),'--cached'],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for name,content in protected.items():
                self.assertEqual((root/name).read_text(),content)
            self.assertEqual(git('branch','--show-current'),'training')
            self.assertEqual((root/'main.py').read_text(),'new training source')
            self.assertEqual((root/'crop_adjustments.py').read_text(),'new training helper')
            self.assertFalse((root/'benchmark_threads.py').exists())
            self.assertEqual(git('show','stash:main.py'),'local modified source')
            self.assertEqual(git('show','stash^3:crop_adjustments.py'),'local untracked helper')
            self.assertTrue(git('branch','--list','backup/pi-*'))


if __name__=='__main__':
    unittest.main()
