import unittest

from scripts.prepare_rq2_human_review import make_packets, select_cases


def example_case(sid):
    state = {'skills': {'a': .2}, 'history_length': 5}
    graph = {'edges': []}
    candidates = [{'problem_id': 'p1', 'skill_id': 'a', 'difficulty': .3},
                  {'problem_id': 'p2', 'skill_id': 'a', 'difficulty': .7}]
    return {'scenario_id': sid, 'state': state, 'bplus': candidates[0],
            'shared_input': {'state': state, 'graph': graph, 'candidates': candidates}}


class HumanReviewPacketTests(unittest.TestCase):
    def test_fixed_selection_and_blind_packet(self):
        cases = [example_case(f'test_{i:03d}') for i in range(1, 6)]
        self.assertEqual([c['scenario_id'] for c in select_cases(cases, count=3)],
                         [c['scenario_id'] for c in select_cases(cases[::-1], count=3)])
        runs = [{'scenario_id': c['scenario_id'], 'repeat': repeat,
                 'candidate_valid': True,
                 'selected_problem_id': 'p2' if repeat == 1 else 'p1'}
                for c in cases for repeat in (1, 2, 3)]
        rows, key = make_packets(cases, runs, count=3)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len(key), 6)
        self.assertNotIn('policy', rows[0])
        self.assertNotIn('student_id', str(rows))
        self.assertEqual({r['selected_problem_id'] for r in rows}, {'p1', 'p2'})

    def test_invalid_first_attempt_is_not_replaced(self):
        cases = [example_case('test_001')]
        runs = [{'scenario_id': 'test_001', 'repeat': 1,
                 'candidate_valid': False, 'selected_problem_id': None},
                {'scenario_id': 'test_001', 'repeat': 2,
                 'candidate_valid': True, 'selected_problem_id': 'p2'}]
        rows, key = make_packets(cases, runs, count=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual([k['status'] for k in key], ['VALID', 'INVALID'])


if __name__ == '__main__':
    unittest.main()
