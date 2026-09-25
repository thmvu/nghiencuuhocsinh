"""Independent synthetic checks for locked BKT and XGBoost development."""
import io
import json
from decimal import Decimal, localcontext
from pathlib import Path
import unittest

import joblib
import numpy as np
import pandas as pd

from src.models.bkt import BKT, sequence_negative_log_likelihood
from src.preprocessing.pipeline import add_history_features
from src.evaluation.sequential import sequential_predict


def trajectories():
    rows = []
    for user in ['a', 'b']:
        for t, (skill, label) in enumerate([('s', 1), ('q', 0), ('s', 0), ('q', 1)]):
            rows.append(dict(user_id=user, order_id=t, source_row=len(rows),
                             skill_id=skill, problem_id=str(t), correct=label, split='train'))
    return pd.DataFrame(rows)


class IndependentBKTTests(unittest.TestCase):
    def model(self):
        return BKT.from_parameters((.2, .1, .2, .1))

    def test_hand_derived_bayes_update_learning_and_no_cross_skill_bleed(self):
        model = self.model()
        model.reset('a')
        self.assertAlmostEqual(model.predict({'user_id': 'a', 'skill_id': 's'}), .34)
        model.update({'user_id': 'a', 'skill_id': 's', 'correct': 1})
        # posterior=.18/.34=9/17; learning -> (9/17)+(8/17)*.1=49/85.
        mastery = 49 / 85
        self.assertAlmostEqual(model.predict({'user_id': 'a', 'skill_id': 's'}), .2 + .7 * mastery)
        self.assertAlmostEqual(model.predict({'user_id': 'a', 'skill_id': 'q'}), .34)
        model.update({'user_id': 'a', 'skill_id': 'q', 'correct': 0})
        # posterior=.02/.66=1/33; learning -> 7/55.
        self.assertAlmostEqual(model.predict({'user_id': 'a', 'skill_id': 'q'}), .2 + .7 * (7 / 55))
        self.assertAlmostEqual(model.predict({'user_id': 'a', 'skill_id': 's'}), .2 + .7 * mastery)
        model.reset('b')
        self.assertAlmostEqual(model.predict({'user_id': 'b', 'skill_id': 's'}), .34)

    def test_current_label_change_cannot_change_own_prediction(self):
        data = trajectories()
        baseline = sequential_predict(data, self.model(), warmup=0)
        for cutoff in range(4):
            changed = data.copy()
            changed.loc[(changed.user_id == 'a') & (changed.order_id >= cutoff), 'correct'] ^= 1
            actual = sequential_predict(changed, self.model(), warmup=0)
            protected = (baseline.user_id != 'a') | (baseline.order_id <= cutoff)
            np.testing.assert_allclose(baseline.loc[protected, 'probability'], actual.loc[protected, 'probability'])

    def test_pooled_objective_restarts_each_student_skill_sequence(self):
        parameters = (.2, .1, .2, .1)
        separate = sequence_negative_log_likelihood(parameters, [np.array([1]), np.array([0])])
        self.assertAlmostEqual(separate, -np.log(.34) - np.log(.66))
        same_sequence = sequence_negative_log_likelihood(parameters, [np.array([1, 0])])
        after_success = .2 + .7 * (49 / 85)
        self.assertAlmostEqual(same_sequence, -np.log(.34) - np.log(1 - after_success))
        self.assertNotAlmostEqual(separate, same_sequence)

    def test_long_sequence_likelihood_against_high_precision_oracle(self):
        parameters = (.999, .001, .001, .3)
        sequences = [np.array(([1] * 19 + [0] * 7) * 80, dtype=int),
                     np.array(([0] * 23 + [1] * 3) * 80, dtype=int)]
        with localcontext() as context:
            context.prec = 70
            l0, transition, guess, slip = map(lambda value: Decimal(str(value)), parameters)
            expected = Decimal(0)
            for sequence in sequences:
                mastery = l0
                for label in sequence:
                    success = mastery * (1 - slip) + (1 - mastery) * guess
                    observed = success if label else 1 - success
                    expected -= observed.ln()
                    posterior = (mastery * (1 - slip) if label else mastery * slip) / observed
                    mastery = posterior + (1 - posterior) * transition
        actual = sequence_negative_log_likelihood(parameters, sequences)
        self.assertAlmostEqual(actual, float(expected), delta=1e-8)

    def test_unseen_skill_uses_pooled_parameters(self):
        model = BKT.from_parameters((.2, .1, .2, .1), {'known': (.8, .2, .1, .2)})
        model.reset('a')
        self.assertAlmostEqual(model.predict({'user_id': 'a', 'skill_id': 'unseen'}), .34)
        self.assertAlmostEqual(model.predict({'user_id': 'a', 'skill_id': 'known'}), .66)

    def test_heldout_fit_rows_rejected_before_optimization(self):
        for split in ['validation', 'test']:
            data = trajectories()
            data.loc[0, 'split'] = split
            with self.subTest(split=split), self.assertRaises(ValueError):
                BKT().fit(data)

    def test_sparse_skills_fit_only_pooled_with_separate_sequences(self):
        from unittest.mock import patch
        model = BKT()
        with patch.object(model, '_fit_group', return_value=((.2, .1, .2, .1), {'runs': [], 'converged': True})) as fit:
            model.fit(trajectories())
        self.assertEqual(fit.call_count, 1)
        actual = [sequence.tolist() for sequence in fit.call_args.args[0]]
        self.assertCountEqual(actual, [[1, 0], [0, 1], [1, 0], [0, 1]])
        self.assertEqual(model.skill_parameters_, {})
        self.assertEqual(model.fit_diagnostics_['sparse_or_one_class_skills'], 2)

    def test_failed_eligible_skill_falls_back_but_failed_pooled_stops(self):
        from unittest.mock import patch
        data = pd.concat([trajectories().assign(user_id=lambda df: df.user_id + str(i)) for i in range(26)], ignore_index=True)
        diagnostics = {'runs': [], 'converged': False}
        model = BKT()
        with patch.object(model, '_fit_group', side_effect=[((.2, .1, .2, .1), diagnostics), (None, diagnostics.copy()), (None, diagnostics.copy())]):
            model.fit(data)
        self.assertEqual(model.skill_parameters_, {})
        self.assertTrue(all(item['pooled_fallback'] for item in model.fit_diagnostics_['skills'].values()))
        with patch.object(BKT, '_fit_group', return_value=(None, diagnostics)), self.assertRaises(RuntimeError):
            BKT().fit(data)

    def test_actual_parameter_mutation_rejected_by_evaluator(self):
        class MutatingBKT(BKT):
            def update(self, row):
                super().update(row)
                self.pooled_parameters_ = (.3, .1, .2, .1)
        model = MutatingBKT.from_parameters((.2, .1, .2, .1))
        with self.assertRaisesRegex(RuntimeError, 'global parameters'):
            sequential_predict(trajectories(), model)

    def test_checkpoint_roundtrip_and_batch_alignment(self):
        data = trajectories().sample(frac=1, random_state=9)
        model = self.model()
        baseline = sequential_predict(data, model, warmup=0).set_index('source_row').probability
        expected = baseline.loc[data.source_row].to_numpy()
        np.testing.assert_allclose(model.predict_batch(data), expected)
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        buffer.seek(0)
        restored = joblib.load(buffer)
        np.testing.assert_allclose(restored.predict_batch(data), expected)


class IndependentXGBoostTests(unittest.TestCase):
    def data(self):
        data = add_history_features(trajectories())
        data['problem_difficulty'] = .6
        return data

    def model(self):
        from src.models.xgboost_model import XGBoostModel
        return XGBoostModel(n_estimators=2).fit(self.data())

    def test_exact_whitelist_and_unseen_skill_zero_block(self):
        model = self.model()
        query = self.data().iloc[:2].copy()
        query['skill_id'] = 'never_in_train'
        query['correct'] = 999
        query['hint_count'] = 123456
        design = model._design(query)
        columns = ['prior_skill_success', 'prior_skill_failure', 'prior_skill_accuracy',
                   'prior_overall_accuracy', 'history_length', 'problem_difficulty']
        self.assertEqual(design.shape, (2, 6 + 2))
        np.testing.assert_allclose(design[:, :6], query[columns].to_numpy())
        np.testing.assert_array_equal(design[:, 6:], 0)
        self.assertEqual(model.skills, ['q', 's'])
        changed = query.copy()
        for column in ['user_id', 'order_id', 'problem_id', 'source_row', 'correct', 'hint_count']:
            changed[column] = 'anything'
        np.testing.assert_array_equal(model._design(changed), design)
        np.testing.assert_array_equal(model.predict_batch(changed), model.predict_batch(query))
        self.assertEqual(model.skills, ['q', 's'])

    def test_heldout_training_rejected(self):
        from src.models.xgboost_model import XGBoostModel
        for split in ['validation', 'test']:
            data = self.data()
            data.loc[0, 'split'] = split
            with self.subTest(split=split), self.assertRaises(ValueError):
                XGBoostModel(n_estimators=2).fit(data)

    def test_batch_sequential_and_serialized_bundle_match(self):
        data, model = self.data(), self.model()
        expected = model.predict_batch(data)
        actual = sequential_predict(data, model, warmup=0)
        np.testing.assert_allclose(actual.probability, expected)
        snapshot = model.global_parameters_snapshot()
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        buffer.seek(0)
        restored = joblib.load(buffer)
        self.assertEqual(restored.skills, model.skills)
        self.assertEqual(restored.global_parameters_snapshot(), snapshot)
        np.testing.assert_array_equal(restored.predict_batch(data), expected)


if __name__ == '__main__':
    unittest.main()

