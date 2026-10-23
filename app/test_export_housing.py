import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('export_housing', Path(__file__).with_name('export_housing.py'))

class ExportTests(unittest.TestCase):
    def module(self):
        self.assertTrue(Path(SPEC.origin).exists(), 'display snapshot exporter is missing')
        module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(module)
        return module

    def write_source(self, root, rows):
        p = Path(root) / 'source.csv'
        fields = ['zpid', 'row_id', 'latitude', 'longitude', 'zipcode', 'city', 'homeType', 'bedrooms', 'bathrooms', 'livingArea', 'lot_sqft', 'yearBuilt', 'price', 'zestimate', 'rentZestimate']
        with p.open('w') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(zpid='123', row_id='0', latitude='29.7', longitude='-95.3', zipcode='77004', city='Houston', homeType='SINGLE_FAMILY', **row))
        return p

    def test_display_export_excludes_price_fields_and_preserves_unknowns(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_source(tmp, [dict(price='350000', zestimate='400000', rentZestimate='2000', bedrooms='', bathrooms='0')])
            before = p.read_bytes()
            result = module.export_snapshot(p)
            self.assertEqual(before, p.read_bytes())
            self.assertEqual(result['metadata']['totalRecords'], 1)
            self.assertEqual(len(result['metadata']['sourceSha256']), 64)
            home = result['homes'][0]
            self.assertEqual(home['rowId'], 0)
            self.assertIsNone(home['beds'])
            self.assertEqual(home['baths'], 0)
            self.assertEqual(home['zip'], '77004')
            self.assertFalse(set(home) & {'price', 'zestimate', 'rentZestimate', 'pred', 'zpid'})

    def test_duplicate_ids_and_invalid_coordinates_fail_without_partial_export(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_source(tmp, [{}, {}])
            with self.assertRaisesRegex(ValueError, 'row_id'):
                module.export_snapshot(p)
            p.write_text('row_id,latitude,longitude,zipcode,city,homeType,bedrooms,bathrooms,livingArea,lot_sqft,yearBuilt\n0,nan,-95.3,77004,Houston,SINGLE_FAMILY,,,,,\n')
            with self.assertRaisesRegex(ValueError, 'coordinate'):
                module.export_snapshot(p)

    def test_addresses_join_by_verified_identity_and_reject_mismatched_properties(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_source(tmp, [{}])
            record = {'row_id': 0, 'zpid': 123, 'lat': 29.7, 'lon': -95.3,
                      'zip': '77004', 'city': 'Houston', 'address': '123 Main St, Houston TX 77004'}
            result = module.export_snapshot(p, address_records=[record], address_source_sha256='a' * 64)
            self.assertEqual(result['homes'][0]['address'], record['address'])
            self.assertEqual(result['metadata']['addressMatches'], 1)
            self.assertEqual(result['metadata']['addressSourceSha256'], 'a' * 64)
            for field, value in [('zpid', 456), ('lat', 29.8), ('zip', '77005')]:
                with self.assertRaisesRegex(ValueError, 'identity'):
                    module.export_snapshot(p, address_records=[dict(record, **{field: value})], address_source_sha256='a' * 64)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                module.export_snapshot(p, address_records=[record, record], address_source_sha256='a' * 64)
            city_only = dict(record, address='Houston TX 77004')
            result = module.export_snapshot(p, address_records=[city_only], address_source_sha256='a' * 64)
            self.assertIsNone(result['homes'][0]['address'])
            self.assertEqual(result['metadata']['addressMissing'], 1)

if __name__ == '__main__':
    unittest.main()
