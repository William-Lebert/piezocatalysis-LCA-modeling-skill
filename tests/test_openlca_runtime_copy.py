"""Runtime copy excludes only known mutable GUI caches."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from openlca_local_launch import copy_runtime_bundle


class RuntimeCopyTests(unittest.TestCase):
    def test_copy_excludes_caches_but_retains_signed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); app=root/'source.app'; dst=root/'runtime.app'
            cfg=app/'Contents/Eclipse/configuration'; cfg.mkdir(parents=True)
            (cfg/'config.ini').write_text('original')
            (cfg/'org.eclipse.osgi').mkdir(); (cfg/'org.eclipse.osgi/cache').write_text('cache')
            mac=app/'Contents/MacOS'; mac.mkdir(parents=True)
            (mac/'openLCA').write_text('signed'); (mac/'derby.log').write_text('log')
            (mac/'other').write_text('must remain for signature check')
            copy_runtime_bundle(app,dst,copy_function=shutil.copy2)
            self.assertEqual((dst/'Contents/Eclipse/configuration/config.ini').read_text(),'original')
            self.assertFalse((dst/'Contents/Eclipse/configuration/org.eclipse.osgi').exists())
            self.assertFalse((dst/'Contents/MacOS/derby.log').exists())
            self.assertTrue((dst/'Contents/MacOS/other').exists())
            self.assertTrue((cfg/'org.eclipse.osgi/cache').exists())


if __name__=='__main__': unittest.main()
