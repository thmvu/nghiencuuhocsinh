"""A runtime change must preserve the last response and stop further calls."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_foundational_rq2_explanation1_replication as runner
from src.rq2.foundational_validation import compact_graph
from src.rq2.grounded_explanation import explanation_packet, template_explanation

ROOT = Path(__file__).resolve().parents[1]


class RuntimeGuardTests(unittest.TestCase):
    def test_changed_runtime_preserves_response_and_stops_before_next_call(self):
        config = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_explanation1.json').read_text(encoding='utf-8'))
        config['expected_ollama_version'] = '0.35.1'
        policy = {'source_weak_threshold': .5, 'target_weak_threshold': .5, 'target_train_success_rate': .7}
        graph = compact_graph({'skills': ['a'], 'skill_to_standard': {'a': 'S'}, 'edges': []}, 'no_edges')
        shared = {'state': {'state_type': 'BKT_p_mastery', 'history_length': 5, 'skills': {'a': .2}},
                  'graph': graph, 'candidates': [{'problem_id': 'P', 'skill_id': 'a', 'difficulty': .7, 'support': 10}]}
        schedule = [{'cohort': 'toy', 'scenario_id': 'toy1', 'student_id': 'fictional', 'repetition': 0,
                     'graph_variant': variant, 'permutation': [0], 'shared': shared, 'enum_ids': ['P']}
                    for variant in ('curriculum_edges', 'no_edges')]
        packet, factor = explanation_packet(shared, policy)
        output = template_explanation(packet, factor)
        calls = []
        def chat(request, timeout):
            calls.append(request)
            return {'message': {'content': json.dumps(output)}, 'done': True, 'done_reason': 'stop',
                    'prompt_eval_count': 100, 'eval_count': 100}
        def local(endpoint, payload=None):
            if endpoint == 'version':
                return {'version': '0.36.0' if len(calls) >= 5 else '0.35.1'}
            if endpoint == 'tags':
                return {'models': [{'name': config['model'], 'digest': config['model_digest']}]}
            return {'model_info': {'toy.context_length': 32768}}
        prepared = (config, policy, schedule, {'toy': {'n_students': 1}}, {}, [])
        with tempfile.TemporaryDirectory() as directory:
            private, summary = Path(directory) / 'private', Path(directory) / 'summary.json'
            with patch.object(runner, 'PRIVATE', private), patch.object(runner, 'OUTPUT', summary), \
                    patch.object(runner, 'prepare_replication', return_value=prepared), \
                    patch.object(runner, 'local_json', side_effect=local), patch.object(runner, 'call_chat', side_effect=chat), \
                    patch.object(sys, 'argv', ['replication', '--run-agent']):
                with self.assertRaisesRegex(ValueError, 'pinned model/runtime'):
                    runner.main()
            rows = json.loads((private / 'runs.partial.json').read_text(encoding='utf-8'))
            self.assertEqual(len(calls), 5)  # four context probes plus one study call
            self.assertEqual(len(rows), 1)
            self.assertIsNotNone(rows[0]['raw_response'])
            self.assertEqual(rows[0]['observed_runtime_version_before_call'], '0.35.1')
            self.assertEqual(rows[0]['observed_runtime_version_after_call'], '0.36.0')
            self.assertFalse((private / 'runs.json').exists())

    def test_partial_calls_cannot_be_overwritten_or_silently_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            (private / 'runs.partial.json').write_text('[]', encoding='utf-8')
            with patch.object(runner, 'PRIVATE', private), patch.object(runner, 'prepare_replication') as prepare, \
                    patch.object(sys, 'argv', ['replication', '--run-agent']):
                with self.assertRaisesRegex(ValueError, 'never overwrite'):
                    runner.main()
                prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
