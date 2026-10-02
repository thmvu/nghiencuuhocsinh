"""Calculator evidence semantics, fairness and logging boundaries."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.rq2.agent_revision import revision_request
from src.rq2.calculator_agent import candidate_evidence, calculator_request, recommend_calculator_bplus, run_calculator_call
from src.rq2.foundational_validation import compact_graph, recommend_foundational_bplus

ROOT = Path(__file__).resolve().parents[1]


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_validation.json').read_text(encoding='utf-8'))
        graph = compact_graph({'skills': ['a', 'b', 'c'],
                               'skill_to_standard': {'a': 'S', 'b': 'T', 'c': 'S'},
                               'edges': [{'prerequisite': 'a', 'target': 'b'},
                                         {'prerequisite': 'c', 'target': 'b'}]}, 'curriculum_edges')
        self.config.update(reference_graph=graph, reason_max_chars=160)
        self.shared = {'state': {'state_type': 'BKT_p_mastery', 'history_length': 5,
                                 'skills': {'a': .2, 'b': .3, 'c': .9}},
                       'graph': graph,
                       'candidates': [{'problem_id': 'C', 'skill_id': 'c', 'difficulty': .7, 'support': 10},
                                      {'problem_id': 'B', 'skill_id': 'b', 'difficulty': .7, 'support': 10},
                                      {'problem_id': 'A', 'skill_id': 'a', 'difficulty': .99, 'support': 10}]}
        self.enum = ['A', 'C', 'B']

    def response(self, selected='A'):
        return {'message': {'content': json.dumps({'problem_id': selected, 'reason': 'Computed evidence'})},
                'prompt_eval_count': 100, 'eval_count': 20, 'done': True, 'done_reason': 'stop'}

    def test_multiple_ids_keep_distinct_mastery_and_evidence_display_order(self):
        before = deepcopy(self.shared)
        facts = candidate_evidence(self.shared, self.config['bplus'])
        self.assertEqual([e['problem_id'] for e in facts], ['C', 'B', 'A'])
        self.assertEqual([e['weak_linked_source'] for e in facts], [False, False, True])
        self.assertEqual(set(facts[0]), {'problem_id', 'weak_linked_source', 'train_success_gap', 'train_support'})
        self.assertEqual(self.shared, before)

    def test_no_edges_does_not_use_evaluation_reference_graph(self):
        shared = deepcopy(self.shared)
        shared['graph']['edges'] = []
        request, _ = calculator_request(shared, self.config, self.enum)
        payload = json.loads(request['messages'][1]['content'])
        self.assertEqual(payload['graph']['edges'], [])
        self.assertFalse(any(e['weak_linked_source'] for e in payload['calculator_evidence']))
        self.assertNotIn('reference_graph', json.dumps(request))

    def test_target_endpoint_and_mastery_affect_signal(self):
        for mutate in ('remove_target_candidate', 'strong_target', 'change_target'):
            shared = deepcopy(self.shared)
            if mutate == 'remove_target_candidate':
                shared['candidates'] = [c for c in shared['candidates'] if c['skill_id'] != 'b']
            elif mutate == 'strong_target':
                shared['state']['skills']['b'] = .8
            else:
                shared['graph']['edges'] = [{'prerequisite': 'a', 'target': 'c'}]
            self.assertFalse(any(e['weak_linked_source'] for e in candidate_evidence(shared, self.config['bplus'])))

    def test_bplus_parity_ties_and_unrounded_numeric_gaps(self):
        for graph in (self.shared['graph'], {**self.shared['graph'], 'edges': []}):
            shared = {**self.shared, 'graph': graph}
            facts = candidate_evidence(shared, self.config['bplus'])
            for candidate, fact in zip(shared['candidates'], facts):
                self.assertEqual(fact['train_success_gap'], abs(candidate['difficulty'] - .7))
            self.assertEqual(recommend_calculator_bplus(shared, self.config['bplus'], facts), recommend_foundational_bplus(shared, self.config['bplus']))
        shared = deepcopy(self.shared)
        shared['graph']['edges'] = []
        shared['candidates'][0].update(difficulty=.7, support=50)
        facts = candidate_evidence(shared, self.config['bplus'])
        self.assertEqual(recommend_calculator_bplus(shared, self.config['bplus'], facts)['problem_id'], 'C')

    def test_tampered_or_reordered_evidence_rejected(self):
        facts = candidate_evidence(self.shared, self.config['bplus'])
        for bad in (list(reversed(facts)), facts[:-1], [{**facts[0], 'train_success_gap': 0.5}] + facts[1:]):
            with self.assertRaises(ValueError):
                recommend_calculator_bplus(self.shared, self.config['bplus'], bad)

    def test_request_only_adds_evidence_and_instruction_not_rank_or_answer(self):
        old, _ = revision_request(self.shared, self.config, 'schema_and_objective', self.enum)
        request, bound = calculator_request(self.shared, self.config, self.enum)
        old_payload = json.loads(old['messages'][1]['content'])
        payload = json.loads(request['messages'][1]['content'])
        payload.pop('calculator_evidence')
        self.assertEqual(payload, old_payload)
        self.assertEqual(request['format'], old['format'])
        self.assertEqual(request['options'], old['options'])
        self.assertEqual(request['format']['properties']['problem_id']['enum'], self.enum)
        self.assertTrue(request['messages'][0]['content'].startswith(old['messages'][0]['content']))
        tight = deepcopy(self.config)
        tight['agent']['num_ctx'] = bound + tight['agent']['num_predict'] - 1
        with self.assertRaises(ValueError):
            calculator_request(self.shared, tight, self.enum)

    def test_logger_stores_actual_calculator_request_and_never_replaces_bad_id(self):
        calls = []
        def call(request, timeout):
            calls.append(request)
            return self.response('outside')
        row = run_calculator_call(self.shared, self.config, self.enum, call)
        self.assertEqual(len(calls), 1)
        self.assertEqual(row['request'], calls[0])
        self.assertIn('calculator_evidence', json.loads(row['request']['messages'][1]['content']))
        self.assertEqual(row['error_stage'], 'candidate_membership')
        self.assertIsNone(row['selected_problem_id'])

    def test_valid_logging_and_output_limit_telemetry(self):
        row = run_calculator_call(self.shared, self.config, self.enum, lambda request, timeout: self.response())
        self.assertTrue(row['candidate_valid'])
        self.assertTrue(row['agrees_with_bplus'])
        self.assertEqual(row['selected_position'], 2)
        self.assertEqual(row['selected_enum_position'], 0)
        response = {**self.response(), 'done_reason': 'length', 'eval_count': 256}
        row = run_calculator_call(self.shared, self.config, self.enum, lambda request, timeout: response)
        self.assertEqual(row['error_stage'], 'telemetry')
        self.assertEqual(row['eval_count'], 256)
        self.assertFalse(row['candidate_valid'])


if __name__ == '__main__':
    unittest.main()
