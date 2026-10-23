"""Build a display-only frontend snapshot; never called at app startup.

python3 app/export_housing.py --input /path/to/data/houses_clean.csv
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {'row_id', 'latitude', 'longitude', 'zipcode', 'city', 'homeType',
            'bedrooms', 'bathrooms', 'livingArea', 'lot_sqft', 'yearBuilt'}


def number(value):
    try:
        result = float(value)
        return (int(result) if result.is_integer() else result) if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def export_snapshot(path, address_records=None, address_source_sha256=None):
    raw = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not REQUIRED <= set(reader.fieldnames):
        raise ValueError('Missing or duplicate source columns')
    homes, ids, source_identities = [], set(), {}
    for row in reader:
        if None in row or any(row[k] is None for k in REQUIRED):
            raise ValueError('Malformed housing row')
        if not re.fullmatch(r'0|[1-9][0-9]*', row['row_id']):
            raise ValueError('Invalid row_id')
        rid = int(row['row_id'])
        if rid in ids or rid > 2**53 - 1:
            raise ValueError('Duplicate or unsafe row_id')
        ids.add(rid)
        lat, lng = number(row['latitude']), number(row['longitude'])
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError(f'Invalid coordinates for row_id {rid}')
        home = {'rowId': rid, 'lat': lat, 'lng': lng,
                'zip': row['zipcode'] if re.fullmatch(r'[0-9]{5}', row['zipcode']) and row['zipcode'] != '00000' else None,
                'city': row['city'].strip() or None,
                'homeType': row['homeType'].strip() or None}
        for dest, source in [('beds', 'bedrooms'), ('baths', 'bathrooms'),
                             ('livingArea', 'livingArea'), ('lotSqft', 'lot_sqft'), ('yearBuilt', 'yearBuilt')]:
            value = number(row[source])
            home[dest] = value if value is not None and value >= 0 else None
        home['address'] = None
        source_identities[rid] = number(row.get('zpid'))
        homes.append(home)
    if not homes:
        raise ValueError('Empty housing catalog')
    homes.sort(key=lambda home: home['rowId'])
    groups = Counter((home['lng'], home['lat']) for home in homes)
    snapshot = {'metadata': {
        'schemaVersion': 1,
        'label': 'Historical Houston housing (2024)',
        'warning': 'Historical observations; dates and current availability unverified. Not active listings.',
        'source': 'Kaggle Houston Housing Market 2024 clean dataset',
        'sourceUrl': 'https://www.kaggle.com/datasets/mohamedalmansop/houston-housing-market-2024-clean-dataset',
        'sourceFile': 'data/houses_clean.csv',
        'sourceSha256': hashlib.sha256(raw).hexdigest(),
        'sourceAccessDate': None,
        'exporterVersion': 2,
        'license': 'Public redistribution rights unverified; internal local prototype.',
        'totalRecords': len(homes),
        'uniqueCoordinates': len(groups),
        'recordsAtSharedCoordinates': sum(n for n in groups.values() if n > 1),
        'predictionAvailable': False,
    }, 'homes': homes}
    if address_records is not None:
        if not isinstance(address_source_sha256, str) or not re.fullmatch('[a-f0-9]{64}', address_source_sha256):
            raise ValueError('An address artifact checksum is required')
        by_id = {home['rowId']: home for home in homes}
        seen = set()
        for record in address_records:
            rid = record['row_id']
            if isinstance(rid, bool) or not isinstance(rid, int) or rid not in by_id:
                raise ValueError('Address artifact identity is not in the source catalog')
            if rid in seen:
                raise ValueError('Duplicate address artifact row_id')
            seen.add(rid)
            home = by_id[rid]
            if (source_identities[rid] is None or record['zpid'] != source_identities[rid]
                or record['lat'] != home['lat'] or record['lon'] != home['lng']
                or record['zip'] != home['zip']):
                raise ValueError(f'Address artifact identity mismatch for row_id {rid}')
            address = record.get('address')
            address = address.strip() if isinstance(address, str) else ''
            city_only = f"{record.get('city') or ''} TX {record['zip']}"
            if address and ' '.join(address.split()).casefold() != ' '.join(city_only.split()).casefold():
                home['address'] = address
        snapshot['metadata'].update({
            'addressSourceFile': 'artifacts/houses_scored.parquet',
            'addressSourceSha256': address_source_sha256,
        })
    snapshot['metadata']['addressMatches'] = sum(home['address'] is not None for home in homes)
    snapshot['metadata']['addressMissing'] = len(homes) - snapshot['metadata']['addressMatches']
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--addresses-artifact', type=Path, help='Optional scored Parquet artifact supplying recorded street addresses')
    parser.add_argument('--output', type=Path, default=ROOT / 'frontend/public/houston-homes.json')
    args = parser.parse_args()
    records, address_sha = None, None
    if args.addresses_artifact:
        try:
            import pyarrow.parquet as parquet
        except ModuleNotFoundError:
            parser.error('Address enrichment requires PyArrow: python3 -m pip install pyarrow==24.0.0')
        address_sha = hashlib.sha256(args.addresses_artifact.read_bytes()).hexdigest()
        records = parquet.read_table(args.addresses_artifact, columns=[
            'row_id', 'zpid', 'address', 'lat', 'lon', 'zip', 'city']).to_pylist()
    snapshot = export_snapshot(args.input, records, address_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, allow_nan=False, ensure_ascii=False, indent=2) + '\n')
    print(f"Exported {len(snapshot['homes']):,} historical observations to {args.output}; {snapshot['metadata']['addressMatches']:,} recorded street addresses")


if __name__ == '__main__':
    main()
