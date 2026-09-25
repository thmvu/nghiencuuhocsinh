import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.evaluate_rq1_test import preflight, compare_predictions


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalTestEvaluationTests(unittest.TestCase):
    def test_preflight_rejects_modified_checkpoint_before_test_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'configs').mkdir()
            (root / 'data/processed').mkdir(parents=True)
            (root / 'artifacts/models').mkdir(parents=True)
            (root / 'configs/protocol_a.json').write_text('{}')
            (root / 'data/processed/student_split.json').write_text('{}')
            for part in ('train', 'validation', 'test'):
                (root / f'data/processed/{part}.parquet').write_bytes(part.encode())
            model_path = root / 'artifacts/models/model.joblib'
            model_path.write_bytes(b'original')
            lock = {
                'stage': 'B', 'gate_b': 'RQ1 PRE-TEST CHECKLIST PASS', 'test_opened': False,
                'protocol_a_sha256': digest(root / 'configs/protocol_a.json'),
                'split_manifest_sha256': digest(root / 'data/processed/student_split.json'),
                'input_sha256': {p: digest(root / f'data/processed/{p}.parquet')
                                 for p in ('train', 'validation', 'test')},
                'models': {name: {'path': 'artifacts/models/model.joblib',
                                  'sha256': digest(model_path)}
                           for name in ('Global', 'Problem', 'PFA', 'BKT', 'XGBoost')},
                'selection': {'pfa_C': .1,
                              'xgboost': {'max_depth': 4, 'learning_rate': .1, 'n_estimators': 300},
                              'calibrator': 'none'},
                'evaluation': {'warmup': 5, 'scored_only': True,
                               'bootstrap': {'unit': 'student', 'iterations': 1000, 'seed': 42,
                                             'ci_quantiles': [.025, .975], 'metric': 'brier_score',
                                             'pairing': 'same_scored_rows',
                                             'difference': 'model_minus_XGBoost',
                                             'aggregation': 'interaction_weighted'}},
                'validation_artifact_sha256': {},
            }
            self.assertEqual(preflight(root, lock)['test'], (root / 'data/processed/test.parquet').resolve())
            model_path.write_bytes(b'modified')
            with self.assertRaisesRegex(ValueError, 'hash'):
                preflight(root, lock)

    def test_common_population_requires_identical_rows_labels_and_mask(self):
        base = pd.DataFrame({'source_row': [1, 2], 'user_id': ['a', 'a'],
                             'correct': [0, 1], 'is_scored': [False, True],
                             'probability': [.2, .8]})
        same = base.copy()
        frames = {name: base.copy() for name in ('Global', 'Problem', 'PFA', 'BKT')}
        frames['XGBoost'] = same
        self.assertEqual(len(compare_predictions(frames)), 2)
        mixed = {name: base.copy() for name in frames}
        for name in ('Global', 'Problem', 'PFA', 'XGBoost'):
            mixed[name]['user_id'] = mixed[name]['user_id'].astype('string')
        self.assertEqual(len(compare_predictions(mixed)), 2)
        wrong = base.copy()
        wrong.loc[1, 'is_scored'] = False
        with self.assertRaises(ValueError):
            compare_predictions({**frames, 'XGBoost': wrong})
        wrong = base.copy()
        wrong.loc[1, 'correct'] = 0
        with self.assertRaises(ValueError):
            compare_predictions({**frames, 'XGBoost': wrong})


if __name__ == '__main__':
    unittest.main()
