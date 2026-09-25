import unittest

import pandas as pd

from src.models.bkt import BKT
from src.rq2.state import bkt_mastery_snapshot


class RQ2StateTests(unittest.TestCase):
    def test_snapshot_uses_only_prefix_and_does_not_change_fitted_parameters(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        history = pd.DataFrame({'user_id': ['a', 'a'], 'order_id': [1, 2],
                                'skill_id': ['x', 'x'], 'correct': [1, 0],
                                'split': ['validation', 'validation']})
        frozen = model.global_parameters_snapshot()
        state = bkt_mastery_snapshot(model, history.iloc[:1])
        self.assertEqual(state['state_type'], 'BKT_p_mastery')
        self.assertEqual(state['history_length'], 1)
        self.assertAlmostEqual(state['skills']['x'], 49/85)
        self.assertEqual(model.global_parameters_snapshot(), frozen)
        self.assertNotEqual(state, bkt_mastery_snapshot(model, history))

    def test_unseen_graph_skill_uses_fitted_initial_mastery(self):
        model = BKT.from_parameters((.2, .1, .2, .1), {'y': (.4, .1, .2, .1)})
        history = pd.DataFrame({'user_id': ['a'], 'order_id': [1],
                                'skill_id': ['x'], 'correct': [1], 'split': ['validation']})
        state = bkt_mastery_snapshot(model, history, skill_universe=['x', 'y', 'z'])
        self.assertAlmostEqual(state['skills']['y'], .4)
        self.assertAlmostEqual(state['skills']['z'], .2)

    def test_rejects_colliding_skill_string_representations(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        history = pd.DataFrame({'user_id': ['a', 'a'], 'order_id': [1, 2],
                                'skill_id': [1, '1'], 'correct': [1, 0],
                                'split': ['validation', 'validation']})
        with self.assertRaisesRegex(ValueError, 'ambiguous skill string identifier'):
            bkt_mastery_snapshot(model, history)

    def test_rejects_test_and_mixed_students(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        row = pd.DataFrame({'user_id': ['a'], 'order_id': [1], 'skill_id': ['x'],
                            'correct': [1], 'split': ['test']})
        with self.assertRaises(ValueError):
            bkt_mastery_snapshot(model, row)
        row['split'] = 'validation'
        mixed = pd.concat([row, row.assign(user_id='b')])
        with self.assertRaises(ValueError):
            bkt_mastery_snapshot(model, mixed)

    def test_explicit_test_context_replays_without_relabeling_rows(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        test = pd.DataFrame({'user_id': ['a', 'a'], 'order_id': [1, 2],
                             'skill_id': ['x', 'x'], 'correct': [1, 0],
                             'split': ['test', 'test']})
        expected = bkt_mastery_snapshot(model, test.assign(split='validation'))
        actual = bkt_mastery_snapshot(model, test, expected_split='test')
        self.assertEqual(actual, expected)
        self.assertTrue(test.split.eq('test').all())
        with self.assertRaises(ValueError):
            bkt_mastery_snapshot(model, test, expected_split='train')


if __name__ == '__main__':
    unittest.main()
