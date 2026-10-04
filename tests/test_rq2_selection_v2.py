"""Lost-runtime-endpoint regression and independent selection contract."""

from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from src.rq2.foundational_validation import compact_graph
from src.rq2.runtime_journal import RuntimeIntegrityError, RuntimeJournal
from src.rq2.selection_agent_v2 import run_selection, selection_request
from scripts import prepare_foundational_rq2_selection_v2 as runner
from scripts.prepare_foundational_rq2_selection_v2 import aggregate, mastery_metrics

ROOT = Path(__file__).resolve().parents[1]


class JournalTests(unittest.TestCase):
    def test_response_is_on_disk_before_post_runtime_endpoint_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calls.jsonl'
            journal = RuntimeJournal(path)
            observations = []
            def identity():
                observations.append(1)
                if len(observations) == 2:
                    saved = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
                    self.assertEqual(saved[-1]['event'], 'response_received')
                    self.assertEqual(saved[-1]['raw_response'], {'real_response': 'received'})
                    raise OSError('synthetic endpoint connection lost')
                return {'version': '1'}
            with self.assertRaisesRegex(RuntimeIntegrityError, 'observation unavailable'):
                journal.chat({'model': 'toy'}, timeout=1, call=lambda request, timeout: {'real_response': 'received'},
                             read_identity=identity, expected={'version': '1'})
            saved = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(saved[-1]['event'], 'runtime_observation_failed')
            self.assertEqual(saved[-1]['phase'], 'after_call')

    def test_runtime_mismatch_preserves_response_and_rejects_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calls.jsonl'
            journal = RuntimeJournal(path)
            values = iter(({'version': '1'}, {'version': '2'}))
            with self.assertRaises(RuntimeIntegrityError):
                journal.chat({}, timeout=1, call=lambda request, timeout: {'done': True},
                             read_identity=lambda: next(values), expected={'version': '1'})
            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(events[-1]['event'], 'runtime_mismatch')
            self.assertTrue(any(e['event'] == 'response_received' for e in events))

    def test_transport_error_body_survives_for_journal_and_caller(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calls.jsonl'
            journal = RuntimeJournal(path)
            def call(request, timeout):
                raise HTTPError('http://127.0.0.1/toy', 500, 'synthetic', {}, io.BytesIO(b'private diagnostic'))
            try:
                journal.chat({}, timeout=1, call=call, read_identity=lambda: {'v': 1}, expected={'v': 1})
            except HTTPError as error:
                self.assertEqual(error.read(), b'private diagnostic')
            else:
                self.fail('transport error was suppressed')
            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            failure = next(e for e in events if e['event'] == 'transport_failed')
            self.assertEqual(failure['http_body'], 'private diagnostic')
            self.assertEqual(events[-1]['phase'], 'after_transport_failure')

    def test_connection_error_is_logged_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calls.jsonl'
            journal = RuntimeJournal(path)
            def call(request, timeout):
                raise OSError('synthetic connection refused')
            with self.assertRaisesRegex(OSError, 'connection refused'):
                journal.chat({}, timeout=1, call=call, read_identity=lambda: {'v': 1}, expected={'v': 1})
            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(events[-2]['event'], 'transport_failed')
            self.assertEqual(events[-1]['phase'], 'after_transport_failure')

    def test_existing_journal_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calls.jsonl'
            path.write_text('preserved', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                RuntimeJournal(path)
            self.assertEqual(path.read_text(encoding='utf-8'), 'preserved')


class AggregateTests(unittest.TestCase):
    def test_changing_problem_with_same_skill_is_skill_stable_and_rank_excluded(self):
        shared = {'state': {'skills': {'a': .2}}, 'candidates': [
            {'problem_id': 'A1', 'skill_id': 'a'}, {'problem_id': 'A2', 'skill_id': 'a'}]}
        schedule = [{'cohort': 'pilot', 'student_id': 'local', 'repetition': rep,
                     'graph_variant': variant, 'shared': shared}
                    for rep in range(3) for variant in ('curriculum_edges', 'no_edges')]
        rows = [{**item, 'candidate_valid': True, 'selected_problem_id': 'A1' if item['repetition'] == 0 else 'A2',
                 'selected_position': 0, 'selected_enum_position': 0, 'agrees_with_bplus': False,
                 'reference_soft_remediation': False, 'selected_mastery': .2,
                 'selected_train_success_rate': .7, 'selected_support': 10, 'latency_seconds': 1, 'error_stage': None}
                for item in schedule]
        for row in rows:
            row.update(mastery_metrics(shared, row['selected_problem_id']))
        cell = aggregate(rows, schedule, {'pilot': {}})['pilot']['no_edges']
        self.assertEqual(cell['id_stable_fraction_complete_triplets'], 0)
        self.assertEqual(cell['skill_stable_fraction_complete_triplets'], 1)
        self.assertEqual(cell['mastery_rank_excluded_single_skill_valid_calls'], 3)
        self.assertEqual(cell['mastery_rank_coverage_all_planned_calls'], 0)
        self.assertIsNone(cell['mastery_rank_mean_valid_defined'])

    def test_failures_remain_in_planned_denominator_and_graph_pair_count(self):
        schedule = [{'cohort': 'pilot', 'student_id': 'local', 'repetition': rep, 'graph_variant': variant}
                    for rep in range(3) for variant in ('curriculum_edges', 'no_edges')]
        shared = {'state': {'skills': {'a': .2, 'b': .3}}, 'candidates': [
            {'problem_id': 'curriculum_edges', 'skill_id': 'a'}, {'problem_id': 'no_edges', 'skill_id': 'b'}]}
        for item in schedule:
            item['shared'] = shared
        rows = [{**item, 'candidate_valid': not (item['repetition'] == 2 and item['graph_variant'] == 'no_edges'),
                 'selected_problem_id': item['graph_variant'], 'selected_position': 0, 'selected_enum_position': 1,
                 'agrees_with_bplus': False, 'reference_soft_remediation': False,
                 'selected_mastery': .2, 'selected_train_success_rate': .7, 'selected_support': 10,
                 'latency_seconds': 1, 'error_stage': 'transport' if item['repetition'] == 2 and item['graph_variant'] == 'no_edges' else None}
                for item in schedule]
        for row in rows:
            row.update(mastery_metrics(shared, row['selected_problem_id'] if row['candidate_valid'] else None))
        result = aggregate(rows, schedule, {'pilot': {}})['pilot']
        self.assertEqual(result['no_edges']['valid_selection_fraction_all_planned_calls'], 2 / 3)
        self.assertEqual(result['no_edges']['complete_valid_triplets'], 0)
        self.assertEqual(result['no_edges']['incomplete_valid_triplets'], 1)
        self.assertEqual(result['no_edges']['mastery_rank_coverage_all_planned_calls'], 2 / 3)
        self.assertEqual(result['paired_graph_sensitivity_descriptive'], {
            'planned_pairs': 3, 'valid_pairs': 2, 'incomplete_valid_pairs': 1, 'changed_choice_count': 2})


class RankTests(unittest.TestCase):
    def test_distinct_skill_midrank_and_random_item_weights(self):
        shared = {'state': {'skills': {'a': .2, 'b': .2, 'c': .9}}, 'candidates': [
            {'problem_id': str(i), 'skill_id': skill} for i, skill in enumerate(['a', 'a', 'a', 'b', 'c'])]}
        result = mastery_metrics(shared, '0')
        self.assertEqual(result['selected_mastery_rank_normalized'], .25)
        self.assertAlmostEqual(result['random_expected_mastery_rank'], .4)
        self.assertAlmostEqual(result['random_probability_lowest_mastery_skill'], .8)
        self.assertAlmostEqual(result['random_probability_skill_stable'], .232)
        self.assertEqual(result['random_probability_id_stable'], 1 / 25)
        self.assertTrue(result['selected_lowest_mastery_skill'])
        self.assertEqual(mastery_metrics(shared, '4')['selected_mastery_rank_normalized'], 1)

    def test_all_tied_is_half_and_single_skill_is_undefined(self):
        shared = {'state': {'skills': {'a': .2, 'b': .2}}, 'candidates': [
            {'problem_id': 'A', 'skill_id': 'a'}, {'problem_id': 'B', 'skill_id': 'b'}]}
        self.assertEqual(mastery_metrics(shared, 'A')['selected_mastery_rank_normalized'], .5)
        shared['candidates'][1]['skill_id'] = 'a'
        result = mastery_metrics(shared, 'B')
        self.assertIsNone(result['selected_mastery_rank_normalized'])
        self.assertIsNone(result['random_expected_mastery_rank'])
        self.assertEqual(result['random_probability_skill_stable'], 1)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_selection_v2.json').read_text(encoding='utf-8'))
        graph = compact_graph({'skills': ['a', 'b'], 'skill_to_standard': {'a': 'S', 'b': 'T'},
                               'edges': [{'prerequisite': 'a', 'target': 'b'}]}, 'curriculum_edges')
        self.shared = {'state': {'state_type': 'BKT_p_mastery', 'history_length': 5, 'skills': {'a': .2, 'b': .3}},
                       'graph': graph, 'candidates': [
                           {'problem_id': 'A', 'skill_id': 'a', 'difficulty': .99, 'support': 10},
                           {'problem_id': 'B', 'skill_id': 'b', 'difficulty': .7, 'support': 10}]}

    def response(self, problem):
        return {'message': {'content': json.dumps({'problem_id': problem, 'reason': 'Mastery là ước lượng.'})},
                'prompt_eval_count': 100, 'eval_count': 30, 'done': True, 'done_reason': 'stop'}

    def test_choice_different_from_bplus_is_valid_and_not_replaced(self):
        # Frozen B+ chooses A; choosing B under a different tradeoff remains admissible.
        row = run_selection(self.shared, self.config, ['B', 'A'], lambda request, timeout: self.response('B'))
        self.assertTrue(row['candidate_valid'])
        self.assertEqual(row['selected_problem_id'], 'B')
        self.assertFalse(row['reason_semantically_verified'])

    def test_prompt_preserves_membership_order_and_has_no_winner_or_exact_bplus_objective(self):
        before = deepcopy(self.shared)
        request, _ = selection_request(self.shared, self.config, ['B', 'A'])
        self.assertEqual(json.loads(request['messages'][1]['content']), self.shared)
        self.assertNotIn('lexicographic rule', request['messages'][0]['content'])
        self.assertEqual(request['format']['properties']['problem_id']['enum'], ['B', 'A'])
        self.assertEqual(self.shared, before)
        self.assertIn('author-proposed curriculum graph', request['messages'][0]['content'])
        self.assertNotIn('prerequisite graph', request['messages'][0]['content'])
        shared = deepcopy(self.shared)
        shared['graph']['edges'] = []
        config = {**self.config, 'reference_graph': self.shared['graph']}
        request, _ = selection_request(shared, config, ['B', 'A'])
        self.assertEqual(json.loads(request['messages'][1]['content'])['graph']['edges'], [])
        self.assertNotIn('reference_graph', json.dumps(request))

    def test_changed_shared_prompt_wording_fails_explicitly(self):
        request, bound = selection_request(self.shared, self.config, ['B', 'A'])
        with patch('src.rq2.selection_agent_v2.make_agent_request', return_value=(request, bound)):
            with self.assertRaisesRegex(ValueError, 'graph wording changed'):
                selection_request(self.shared, self.config, ['B', 'A'])

    def test_invalid_choice_fails_without_retry_or_fallback(self):
        calls = []
        def call(request, timeout):
            calls.append(request)
            return self.response('outside')
        row = run_selection(self.shared, self.config, ['B', 'A'], call)
        self.assertEqual(len(calls), 1)
        self.assertFalse(row['candidate_valid'])
        self.assertIsNone(row['selected_problem_id'])
        self.assertEqual(row['error_stage'], 'output_contract')
        with self.assertRaises(ValueError):
            selection_request(self.shared, {**self.config, 'test_access': True}, ['B', 'A'])

    def test_runtime_failure_is_classified_separately(self):
        def call(request, timeout):
            raise RuntimeIntegrityError('synthetic post-call identity check failure')
        row = run_selection(self.shared, self.config, ['B', 'A'], call)
        self.assertEqual(row['error_stage'], 'runtime_integrity')
        self.assertFalse(row['candidate_valid'])


class RunnerTests(unittest.TestCase):
    setUp = SelectionTests.setUp
    response = SelectionTests.response
    # Exercise the real journal and main loop with synthetic transport only.
    def execute(self, directory, mismatch=None, before_mismatch=False):
        schedule = [{'cohort': 'pilot', 'scenario_id': 'toy', 'student_id': 'local', 'repetition': rep,
                     'graph_variant': variant, 'permutation': [0, 1], 'enum_ids': ['A', 'B'],
                     'shared': self.shared} for rep in range(3) for variant in ('curriculum_edges', 'no_edges')]
        old = {'reference_graph': self.shared['graph'], 'bplus': {
            'source_weak_threshold': .5, 'target_weak_threshold': .5, 'target_train_success_rate': .7}}
        config = {**self.config, 'new_calls_planned': len(schedule)}
        calls = []
        observations = []
        def transport(request, timeout):
            calls.append(request)
            return self.response('A')
        def local_json(endpoint):
            if endpoint == 'tags':
                return {'models': [{'name': config['agent']['model'], 'digest': config['model_digest']}]}
            observations.append(1)
            drift = (len(observations) == 2 * mismatch - 1 if before_mismatch else len(calls) == mismatch) if mismatch is not None else False
            return {'version': 'changed' if drift else config['expected_ollama_version']}
        private, output = Path(directory) / 'private', Path(directory) / 'summary.json'
        with patch.object(runner, 'PRIVATE', private), patch.object(runner, 'OUTPUT', output), \
             patch.object(runner, 'prepare_selection', return_value=(config, old, schedule, {'pilot': {'n_students': 1, 'legacy_records': []}}, {})), \
             patch.object(runner, 'baseline_rows', return_value={}), \
             patch.object(runner, 'local_json', side_effect=local_json), \
             patch.object(runner, 'call_chat', side_effect=transport), \
             patch.object(runner.sys, 'argv', ['runner', '--run-agent']):
            if mismatch is not None:
                with self.assertRaises(RuntimeIntegrityError):
                    runner.main()
            else:
                runner.main()
        return calls, private, json.loads(output.read_text())

    def test_post_call_mismatch_stops_at_k_and_preserves_k_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, private, summary = self.execute(directory, mismatch=6)
            self.assertEqual(len(calls), 4 + 2)
            rows = json.loads((private / 'runs.partial.json').read_text())
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]['error_stage'], 'runtime_integrity')
            self.assertFalse((private / 'runs.json').exists())
            self.assertEqual(summary['call_accounting']['study'], {
                'attempts_started': 2, 'transport_calls': 2, 'responses_received': 2})

    def test_success_separates_probe_and_study_calls_from_event_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, private, summary = self.execute(directory)
            self.assertEqual(len(calls), 4 + 6)
            self.assertEqual(summary['planned_probe_calls'], 4)
            self.assertEqual(summary['planned_study_calls'], 6)
            self.assertEqual(summary['call_accounting']['probe']['transport_calls'], 4)
            self.assertEqual(summary['call_accounting']['study']['transport_calls'], 6)
            self.assertGreater(len((private / 'calls.jsonl').read_text().splitlines()), len(calls))
            self.assertEqual(summary['agent_status'], 'completed_validation_not_test')

    def test_pre_call_mismatch_records_attempt_without_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, private, summary = self.execute(directory, mismatch=6, before_mismatch=True)
            self.assertEqual(len(calls), 5)
            self.assertEqual(len(json.loads((private / 'runs.partial.json').read_text())), 2)
            self.assertEqual(summary['call_accounting']['study'], {
                'attempts_started': 2, 'transport_calls': 1, 'responses_received': 1})
            self.assertEqual(summary['model_calls_completed'], 1)
            self.assertEqual(summary['study_rows_recorded'], 2)


if __name__ == '__main__':
    unittest.main()
