import unittest

import pandas as pd

try:
    from src.evaluation.sequential import sequential_predict
except ImportError:
    sequential_predict = None


class HistoryModel:
    def reset(self, user_id):
        self.successes = 0
        self.count = 0

    def predict(self, row):
        if any(k in row for k in ('correct', 'hint_count', 'attempt_count', 'prior_leaked')):
            raise AssertionError('response leaked')
        return (self.successes + 1) / (self.count + 2)

    def update(self, row):
        self.successes += row['correct']
        self.count += 1


def fixture():
    return pd.DataFrame({
        'user_id': [1, 1, 1, 2], 'order_id': [1, 2, 3, 1],
        'problem_id': [10, 11, 12, 10], 'skill_id': [3, 3, 3, 3],
        'source_row': [0, 1, 2, 3], 'correct': [1, 0, 1, 0],
        'hint_count': [0, 9, 1, 8], 'attempt_count': [1, 9, 2, 8],
        'prior_leaked': [1, 0, 1, 0],
    })


class SequentialTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(sequential_predict, 'sequential evaluator missing')

    def test_prediction_precedes_update_and_state_resets(self):
        result = sequential_predict(fixture(), HistoryModel(), warmup=1)
        self.assertEqual(result.probability.tolist(), [0.5, 2/3, 0.5, 0.5])
        self.assertEqual(result.is_scored.tolist(), [False, True, True, False])
        self.assertEqual(result.history_length.tolist(), [0, 1, 2, 0])

    def test_sort_is_deterministic_and_input_unchanged(self):
        frame = fixture().iloc[[2, 3, 0, 1]].copy()
        before = frame.copy(deep=True)
        result = sequential_predict(frame, HistoryModel(), warmup=0)
        self.assertEqual(result.source_row.tolist(), [0, 1, 2, 3])
        self.assertTrue(result.is_scored.all())
        pd.testing.assert_frame_equal(frame, before)

    def test_short_and_empty_sequences_have_no_scored_rows(self):
        self.assertFalse(sequential_predict(fixture(), HistoryModel()).is_scored.any())
        self.assertTrue(sequential_predict(fixture().iloc[:0], HistoryModel()).empty)

    def test_invalid_probability_rejected_before_observation(self):
        class Invalid(HistoryModel):
            def predict(self, row):
                return self.value
            def update(self, row):
                raise AssertionError('invalid prediction was updated')
        for value in [float('nan'), float('inf'), -0.1, 1.1, '0.5', True]:
            model = Invalid()
            model.value = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                sequential_predict(fixture(), model)

    def test_invalid_identity_labels_and_warmup_rejected(self):
        for col, value in [('source_row', 0), ('order_id', 1), ('correct', 2), ('user_id', None)]:
            frame = fixture()
            frame.loc[1, col] = value
            with self.subTest(col=col), self.assertRaises(ValueError):
                sequential_predict(frame, HistoryModel())
        for warmup in [-1, 0.5, True]:
            with self.assertRaises(ValueError):
                sequential_predict(fixture(), HistoryModel(), warmup)

    def test_fitted_parameters_cannot_mutate_when_snapshot_hook_supplied(self):
        class Mutating(HistoryModel):
            parameter = 1
            def global_parameters_snapshot(self):
                return {'parameter': self.parameter}
            def update(self, row):
                self.parameter += 1
        with self.assertRaises(RuntimeError):
            sequential_predict(fixture(), Mutating())


if __name__ == '__main__':
    unittest.main()
