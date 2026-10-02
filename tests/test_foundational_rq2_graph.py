"""Boundary and adversarial checks for the provisional curriculum graph."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

import pandas as pd

from src.rq2.curriculum_graph import build_foundational_curriculum_graph

ROOT = Path(__file__).resolve().parents[1]


class FoundationalGraphTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_curriculum_graph.json').read_text(encoding='utf-8'))
        self.train = pd.DataFrame([{'skill_id': skill, 'split': 'train'}
                                   for ids in self.config['pilot_skill_ids_by_node_code'].values() for skill in ids])

    def test_expansion_preserves_distinct_states_and_provenance(self):
        graph = build_foundational_curriculum_graph(self.train, self.config)
        self.assertEqual(len(graph['skills']), 18)
        self.assertEqual(len(graph['standard_edges']), 9)
        self.assertEqual(len(graph['edges']), 13)
        self.assertEqual({e['prerequisite'] for e in graph['edges'] if e['target'] == '198'}, {'131', '132', '133'})
        self.assertFalse(graph['expert_validated'])
        self.assertTrue(all(e['source_refs'] and e['human_review'] == 'not_performed' for e in graph['edges']))
        before = deepcopy(self.config)
        graph['sources'].clear()
        self.assertEqual(self.config, before)

    def test_heldout_rows_and_untagged_data_rejected(self):
        for split in ('validation', 'test'):
            with self.assertRaises(ValueError):
                build_foundational_curriculum_graph(self.train.assign(split=split), self.config)
        with self.assertRaises(ValueError):
            build_foundational_curriculum_graph(self.train.drop(columns='split'), self.config)

    def test_cycle_rejected_even_with_source(self):
        edge = deepcopy(self.config['standard_edges'][0])
        edge['source'], edge['target'] = edge['target'], edge['source']
        self.config['standard_edges'].append(edge)
        with self.assertRaisesRegex(ValueError, 'cycle'):
            build_foundational_curriculum_graph(self.train, self.config)

    def test_substandard_siblings_cannot_be_made_a_chain(self):
        edge = deepcopy(self.config['standard_edges'][0])
        edge.update(source='6.RP.A.3a', target='6.RP.A.3b')
        self.config['standard_edges'].append(edge)
        with self.assertRaisesRegex(ValueError, 'sibling'):
            build_foundational_curriculum_graph(self.train, self.config)

    def test_missing_sources_and_unsupported_skills_rejected(self):
        with self.assertRaisesRegex(ValueError, 'absent'):
            build_foundational_curriculum_graph(self.train.iloc[1:], self.config)
        self.config['standard_edges'][0]['source_refs'] = ['nonexistent']
        with self.assertRaisesRegex(ValueError, 'provenance'):
            build_foundational_curriculum_graph(self.train, self.config)

    def test_alias_duplicate_and_unknown_endpoint_rejected(self):
        config = deepcopy(self.config)
        config['pilot_skill_ids_by_node_code']['7.RP.A.1'].append('135')
        with self.assertRaisesRegex(ValueError, 'unique'):
            build_foundational_curriculum_graph(self.train, config)
        config = deepcopy(self.config)
        config['standard_edges'].append(deepcopy(config['standard_edges'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            build_foundational_curriculum_graph(self.train, config)
        self.config['standard_edges'][0]['target'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'unknown'):
            build_foundational_curriculum_graph(self.train, self.config)

    def test_test_access_or_fake_expert_approval_rejected(self):
        for key in ('test_access', 'expert_validated'):
            config = deepcopy(self.config)
            config[key] = True
            with self.assertRaises(ValueError):
                build_foundational_curriculum_graph(self.train, config)


if __name__ == '__main__':
    unittest.main()
