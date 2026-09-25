import unittest
import pandas as pd

from src.rq2.graph import build_prototype_graph
from src.rq2.candidates import build_candidate_pool, generate_candidates
from src.rq2.policy import recommend_bplus


def train_data():
    rows = []
    for skill in ['277', '279', '311', '312', '47', '77', '79', '18', '17', '280']:
        for problem, outcomes in [(f'{skill}-a', [0, 1, 0]), (f'{skill}-b', [1, 1, 1])]:
            for correct in outcomes:
                rows.append({'skill_id': skill, 'problem_id': problem, 'correct': correct})
    return pd.DataFrame(rows)


class RQ2PolicyTests(unittest.TestCase):
    def test_rejects_heldout_rows_in_graph_and_pool(self):
        train = train_data()
        train['split'] = 'train'
        graph = build_prototype_graph(train, n_skills=10)
        heldout = train.copy()
        heldout.loc[0, 'split'] = 'validation'
        with self.assertRaises(ValueError):
            build_prototype_graph(heldout, n_skills=10)
        with self.assertRaises(ValueError):
            build_candidate_pool(heldout, graph)

    def test_graph_and_pool_use_training_metadata_with_explicit_assumption(self):
        train = train_data()
        graph = build_prototype_graph(train, n_skills=10)
        self.assertEqual(len(graph['skills']), 10)
        self.assertGreaterEqual(len(graph['edges']), 4)
        self.assertTrue(all(e['basis'] == 'prototype_assumption' for e in graph['edges']))
        pool = build_candidate_pool(train, graph)
        self.assertEqual(len(pool), 20)
        self.assertTrue(all(set(c) == {'problem_id', 'skill_id', 'difficulty', 'support'} for c in pool))
        self.assertTrue(all(c['support'] == 3 for c in pool))

    def test_candidates_are_valid_and_diverse(self):
        graph = build_prototype_graph(train_data(), n_skills=10)
        pool = build_candidate_pool(train_data(), graph)
        state = {'state_type': 'BKT_p_mastery', 'skills': {s: i / 10 for i, s in enumerate(graph['skills'])}}
        selected = generate_candidates(state, graph, pool, n_candidates=8)
        self.assertEqual(len(selected), 8)
        self.assertGreaterEqual(len({c['skill_id'] for c in selected}), 4)
        self.assertGreaterEqual(len({c['difficulty'] for c in selected}), 2)
        self.assertTrue({c['problem_id'] for c in selected} <= {c['problem_id'] for c in pool})

    def test_candidates_include_weak_and_strong_readiness(self):
        graph = {'skills': [str(i) for i in range(20)], 'edges': []}
        state = {'skills': {str(i): i / 19 for i in range(20)}}
        pool = [{'problem_id': str(i), 'skill_id': str(i),
                 'difficulty': i / 19, 'support': 5} for i in range(20)]
        selected = generate_candidates(state, graph, pool, n_candidates=8)
        levels = [state['skills'][c['skill_id']] for c in selected]
        self.assertEqual(len(selected), 8)
        self.assertTrue(any(x < .3 for x in levels))
        self.assertTrue(any(x > .7 for x in levels))

    def test_bplus_prioritizes_weak_prerequisite_then_fit_then_support_id(self):
        graph = {'skills': ['a', 'b', 'c'], 'edges': [{'prerequisite': 'a', 'target': 'b', 'basis': 'prototype_assumption'}]}
        state = {'state_type': 'BKT_p_mastery', 'skills': {'a': .2, 'b': .4, 'c': .9}}
        candidates = [
            {'problem_id': 'z', 'skill_id': 'b', 'difficulty': .5, 'support': 100},
            {'problem_id': 'b', 'skill_id': 'a', 'difficulty': .2, 'support': 2},
            {'problem_id': 'a', 'skill_id': 'a', 'difficulty': .2, 'support': 2},
            {'problem_id': 'c', 'skill_id': 'c', 'difficulty': .9, 'support': 1000},
        ]
        self.assertEqual(recommend_bplus(state, graph, candidates)['problem_id'], 'a')

    def test_invalid_candidates_rejected(self):
        with self.assertRaises(ValueError):
            recommend_bplus({'skills': {'a': .5}}, {'skills': ['a'], 'edges': []},
                            [{'problem_id': 'p', 'skill_id': 'a', 'difficulty': 1.2, 'support': 1}])
