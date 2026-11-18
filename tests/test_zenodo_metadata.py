import json
import unittest
from pathlib import Path


class ZenodoMetadataTests(unittest.TestCase):
    def test_creator_and_contributor_roles(self):
        root = Path(__file__).resolve().parents[1]
        metadata = json.loads((root / '.zenodo.json').read_text())
        self.assertEqual([(x['name'], x['type']) for x in metadata['creators']], [('Pu, Xiaoyu', 'ProjectLeader')])
        self.assertEqual([(x['name'], x['type']) for x in metadata['contributors']], [('Gu, Jing', 'RelatedPerson')])
        self.assertNotIn('version', metadata)
        self.assertNotIn('doi', metadata)


if __name__ == '__main__':
    unittest.main()
