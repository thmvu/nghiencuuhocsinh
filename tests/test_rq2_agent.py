import json
import unittest

from src.rq2.agent import build_agent_request, validate_agent_output


class AgentContractTests(unittest.TestCase):
    def setUp(self):
        self.state = {'state_type': 'BKT_p_mastery', 'skills': {'11': .25, '12': .8},
                      'history_length': 12}
        self.graph = {'skills': ['11', '12'], 'edges': [
            {'prerequisite': '11', 'target': '12', 'basis': 'prototype_assumption'}]}
        self.candidates = [
            {'problem_id': 'p1', 'skill_id': '11', 'difficulty': .4, 'support': 20},
            {'problem_id': 'p2', 'skill_id': '12', 'difficulty': .7, 'support': 15},
        ]

    def test_request_contains_same_explicit_inputs_and_schema(self):
        request = build_agent_request(self.state, self.graph, self.candidates,
                                      model='local-model', temperature=0, num_ctx=2048)
        self.assertEqual(request['model'], 'local-model')
        self.assertFalse(request['stream'])
        self.assertEqual(request['options']['temperature'], 0)
        self.assertEqual(request['options']['num_ctx'], 2048)
        self.assertEqual(set(request['format']['required']), {'problem_id', 'reason'})
        body = json.loads(request['messages'][1]['content'])
        self.assertEqual(body['state'], self.state)
        self.assertEqual(body['graph'], self.graph)
        self.assertEqual(body['candidates'], self.candidates)
        self.assertNotIn('student_id', request['messages'][1]['content'])

    def test_output_schema_and_candidate_membership(self):
        valid = validate_agent_output('{"problem_id":"p1","reason":"weak prerequisite"}',
                                      self.candidates)
        self.assertEqual(valid['problem_id'], 'p1')
        for content in ('not json', '{"problem_id":"outside","reason":"x"}',
                        '{"problem_id":"p1","reason":""}',
                        '{"problem_id":"p1","reason":"x","extra":1}'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_agent_output(content, self.candidates)

    def test_rejects_duplicate_candidates_and_invalid_state(self):
        with self.assertRaises(ValueError):
            build_agent_request(self.state, self.graph, self.candidates * 2, model='local')
        with self.assertRaises(ValueError):
            build_agent_request({**self.state, 'skills': {'11': 1.2}}, self.graph,
                                self.candidates, model='local')


if __name__ == '__main__':
    unittest.main()
