import json
import unittest

import pandas as pd

from src.rq2.test_evaluation import (sample_test_scenarios, run_test_cases,
                                     summarize_test_runs, validate_lock_c)


class RQ2TestEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.shared = {
            'state': {'state_type': 'BKT_p_mastery', 'skills': {'1': .2}, 'history_length': 5},
            'graph': {'skills': ['1'], 'edges': []},
            'candidates': [{'problem_id': 'p1', 'skill_id': '1', 'difficulty': .5, 'support': 3}],
        }

    def test_fifty_distinct_students_and_prefix_only(self):
        frame = pd.DataFrame([{'user_id': f's{i}', 'order_id': j, 'skill_id': 1,
                               'correct': j % 2, 'split': 'test'}
                              for i in range(50) for j in range(6)])
        seen = []

        def snapshot(_model, prefix, skill_universe, expected_split):
            self.assertEqual(expected_split, 'test')
            seen.append((prefix.user_id.nunique(), len(prefix), prefix.split.unique().tolist()))
            return self.shared['state']

        cases = sample_test_scenarios(frame, object(), self.shared['graph'],
                                      self.shared['candidates'], n_students=50,
                                      n_candidates=1, min_history=5, snapshot=snapshot)
        self.assertEqual(len(cases), 50)
        self.assertEqual(len({c['student_id'] for c in cases}), 50)
        self.assertTrue(all(n == 1 and 5 <= length <= 6 and splits == ['test']
                            for n, length, splits in seen))
        self.assertTrue(all(c['scenario_id'].startswith('test_') for c in cases))

    def test_repeated_runs_aggregate_by_scenario_and_no_ids(self):
        cases = [{'scenario_id': f'test_{i}', 'student_id': f'private_{i}',
                  'state': self.shared['state'], 'shared_input': self.shared,
                  'bplus': self.shared['candidates'][0]} for i in range(2)]
        replies = iter(['{"problem_id":"p1","reason":"x"}',
                        '{"problem_id":"p1","reason":"x"}',
                        '{"problem_id":"p1","reason":"x"}',
                        '{"problem_id":"p1","reason":"x"}',
                        '{"problem_id":"outside","reason":"x"}', 'bad json'])
        runs = run_test_cases(cases, model='fake', runs_per_scenario=3,
                              call=lambda request, timeout: next(replies))
        summary = summarize_test_runs(runs, expected_students=2, runs_per_scenario=3)
        self.assertEqual(summary['n_students'], 2)
        self.assertEqual(summary['n_runs'], 6)
        self.assertEqual(summary['json_syntax_valid_count'], 5)
        self.assertEqual(summary['schema_valid_count'], 5)
        self.assertEqual(summary['candidate_valid_count'], 4)
        self.assertEqual(summary['within_scenario_consistency_rate'], .5)
        self.assertIn('candidate_valid_student_bootstrap_ci_low', summary)
        self.assertIn('candidate_valid_student_bootstrap_ci_high', summary)
        self.assertNotIn('private_', json.dumps(summary))

    def test_lock_fails_closed_before_test_read(self):
        with self.assertRaises(ValueError):
            validate_lock_c({'stage': 'C', 'gate_c': 'RQ2 PRE-TEST CHECKLIST PASS'},
                            lambda path: 'hash')


if __name__ == '__main__':
    unittest.main()
