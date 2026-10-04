from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.rq2.foundational_validation import compact_graph
from src.rq2.selection_agent_v3 import (selection_request, run_selection, rationale_flags, choose_contract,
                                      rubric_estimate, stop_decision)
from scripts.run_foundational_rq2_selection_v3 import accounting, rubric_packet
from scripts import run_foundational_rq2_selection_v3 as runner
from src.rq2.runtime_journal import RuntimeJournal, RuntimeIntegrityError


class V3Tests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.config = json.loads((root / 'configs/foundationalassist_v4_rq2_selection_v3_diagnostic.json').read_text(encoding='utf-8'))
        self.shared = {'state': {'state_type': 'BKT_p_mastery', 'history_length': 5, 'skills': {'1': .234, '2': .8}},
                       'graph': compact_graph({'skills': ['1', '2'], 'skill_to_standard': {'1': 'S', '2': 'T'}, 'edges': []}, 'no_edges'),
                       'candidates': [{'problem_id': '10', 'skill_id': '1', 'difficulty': .7, 'support': 12},
                                      {'problem_id': '20', 'skill_id': '2', 'difficulty': .5, 'support': 20}],
                       'selected_problem_id': '10'}
        self.shared.pop('selected_problem_id')

    def test_contract_arms_differ_only_in_schema_cap(self):
        a, _ = selection_request(self.shared, self.config, ['20', '10'])
        b, _ = selection_request(self.shared, {**self.config, 'reason_max_chars': 600}, ['20', '10'])
        a['format']['properties']['reason']['maxLength'] = 600
        self.assertEqual(a, b)
        self.assertIn('tiếng Việt', a['messages'][0]['content'])

    def test_observed_flags_are_separate_from_failure_budgets(self):
        f = rationale_flags(None, self.shared, 360, False)
        self.assertFalse(f['observed_cjk_ideograph'])
        self.assertFalse(f['observed_length_cap'])
        self.assertTrue(f['budget_cjk_ideograph'])
        self.assertTrue(f['budget_length_cap'])
        self.assertTrue(f['reason_unavailable'])

    def test_cjk_punctuation_not_ideographs_and_terminal_only_heuristic(self):
        f = rationale_flags('Ví dụ。', self.shared, 360, True)
        self.assertFalse(f['observed_cjk_ideograph'])
        self.assertTrue(f['observed_cjk_punctuation'])
        self.assertTrue(f['observed_no_terminal_punctuation'])
        self.assertTrue(rationale_flags('中文.', self.shared, 360, True)['observed_cjk_ideograph'])

    def test_numeric_rounding_and_exact_support_id(self):
        shared = {**self.shared, 'selected_problem_id': '10'}
        self.assertFalse(rationale_flags('Mastery 23%, support 12.', shared, 360, True)['numeric_mismatch'])
        self.assertTrue(rationale_flags('Support 13.', shared, 360, True)['numeric_mismatch'])
        self.assertTrue(rationale_flags('problem_id 11.', shared, 360, True)['unknown_id'])
        self.assertFalse(rationale_flags('Mastery 0,23.', shared, 360, True)['numeric_mismatch'])

    def test_failed_generation_preserves_reason_and_flags(self):
        response = {'message': {'content': json.dumps({'problem_id': '10', 'reason': '中文.'})},
                    'prompt_eval_count': 100, 'eval_count': 512, 'done': True, 'done_reason': 'length'}
        row = run_selection(self.shared, self.config, ['10', '20'], lambda request, timeout: response)
        self.assertFalse(row['candidate_valid'])
        self.assertEqual(row['reason'], '中文.')
        self.assertTrue(row['rationale_flags']['observed_cjk_ideograph'])

    def test_contract_rejects_lower_cap_rate_with_more_errors(self):
        rows = [{'cap': cap, 'candidate_valid': True, 'rationale_flags': rationale_flags('OK.', self.shared, cap, True)} for cap in (360, 600) for _ in range(24)]
        rows[0]['rationale_flags']['observed_length_cap'] = True
        self.assertEqual(choose_contract(rows)['selected_cap'], 600)
        rows[24]['candidate_valid'] = False
        self.assertEqual(choose_contract(rows)['selected_cap'], 360)

    def test_rubric_weights_variants_and_zero_valid_contributes_zero(self):
        rows = [{'graph_variant': v, 'candidate_valid': i < valid} for v, valid in [('curriculum_edges', 120), ('no_edges', 60)] for i in range(120)]
        ratings = [{'graph_variant': v, 'student_id': 'local', 'scores': [score] * 4} for v, score in [('curriculum_edges', 2), ('no_edges', 1)]]
        self.assertEqual(rubric_estimate(rows, ratings)['unconditional_mean'], 1.25)
        for r in rows:
            if r['graph_variant'] == 'no_edges': r['candidate_valid'] = False
        self.assertEqual(rubric_estimate(rows, ratings[:1])['unconditional_mean'], 1)

    def test_missing_human_ratings_never_pass(self):
        rows = [{'graph_variant': v, 'candidate_valid': True} for v in ['curriculum_edges', 'no_edges']]
        self.assertFalse(rubric_estimate(rows, [])['pass'])

    def test_stop_stability_uses_32_of_40_and_all_failure_budgets(self):
        flags = rationale_flags('Đủ câu.', self.shared, 360, True)
        rows = [{'graph_variant': v, 'candidate_valid': True, 'rationale_flags': deepcopy(flags)} for v in ['curriculum_edges', 'no_edges'] for _ in range(120)]
        metrics = {'representative': {v: {'id_stable_students': 31} for v in ['curriculum_edges', 'no_edges']}}
        result = stop_decision(rows, metrics, [])
        self.assertFalse(result['stability_pass'])
        self.assertFalse(result['all_operational_requirements_met'])
        for i in range(3):
            rows[i]['candidate_valid'] = False
            rows[i]['rationale_flags'] = rationale_flags(None, self.shared, 360, False)
        self.assertFalse(stop_decision(rows, metrics, [])['rationale_flags_pass'])

    def test_packet_samples_flagged_valid_rows_and_only_actual_available_rows(self):
        rows = [{'candidate_valid': True, 'graph_variant': v, 'student_id': i, 'selected_problem_id': '10',
                 'reason': '中文.', 'request': {'messages': [{}, {'content': '{}'}]}} for v in ['curriculum_edges', 'no_edges'] for i in range(25)]
        packet = rubric_packet(rows, self.config)
        self.assertEqual(len(packet), 40)
        self.assertTrue(all(r['scores'] is None and r['reason'] == '中文.' for r in packet))

    def test_repeat_scope_accounting_and_post_runtime_failure_preserves_response(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = RuntimeJournal(Path(directory) / 'calls.jsonl')
            journal.append(1, 'call_scope', scope='repeat')
            def call(request, timeout):
                journal.append(journal.call_index, 'transport_started')
                return {'real': True}
            identities = iter(({'v': 1}, {'v': 2}))
            with self.assertRaises(RuntimeIntegrityError):
                journal.chat({}, timeout=1, call=call, read_identity=lambda: next(identities), expected={'v': 1})
            self.assertEqual(accounting(journal.path)['repeat'], {'attempts': 1, 'transport': 1, 'responses': 1})

    def test_v3_batch_stops_before_next_study_call_on_runtime_drift(self):
        schedule = [{'shared': self.shared, 'enum_ids': ['10', '20'], 'scope': 'study',
                     'cohort': 'representative', 'student_id': 'local', 'scenario_id': 'toy',
                     'graph_variant': variant, 'repetition': 0, 'permutation': [0, 1]}
                    for variant in ['curriculum_edges', 'no_edges']]
        old = {'reference_graph': self.shared['graph'], 'bplus': {
            'source_weak_threshold': .5, 'target_weak_threshold': .5, 'target_train_success_rate': .7}}
        calls = []
        def transport(request, timeout):
            calls.append(request)
            return {'message': {'content': json.dumps({'problem_id': '10', 'reason': 'Ước lượng kỹ năng.'})},
                    'prompt_eval_count': 100, 'eval_count': 20, 'done': True, 'done_reason': 'stop'}
        def local(endpoint):
            if endpoint == 'tags':
                return {'models': [{'name': self.config['agent']['model'], 'digest': self.config['model_digest']}]}
            return {'version': 'drift' if len(calls) == 5 else self.config['expected_ollama_version']}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'output', lambda phase: root / (phase + '.json')), \
                 patch.object(runner, 'committed', return_value='synthetic-test'), \
                 patch.object(runner, 'local_json', side_effect=local), patch.object(runner, 'call_chat', side_effect=transport):
                with self.assertRaises(RuntimeIntegrityError):
                    runner.execute('study', self.config, old, schedule, {}, [], {}, {})
            self.assertEqual(len(calls), 5)
            self.assertEqual(len(json.loads((root / 'study/runs.partial.json').read_text(encoding='utf-8'))), 1)
            self.assertEqual(accounting(root / 'study/calls.jsonl')['study'], {'attempts': 1, 'transport': 1, 'responses': 1})


if __name__ == '__main__':
    unittest.main()
