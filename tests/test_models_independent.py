"""Independent synthetic model/protocol checks; never load research data."""
import unittest
import io
import joblib

import numpy as np
import pandas as pd

from src.models.baselines import GlobalBaseline, ProblemBaseline
from src.models.pfa import PFA
from src.preprocessing.pipeline import add_history_features
from src.evaluation.sequential import sequential_predict
from src.evaluation.metrics import evaluate_predictions


def synthetic():
    rows = []
    for user in range(6):
        for t in range(9):
            rows.append(dict(user_id=str(user), order_id=t, source_row=len(rows),
                             skill_id=str(t % 2), problem_id=str(t % 3),
                             correct=int((user + 2 * t) % 5 < 3), split='train'))
    return add_history_features(pd.DataFrame(rows))


class IndependentModelTests(unittest.TestCase):
    def models(self):
        return [GlobalBaseline(), ProblemBaseline(alpha=10), PFA(C=.01)]

    def test_batch_sequential_and_target_independence(self):
        train = synthetic()
        query = train.copy()
        query['split'] = 'validation'
        query['user_id'] = 'held_' + query.user_id
        for model in self.models():
            with self.subTest(model=type(model).__name__):
                model.fit(train)
                before = model.global_parameters_snapshot()
                expected = np.asarray(model.predict_batch(query))
                actual = sequential_predict(query, model)
                np.testing.assert_allclose(actual.probability, expected, rtol=1e-12, atol=1e-12)
                changed = query.copy()
                changed['correct'] = 1 - changed.correct
                changed['hint_count'] = 999999
                np.testing.assert_allclose(model.predict_batch(changed), expected)
                self.assertEqual(model.global_parameters_snapshot(), before)

    def test_fitting_heldout_rows_is_rejected(self):
        for split in ['validation', 'test']:
            train = synthetic()
            train.loc[0, 'split'] = split
            for model in self.models():
                with self.subTest(split=split, model=type(model).__name__), self.assertRaises(ValueError):
                    model.fit(train)

    def test_baseline_hand_calculation_and_unseen_problem(self):
        train = synthetic().iloc[:4].copy()
        train['correct'] = [1, 1, 1, 0]
        train['problem_id'] = ['a', 'a', 'b', 'b']
        query = train.iloc[:3].copy()
        query['problem_id'] = ['a', 'b', 'unseen']
        global_model = GlobalBaseline().fit(train)
        problem_model = ProblemBaseline(alpha=10).fit(train)
        np.testing.assert_allclose(global_model.predict_batch(query), [.75] * 3)
        np.testing.assert_allclose(problem_model.predict_batch(query), [9.5 / 12, 8.5 / 12, .75])

    def test_unknown_skill_zero_blocks_ignore_its_history(self):
        model = PFA(C=.01).fit(synthetic())
        query = synthetic().iloc[:2].copy()
        query['skill_id'] = 'unseen_skill'
        query['prior_skill_success'] = [0, 100000]
        query['prior_skill_failure'] = [0, 99999]
        result = model.predict_batch(query)
        self.assertEqual(result[0], result[1])
        self.assertTrue(0 < result[0] < 1)

    def test_snapshot_detects_actual_weight_mutation_in_update(self):
        class MutatingPFA(PFA):
            def update(self, row):
                self.classifier.coef_[0, 0] += .001
        model = MutatingPFA(C=.01).fit(synthetic())
        with self.assertRaisesRegex(RuntimeError, 'global parameters'):
            sequential_predict(synthetic().iloc[:3], model)

    def test_all_models_joblib_roundtrip(self):
        data = synthetic()
        for model in self.models():
            with self.subTest(model=type(model).__name__):
                model.fit(data)
                buffer = io.BytesIO()
                joblib.dump(model, buffer)
                buffer.seek(0)
                loaded = joblib.load(buffer)
                np.testing.assert_allclose(loaded.predict_batch(data), model.predict_batch(data))

    def test_problem_table_replacement_cannot_evade_snapshot(self):
        from types import MappingProxyType
        class ReplacingProblem(ProblemBaseline):
            def update(self, row):
                self.problem_probabilities_ = MappingProxyType({str(i): .999 for i in range(3)})
        model = ReplacingProblem().fit(synthetic())
        with self.assertRaises((RuntimeError, AttributeError, TypeError)):
            sequential_predict(synthetic().iloc[:3], model)


class IndependentMetricTests(unittest.TestCase):
    def test_mask_excludes_deliberately_bad_warmup_predictions(self):
        predictions = pd.DataFrame(dict(source_row=[0, 1, 2], user_id=['a', 'a', 'b'], correct=[1, 0, 1],
                                        probability=[0, .25, .75], is_scored=[False, True, True]))
        result = evaluate_predictions(predictions)
        self.assertEqual(result['n_rows'], 2)
        self.assertEqual(result['n_students'], 2)
        self.assertAlmostEqual(result['brier_score'], .0625)
        self.assertAlmostEqual(result['log_loss'], -np.log(.75))
        self.assertAlmostEqual(result['roc_auc'], 1.)

    def test_one_class_auc_is_undefined_and_extreme_log_loss_is_finite(self):
        predictions = pd.DataFrame(dict(source_row=[0, 1], user_id=['a', 'b'], correct=[1, 1],
                                        probability=[0., 1.], is_scored=[True, True]))
        result = evaluate_predictions(predictions)
        self.assertIsNone(result['roc_auc'])
        self.assertTrue(np.isfinite(result['log_loss']))
        self.assertAlmostEqual(result['log_loss'], -np.log(1e-15) / 2, places=12)


if __name__ == '__main__':
    unittest.main()
