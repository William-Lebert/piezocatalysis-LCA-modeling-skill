# Jython fixture: build a fictional one-service model from a functional-unit CSV.
import csv,json,sys
from java.io import File
from org.openlca.core.database import Derby,UnitGroupDao,FlowPropertyDao,FlowDao,ProcessDao,ProductSystemDao,ImpactCategoryDao,ImpactMethodDao
from org.openlca.core.model import UnitGroup,FlowProperty,Flow,Process,ProductSystem,ImpactCategory,ImpactMethod,Parameter
root=File(sys.argv[1]);inventory=sys.argv[2]
if root.exists():raise Exception('fixture already exists')
root.getParentFile().mkdirs()
rows=[]
with open(inventory,'r') as f:
 for r in csv.DictReader(f):
  if r['included']=='true':rows.append(r)
if not rows:raise Exception('empty synthetic inventory')
groups={}
for r in rows:
 key=(r['flow_name'],r['unit'],r['direction'])
 groups[key]=groups.get(key,0.0)+float(r['amount'])
db=Derby(root)
try:
 ugdao=UnitGroupDao(db);fdao=FlowDao(db);pdao=ProcessDao(db)
 units={}
 for u in sorted(set(k[1] for k in groups)|set(['service'])):
  group=ugdao.insert(UnitGroup.of('Synthetic cycle units '+u,u));prop=FlowPropertyDao(db).insert(FlowProperty.of('Synthetic cycle property '+u,group));units[u]=(group,prop)
 service=fdao.insert(Flow.product('Synthetic cycle treatment service',units['service'][1]))
 foreground=Process.of('Synthetic cycle treatment foreground',service)
 foreground.parameters.add(Parameter.process('ultrasound_scale',1.0))
 impact=ImpactCategory.of('Synthetic cycle impact','synthetic score');providers=[];chosen=None
 for (name,unit,direction),amount in sorted(groups.items()):
  prop=units[unit][1]
  elementary=fdao.insert(Flow.elementary('Synthetic cycle emission '+direction+' '+name+' '+unit,prop))
  impact.factor(elementary,1.6)
  if direction=='input':
   product=fdao.insert(Flow.product('Synthetic cycle supply '+name+' '+unit,prop))
   provider=Process.of('Synthetic cycle provider '+name+' '+unit,product);provider.output(elementary,1.0);provider=pdao.insert(provider);providers.append(provider)
   exchange=foreground.input(product,amount);exchange.defaultProviderId=provider.id
   if name=='ultrasound electricity':exchange.formula=str(amount)+'*ultrasound_scale';chosen=provider
  else:foreground.output(elementary,amount)
 foreground=pdao.insert(foreground)
 system=ProductSystem.of('Synthetic cyclic workflow',foreground)
 for provider in providers:system.link(provider,foreground)
 system=ProductSystemDao(db).insert(system)
 impact=ImpactCategoryDao(db).insert(impact);method=ImpactMethod.of('Synthetic cycle method');method.add(impact);method=ImpactMethodDao(db).insert(method)
 if chosen is None or len(system.processLinks)!=len(providers):raise Exception('missing supply link')
 print('RESULT_JSON='+json.dumps({'system':system.refId,'process':foreground.refId,'unit':units['service'][0].referenceUnit.refId,'property':units['service'][1].refId,'method':method.refId,'category':impact.refId,'provider':chosen.refId,'input_count':len(providers),'links':len(system.processLinks),'expected_baseline':sum(groups.values())*1.6,'expected_power_delta':groups[('ultrasound electricity','kWh','input')]*1.6}))
finally:db.close()
