#!/usr/bin/env python3
"""Import one experimental campaign's observations into a cyclic inventory and evidence audit."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile

from audit_and_scale_inventory import UNITS, scaled_product
from cyclic_foreground import build, write_inventory
from evidence_chain import COLUMNS, EVIDENCE, audit, conversion, digest, finite, quantities, read_json, text


REQUIRED_COLUMNS = (COLUMNS - {'basis'}) | {
    'record_id', 'target', 'selected', 'campaign_id', 'cycle_id', 'sample_id', 'sample_role',
    'original_id', 'original_locator', 'energy_basis', 'selection_reason',
}
OBSERVATIONS_ID = 'intake-observations'
ENERGY_BASES = {
    'power': {'metered_input_power', 'instrument_reading', 'rated_power'},
    'duration': {'elapsed_runtime', 'specified_runtime'},
    'quantity': {'metered_energy', 'estimated_energy'},
}
WATER_FIELDS = {'influent_volume', 'effluent_volume', 'influent_concentration', 'effluent_concentration'}


def observation_rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    fields = reader.fieldnames or []
    if len(fields) != len(set(fields)) or not REQUIRED_COLUMNS.issubset(fields):
        raise ValueError('observations CSV has duplicate or missing columns: ' + ', '.join(sorted(REQUIRED_COLUMNS - set(fields))))
    rows = list(reader)
    if not rows or any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError('observations CSV is empty or has malformed records')
    return fields, [{key: value.strip() for key, value in row.items()} for row in rows]


def original_sources(spec, base, records, raw, output):
    sources = {OBSERVATIONS_ID: {'id': OBSERVATIONS_ID, 'path': os.path.relpath(records, output), 'sha256': digest(raw)}}
    originals = spec.get('raw_records', [])
    if not isinstance(originals, list):
        raise ValueError('raw_records must be a list')
    for item in originals:
        source_id = text(item.get('id'), 'original ID')
        if source_id in sources:
            raise ValueError('duplicate or reserved original ID: ' + source_id)
        path = (base / text(item.get('local_path'), 'original path')).resolve()
        checksum = digest(path.read_bytes())
        if item.get('sha256') and item['sha256'] != checksum:
            raise ValueError(source_id + ': original SHA-256 mismatch')
        sources[source_id] = {'id': source_id, 'path': os.path.relpath(path, output), 'sha256': checksum}
    return sources


def normalize_quantity(row, target, field):
    qualifier = row['qualifier']
    evidence = row['evidence_class']
    if evidence not in EVIDENCE:
        raise ValueError('invalid evidence_class')
    factor = conversion(row['unit'], target['unit'])
    quantity = {'value': None, 'unit': target['unit'], 'evidence_class': evidence, 'qualifier': qualifier}
    if qualifier == 'exact' and row['value'] and not row['limit']:
        value = finite(row['value'], 'value')
        if value < 0:
            raise ValueError('observations must be non-negative')
        quantity['value'] = scaled_product(value, factor, 'converted value')
    elif qualifier == 'missing' and not row['value'] and not row['limit']:
        pass
    elif qualifier in ('below_lod', 'below_loq') and field == 'effluent_concentration' and not row['value'] and row['limit']:
        limit = finite(row['limit'], 'limit')
        if limit <= 0:
            raise ValueError('detection or quantification limit must be positive')
        quantity['limit'] = scaled_product(limit, factor, 'converted limit')
    else:
        raise ValueError('invalid value, qualifier or limit for ' + field)
    return quantity


def apply_observations(foreground, rows, campaign, originals):
    targets = dict(quantities(foreground))
    if not targets:
        raise ValueError('foreground template has no quantity slots')
    records, selected, counts, sample_locations, pairs = set(), {}, {}, {}, {}
    for position, row in enumerate(rows, 1):
        record_id = text(row['record_id'], 'record_id')
        if record_id in records:
            raise ValueError('duplicate record_id: ' + record_id)
        records.add(record_id)
        path = row['target']
        if path not in targets or row['selected'] not in ('yes', 'no') or row['campaign_id'] != campaign:
            raise ValueError(record_id + ': invalid target, selection or campaign')
        parts = path.split('/')
        cycle = foreground['cycles'][int(parts[2])]['cycle_id'] if parts[1] == 'cycles' else ''
        field = parts[-1]
        water_role = field.split('_', 1)[0] if len(parts) == 4 and cycle and field in WATER_FIELDS else ''
        if row['cycle_id'] != cycle or row['sample_role'] != water_role or bool(row['sample_id']) != bool(water_role):
            raise ValueError(record_id + ': cycle or sample role differs from the target')
        if water_role:
            identity = (cycle, water_role)
            if sample_locations.setdefault(row['sample_id'], identity) != identity:
                raise ValueError(record_id + ': sample ID reused across cycles or roles')
        energy_field = None
        if field in ('power', 'duration') and parts[-3] in ('activities', 'preparation_activities'):
            energy_field = field
        if field == 'quantity' and UNITS.get(targets[path]['unit'], ('',))[0] == 'energy':
            energy_field = field
        energy_basis = row['energy_basis']
        if (energy_field and energy_basis not in ENERGY_BASES[energy_field]) or (not energy_field and energy_basis):
            raise ValueError(record_id + ': energy_basis differs from the observed quantity')
        if energy_basis in ('rated_power', 'estimated_energy', 'specified_runtime') and row['evidence_class'] == 'measured':
            raise ValueError(record_id + ': this energy basis cannot be marked measured')
        try:
            quantity = normalize_quantity(row, targets[path], field)
        except ValueError as exc:
            raise ValueError(record_id + ': ' + str(exc)) from exc
        if not row['original_id'] and not row['original_locator']:
            column = {'exact': 'value', 'missing': 'qualifier'}.get(row['qualifier'], 'limit')
            row['original_id'] = OBSERVATIONS_ID
            row['original_locator'] = f'CSV data record {position}, column {column}'
        elif row['original_id'] not in originals or row['original_id'] == OBSERVATIONS_ID or not row['original_locator']:
            raise ValueError(record_id + ': original ID and locator must be supplied together and registered')
        row['basis'] = 'cycle-' + cycle if cycle else 'campaign-' + campaign
        counts[path] = counts.get(path, 0) + 1
        if row['selected'] == 'no':
            continue
        if path in selected:
            raise ValueError('multiple records selected for ' + path)
        if water_role:
            sample_id = row['sample_id']
            if pairs.setdefault((cycle, water_role), sample_id) != sample_id:
                raise ValueError(record_id + ': selected volume and concentration refer to different samples')
        provenance = f"{row['original_id']}: {row['original_locator']} [{record_id}]"
        quantity['source'] = provenance + (f' ({energy_basis})' if energy_basis else '')
        slot = targets[path]
        slot.clear()
        slot.update(quantity)
        selected[path] = (position, row)
    missing = targets.keys() - selected.keys()
    if missing:
        raise ValueError('no record selected for ' + ', '.join(sorted(missing)) + '; declare missing observations explicitly')
    for path, (_, row) in selected.items():
        if counts[path] > 1 and not row['selection_reason']:
            raise ValueError(row['record_id'] + ': give a selection reason for repeated observations')
    return selected


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def import_case(spec_path, output):
    output = output.parent.resolve(strict=True) / output.name
    spec, spec_hash = read_json(spec_path)
    if spec.get('schema_version') != 'piezolca.real-case-intake/1' or not isinstance(spec.get('import'), dict):
        raise ValueError('an intake /1 specification with an import block is required')
    if spec.get('service', {}).get('kind') != 'apparent_pollutant_removal':
        raise ValueError('this importer requires a cyclic apparent-pollutant-removal case')
    base = spec_path.resolve().parent
    campaign = text(spec['experiment'].get('campaign_id'), 'campaign_id')
    config = spec['import']
    records = (base / text(config.get('observations_csv'), 'observations_csv')).resolve()
    foreground, template_hash = read_json(base / text(config.get('foreground_template'), 'foreground_template'))
    if not isinstance(foreground, dict) or not isinstance(foreground.get('cycles'), list) or not foreground['cycles']:
        raise ValueError('a cyclic foreground template with at least one cycle is required')
    if os.path.lexists(output):
        raise FileExistsError('output directory already exists: ' + str(output))
    raw = records.read_bytes()
    fields, rows = observation_rows(raw)
    originals = original_sources(spec, base, records, raw, output)
    selected = apply_observations(foreground, rows, campaign, originals)
    model = build(foreground)
    with tempfile.TemporaryDirectory(prefix='.intake-', dir=output.parent) as temp:
        stage = Path(temp)
        foreground_bytes = json_bytes(foreground)
        (stage / 'foreground.json').write_bytes(foreground_bytes)
        inventory = stage / 'inventory.csv'
        manifest = write_inventory(model, foreground_bytes, 'foreground.json', inventory)
        normalized = stage / 'observations.csv'
        with normalized.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields if 'basis' in fields else fields + ['basis'])
            writer.writeheader()
            writer.writerows(rows)
        links = []
        for path, (position, row) in selected.items():
            link = {'target': path, 'source': 'normalized', 'record': position, 'basis': row['basis']}
            if row['sample_id']:
                link['sample'] = {key: row[key] for key in ('campaign_id', 'cycle_id', 'sample_id', 'sample_role')}
            links.append(link)
        evidence_spec = {'schema_version': 'piezolca.evidence-chain/1', 'foreground_sha256': digest(foreground_bytes),
                         'sources': [{'id': 'normalized', 'path': normalized.name, 'sha256': digest(normalized.read_bytes())}],
                         'originals': list(originals.values()), 'links': links}
        (stage / 'evidence.json').write_bytes(json_bytes(evidence_spec))
        evidence = audit(evidence_spec, stage, foreground, evidence_spec['foreground_sha256'], inventory, manifest)
        evidence['spec_sha256'] = digest((stage / 'evidence.json').read_bytes())
        (stage / 'evidence-report.json').write_bytes(json_bytes(evidence))
        summary = {'schema_version': 'piezolca.real-case-intake-result/1', 'status': 'review_required',
                   'campaign_id': campaign, 'intake_sha256': spec_hash, 'template_sha256': template_hash,
                   'originals': list(originals.values()), 'coverage': evidence['coverage'],
                   'records': {key: sum(row['qualifier'] == key for _, row in selected.values())
                               for key in ('exact', 'missing', 'below_lod', 'below_loq')},
                   'unselected_record_ids': [row['record_id'] for row in rows if row['selected'] == 'no'],
                   'campaigns_per_functional_unit': model['campaign']['campaigns_per_functional_unit'],
                   'model_warnings': model['warnings']}
        (stage / 'intake-report.json').write_bytes(json_bytes(summary))
        if os.path.lexists(output):
            raise FileExistsError('output directory already exists: ' + str(output))
        stage.rename(output)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('specification', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json_bytes(import_case(args.specification, args.output_dir.absolute())).decode().strip())
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, csv.Error) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
