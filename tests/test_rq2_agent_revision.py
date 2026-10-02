"""Revision schema invariants and auditable failure boundaries."""

from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from urllib.error import HTTPError

from src.rq2.agent_revision import revision_request, run_revision_call
from src.rq2.foundational_validation import compact_graph, make_agent_request

ROOT = Path(__file__).resolve().parents[1]


class AgentRevisionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_validation.json').read_text(encoding='utf-8'))
        audit = {'skills': ['a', 'b'], 'skill_to_standard': {'a': 'S', 'b': 'T'},
                 'edges': [{'prerequisite': 'a', 'target': 'b'}]}
        graph = compact_graph(audit, 'curriculum_edges')
        self.config['reference_graph'] = graph
        self.config['reason_max_chars'] = 160
        self.shared = {'state': {'state_type': 'BKT_p_mastery', 'history_length': 5, 'skills': {'a': .2, 'b': .3}},
                       'graph': graph,
                       'candidates': [{'problem_id': 'A', 'skill_id': 'a', 'difficulty': .99, 'support': 10},
                                      {'problem_id': 'B', 'skill_id': 'b', 'difficulty': .7, 'support': 10}]}

    def response(self, problem='A', reason='skill a with mastery 0.2'):
        return {'message': {'content': json.dumps({'problem_id': problem, 'reason': reason})},
                'prompt_eval_count': 100, 'eval_count': 20, 'done': True, 'done_reason': 'stop'}

    def run_response(self, response):
        return run_revision_call(self.shared, self.config, 'schema_only', ['B', 'A'],
                                 lambda request, timeout: response)

    def test_enum_is_exact_independent_of_display_and_only_prompt_changes_between_arms(self):
        before = deepcopy(self.shared)
        old, _ = make_agent_request(self.shared, self.config['agent'])
        schema, _ = revision_request(self.shared, self.config, 'schema_only', ['B', 'A'])
        objective, _ = revision_request(self.shared, self.config, 'schema_and_objective', ['B', 'A'])
        self.assertEqual(schema['messages'], old['messages'])
        self.assertEqual(schema['format']['properties']['problem_id']['enum'], ['B', 'A'])
        self.assertEqual(schema['format']['properties']['reason']['maxLength'], 160)
        self.assertEqual(schema['format'], objective['format'])
        self.assertEqual(schema['messages'][1], objective['messages'][1])
        self.assertIn('compare ALL candidates', objective['messages'][0]['content'])
        self.assertEqual(self.shared, before)
        for ids in (['A'], ['A', 'A'], ['A', 'X']):
            with self.assertRaises(ValueError):
                revision_request(self.shared, self.config, 'schema_only', ids)

    def test_no_edges_cannot_leak_reference_graph_into_objective_prompt(self):
        shared = deepcopy(self.shared)
        shared['graph']['edges'] = []
        request, _ = revision_request(shared, self.config, 'schema_and_objective', ['A', 'B'])
        payload = json.loads(request['messages'][1]['content'])
        self.assertEqual(payload['graph']['edges'], [])
        self.assertNotIn('reference_graph', json.dumps(request))
        with self.assertRaises(ValueError):
            revision_request(shared, {**self.config, 'test_access': True}, 'schema_only', ['A', 'B'])

    def test_valid_output_records_real_positions_and_raw_response(self):
        response = self.response()
        row = self.run_response(response)
        self.assertTrue(row['candidate_valid'])
        self.assertEqual(row['selected_position'], 0)
        self.assertEqual(row['selected_enum_position'], 1)
        self.assertEqual(row['raw_response'], response)
        self.assertIsNone(row['error_stage'])

    def test_rejected_id_is_logged_without_retry_or_fallback(self):
        calls = []
        def call(request, timeout):
            calls.append(request)
            return self.response('outside')
        row = run_revision_call(self.shared, self.config, 'schema_only', ['B', 'A'], call)
        self.assertEqual(len(calls), 1)
        self.assertTrue(row['schema_valid'])
        self.assertFalse(row['candidate_valid'])
        self.assertEqual(row['error_stage'], 'candidate_membership')
        self.assertIsNone(row['selected_problem_id'])
        self.assertIn('outside', row['raw_response']['message']['content'])

    def test_blank_reason_and_malformed_output_have_distinct_stages(self):
        row = self.run_response(self.response(reason='   '))
        self.assertEqual(row['error_stage'], 'reason')
        response = self.response()
        response['message']['content'] = 'malformed'
        row = self.run_response(response)
        self.assertEqual(row['error_stage'], 'schema')
        self.assertFalse(row['schema_valid'])
        row = self.run_response(self.response(reason='x' * 161))
        self.assertEqual(row['error_stage'], 'reason')

    def test_output_limit_retains_token_telemetry_and_http_error_retains_body(self):
        response = {**self.response(), 'done_reason': 'length', 'eval_count': 256}
        row = self.run_response(response)
        self.assertEqual(row['error_stage'], 'telemetry')
        self.assertEqual(row['prompt_eval_count'], 100)
        self.assertEqual(row['eval_count'], 256)
        def call(request, timeout):
            raise HTTPError('http://127.0.0.1:11434/api/chat', 500, 'test only', {}, io.BytesIO(b'{"error":"synthetic"}'))
        row = run_revision_call(self.shared, self.config, 'schema_only', ['A', 'B'], call)
        self.assertEqual(row['error_stage'], 'transport')
        self.assertEqual(row['http_status'], 500)
        self.assertEqual(row['http_body'], '{"error":"synthetic"}')
        self.assertFalse(row['candidate_valid'])

    def test_revised_schema_and_prompt_are_included_in_budget(self):
        _, bound = make_agent_request(self.shared, self.config['agent'])
        config = deepcopy(self.config)
        config['agent']['num_ctx'] = bound + config['agent']['num_predict'] + 5
        with self.assertRaisesRegex(ValueError, 'revision context'):
            revision_request(self.shared, config, 'schema_and_objective', ['A', 'B'])


if __name__ == '__main__':
    unittest.main()
