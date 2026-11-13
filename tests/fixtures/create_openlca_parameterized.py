# Jython fixture: entirely fictional parameters, processes and LCIA factor.
import sys
from java.io import File
from org.openlca.core.database import Derby, UnitGroupDao, FlowPropertyDao, FlowDao, ProcessDao, ProductSystemDao, ImpactCategoryDao, ImpactMethodDao
from org.openlca.core.model import UnitGroup, FlowProperty, Flow, Process, ProductSystem, ImpactCategory, ImpactMethod, Parameter
root=File(sys.argv[1])
if root.exists(): raise Exception('fixture exists; preserving it')
root.getParentFile().mkdirs()
db=Derby(root)
try:
 ug=UnitGroupDao(db).insert(UnitGroup.of('Synthetic mass units','kg'))
 prop=FlowPropertyDao(db).insert(FlowProperty.of('Synthetic mass',ug))
 product=FlowDao(db).insert(Flow.product('Synthetic service',prop))
 emission=FlowDao(db).insert(Flow.elementary('Synthetic emission',prop))
 proc=Process.of('Synthetic parametric process',product)
 proc.parameters.add(Parameter.process('power',2.0))
 proc.parameters.add(Parameter.process('hours',1.0))
 proc.parameters.add(Parameter.process('reuse',2.0))
 exchange=proc.output(emission,3.0);exchange.formula='power*hours+2/reuse'
 proc=ProcessDao(db).insert(proc)
 ps=ProductSystemDao(db).insert(ProductSystem.of('Synthetic parametric system',proc))
 category=ImpactCategory.of('Synthetic impact','synthetic impact unit');category.factor(emission,1.6);category=ImpactCategoryDao(db).insert(category)
 method=ImpactMethod.of('Synthetic method');method.add(category);method=ImpactMethodDao(db).insert(method)
 print('SYSTEM='+ps.refId);print('PROCESS='+proc.refId);print('METHOD='+method.refId);print('UNIT='+ug.referenceUnit.refId);print('PROPERTY='+prop.refId)
finally: db.close()
