"""Build the fictional guard fixture, with optional distinct linked suppliers."""
import sys
from java.io import File
from org.openlca.core.database import (Derby, FlowDao, FlowPropertyDao, ImpactCategoryDao,
                                      ImpactMethodDao, ProcessDao, ProductSystemDao, UnitGroupDao)
from org.openlca.core.model import (Flow, FlowProperty, ImpactCategory, ImpactMethod,
                                   Process, ProductSystem, UnitGroup)

root = File(sys.argv[1])
if root.exists():
    raise ValueError('fixture path already exists; preserving it')
provider_count = int(sys.argv[2]) if len(sys.argv) > 2 else 0
root.getParentFile().mkdirs()
db = Derby(root)
try:
    units = UnitGroupDao(db).insert(UnitGroup.of('Synthetic units of mass', 'kg'))
    prop = FlowPropertyDao(db).insert(FlowProperty.of('Synthetic mass', units))
    flows = FlowDao(db)
    processes = ProcessDao(db)
    product = flows.insert(Flow.product('Synthetic treatment service', prop))
    emission = flows.insert(Flow.elementary('Synthetic emission', prop))
    process = Process.of('Synthetic treatment process', product)
    process.output(emission, 2.0)
    providers = []
    for index in range(provider_count):
        supply = flows.insert(Flow.product('Synthetic supply %d' % index, prop))
        provider = Process.of('Synthetic provider %d' % index, supply)
        provider.output(emission, 1.0)
        provider = processes.insert(provider)
        providers.append(provider)
        process.input(supply, 1.0).defaultProviderId = provider.id
    process = processes.insert(process)
    system = ProductSystem.of('Synthetic product system', process)
    for provider in providers:
        system.link(provider, process)
    assert len(system.processLinks) == provider_count
    system = ProductSystemDao(db).insert(system)
    category = ImpactCategory.of('Synthetic impact', 'synthetic impact unit')
    category.factor(emission, 1.6)
    category = ImpactCategoryDao(db).insert(category)
    method = ImpactMethod.of('Synthetic LCIA method')
    method.add(category)
    method = ImpactMethodDao(db).insert(method)
    for key, value in [('SYSTEM', system.refId), ('METHOD', method.refId), ('CATEGORY', category.refId),
                       ('UNIT', units.referenceUnit.refId), ('PROPERTY', prop.refId)]:
        print('%s=%s' % (key, value))
    print('EXPECTED=%s synthetic impact units per 1 kg service' % ((2 + provider_count) * 1.6))
finally:
    db.close()
