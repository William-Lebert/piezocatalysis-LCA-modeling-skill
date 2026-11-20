#!/usr/bin/env python3
"""Build a traceable per-functional-unit foreground for piezocatalytic H2O2."""
import argparse,csv,hashlib,io,json,math,sys
from pathlib import Path
from audit_and_scale_inventory import UNITS,scaled_product,unit_factor
from cyclic_foreground import activity
from experimental_foreground import CANONICAL,CSV_FIELDS,quantity,units_for


# Published inventory bases can be scaled while their physical product definition remains open.
PRODUCT_BASES = ('net_accumulated', 'recovered_product', 'reported_production')


def build(data):
    if not isinstance(data,dict) or any(not isinstance(data.get(k),str) or not data[k].strip() for k in ('system','boundary')):
        raise ValueError('system and boundary are required')
    basis = data.get('product_basis')
    if basis not in PRODUCT_BASES:
        raise ValueError('product_basis must be one of ' + ', '.join(PRODUCT_BASES))
    if not isinstance(data.get('product_definition'),str) or not data['product_definition'].strip():
        raise ValueError('product_definition must describe measurement and correction of external inputs')
    if data.get('catalyst_mass_basis')!='dry':raise ValueError('catalyst_mass_basis must be dry; wet mass requires an explicit conversion')
    mass=units_for('mass')
    target=quantity(data.get('functional_unit'),'functional_unit',mass,positive=True)
    product_field = 'reported_product_per_campaign' if basis == 'reported_production' else 'net_product_per_campaign'
    if basis == 'reported_production' and 'net_product_per_campaign' in data:
        raise ValueError('use reported_product_per_campaign for a literature production basis')
    product = quantity(data.get(product_field), product_field, mass, allow_missing=True)
    fresh=quantity(data.get('fresh_catalyst_per_campaign'),'fresh_catalyst_per_campaign',mass,allow_missing=True)
    yield_g=quantity(data.get('dry_yield'),'dry_yield',mass,positive=True,allow_missing=True)
    if data.get('catalyst_destination') not in ('unknown','retained','disposed'):
        raise ValueError('catalyst_destination must be unknown, retained or disposed')
    prep=data.get('preparation_activities');campaign=data.get('campaign_activities')
    if not isinstance(prep,list) or not prep or not isinstance(campaign,list) or not campaign:
        raise ValueError('preparation_activities and campaign_activities must be nonempty lists')
    ids=set();groups=set()
    acts=[activity(a,'preparation',None,ids,groups) for a in prep]+[activity(a,'treatment',None,ids,groups) for a in campaign]
    scale=None if product is None or product<=0 else target/product
    prep_scale=None if scale is None or fresh is None or yield_g is None else scale*fresh/yield_g
    if any(x is not None and not math.isfinite(x) for x in (scale,prep_scale)):raise ValueError('nonfinite scaling')
    rows=[]
    for a in acts:
        factor=prep_scale if a['stage']=='preparation' else scale
        u=CANONICAL[UNITS[a['unit']][0]]
        value=None if a['value'] is None or factor is None else scaled_product(a['value'],factor*unit_factor(a['unit'],u),a['activity_id'])
        rows.append({**a,'campaign_value':a['value'],'campaign_unit':a['unit'],'amount':value,'unit':u})
    warnings=[]
    if scale is None:warnings.append('The H2O2 product amount is missing or zero; functional-unit scaling is unavailable.')
    if prep_scale is None:warnings.append('Catalyst preparation allocation is unavailable; missing fresh catalyst, dry yield or product amount.')
    if data['catalyst_destination']=='unknown':warnings.append('Final catalyst destination is unknown.')
    if data['catalyst_destination']=='disposed':
        disposal_id=data.get('catalyst_disposal_activity_id')
        if not any(a['activity_id']==disposal_id and a['direction']=='output' and a['kind']=='waste' and a['included'] for a in acts):
            warnings.append('Catalyst disposal was declared but no identified catalyst waste output activity was provided.')
    if any(r['included'] and r['amount'] is None for r in rows):warnings.append('Some included inventory amounts remain unknown.')
    warnings.append('Product basis is declared by the researcher; net accumulation may exclude H2O2 consumed in situ and is not automatically equivalent to recovered or delivered product.')
    if basis == 'reported_production':
        warnings.append('Literature production basis requires review before comparison with net accumulation or recovered product.')
    product_grams_field = 'reported_h2o2_g' if basis == 'reported_production' else 'net_h2o2_g'
    return {'system':data['system'],'boundary':data['boundary'],'functional_unit_type':'h2o2_product',
            'functional_unit':data['functional_unit'],'product_basis':data['product_basis'],
            'product_definition':data['product_definition'],
            'campaign':{product_grams_field:product,'target_h2o2_g':target,'campaigns_per_functional_unit':scale,
                        'fresh_catalyst_g':fresh,'dry_yield_g_per_preparation_batch':yield_g,
                        'preparation_batches_per_functional_unit':prep_scale,'catalyst_destination':data['catalyst_destination'],
                        'allocation_note':'All stated fresh dry catalyst is allocated to this campaign; no residual credit is assumed.'},
            'functional_unit_flows':rows,'warnings':warnings}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--inventory-csv',type=Path);a=p.parse_args()
    try:
        raw=a.input.read_bytes();data=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid JSON number '+x)));r=build(data)
        if a.inventory_csv:
            manifest_path=a.inventory_csv.with_name(a.inventory_csv.name+'.manifest.json')
            if a.inventory_csv.exists() or manifest_path.exists():raise FileExistsError('inventory or manifest already exists')
            with io.StringIO(newline='') as out:
                w=csv.DictWriter(out,fieldnames=CSV_FIELDS+['cycle_id','inventory_schema_version','amount_basis']);w.writeheader()
                for row in r['functional_unit_flows']:
                    w.writerow({'system':r['system'],'stage':row['stage'],'flow_name':row['flow_name'],'amount':row['amount'],
                      'unit':row['unit'],'direction':row['direction'],'evidence_class':row['evidence_class'],'source':row['source'],
                      'dataset_mapping':row['dataset_mapping'],'included':str(row['included']).lower(),'note':row['note'],
                      'activity_id':row['activity_id'],'overlap_group':row['overlap_group'],'cycle_id':'',
                      'inventory_schema_version':'piezolca.inventory/2','amount_basis':'per_functional_unit'})
                content=out.getvalue().encode('utf-8')
            scripts=Path(__file__).parent
            manifest={'schema_version':'piezolca.inventory-manifest/1','inventory_schema_version':'piezolca.inventory/2',
              'amount_basis':'per_functional_unit','inventory_sha256':hashlib.sha256(content).hexdigest(),'input_sha256':hashlib.sha256(raw).hexdigest(),
              'input_name':a.input.name,'generator':'h2o2_foreground','generator_version':'1.0.0',
              'code_sha256':{n:hashlib.sha256((scripts/n).read_bytes()).hexdigest() for n in ('h2o2_foreground.py','cyclic_foreground.py','experimental_foreground.py','audit_and_scale_inventory.py','validate_inventory.py')},
              'system':r['system'],'boundary':r['boundary'],'functional_unit_type':r['functional_unit_type'],
              'functional_unit':r['functional_unit'],'product_basis':r['product_basis'],'product_definition':r['product_definition'],
              'scaling':{'campaigns_per_functional_unit':r['campaign']['campaigns_per_functional_unit'],'allocation_note':r['campaign']['allocation_note']},
              'campaign':{'catalyst_mass_basis':'dry','final_recovered_destination':r['campaign']['catalyst_destination'],'loss_g_by_cycle':[]},'warnings':r['warnings']}
            with a.inventory_csv.open('xb') as f:f.write(content)
            with manifest_path.open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
        print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as e:
        print('ERROR:',e,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
