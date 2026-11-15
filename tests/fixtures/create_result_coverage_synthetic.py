# Jython: fully fictional database for result coverage and cancellation.
import sys
from java.io import File
from org.openlca.core.database import Derby, UnitGroupDao, FlowPropertyDao, FlowDao, ProcessDao, ProductSystemDao, ImpactCategoryDao, ImpactMethodDao
from org.openlca.core.model import UnitGroup, FlowProperty, Flow, Process, ProductSystem, ImpactCategory, ImpactMethod
root=File(sys.argv[1])
if root.exists():raise Exception('fixture path already exists')
root.getParentFile().mkdirs();db=Derby(root)
try:
 ug=UnitGroupDao(db).insert(UnitGroup.of('Synthetic mass unit','kg'));prop=FlowPropertyDao(db).insert(FlowProperty.of('Synthetic mass',ug));fd=FlowDao(db);pd=ProcessDao(db)
 emission=fd.insert(Flow.elementary('Synthetic cancellation emission',prop));missing=fd.insert(Flow.elementary('Synthetic uncharacterized emission',prop));waste=fd.insert(Flow.waste('Synthetic unlinked waste',prop))
 services=[fd.insert(Flow.product('Synthetic component '+x,prop)) for x in ('positive','negative')]
 providers=[]
 for name,flow,amount in [('positive',services[0],1),('negative',services[1],-1)]:
  p=Process.of('Synthetic '+name,flow);p.output(emission,amount);p=pd.insert(p);providers.append(p)
 finalflow=fd.insert(Flow.product('Synthetic final service',prop));rootp=Process.of('Synthetic final',finalflow)
 for p in providers:
  e=rootp.input(p.quantitativeReference.flow,1);e.defaultProviderId=p.id
 rootp.output(missing,1);rootp.output(waste,1);rootp=pd.insert(rootp)
 system=ProductSystem.of('Synthetic offsetting system',rootp)
 for p in providers:system.link(p,rootp)
 system=ProductSystemDao(db).insert(system)
 c=ImpactCategory.of('Synthetic cancelling impact','synthetic units');c.factor(emission,1);c=ImpactCategoryDao(db).insert(c)
 z=ImpactCategory.of('Synthetic explicit zero impact','synthetic units');z.factor(emission,0);z=ImpactCategoryDao(db).insert(z)
 m=ImpactMethod.of('Synthetic two-category method');m.add(c);m.add(z);m=ImpactMethodDao(db).insert(m)
 for key,val in [('SYSTEM',system.refId),('METHOD',m.refId),('UNIT',ug.referenceUnit.refId),('PROPERTY',prop.refId),('CANCEL',c.refId),('ZERO',z.refId),('EMISSION',emission.refId),('MISSING',missing.refId)]:print(key+'='+val)
finally:db.close()
