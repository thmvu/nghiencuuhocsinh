"""Trace correctness and explicit explanation rejection, independent of LLM luck."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.rq2.foundational_validation import compact_graph, recommend_foundational_bplus
from src.rq2.grounded_explanation import assess_explanation, explanation_packet, explanation_request, render_verified, run_explanation, template_explanation

ROOT = Path(__file__).resolve().parents[1]


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_explanation1.json').read_text(encoding='utf-8'))
        self.policy = {'source_weak_threshold': .5, 'target_weak_threshold': .5, 'target_train_success_rate': .7}
        graph = compact_graph({'skills': ['a', 'b', 'c'], 'skill_to_standard': {'a': 'S', 'b': 'T', 'c': 'S'},
                               'edges': [{'prerequisite': 'a', 'target': 'b'}, {'prerequisite': 'c', 'target': 'b'}]}, 'curriculum_edges')
        self.shared = {'state': {'state_type': 'BKT_p_mastery', 'history_length': 5, 'skills': {'a': .2, 'b': .3, 'c': .9}},
                       'graph': graph,
                       'candidates': [{'problem_id': 'B', 'skill_id': 'b', 'difficulty': .7, 'support': 10},
                                      {'problem_id': 'A', 'skill_id': 'a', 'difficulty': .99, 'support': 10}]}

    def response(self, output):
        return {'message': {'content': json.dumps(output)}, 'prompt_eval_count': 100,
                'eval_count': 80, 'done': True, 'done_reason': 'stop'}

    def good(self, shared=None):
        packet, decisive = explanation_packet(shared or self.shared, self.policy)
        return packet, decisive, template_explanation(packet, decisive)

    def test_first_unique_stage_and_parity_across_permutations(self):
        before = deepcopy(self.shared)
        for candidates in (self.shared['candidates'], list(reversed(self.shared['candidates']))):
            shared = {**self.shared, 'candidates': candidates}
            packet, factor = explanation_packet(shared, self.policy)
            self.assertEqual(factor, 'source_signal')
            self.assertEqual(packet['selected_problem_id'], recommend_foundational_bplus(shared, self.policy)['problem_id'])
            self.assertEqual(packet['selection_trace'][0], {'factor': 'source_signal', 'before': 2, 'after': 1})
        self.assertEqual(self.shared, before)

    def test_gap_support_id_and_singleton_traces(self):
        shared = deepcopy(self.shared)
        shared['graph']['edges'] = []
        self.assertEqual(explanation_packet(shared, self.policy)[1], 'success_gap')
        shared['candidates'][1]['difficulty'] = .7
        shared['candidates'][1]['support'] = 30
        self.assertEqual(explanation_packet(shared, self.policy)[1], 'support')
        shared['candidates'][1]['support'] = 10
        self.assertEqual(explanation_packet(shared, self.policy)[1], 'problem_id')
        shared['candidates'] = shared['candidates'][:1]
        self.assertEqual(explanation_packet(shared, self.policy)[1], 'single_candidate')

    def test_no_edge_projection_and_separate_multi_id_state(self):
        shared = deepcopy(self.shared)
        shared['graph']['edges'] = []
        packet, _ = explanation_packet(shared, self.policy)
        self.assertFalse(packet['selected_numeric_evidence']['weak_linked_source'])
        self.assertFalse(packet['graph_has_edges'])
        self.assertEqual(packet['selected_skill_id'], 'b')
        packet, _ = explanation_packet(self.shared, self.policy)
        self.assertEqual(packet['selected_skill_id'], 'a')
        self.assertIn('0.200000', next(f['text'] for f in packet['fact_catalog'] if f['id'] == 'state_estimate'))
        self.assertNotIn('reference_graph', json.dumps(packet))

    def test_template_passes_and_renderer_never_uses_draft(self):
        packet, factor, output = self.good()
        output['draft'] = 'Học sinh chắc chắn sẽ học tốt hơn.'
        parsed, checks = assess_explanation(json.dumps(output), packet, factor, 240)
        self.assertTrue(all(checks.values()))
        rendered = render_verified(parsed, packet, checks)
        self.assertNotIn(output['draft'], rendered)
        self.assertIn('không chứng minh', rendered)
        # Passing structure must never be called semantic verification of this draft.
        row = run_explanation(self.shared, self.policy, self.config, ['B', 'A'], lambda request, timeout: self.response(output))
        self.assertTrue(row['accepted'])
        self.assertFalse(row['draft_semantically_verified'])

    def test_wrong_id_and_wrong_decisive_factor_rejected_without_reselection(self):
        packet, factor, output = self.good()
        for change in ({'problem_id': 'B'}, {'decisive_factor': 'problem_id'}):
            wrong = {**output, **change}
            row = run_explanation(self.shared, self.policy, self.config, ['B', 'A'], lambda request, timeout: self.response(wrong))
            self.assertFalse(row['accepted'])
            self.assertEqual(row['fixed_problem_id'], 'A')
            self.assertEqual(row['error_stage'], 'evidence_checks')
            self.assertIsNone(row['rendered_explanation'])

    def test_unknown_duplicate_and_missing_caveat_citations_rejected(self):
        packet, factor, output = self.good()
        for ids in (output['evidence_ids'] + ['unknown'], output['evidence_ids'] + ['selected_item'],
                    [i for i in output['evidence_ids'] if i != 'learning_limit']):
            wrong = {**output, 'evidence_ids': ids}
            parsed, checks = assess_explanation(json.dumps(wrong), packet, factor, 240)
            self.assertFalse(all(checks.values()))
            with self.assertRaises(ValueError):
                render_verified(parsed, packet, checks)
            forged = {k: True for k in checks}
            with self.assertRaises(ValueError):
                render_verified(parsed, packet, forged)

    def test_blank_or_overlong_draft_and_extra_fields_rejected(self):
        packet, factor, output = self.good()
        for wrong in ({**output, 'draft': ' '}, {**output, 'draft': 'x' * 241}, {**output, 'invented': 42}):
            with self.assertRaises(ValueError):
                assess_explanation(json.dumps(wrong), packet, factor, 240)

    def test_request_limits_validation_only_and_exact_candidate_schema(self):
        packet, _, _ = self.good()
        request, bound = explanation_request(packet, self.config, ['B', 'A'])
        self.assertEqual(request['format']['properties']['problem_id']['enum'], ['B', 'A'])
        self.assertEqual(request['format']['properties']['draft']['maxLength'], 240)
        self.assertNotIn('decisive_factor', json.loads(request['messages'][1]['content']))
        for bad in (['A', 'A'], ['B']):
            with self.assertRaises(ValueError):
                explanation_request(packet, self.config, bad)
        with self.assertRaises(ValueError):
            explanation_request(packet, {**self.config, 'test_access': True}, ['B', 'A'])
        tight = deepcopy(self.config)
        tight['agent']['num_ctx'] = bound + tight['agent']['num_predict'] - 1
        with self.assertRaises(ValueError):
            explanation_request(packet, tight, ['B', 'A'])

    def test_telemetry_failure_has_raw_record_and_no_retry_or_render(self):
        _, _, output = self.good()
        calls = []
        def call(request, timeout):
            calls.append(request)
            return {**self.response(output), 'done_reason': 'length', 'eval_count': 512}
        row = run_explanation(self.shared, self.policy, self.config, ['A', 'B'], call)
        self.assertEqual(len(calls), 1)
        self.assertEqual(row['request'], calls[0])
        self.assertEqual(row['eval_count'], 512)
        self.assertEqual(row['error_stage'], 'telemetry')
        self.assertFalse(row['accepted'])
        self.assertIsNone(row['rendered_explanation'])


if __name__ == '__main__':
    unittest.main()
