import unittest

import pandas as pd

from src.models.bkt import BKT
from src.rq2.scenarios import sample_validation_scenarios


class RQ2ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame([
            {'user_id': student, 'order_id': step, 'skill_id': 'x',
             'correct': step % 2, 'split': 'validation'}
            for student in ('a', 'b', 'c') for step in range(8)
        ])

    def test_fixed_seed_unique_students_and_no_future_label_leakage(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        first = sample_validation_scenarios(self.frame, model, n_scenarios=2, seed=9,
                                            min_history=5)
        self.assertEqual(first, sample_validation_scenarios(self.frame, model,
                                                            n_scenarios=2, seed=9,
                                                            min_history=5))
        self.assertEqual(len(set(s['student_id'] for s in first)), 2)
        for scenario in first:
            self.assertGreaterEqual(scenario['state']['history_length'], 5)
            self.assertNotIn('correct', scenario)
            self.assertNotIn('future', scenario)
        altered = self.frame.copy()
        for scenario in first:
            student = scenario['student_id']
            future = (altered.user_id == student) & (altered.order_id > scenario['cutoff_order_id'])
            altered.loc[future, 'correct'] = 1 - altered.loc[future, 'correct']
        self.assertEqual(first, sample_validation_scenarios(altered, model,
                                                            n_scenarios=2, seed=9,
                                                            min_history=5))

    def test_rejects_test_split_and_insufficient_students(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        with self.assertRaises(ValueError):
            sample_validation_scenarios(self.frame.assign(split='test'), model, 2)
        with self.assertRaises(ValueError):
            sample_validation_scenarios(self.frame, model, 4)


if __name__ == '__main__':
    unittest.main()
