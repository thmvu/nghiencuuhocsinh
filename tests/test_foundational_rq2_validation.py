"""V4 policy behavior, edge ablation, repeated-input and runtime boundaries."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

import pandas as pd

from src.models.bkt import BKT
from src.rq2.foundational_validation import (
    LINK_SEMANTICS, build_foundational_cases, build_observed_link_challenge, case_coverage, checked_telemetry, compact_graph,
    make_agent_request, recommend_foundational_bplus, relevant_weak_sources,
    run_agent, run_deterministic, shared_repetitions, summarize_operational,
)

ROOT = Path(__file__).resolve().parents[1]


class FoundationalValidationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_validation.json').read_text(encoding='utf-8'))
        self.config.update(validation_scenarios=2, candidates_per_scenario=3, minimum_train_support=1)
        self.audit = {'skills': ['a', 'b', 'c'], 'skill_to_standard': {'a': 'S', 'b': 'T', 'c': 'U'},
                      'edges': [{'prerequisite': 'a', 'target': 'b'}],
                      'standard_edges': ['must_not_reach_prompt'], 'standard_topological_order': ['secret_order'],
                      'sources': {'audit_only': 'source'}, 'input_sha256': {'hash': 'audit'}}
        self.shared = {'state': {'state_type': 'BKT_p_mastery', 'history_length': 5,
                                  'skills': {'a': .2, 'b': .3, 'c': .3}},
                       'graph': compact_graph(self.audit, 'curriculum_edges'),
                       'candidates': [{'problem_id': 'A', 'skill_id': 'a', 'difficulty': .99, 'support': 10},
                                      {'problem_id': 'B', 'skill_id': 'b', 'difficulty': .7, 'support': 10}]}

    def test_endpoint_changes_choice_when_new_target_absent(self):
        self.assertEqual(recommend_foundational_bplus(self.shared, self.config['bplus'])['problem_id'], 'A')
        shared = deepcopy(self.shared)
        shared['graph']['edges'][0]['target'] = 'c'
        self.assertEqual(recommend_foundational_bplus(shared, self.config['bplus'])['problem_id'], 'B')
        shared = deepcopy(self.shared)
        shared['state']['skills']['b'] = .9
        self.assertEqual(recommend_foundational_bplus(shared, self.config['bplus'])['problem_id'], 'B')

    def test_multiple_source_ids_neither_merged_nor_AND_gated(self):
        shared = deepcopy(self.shared)
        shared['graph']['skill_to_standard']['c'] = 'S'
        shared['graph']['edges'].append({'prerequisite': 'c', 'target': 'b'})
        shared['state']['skills']['c'] = .95
        before = deepcopy(shared)
        self.assertEqual(relevant_weak_sources(shared, self.config['bplus']), {'a'})
        self.assertEqual(recommend_foundational_bplus(shared, self.config['bplus'])['problem_id'], 'A')
        shared['graph']['edges'] *= 3
        self.assertEqual(recommend_foundational_bplus(shared, self.config['bplus'])['problem_id'], 'A')
        self.assertEqual(shared['state'], before['state'])

    def test_coverage_distinguishes_weak_source_from_active_candidate_signal(self):
        case = {'state': self.shared['state'], 'candidates': self.shared['candidates']}
        result = case_coverage([case], self.audit, self.config)
        self.assertEqual(result['scenarios_with_relevant_source_candidate'], 1)
        case = deepcopy(case)
        case['candidates'] = case['candidates'][:1]
        result = case_coverage([case], self.audit, self.config)
        self.assertEqual(result['scenarios_with_any_weak_source'], 1)
        self.assertEqual(result['scenarios_with_relevant_source_candidate'], 0)

    def test_ablation_allowlist_cannot_leak_audit_edges_or_topology(self):
        shared = deepcopy(self.shared)
        shared['graph'] = compact_graph(self.audit, 'no_edges')
        request, bound = make_agent_request(shared, self.config['agent'])
        payload = json.loads(request['messages'][1]['content'])
        self.assertEqual(payload['graph']['edges'], [])
        self.assertEqual(set(payload['graph']), {'skills', 'edges', 'skill_to_standard', 'link_semantics'})
        self.assertNotIn('must_not_reach_prompt', json.dumps(request))
        self.assertNotIn('secret_order', json.dumps(request))
        self.assertEqual(payload['state'], shared['state'])
        self.assertEqual(payload['candidates'], shared['candidates'])
        self.assertLess(bound + self.config['agent']['num_predict'], self.config['agent']['num_ctx'])
        shared['graph']['standard_edges'] = self.audit['standard_edges']
        with self.assertRaises(ValueError):
            make_agent_request(shared, self.config['agent'])

    def build_cases(self):
        validation = pd.DataFrame([{'user_id': u, 'order_id': i, 'skill_id': ('a', 'b', 'c')[i % 3],
                                     'correct': i % 2, 'split': 'validation'}
                                    for u in ('private_a', 'private_b') for i in range(1, 12)])
        model = BKT.from_parameters((.2, .1, .2, .1))
        pool = self.shared['candidates'] + [{'problem_id': 'C', 'skill_id': 'c', 'difficulty': .5, 'support': 10}]
        cases, pool = build_foundational_cases(validation, model, self.audit, pool, self.config)
        return cases, validation, model, pool

    def test_repetitions_share_membership_order_and_baseline_draws(self):
        cases, _, _, _ = self.build_cases()
        before = deepcopy(cases)
        repetitions = list(shared_repetitions(cases, self.audit, self.config))
        for i in range(0, len(repetitions), 2):
            left, right = repetitions[i:i + 2]
            self.assertEqual(left[1], right[1])
            self.assertEqual(left[3:5], right[3:5])
            self.assertEqual(left[5]['state'], right[5]['state'])
            self.assertEqual(left[5]['candidates'], right[5]['candidates'])
        runs = run_deterministic(cases, self.audit, self.config)
        self.assertEqual(runs, run_deterministic(cases, self.audit, self.config))
        self.assertEqual(cases, before)
        for name in ('B+', 'random'):
            for case in cases:
                group = [r for r in runs if r['policy'] == name and r['scenario_id'] == case['scenario_id'] and r['graph_variant'] == 'curriculum_edges']
                if name == 'B+':
                    self.assertEqual(len({r['selected_problem_id'] for r in group}), 1)
        summary = summarize_operational(runs)
        self.assertNotIn('private_a', json.dumps(summary))
        self.assertEqual(summary['policies']['random']['paired_selection_change_rate_among_valid_pairs'], 0)
        self.assertEqual(summary['policies']['always_first']['paired_selection_change_rate_among_valid_pairs'], 0)

    def test_future_labels_and_heldout_boundaries(self):
        cases, validation, model, pool = self.build_cases()
        altered = validation.copy()
        for case in cases:
            mask = (altered.user_id == case['student_id']) & (altered.order_id > case['cutoff_order_id'])
            altered.loc[mask, 'correct'] = 1 - altered.loc[mask, 'correct']
        after, _ = build_foundational_cases(altered, model, self.audit, pool, self.config)
        self.assertEqual(cases, after)
        with self.assertRaises(ValueError):
            build_foundational_cases(validation.assign(split='test'), model, self.audit, pool, self.config)
        for stage in ('test', 'lock_c'):
            with self.assertRaises(ValueError):
                build_foundational_cases(validation, model, self.audit, pool, {**self.config, 'stage': stage})

    def test_context_rejects_overbudget_missing_counts_and_output_cutoff(self):
        runtime = {**self.config['agent'], 'num_ctx': 256}
        with self.assertRaisesRegex(ValueError, 'budget'):
            make_agent_request(self.shared, runtime)
        runtime = self.config['agent']
        with self.assertRaisesRegex(ValueError, 'telemetry'):
            checked_telemetry({'done': True}, runtime, 3000)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            checked_telemetry({'prompt_eval_count': 20, 'eval_count': 256, 'done': True, 'done_reason': 'length'}, runtime, 3000)
        self.assertEqual(checked_telemetry({'prompt_eval_count': 20, 'eval_count': 30, 'done': True, 'done_reason': 'stop'}, runtime, 3000), 20)

    def test_mock_transport_is_only_a_unit_test_not_study_result(self):
        cases, _, _, _ = self.build_cases()
        def call(request, timeout):
            candidate = json.loads(request['messages'][1]['content'])['candidates'][0]
            return {'message': {'content': json.dumps({'problem_id': candidate['problem_id'], 'reason': 'synthetic test'})},
                    'prompt_eval_count': 100, 'eval_count': 20, 'done': True, 'done_reason': 'stop'}
        completed = []
        runs = run_agent(cases, self.audit, self.config, call,
                         checkpoint=lambda records: completed.append(len(records)))
        self.assertEqual(len(runs), 12)
        self.assertEqual(completed, list(range(1, 13)))
        self.assertTrue(all(r['candidate_valid'] for r in runs))
        summary = summarize_operational(runs)
        self.assertEqual(summary['policies']['Agent']['paired_selection_change_rate_among_valid_pairs'], 0)

    def challenge_inputs(self):
        frame = pd.DataFrame([{'user_id': u, 'order_id': i, 'skill_id': ('a' if u == 'unobserved_target' else ('a', 'b')[i % 2]),
                               'correct': 0, 'split': 'validation'}
                              for u in ('observed_pair', 'unobserved_target') for i in range(1, 9)])
        config = deepcopy(self.config)
        config['supplementary_challenge']['prefix_length'] = 5
        model = BKT.from_parameters((.2, .01, .2, .1))
        pool = self.shared['candidates'] + [{'problem_id': 'C', 'skill_id': 'c', 'difficulty': .5, 'support': 10}]
        return frame, model, pool, config

    def test_challenge_excludes_unobserved_priors_and_keeps_common_candidates(self):
        frame, model, pool, config = self.challenge_inputs()
        frozen = model.global_parameters_snapshot()
        cases, _ = build_observed_link_challenge(frame, model, self.audit, pool, config)
        self.assertEqual([c['student_id'] for c in cases], ['observed_pair'])
        self.assertEqual(cases[0]['state']['history_length'], 5)
        self.assertEqual(cases[0]['construction_skill_pair'], ['a', 'b'])
        self.assertEqual(model.global_parameters_snapshot(), frozen)
        coverage = case_coverage(cases, self.audit, config)
        self.assertEqual(coverage['scenarios_with_relevant_source_candidate'], 1)
        repetitions = list(shared_repetitions(cases, self.audit, config))
        for i in range(0, len(repetitions), 2):
            self.assertEqual(repetitions[i][5]['candidates'], repetitions[i + 1][5]['candidates'])
            self.assertEqual(repetitions[i][3], repetitions[i + 1][3])
            request, _ = make_agent_request(repetitions[i + 1][5], config['agent'])
            self.assertNotIn('construction_skill_pair', json.dumps(request))
        summary = summarize_operational(run_deterministic(cases, self.audit, config))
        self.assertNotIn('observed_pair', json.dumps(summary))
        for name in ('random', 'always_first'):
            variants = summary['policies'][name]['variants']
            self.assertEqual(variants['curriculum_edges']['soft_source_remediation_selected_rate'],
                             variants['no_edges']['soft_source_remediation_selected_rate'])

    def test_challenge_future_outcomes_do_not_select_cases_or_candidates(self):
        frame, model, pool, config = self.challenge_inputs()
        before, _ = build_observed_link_challenge(frame, model, self.audit, pool, config)
        frame.loc[frame.order_id > 5, 'correct'] = 1
        after, _ = build_observed_link_challenge(frame, model, self.audit, list(reversed(pool)), config)
        self.assertEqual(before, after)

    def test_challenge_rejects_test_duplicate_chronology_and_no_observed_links(self):
        frame, model, pool, config = self.challenge_inputs()
        for bad in (frame.assign(split='test'), pd.concat([frame, frame.iloc[:1]])):
            with self.assertRaises(ValueError):
                build_observed_link_challenge(bad, model, self.audit, pool, config)
        with self.assertRaisesRegex(ValueError, 'no observed'):
            build_observed_link_challenge(frame.assign(skill_id='a'), model, self.audit, pool, config)

    def test_challenge_rejects_shared_problem_ids_across_skills(self):
        frame, model, pool, config = self.challenge_inputs()
        pool.append({**pool[0], 'skill_id': 'b'})
        with self.assertRaisesRegex(ValueError, 'unique problem'):
            build_observed_link_challenge(frame, model, self.audit, pool, config)


if __name__ == '__main__':
    unittest.main()
