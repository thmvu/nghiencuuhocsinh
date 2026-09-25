"""Independent adversarial checks of RQ2 validation-only construction."""

import unittest

import pandas as pd

from src.models.bkt import BKT
from src.rq2.scenarios import sample_validation_scenarios
from src.rq2.state import bkt_mastery_snapshot
from src.rq2.graph import build_prototype_graph
from src.rq2.candidates import build_candidate_pool, generate_candidates
from src.rq2.policy import recommend_bplus
from src.rq2.agent_validation import run_validation_cases, summarize_agent_validation


def _history():
    return pd.DataFrame([
        {'user_id': student, 'order_id': step, 'skill_id': 'x',
         'correct': step % 2, 'split': 'validation'}
        for student in ('a', 'b', 'c', 'd') for step in range(1, 9)
    ])


class IndependentRQ2Tests(unittest.TestCase):
    def test_future_outcomes_cannot_change_selected_validation_scenarios(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        frame = _history()
        scenarios = sample_validation_scenarios(frame, model, 3, seed=19,
                                                 min_history=5, skill_universe=['x', 'y'])
        altered = frame.copy()
        for scenario in scenarios:
            mask = ((altered.user_id == scenario['student_id']) &
                    (altered.order_id > scenario['cutoff_order_id']))
            altered.loc[mask, 'correct'] = 1 - altered.loc[mask, 'correct']
        self.assertEqual(scenarios, sample_validation_scenarios(
            altered, model, 3, seed=19, min_history=5, skill_universe=['x', 'y']))
        self.assertEqual(len({scenario['student_id'] for scenario in scenarios}), 3)
        self.assertTrue(all(scenario['state']['history_length'] == scenario['cutoff_order_id']
                            for scenario in scenarios))

    def test_snapshot_rejects_ambiguous_stringified_skill_ids(self):
        model = BKT.from_parameters((.2, .1, .2, .1))
        history = pd.DataFrame([
            {'user_id': 'a', 'order_id': 1, 'skill_id': 1, 'correct': 1, 'split': 'validation'},
            {'user_id': 'a', 'order_id': 2, 'skill_id': '1', 'correct': 0, 'split': 'validation'},
        ])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            bkt_mastery_snapshot(model, history)

    def test_training_metadata_builders_reject_validation_rows(self):
        frame = pd.DataFrame([
            {'problem_id': f'p{i}', 'skill_id': str(i), 'correct': i % 2,
             'split': 'validation'} for i in range(10)
        ])
        graph = {'skills': [str(i) for i in range(10)], 'edges': []}
        with self.assertRaises(ValueError):
            build_prototype_graph(frame, n_skills=10)
        with self.assertRaises(ValueError):
            build_candidate_pool(frame, graph)

    def test_bplus_does_not_mutate_shared_candidate_set(self):
        graph = {'skills': ['a', 'b'], 'edges': [
            {'prerequisite': 'a', 'target': 'b', 'basis': 'prototype_assumption'}]}
        state = {'state_type': 'BKT_p_mastery', 'skills': {'a': .2, 'b': .7}}
        candidates = [
            {'problem_id': 'p2', 'skill_id': 'b', 'difficulty': .6, 'support': 10},
            {'problem_id': 'p1', 'skill_id': 'a', 'difficulty': .3, 'support': 3},
        ]
        before = [dict(candidate) for candidate in candidates]
        chosen = recommend_bplus(state, graph, candidates)
        self.assertIn(chosen, candidates)
        self.assertEqual(candidates, before)
        chosen['support'] = -1
        self.assertEqual(candidates, before)

    def test_agent_runner_rejects_misreported_bplus_choice(self):
        graph = {'skills': ['a', 'b'], 'edges': [
            {'prerequisite': 'a', 'target': 'b', 'basis': 'prototype_assumption'}]}
        state = {'state_type': 'BKT_p_mastery', 'skills': {'a': .2, 'b': .7},
                 'history_length': 5}
        candidates = [
            {'problem_id': 'p1', 'skill_id': 'a', 'difficulty': .3, 'support': 3},
            {'problem_id': 'p2', 'skill_id': 'b', 'difficulty': .6, 'support': 10},
        ]
        shared = {'state': state, 'graph': graph, 'candidates': candidates}
        case = {'scenario_id': 'validation_001', 'student_id': 'private_1',
                'state': state, 'shared_input': shared,
                'bplus': candidates[1]}
        self.assertEqual(recommend_bplus(state, graph, candidates)['problem_id'], 'p1')
        with self.assertRaises(ValueError):
            run_validation_cases([case], model='mock', call=lambda request, timeout: '{}')
