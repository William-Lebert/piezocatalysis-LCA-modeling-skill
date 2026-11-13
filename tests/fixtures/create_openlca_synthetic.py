import sys
from java.io import File
from org.openlca.core.database import Derby, UnitGroupDao, FlowPropertyDao, FlowDao, ProcessDao, ProductSystemDao, ImpactCategoryDao, ImpactMethodDao
from org.openlca.core.model import UnitGroup, FlowProperty, Flow, Process, ProductSystem, ImpactCategory, ImpactMethod
root=File(sys.argv[1])
if root.exists(): raise Exception('fixture path already exists; preserving it')
root.getParentFile().mkdirs();db=Derby(root)
ug=UnitGroupDao(db).insert(UnitGroup.of('Synthetic units of mass','kg'))
prop=FlowPropertyDao(db).insert(FlowProperty.of('Synthetic mass',ug))
product=FlowDao(db).insert(Flow.product('Synthetic treatment service',prop))
emission=FlowDao(db).insert(Flow.elementary('Synthetic emission',prop))
proc=Process.of('Synthetic treatment process',product)
proc.output(emission,2.0)
proc=ProcessDao(db).insert(proc)
ps=ProductSystemDao(db).insert(ProductSystem.of('Synthetic product system',proc))
category=ImpactCategory.of('Synthetic impact','synthetic impact unit');category.factor(emission,1.6);category=ImpactCategoryDao(db).insert(category)
method=ImpactMethod.of('Synthetic LCIA method');method.add(category);method=ImpactMethodDao(db).insert(method)
print('SYSTEM='+ps.refId);print('METHOD='+method.refId);print('UNIT='+ug.referenceUnit.refId);print('PROPERTY='+prop.refId)
print('EXPECTED=3.2 synthetic impact units per 1 kg service');db.close()
