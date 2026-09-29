"""Synthetic leakage gate for the FoundationalASSIST v4 RQ1 pipeline.

No dataset files, checkpoints, optimization, or real held-out rows are read.
"""
import unittest

import numpy as np
import pandas as pd

from src.evaluation.sequential import sequential_predict
from src.models.bkt import BKT
from src.preprocessing.pipeline import add_history_features, add_problem_difficulty


HISTORY = ['prior_skill_count', 'prior_skill_success', 'prior_skill_failure',
           'prior_skill_accuracy', 'prior_overall_accuracy', 'history_length', 'scored']


def synthetic():
    rows = []
    for student in range(7):
        for step in range(7):
            rows.append(dict(user_id=f'u{student}', order_id=step,
                             source_row=len(rows), problem_id=f'p{step % 3}',
                             skill_id=f's{step % 2}', correct=(student + step) % 2,
                             split='train' if student < 5 else 'validation',
                             answer_text='response', hint_count=step, saw_answer=True,
                             discrete_score=(student + step) % 2))
    return pd.DataFrame(rows)


class ObservationSpy:
    """Fail if response fields arrive early, or update is skipped/reordered."""
    def __init__(self):
        self.resets = []
        self.events = []

    def reset(self, user_id):
        self.resets.append(user_id)
        self.count = self.successes = 0
        self.pending = None

    def predict(self, row):
        assert not {'correct', 'discrete_score', 'answer_text', 'hint_count',
                    'saw_answer', 'future_label'}.intersection(row)
        assert self.pending is None
        assert row['history_length'] == self.count
        self.pending = row['source_row']
        self.events.append(('predict', self.pending))
        return (self.successes + 1) / (self.count + 2)

    def update(self, row):
        assert self.pending == row['source_row']
        self.events.append(('update', self.pending))
        self.successes += row['correct']
        self.count += 1
        self.pending = None


class FoundationalRQ1GateTests(unittest.TestCase):
    def test_current_and_future_labels_cannot_change_prior_features(self):
        raw = synthetic()
        expected = add_history_features(raw)
        for cutoff in range(7):
            changed = raw.copy()
            changed.loc[changed.user_id.eq('u5') & changed.order_id.ge(cutoff), 'correct'] ^= 1
            actual = add_history_features(changed.sample(frac=1, random_state=42))
            protected = expected.user_id.ne('u5') | expected.order_id.le(cutoff)
            pd.testing.assert_frame_equal(expected.loc[protected, HISTORY], actual.loc[protected, HISTORY])

    def test_histories_have_independent_student_and_skill_counters(self):
        featured = add_history_features(synthetic(), warmup=5)
        first = featured.loc[featured.order_id.eq(0)]
        self.assertTrue(first.prior_skill_success.eq(0).all())
        self.assertTrue(first.prior_overall_accuracy.eq(.5).all())
        student = featured.loc[featured.user_id.eq('u0')]
        self.assertEqual(student.prior_skill_success.tolist(), [0, 0, 0, 1, 0, 2, 0])
        self.assertEqual(student.prior_skill_failure.tolist(), [0, 0, 1, 0, 2, 0, 3])
        self.assertEqual(student.scored.tolist(), [False] * 5 + [True] * 2)

    def test_oof_excludes_all_labels_of_each_held_student(self):
        raw = synthetic()
        original = add_problem_difficulty(raw, n_splits=5, alpha=10)
        for user in raw.loc[raw.split.eq('train'), 'user_id'].unique():
            changed = raw.copy()
            own = changed.user_id.eq(user)
            changed.loc[own, 'correct'] ^= 1
            actual = add_problem_difficulty(changed, n_splits=5, alpha=10)
            np.testing.assert_array_equal(original.loc[own, 'problem_difficulty'],
                                          actual.loc[own, 'problem_difficulty'])

    def test_validation_labels_never_enter_any_difficulty_statistic(self):
        raw = synthetic()
        original = add_problem_difficulty(raw)
        raw.loc[raw.split.eq('validation'), 'correct'] = 999
        actual = add_problem_difficulty(raw)
        np.testing.assert_array_equal(original.problem_difficulty, actual.problem_difficulty)

    def test_unseen_problem_fallback_is_train_mean_and_smoothing_is_exact(self):
        raw = synthetic()
        validation = raw.split.eq('validation')
        raw.loc[validation & raw.order_id.eq(0), 'problem_id'] = 'unseen'
        actual = add_problem_difficulty(raw, alpha=10)
        train = raw.loc[~validation]
        mean = train.correct.mean()
        self.assertTrue(actual.loc[actual.problem_id.eq('unseen'), 'problem_difficulty'].eq(mean).all())
        target = train.loc[train.problem_id.eq('p1'), 'correct']
        expected = (target.sum() + 10 * mean) / (len(target) + 10)
        np.testing.assert_allclose(actual.loc[validation & raw.problem_id.eq('p1'), 'problem_difficulty'], expected)

    def test_predict_observe_update_order_and_reset_with_forbidden_columns(self):
        featured = add_history_features(synthetic())
        featured['future_label'] = featured.correct.shift(-1)
        spy = ObservationSpy()
        output = sequential_predict(featured.sample(frac=1, random_state=2), spy, warmup=5)
        self.assertEqual(spy.resets, [f'u{i}' for i in range(7)])
        self.assertEqual(spy.events, [(event, row) for row in output.source_row
                                      for event in ['predict', 'update']])
        self.assertTrue(output.loc[output.history_length.eq(0), 'probability'].eq(.5).all())

    def test_bkt_future_perturbation_preserves_earlier_predictions_and_other_students(self):
        raw = synthetic()
        baseline = sequential_predict(raw, BKT.from_parameters((.2, .1, .2, .1)))
        for cutoff in range(7):
            changed = raw.copy()
            changed.loc[changed.user_id.eq('u5') & changed.order_id.ge(cutoff), 'correct'] ^= 1
            actual = sequential_predict(changed, BKT.from_parameters((.2, .1, .2, .1)))
            protected = baseline.user_id.ne('u5') | baseline.order_id.le(cutoff)
            np.testing.assert_array_equal(baseline.loc[protected, 'probability'], actual.loc[protected, 'probability'])

    def test_mask_is_shared_across_adapters_and_split_labels(self):
        frame = add_history_features(synthetic(), warmup=5)
        expected = frame.set_index('source_row').scored
        for model in [ObservationSpy(), BKT.from_parameters((.2, .1, .2, .1))]:
            result = sequential_predict(frame, model, warmup=5).set_index('source_row')
            pd.testing.assert_series_equal(result.is_scored, expected, check_names=False)
        # The same synthetic sequence must be treated identically irrespective
        # of evaluation split name. This does not access the dataset TEST.
        validation = frame.loc[frame.split.eq('validation')].copy()
        relabeled = validation.assign(split='test')
        left = sequential_predict(validation, ObservationSpy(), warmup=5)
        right = sequential_predict(relabeled, ObservationSpy(), warmup=5)
        pd.testing.assert_frame_equal(left, right)


if __name__ == '__main__':
    unittest.main()
