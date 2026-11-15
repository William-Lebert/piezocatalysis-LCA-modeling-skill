"""Synthetic handoff checks preserve FU basis, provenance and mapping gaps."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];SKILL=ROOT/'piezocatalysis-lca-modeling';SCRIPTS=SKILL/'scripts';EXAMPLES=SKILL/'assets/examples'
sys.path.insert(0,str(SCRIPTS))
from inventory_handoff import load_handoff


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        self.mapping=self.path/'mapping.csv';shutil.copy2(EXAMPLES/'synthetic-handoff/mapping.csv',self.mapping)
    def generate(self,name):
        output=self.path/(name+'.csv');source=EXAMPLES/'synthetic-cycles'/(name+'.json')
        result=subprocess.run([sys.executable,str(SCRIPTS/'cyclic_foreground.py'),str(source),'--inventory-csv',str(output)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);return output,json.loads(result.stdout)
    def assignments(self,name):
        return EXAMPLES/'synthetic-handoff'/('assignments-'+name+'.csv')
    def report(self,path,assign):
        return load_handoff(path,path.with_name(path.name+'.manifest.json'),self.mapping,assign)
    def change_mapping(self,id,key,value):
        with self.mapping.open(newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
        next(x for x in rows if x['mapping_id']==id)[key]=value
        with self.mapping.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    def test_constant_and_variable_keep_fu_amounts_and_mapping_states(self):
        for name,assign,precursor in [('constant','constant',10.0),('variable-exact','variable',5.2)]:
            with self.subTest(name=name):
                path,cycle=self.generate(name);r=self.report(path,self.assignments(assign));byid={x['activity_id']:x for x in r['rows']}
                self.assertEqual(r['amount_basis'],'per_functional_unit')
                self.assertEqual(byid['precursor']['amount_per_functional_unit'],precursor)
                self.assertAlmostEqual(byid['precursor']['dataset_amount_per_functional_unit'],precursor/1000)
                self.assertEqual(byid['precursor']['mapping_type'],'proxy')
                self.assertEqual(byid['prep-electricity']['mapping_type'],'exact')
                self.assertEqual(byid['ultrasound-1']['cycle_id'],'1')
                self.assertEqual(byid['clean-water-1']['mapping_type'],'unmapped')
                self.assertIsNone(byid['clean-water-1']['dataset_amount_per_functional_unit'])
                self.assertEqual(byid['final-recovered-catalyst']['mapping_type'],'awaiting_disposal_mapping')
                self.assertEqual(r['summary']['status'],'needs_review')
                self.assertEqual(r['input_sha256'],hashlib.sha256((EXAMPLES/'synthetic-cycles'/(name+'.json')).read_bytes()).hexdigest())
                self.assertEqual(r['inventory_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(r['generator_version'],'1.0.0')
                self.assertEqual(r['code_sha256']['cyclic_foreground.py'],hashlib.sha256((SCRIPTS/'cyclic_foreground.py').read_bytes()).hexdigest())
                with path.open(newline='') as f:csvrows=list(csv.DictReader(f))
                self.assertTrue(all(x['amount_basis']=='per_functional_unit' and x['inventory_schema_version']=='piezolca.inventory/2' for x in csvrows))
                if name=='variable-exact':self.assertTrue(any('losses are unaccounted' in x for x in r['model_warnings']))
    def test_marked_functional_unit_inventory_cannot_be_rescaled_even_with_reference(self):
        for name in ('constant','variable-exact'):
            with self.subTest(name=name):
                path,cycle=self.generate(name)
                with path.open(newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
                ref=dict.fromkeys(fields,'');ref.update(system=cycle['system'],stage='preparation',flow_name='dry catalyst',amount='5',unit='g',direction='output',evidence_class='scenario',source='fictional',included='true',activity_id='fake-ref',inventory_schema_version='piezolca.inventory/2',amount_basis='per_functional_unit');rows.append(ref)
                with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
                legacy=EXAMPLES/'synthetic-treatment'
                p=subprocess.run([sys.executable,str(SCRIPTS/'audit_and_scale_inventory.py'),'--inventory',str(path),'--mapping',str(legacy/'dataset_mapping.csv'),'--parameters',str(legacy/'parameters.json'),'--system',cycle['system'],'--reference-flow','dry catalyst'],capture_output=True,text=True)
                self.assertNotEqual(p.returncode,0);self.assertIn('already scaled per functional unit',p.stderr)
    def test_wrong_units_and_direction_block_mapped_amount(self):
        path,_=self.generate('constant');self.change_mapping('map-precursor','dataset_unit','L');self.change_mapping('map-waste','reference_is_input','false')
        rows={x['activity_id']:x for x in self.report(path,self.assignments('constant'))['rows']}
        self.assertIn('unit_conversion_unverified',rows['precursor']['issues']);self.assertIsNone(rows['precursor']['dataset_amount_per_functional_unit'])
        self.assertIn('reference_direction_mismatch',rows['clean-waste-1']['issues']);self.assertIsNone(rows['clean-waste-1']['dataset_amount_per_functional_unit'])
    def test_manifest_hash_detects_csv_change(self):
        path,_=self.generate('constant');path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'SHA-256'):self.report(path,self.assignments('constant'))
    def test_censored_and_missing_values_never_become_zero(self):
        path,_=self.generate('variable-censored');r=self.report(path,self.assignments('variable'))
        self.assertTrue(all(x['amount_per_functional_unit'] is None for x in r['rows']))
        self.assertTrue(all(x['dataset_amount_per_functional_unit'] is None for x in r['rows']))
        self.assertTrue(any('amount_unknown' in x['issues'] for x in r['rows']))
        self.assertTrue(any('Exact positive campaign removal unavailable' in x for x in r['model_warnings']))
    def test_missing_or_invalid_reference_is_not_approved(self):
        path,_=self.generate('constant');self.change_mapping('map-precursor','process_uuid','');self.change_mapping('map-precursor','review_status','reviewed')
        r=self.report(path,self.assignments('constant'));p=next(x for x in r['rows'] if x['activity_id']=='precursor')
        self.assertIn('process_uuid_unverified',p['issues']);self.assertEqual(r['summary']['status'],'needs_review')

    def test_unrecognized_mapping_id_is_visible_without_invented_amount(self):
        path,_=self.generate('constant');assign=self.path/'assignment.csv';assign.write_text('activity_id,mapping_id\nprecursor,absent\n')
        row=next(x for x in self.report(path,assign)['rows'] if x['activity_id']=='precursor')
        self.assertEqual(row['mapping_type'],'mapping_not_found');self.assertIsNone(row['dataset_amount_per_functional_unit'])
    def test_manifest_or_inventory_collision_does_not_overwrite(self):
        path=self.path/'output.csv';sidecar=path.with_name(path.name+'.manifest.json');sidecar.write_text('existing')
        p=subprocess.run([sys.executable,str(SCRIPTS/'cyclic_foreground.py'),str(EXAMPLES/'synthetic-cycles/constant.json'),'--inventory-csv',str(path)],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0);self.assertEqual(sidecar.read_text(),'existing');self.assertFalse(path.exists())
    def test_unknown_assignment_and_modified_basis_rejected(self):
        path,_=self.generate('constant');assign=self.path/'assignment.csv';assign.write_text('activity_id,mapping_id\nmissing,map-precursor\n')
        with self.assertRaisesRegex(ValueError,'unknown or duplicate'):self.report(path,assign)
        # A forged but internally paired manifest must still not authorize a non-FU row.
        text=path.read_text().replace('per_functional_unit','per_batch_or_run',1);path.write_text(text)
        sidecar=path.with_name(path.name+'.manifest.json');data=json.loads(sidecar.read_text());data['inventory_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();sidecar.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'conflicting schema or basis'):self.report(path,None)

    def test_excluded_activity_retains_reason_and_does_not_require_mapping(self):
        source=json.loads((EXAMPLES/'synthetic-cycles/constant.json').read_text())
        source['cycles'][0]['activities'][1].update(included=False,note='outside synthetic boundary')
        inp=self.path/'excluded.json';inp.write_text(json.dumps(source));output=self.path/'excluded.csv'
        run=subprocess.run([sys.executable,str(SCRIPTS/'cyclic_foreground.py'),str(inp),'--inventory-csv',str(output)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        report=self.report(output,self.assignments('constant'))
        row=next(x for x in report['rows'] if x['activity_id']=='clean-water-1')
        self.assertEqual(row['mapping_type'],'excluded');self.assertFalse(row['included'])
        self.assertEqual(row['note'],'outside synthetic boundary');self.assertIsNone(row['dataset_amount_per_functional_unit'])

    def test_volume_to_mass_requires_explicit_sourced_density(self):
        path,_=self.generate('constant')
        with self.mapping.open(newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
        fields += ['conversion_type','density_kg_per_l','density_source','density_evidence_class']
        m=dict(rows[0],mapping_id='map-water',foreground_flow='cleaning water',foreground_unit='L',dataset_unit='kg',conversion_factor='1',
               conversion_type='density',density_kg_per_l='1',density_source='fictional density',density_evidence_class='scenario')
        rows.append(m)
        with self.mapping.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        assign=self.path/'density.csv';assign.write_text('activity_id,mapping_id\nclean-water-1,map-water\n')
        row=next(x for x in self.report(path,assign)['rows'] if x['activity_id']=='clean-water-1')
        self.assertEqual(row['dataset_amount_per_functional_unit'],1)
        self.change_mapping('map-water','density_source','')
        row=next(x for x in self.report(path,assign)['rows'] if x['activity_id']=='clean-water-1')
        self.assertIn('unit_conversion_unverified',row['issues']);self.assertIsNone(row['dataset_amount_per_functional_unit'])

if __name__=='__main__':unittest.main()
