"""Lost-runtime-endpoint regression and independent selection contract."""

from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from src.rq2.foundational_validation import compact_graph
from src.rq2.runtime_journal import RuntimeIntegrityError, RuntimeJournal
from src.rq2.selection_agent_v2 import run_selection, selection_request
from scripts.prepare_foundational_rq2_selection_v2 import aggregate

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
    def test_failures_remain_in_planned_denominator_and_graph_pair_count(self):
        schedule = [{'cohort': 'pilot', 'student_id': 'local', 'repetition': rep, 'graph_variant': variant}
                    for rep in range(3) for variant in ('curriculum_edges', 'no_edges')]
        rows = [{**item, 'candidate_valid': not (item['repetition'] == 2 and item['graph_variant'] == 'no_edges'),
                 'selected_problem_id': item['graph_variant'], 'selected_position': 0, 'selected_enum_position': 1,
                 'agrees_with_bplus': False, 'reference_soft_remediation': False,
                 'selected_mastery': .2, 'selected_train_success_rate': .7, 'selected_support': 10,
                 'latency_seconds': 1, 'error_stage': 'transport' if item['repetition'] == 2 and item['graph_variant'] == 'no_edges' else None}
                for item in schedule]
        result = aggregate(rows, schedule, {'pilot': {}})['pilot']
        self.assertEqual(result['no_edges']['valid_selection_fraction_all_planned_calls'], 2 / 3)
        self.assertEqual(result['no_edges']['complete_valid_triplets'], 0)
        self.assertEqual(result['no_edges']['incomplete_valid_triplets'], 1)
        self.assertEqual(result['paired_graph_sensitivity_descriptive'], {
            'planned_pairs': 3, 'valid_pairs': 2, 'incomplete_valid_pairs': 1, 'changed_choice_count': 2})


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
        shared = deepcopy(self.shared)
        shared['graph']['edges'] = []
        config = {**self.config, 'reference_graph': self.shared['graph']}
        request, _ = selection_request(shared, config, ['B', 'A'])
        self.assertEqual(json.loads(request['messages'][1]['content'])['graph']['edges'], [])
        self.assertNotIn('reference_graph', json.dumps(request))

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


if __name__ == '__main__':
    unittest.main()
