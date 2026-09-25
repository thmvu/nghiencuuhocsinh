import json
import unittest

from src.rq2.agent_validation import run_validation_cases, summarize_agent_validation


class AgentValidationTests(unittest.TestCase):
    def test_same_inputs_and_aggregate_counts_without_student_identity(self):
        shared = {
            'state': {'state_type': 'BKT_p_mastery', 'skills': {'1': .2}, 'history_length': 5},
            'graph': {'skills': ['1'], 'edges': []},
            'candidates': [
                {'problem_id': 'p1', 'skill_id': '1', 'difficulty': .5, 'support': 3},
                {'problem_id': 'p2', 'skill_id': '1', 'difficulty': .7, 'support': 4},
            ],
        }
        cases = [{**{'scenario_id': f'validation_{i}', 'student_id': f'private_{i}',
                     'state': shared['state'], 'shared_input': shared,
                     'bplus': shared['candidates'][0]}}
                 for i in range(2)]
        seen = []

        def fake_call(request, *, timeout):
            seen.append(json.loads(request['messages'][1]['content']))
            return '{"problem_id":"p1","reason":"weak skill"}' if len(seen) == 1 else \
                   '{"problem_id":"outside","reason":"x"}'

        runs = run_validation_cases(cases, model='fake-local', call=fake_call)
        self.assertEqual(seen, [shared, shared])
        summary = summarize_agent_validation(runs)
        self.assertEqual(summary['schema_valid_count'], 2)
        self.assertEqual(summary['candidate_valid_count'], 1)
        self.assertEqual(summary['agreement_with_bplus_count'], 1)
        self.assertEqual(summary['candidate_valid_rate'], .5)
        self.assertEqual(summary['error_rate'], .5)
        self.assertEqual(summary['timeout_count'], 0)
        self.assertNotIn('private_', str(summary))

    def test_json_syntax_count_is_distinct_from_schema_count(self):
        shared = {
            'state': {'state_type': 'BKT_p_mastery', 'skills': {'1': .2}, 'history_length': 5},
            'graph': {'skills': ['1'], 'edges': []},
            'candidates': [{'problem_id': 'p1', 'skill_id': '1', 'difficulty': .5, 'support': 3}],
        }
        cases = [{'scenario_id': f'validation_{i}', 'student_id': f's{i}',
                  'state': shared['state'], 'shared_input': shared,
                  'bplus': shared['candidates'][0]} for i in range(2)]
        replies = iter(['{"problem_id":12,"reason":"x"}', 'not json'])
        runs = run_validation_cases(cases, model='fake',
                                    call=lambda request, timeout: next(replies))
        summary = summarize_agent_validation(runs)
        self.assertEqual(summary['json_syntax_valid_count'], 1)
        self.assertEqual(summary['schema_valid_count'], 0)


if __name__ == '__main__':
    unittest.main()
