"""Synthetic openLCA fixture for factor formulas, regional defaults and duplicate cells."""
import json
import sys
from java.io import File
from java.lang import Class, Object
from java.util import Collections
from jarray import array
from org.openlca.core.database import (Derby, FlowDao, FlowPropertyDao, ImpactCategoryDao,
                                      ImpactMethodDao, LocationDao, NativeSql, ParameterDao, ProcessDao,
                                      ProductSystemDao, UnitGroupDao)
from org.openlca.core.math import SystemCalculator
from org.openlca.core.matrix.index import ImpactIndex
from org.openlca.core.model import (CalculationSetup, Flow, FlowProperty, ImpactCategory, ImpactMethod,
                                   Location, Parameter, ParameterRedef, Process, ProductSystem, UnitGroup)

root = File(sys.argv[1])
assert not root.exists()
db = Derby(root)
try:
    units = UnitGroupDao(db).insert(UnitGroup.of('Fixture mass', 'kg'))
    mass = FlowPropertyDao(db).insert(FlowProperty.of('Fixture mass', units))
    area = Location.of('Fixture region', 'FX')
    area = LocationDao(db).insert(area)
    flow_dao = FlowDao(db)
    product = flow_dao.insert(Flow.product('Fixture service', mass))
    emission = flow_dao.insert(Flow.elementary('Fixture region-dependent emission', mass))
    other = flow_dao.insert(Flow.elementary('Fixture default-only emission', mass))
    process = Process.of('Fixture process', product)
    process.location = area
    process.output(emission, 2.0)
    process.output(other, 3.0)
    process = ProcessDao(db).insert(process)
    target = ProductSystemDao(db).insert(ProductSystem.of('Fixture system', process))

    category_dao = ImpactCategoryDao(db)
    geography = ImpactCategory.of('regional default', 'fixture impact')
    geography.factor(emission, 2.0)
    geography.factor(emission, 4.0).location = area
    geography.factor(other, 3.0)
    geography = category_dao.insert(geography)

    parameter = ParameterDao(db).insert(getattr(Parameter, 'global')('fixture_coefficient', 2.0))
    formula = ImpactCategory.of('formula', 'fixture impact')
    formula.factor(emission, 999.0).formula = 'fixture_coefficient + 3'
    formula = category_dao.insert(formula)

    duplicate = ImpactCategory.of('duplicate', 'fixture impact')
    duplicate.factor(emission, 7.0)
    duplicate.factor(emission, 11.0)
    duplicate = category_dao.insert(duplicate)

    method_dao = ImpactMethodDao(db)
    totals = {}
    methods = {}
    for category in (geography, formula, duplicate):
        method = ImpactMethod.of('Fixture ' + category.name)
        method.add(category)
        method = method_dao.insert(method)
        methods[category.name] = method
        amounts = []
        for regionalized in (False, True):
            setup = CalculationSetup.of(target).withImpactMethod(method).withRegionalization(regionalized)
            result = SystemCalculator(db).calculate(setup)
            impact = result.impactIndex().at(0)
            amounts.append(result.getTotalImpactValueOf(impact))
            result.dispose()
        if category.name == 'formula':
            override = Collections.singletonList(ParameterRedef.of(parameter, 6.0))
            setup = CalculationSetup.of(target).withImpactMethod(method).withParameters(override)
            result = SystemCalculator(db).calculate(setup)
            amounts.append(result.getTotalImpactValueOf(result.impactIndex().at(0)))
            result.dispose()
        totals[category.name] = amounts
    assert totals['regional default'] == [13.0, 17.0], totals
    assert totals['formula'] == [10.0, 10.0, 18.0], totals
    assert all(value in (14.0, 22.0) for value in totals['duplicate']), totals
    print('FACTORS ' + json.dumps(totals, sort_keys=True))

    helper = Class.forName('ImpactFactorQuery')
    scan_field = helper.getDeclaredField('SCAN')
    scan_field.setAccessible(True)
    scan = scan_field.get(None)
    query = next(m for m in helper.getMethods() if m.name == 'query')

    class Handler(NativeSql.QueryResultHandler):
        def __init__(self):
            self.categories = set()

        def accept(self, row):
            self.categories.add(row.getLong(1))
            return True

    def categories_read(method):
        handler = Handler()
        arguments = array([NativeSql.on(db), scan, handler, db, ImpactIndex.of(method)], Object)
        query.invoke(None, arguments)
        return handler.categories

    assert categories_read(methods['regional default']) == {geography.id}
    assert categories_read(methods['duplicate']) == {geography.id, formula.id, duplicate.id}
    print('FALLBACK selected rows and duplicate fallback verified')
finally:
    db.close()
