import io
import math
from decimal import Decimal, localcontext
import unittest

import joblib
import numpy as np
import pandas as pd

try:
    from src.models.bkt import BKT, sequence_negative_log_likelihood
except ImportError:
    BKT = sequence_negative_log_likelihood = None


def data(n=8):
    return pd.DataFrame({'user_id': ['a'] * n, 'order_id': range(n),
                         'source_row': range(n), 'problem_id': range(n),
                         'skill_id': ['x'] * n, 'correct': [i % 2 for i in range(n)],
                         'split': ['train'] * n})


class BKTTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(BKT, 'BKT implementation missing')

    def test_hand_calculated_prediction_bayes_transition_and_reset(self):
        model = BKT.from_parameters((0.2, 0.1, 0.2, 0.1))
        model.reset('a')
        self.assertAlmostEqual(model.predict({'skill_id': 'x'}), 0.34)
        row = {'user_id': 'a', 'skill_id': 'x'}
        self.assertAlmostEqual(model.predict(row), 0.34)
        before = model.global_parameters_snapshot()
        model.update({**row, 'correct': 1})
        # posterior=.18/.34=9/17; transition=49/85; next p=513/850.
        self.assertAlmostEqual(model.predict(row), 513/850)
        self.assertAlmostEqual(model.predict({**row, 'skill_id': 'y'}), 0.34)
        self.assertEqual(model.global_parameters_snapshot(), before)
        model.reset('b')
        row['user_id'] = 'b'
        self.assertAlmostEqual(model.predict(row), 0.34)
        model.update({**row, 'correct': 0})
        # posterior=.02/.66=1/33; transition=7/55; p=159/550.
        self.assertAlmostEqual(model.predict(row), 159/550)

    def test_likelihood_separates_sequences_and_uses_before_response_probability(self):
        params = (0.2, 0.1, 0.2, 0.1)
        self.assertAlmostEqual(sequence_negative_log_likelihood(params, [[1], [0]]),
                               -math.log(0.34) - math.log(0.66))
        self.assertAlmostEqual(sequence_negative_log_likelihood(params, [[1, 0]]),
                               -math.log(0.34) - math.log(337/850))

    def test_long_success_then_failure_run_matches_high_precision_reference(self):
        parameters = (.7734081364588514, .22000034143627412,
                      .25772077805350335, .2095130406887498)
        labels = [1] * 80 + [0] * 240
        expected_predictions = []
        with localcontext() as context:
            context.prec = 150
            mastery, transition, guess, slip = map(lambda x: Decimal(str(x)), parameters)
            one = Decimal(1)
            loss = Decimal(0)
            for label in labels:
                expected_predictions.append(float(mastery * (one - slip) + (one - mastery) * guess))
                known = mastery * ((one - slip) if label else slip)
                unknown = (one - mastery) * (guess if label else (one - guess))
                observed = known + unknown
                loss -= observed.ln()
                posterior = known / observed
                mastery = posterior + (one - posterior) * transition
        with np.errstate(all='raise'):
            actual = sequence_negative_log_likelihood(parameters, [labels])
            model = BKT.from_parameters(parameters)
            model.reset('a')
            predicted = []
            for label in labels:
                predicted.append(model.predict({'skill_id': 'x'}))
                model.update({'skill_id': 'x', 'correct': label})
        self.assertAlmostEqual(actual, float(loss), places=9)
        np.testing.assert_allclose(predicted, expected_predictions, rtol=1e-12, atol=1e-12)
        self.assertTrue(all(0 <= value <= 1 for value in predicted))

    def test_batch_restores_input_order_and_matches_hand_sequence(self):
        model = BKT.from_parameters((0.2, 0.1, 0.2, 0.1))
        frame = data(2).assign(correct=[1, 0]).iloc[::-1]
        np.testing.assert_allclose(model.predict_batch(frame), [513/850, 0.34])

    def test_synthetic_fit_bounds_sparse_pool_and_joblib(self):
        model = BKT().fit(data())
        self.assertEqual(model.skill_parameters_, {})
        for value, bounds in zip(model.pooled_parameters_, [(0.001, .999), (.001, .5), (.001, .3), (.001, .3)]):
            self.assertGreaterEqual(value, bounds[0])
            self.assertLessEqual(value, bounds[1])
        self.assertEqual(len(model.fit_diagnostics_['pooled']['runs']), 3)
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        buffer.seek(0)
        restored = joblib.load(buffer)
        np.testing.assert_allclose(model.predict_batch(data()), restored.predict_batch(data()))
        self.assertEqual(model.global_parameters_snapshot(), restored.global_parameters_snapshot())

    def test_nontrain_invalid_labels_and_ambiguous_chronology_rejected(self):
        for frame in [data().assign(split='test'), data().assign(correct=2),
                      data().iloc[:0], data().assign(order_id=0),
                      data().assign(skill_id=None)]:
            with self.assertRaises(ValueError):
                BKT().fit(frame)

    def test_parameter_mutation_changes_snapshot_and_invalid_state_rejected(self):
        model = BKT.from_parameters((0.2, 0.1, 0.2, 0.1))
        snapshot = model.global_parameters_snapshot()
        model.pooled_parameters_ = (0.3, 0.1, 0.2, 0.1)
        self.assertNotEqual(snapshot, model.global_parameters_snapshot())
        model.reset('a')
        with self.assertRaises(ValueError):
            model.predict({'user_id': 'b', 'skill_id': 'x'})
        with self.assertRaises(ValueError):
            model.update({'user_id': 'a', 'skill_id': 'x', 'correct': 2})
        with self.assertRaises(ValueError):
            BKT.from_parameters((0, 0.1, 0.2, 0.1))


if __name__ == '__main__':
    unittest.main()
