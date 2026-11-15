import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from plot_report import draw

@unittest.skipUnless(importlib.util.find_spec('matplotlib'),'optional matplotlib is not installed')
class PlotReportTests(unittest.TestCase):
 def data(self):
  return {'schema_version':'piezolca.plot-data/1','kind':'stages','title_en':'Synthetic signed contributions','title_zh':'合成贡献','functional_unit':'1 synthetic service',
   'category':{'name':'fictional category','unit':'kg'},'warnings':['Fictional, not a research result.'],'license_note':'Synthetic only.',
   'provenance':{'inputs':{'report':{'name':'fictional.json','sha256':'a'*64}},'generator_sha256':'b'*64},
   'rows':[{'stage':'preparation','contribution':2,'unit':'kg'},{'stage':'treatment','contribution':-2,'unit':'kg'}]}
 def test_svg_png_csv_and_manifest(self):
  with tempfile.TemporaryDirectory() as t:
   dest=Path(t)/'out';manifest=draw(self.data(),dest,'en',None,72)
   for n in ('chart.svg','chart.png','table.csv','plot-data.json','manifest.json'):self.assertTrue((dest/n).is_file())
   svg=(dest/'chart.svg').read_text();self.assertIn('<text',svg);self.assertIn('Fictional, not a research result',svg)
   self.assertEqual((dest/'chart.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n');self.assertEqual(set(manifest['outputs']),{'chart.svg','chart.png','table.csv','plot-data.json'})
   with self.assertRaises(FileExistsError):draw(self.data(),dest,'en',None,72)
 def test_zero_and_null_cycle_values_remain_distinct(self):
  d=self.data();d.update(kind='cycles',data_basis='per cycle',rows=[{'cycle':'1','apparent_removal_mg':0,'removal_lower_mg':0,'removal_upper_mg':0,'treatment_energy_kwh':0}, {'cycle':'2','apparent_removal_mg':None,'removal_lower_mg':1,'removal_upper_mg':2,'treatment_energy_kwh':None}])
  with tempfile.TemporaryDirectory() as t:
   dest=Path(t)/'out';draw(d,dest,'en',None,72);svg=(dest/'chart.svg').read_text();self.assertIn('missing',svg);self.assertIn('Censored interval',svg)
   table=(dest/'table.csv').read_text(encoding='utf-8-sig');self.assertIn('2,,1,2,',table)

if __name__=='__main__':unittest.main()
