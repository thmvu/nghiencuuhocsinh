import math
import pickle
import unittest

import numpy as np
import pandas as pd

try:
    from src.models.baselines import GlobalBaseline, ProblemBaseline
    from src.evaluation.metrics import evaluate_predictions
except ImportError:
    GlobalBaseline = ProblemBaseline = evaluate_predictions = None


def training():
    return pd.DataFrame({'problem_id': ['a', 'a', 'b', 'b'],
                         'correct': [1, 1, 0, 0], 'split': ['train'] * 4})


class BaselineMetricsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(GlobalBaseline, 'baseline and metrics APIs missing')

    def test_global_and_smoothed_problem_probabilities(self):
        frame = pd.DataFrame({'problem_id': ['a', 'b', 'unseen']})
        global_model = GlobalBaseline().fit(training())
        problem_model = ProblemBaseline().fit(training())
        np.testing.assert_allclose(global_model.predict_batch(frame), [0.5] * 3)
        np.testing.assert_allclose(problem_model.predict_batch(frame), [7/12, 5/12, 0.5])
        self.assertEqual(problem_model.predict({'problem_id': 'unseen'}), 0.5)
        snapshot = problem_model.global_parameters_snapshot()
        problem_model.reset('student')
        problem_model.update({'problem_id': 'a', 'correct': 0})
        self.assertEqual(snapshot, problem_model.global_parameters_snapshot())

    def test_snapshot_changes_with_actual_fitted_parameters(self):
        model = ProblemBaseline().fit(training())
        first = model.global_parameters_snapshot()
        changed = training()
        changed['correct'] = [0, 0, 1, 1]
        model.fit(changed)
        self.assertNotEqual(first, model.global_parameters_snapshot())

    def test_serialization_and_replaced_parameter_table(self):
        model = ProblemBaseline().fit(training())
        restored = pickle.loads(pickle.dumps(model))
        self.assertEqual(restored.predict({'problem_id': 'a'}), 7/12)
        self.assertEqual(restored.global_parameters_snapshot(), model.global_parameters_snapshot())
        before = model.global_parameters_snapshot()
        model.problem_probabilities_ = {'a': 0.1, 'b': 0.9}
        self.assertNotEqual(before, model.global_parameters_snapshot())

    def test_fit_rejects_nontrain_nonbinary_empty_and_missing_problem(self):
        bad_split = training().assign(split='validation')
        bad_label = training().assign(correct=[1, 0, 2, 1])
        for cls in [GlobalBaseline, ProblemBaseline]:
            for frame in [bad_split, bad_label, training().iloc[:0]]:
                with self.subTest(model=cls.__name__), self.assertRaises(ValueError):
                    cls().fit(frame)
            with self.assertRaises(RuntimeError):
                cls().predict({'problem_id': 'a'})
        with self.assertRaises(ValueError):
            ProblemBaseline().fit(training().assign(problem_id=None))
        for alpha in [-1, float('nan'), float('inf'), True]:
            with self.assertRaises(ValueError):
                ProblemBaseline(alpha=alpha)

    def test_metrics_exclude_warmup_and_use_manual_values(self):
        frame = pd.DataFrame({'user_id': [1, 1, 2], 'source_row': [0, 1, 2],
                              'correct': [1, 0, 1], 'probability': [0, 0.25, 0.75],
                              'is_scored': [False, True, True]})
        result = evaluate_predictions(frame)
        self.assertEqual(result['n_rows'], 2)
        self.assertEqual(result['n_students'], 2)
        self.assertAlmostEqual(result['brier_score'], 0.0625)
        self.assertAlmostEqual(result['log_loss'], -math.log(0.75))
        self.assertEqual(result['roc_auc'], 1.0)

    def test_one_class_auc_empty_score_and_boundary_log_loss(self):
        frame = pd.DataFrame({'user_id': [1], 'source_row': [0], 'correct': [1],
                              'probability': [0.0], 'is_scored': [True]})
        result = evaluate_predictions(frame)
        self.assertIsNone(result['roc_auc'])
        self.assertAlmostEqual(result['log_loss'], -math.log(1e-15))
        self.assertEqual(result['brier_score'], 1.0)
        result = evaluate_predictions(frame.assign(is_scored=False))
        self.assertEqual(result['n_rows'], 0)
        self.assertEqual(result['n_students'], 0)
        for key in ['brier_score', 'log_loss', 'roc_auc']:
            self.assertIsNone(result[key])

    def test_metrics_reject_bad_masks_probabilities_labels_and_identity(self):
        frame = pd.DataFrame({'user_id': [1, 2], 'source_row': [0, 1],
                              'correct': [0, 1], 'probability': [0.25, 0.75],
                              'is_scored': [True, True]})
        for column, values in [('is_scored', [0, 1]), ('is_scored', [True, None]),
                               ('probability', [float('nan'), 0.5]),
                               ('probability', [0, 1.1]), ('correct', [0, 2]),
                               ('source_row', [0, 0]), ('user_id', [1, None])]:
            with self.subTest(column=column), self.assertRaises(ValueError):
                evaluate_predictions(frame.assign(**{column: values}))


if __name__ == '__main__':
    unittest.main()
