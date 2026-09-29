from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
import scripts.evaluate_foundational_rq1_test as evaluator
from src.models.baselines import GlobalBaseline
from scripts.evaluate_foundational_rq1_test import validate_final_lock, MODELS


class FinalGateTests(unittest.TestCase):
    def test_missing_stage_rejected_before_io(self):
        with self.assertRaises(ValueError):
            validate_final_lock({}, Path('.'))

    def test_incomplete_pins_rejected_before_io(self):
        lock = {'stage': 'RQ1_FINAL_TEST_V4', 'test_opened': False,
                'models': {name: f'{name}.joblib' for name in MODELS},
                'reference': 'Global', 'pinned_sha256': {}}
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            validate_final_lock(lock, Path('.'))

    def test_already_opened_lock_rejected(self):
        with self.assertRaises(ValueError):
            validate_final_lock({'stage': 'RQ1_FINAL_TEST_V4', 'test_opened': True}, Path('.'))

    def test_synthetic_one_shot_complete_then_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'configs').mkdir()
            (root / 'artifacts/tables').mkdir(parents=True)
            base = root / 'data/processed/foundationalassist_v4'
            base.mkdir(parents=True)
            frames = {}
            for part, count in [('train', 5), ('test', 2)]:
                rows = [dict(user_id=f'{part}{s}', source_row=(0 if part == 'train' else 100) + s*8+t,
                             order_id=t, problem_id='p', skill_id='k', correct=t%2, split=part)
                        for s in range(count) for t in range(8)]
                frames[part] = pd.DataFrame(rows)
                frames[part].to_parquet(base / f'{part}.parquet')
            model = GlobalBaseline().fit(frames['train'])
            config = {'evaluation': {'warmup': 5}, 'problem_difficulty': {'n_splits': 5, 'alpha': 10},
                      'bootstrap': {'iterations': 10, 'seed': 42}}
            (root / 'configs/foundationalassist_v4_rq1_training.json').write_text(json.dumps(config))
            lock = {'models': {name: name for name in MODELS}, 'reference': 'Global'}
            (root / 'configs/foundationalassist_v4_rq1_final.json').write_text(json.dumps(lock))
            with patch.object(evaluator, 'ROOT', root), patch.object(evaluator, 'validate_final_lock'), \
                    patch.object(evaluator.joblib, 'load', return_value=model):
                evaluator.main()
                with self.assertRaises(FileExistsError):
                    evaluator.main()
            result = json.loads((root / 'artifacts/tables/foundationalassist_v4_rq1_test.json').read_text())
            self.assertEqual(len(result['metrics']), 5)
            self.assertTrue(all(r['n_rows'] == 6 for r in result['metrics'].values()))
