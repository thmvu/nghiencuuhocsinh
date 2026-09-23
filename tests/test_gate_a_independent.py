"""Independent adversarial Gate A tests; synthetic labels only, no model metrics."""
import unittest

import numpy as np
import pandas as pd

from src.preprocessing.pipeline import (
    add_history_features, add_problem_difficulty, apply_split, clean_interactions,
)
from src.evaluation.sequential import sequential_predict


def frame(users=6, length=8):
    rows = []
    for user in range(users):
        for t in range(length):
            rows.append(dict(user_id=str(user), order_id=t, problem_id=str(t % 3),
                             skill_id=str(t % 2), correct=(user + t) % 2,
                             source_row=len(rows), hint_count=100 + t,
                             bottom_hint=20 + t, attempt_count=30 + t))
    return pd.DataFrame(rows)


HISTORY = ['prior_skill_success', 'prior_skill_failure', 'prior_skill_count',
           'prior_skill_accuracy', 'prior_overall_accuracy', 'history_length', 'scored']


class IndependentHistoryTests(unittest.TestCase):
    def test_every_current_and_future_label_cannot_change_available_history(self):
        original = frame(3)
        baseline = add_history_features(original)
        for cutoff in range(8):
            changed = original.copy()
            changed.loc[(changed.user_id == '1') & (changed.order_id >= cutoff), 'correct'] ^= 1
            actual = add_history_features(changed)
            protected = (baseline.user_id != '1') | (baseline.order_id <= cutoff)
            pd.testing.assert_frame_equal(baseline.loc[protected, HISTORY], actual.loc[protected, HISTORY])

    def test_manual_interleaved_skill_history_and_cleaned_warmup(self):
        data = frame(1, 7)
        data['correct'] = [1, 0, 1, 1, 0, 0, 1]
        result = add_history_features(data, warmup=5)
        self.assertEqual(result.prior_skill_success.tolist(), [0, 0, 1, 0, 2, 1, 2])
        self.assertEqual(result.prior_skill_failure.tolist(), [0, 0, 0, 1, 0, 1, 1])
        self.assertEqual(result.history_length.tolist(), list(range(7)))
        self.assertEqual(result.scored.tolist(), [False] * 5 + [True] * 2)
        self.assertEqual(result.prior_skill_accuracy.iloc[0], .5)
        self.assertEqual(result.prior_overall_accuracy.iloc[0], .5)
        data.loc[1, 'skill_id'] = '1_2'
        data.loc[3, 'skill_id'] = None
        cleaned = add_history_features(clean_interactions(data), warmup=5)
        self.assertEqual(len(cleaned), 5)
        self.assertFalse(cleaned.scored.any())

    def test_split_rejects_overlap_and_unassigned_students(self):
        data = frame(3)
        for students in [dict(train=['0', '1'], validation=['1'], test=['2']),
                         dict(train=['0'], validation=['1'], test=[])]:
            with self.subTest(students=students), self.assertRaises(ValueError):
                apply_split(data, {'students': students})


class IndependentDifficultyTests(unittest.TestCase):
    def data(self):
        data = frame(8, 4)
        data['split'] = np.where(data.user_id.isin(['6']), 'validation',
                                 np.where(data.user_id.isin(['7']), 'test', 'train'))
        return data

    def test_each_students_labels_cannot_influence_own_oof_features(self):
        data = self.data()
        baseline = add_problem_difficulty(data, n_splits=3, alpha=10)
        for user in map(str, range(6)):
            mutated = data.copy()
            mutated.loc[mutated.user_id == user, 'correct'] ^= 1
            result = add_problem_difficulty(mutated, n_splits=3, alpha=10)
            np.testing.assert_allclose(baseline.loc[data.user_id == user, 'problem_difficulty'],
                                       result.loc[data.user_id == user, 'problem_difficulty'])

    def test_heldout_labels_cannot_change_any_difficulty(self):
        data = self.data()
        baseline = add_problem_difficulty(data, n_splits=3)
        data.loc[data.split != 'train', 'correct'] ^= 1
        result = add_problem_difficulty(data, n_splits=3)
        np.testing.assert_allclose(baseline.problem_difficulty, result.problem_difficulty)

    def test_unseen_problem_fallback_is_fold_local_not_global(self):
        data = frame(2, 3)
        data['split'] = 'train'
        data['problem_id'] = data.user_id
        data['correct'] = (data.user_id == '0').astype(int)
        result = add_problem_difficulty(data, n_splits=2, alpha=10)
        # Each fold has only the other student's unseen problem: its local mean is 0 or 1.
        np.testing.assert_allclose(result.loc[data.user_id == '0', 'problem_difficulty'], 0)
        np.testing.assert_allclose(result.loc[data.user_id == '1', 'problem_difficulty'], 1)


class SpyModel:
    def __init__(self):
        self.events = []
        self.count = None

    def reset(self, user_id):
        self.count = 0
        self.events.append(('reset', user_id))

    def predict(self, features):
        forbidden = {'correct', 'hint_count', 'bottom_hint', 'attempt_count', 'answer', 'future_correct'}
        if forbidden.intersection(features):
            raise AssertionError(f'Unsafe predict fields: {forbidden.intersection(features)}')
        try:
            features['correct'] = 1
        except TypeError:
            pass
        else:
            raise AssertionError('Predict features must be read-only')
        self.events.append(('predict', features['user_id'], features['order_id'], self.count))
        return .2 + .05 * self.count

    def update(self, observation):
        assert self.events[-1][:3] == ('predict', observation['user_id'], observation['order_id'])
        assert observation['correct'] in (0, 1)
        self.events.append(('update', observation['user_id'], observation['order_id']))
        self.count += 1


class IndependentSequentialTests(unittest.TestCase):
    def test_predict_before_observe_reset_and_matching_masks_on_shuffled_input(self):
        data = add_history_features(frame(3, 7))
        data['future_correct'] = data.correct
        model = SpyModel()
        result = sequential_predict(data.sample(frac=1, random_state=19), model, warmup=5)
        self.assertEqual(len(result), 21)
        self.assertEqual(len(model.events), 3 + 2 * 21)
        for user, group in result.groupby('user_id'):
            self.assertEqual(group.history_length.tolist(), list(range(7)))
            np.testing.assert_allclose(group.probability, .2 + .05 * np.arange(7))
        expected = data.set_index('source_row').scored.sort_index()
        actual = result.set_index('source_row').is_scored.sort_index()
        self.assertEqual(actual.tolist(), expected.tolist())

    def test_declared_global_parameter_mutation_is_rejected(self):
        class MutatingModel(SpyModel):
            def __init__(self):
                super().__init__()
                self.weight = 1
            def global_parameters_snapshot(self):
                return {'weight': self.weight}
            def update(self, observation):
                super().update(observation)
                self.weight += 1
        with self.assertRaises((ValueError, RuntimeError, AssertionError)):
            sequential_predict(frame(1, 2), MutatingModel())


if __name__ == '__main__':
    unittest.main()
