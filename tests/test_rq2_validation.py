import unittest

from src.models.bkt import BKT
from src.rq2.validation import build_validation_cases, summarize_validation_cases

import pandas as pd


class RQ2ValidationTests(unittest.TestCase):
    def test_common_inputs_and_aggregate_summary_exclude_student_ids(self):
        train = pd.DataFrame([
            {'user_id': 't', 'order_id': i, 'skill_id': str(i),
             'problem_id': f'p{i}', 'correct': i % 2, 'split': 'train'}
            for i in range(10)
        ])
        validation = pd.DataFrame([
            {'user_id': student, 'order_id': i, 'skill_id': str(i % 10),
             'problem_id': f'v{i}', 'correct': i % 2, 'split': 'validation'}
            for student in ('private_a', 'private_b') for i in range(6)
        ])
        model = BKT.from_parameters((.2, .1, .2, .1))
        cases, graph, pool = build_validation_cases(
            train, validation, model, n_scenarios=2, seed=7,
            n_skills=10, min_support=1, n_candidates=4, min_history=5)
        self.assertEqual(len(cases), 2)
        self.assertEqual({case['student_id'] for case in cases}, {'private_a', 'private_b'})
        for case in cases:
            self.assertEqual(case['shared_input']['graph'], graph)
            self.assertEqual(case['shared_input']['state'], case['state'])
            self.assertIn(case['bplus']['problem_id'],
                          {item['problem_id'] for item in case['shared_input']['candidates']})
        summary = summarize_validation_cases(cases, graph, pool)
        self.assertEqual(summary['n_scenarios'], 2)
        self.assertNotIn('private_a', str(summary))
        self.assertNotIn('private_b', str(summary))


if __name__ == '__main__':
    unittest.main()
