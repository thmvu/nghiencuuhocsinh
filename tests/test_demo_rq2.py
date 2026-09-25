import unittest

from scripts.demo_rq2 import build_synthetic_demo, run_demo


class RQ2DemoTests(unittest.TestCase):
    def test_synthetic_state_and_same_candidate_set(self):
        graph = {'skills': [str(i) for i in range(10)], 'edges': [],
                 'status': 'prototype_assumptions_pending_curriculum_review'}
        pool = [{'problem_id': f'p{i}', 'skill_id': str(i),
                 'difficulty': .3 + i * .05, 'support': 5} for i in range(10)]
        shared = build_synthetic_demo(graph, pool, n_candidates=4)
        self.assertEqual(shared['state']['state_type'], 'BKT_p_mastery')
        self.assertEqual(len(shared['candidates']), 4)
        self.assertNotIn('student_id', str(shared))
        seen = []

        def fake_call(request, *, timeout):
            seen.append(request)
            return '{"problem_id":"' + shared['candidates'][0]['problem_id'] + \
                   '","reason":"synthetic state"}'

        result = run_demo(shared, model='mock', call=fake_call)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result['agent']['problem_id'], shared['candidates'][0]['problem_id'])
        self.assertIn(result['bplus']['problem_id'],
                      {item['problem_id'] for item in shared['candidates']})
        self.assertEqual(result['stage'], 'synthetic_demo_not_research_result')


if __name__ == '__main__':
    unittest.main()
