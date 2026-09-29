"""One-shot final v4 TEST, requiring a separate final checkpoint lock."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.preprocessing.pipeline import add_history_features, add_problem_difficulty
from src.evaluation.bootstrap import paired_student_brier_bootstrap
from scripts.train_foundational_rq1 import score_model

MODELS = ['Global', 'Problem', 'PFA', 'BKT', 'XGBoost']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_final_lock(lock, root):
    if lock.get('stage') != 'RQ1_FINAL_TEST_V4' or lock.get('test_opened') is not False:
        raise ValueError('Final TEST lock missing or invalid')
    if set(lock['models']) != set(MODELS) or lock['reference'] not in MODELS:
        raise ValueError('Five frozen models and validation-selected reference required')
    required = {'configs/foundationalassist_v4_rq1_training.json',
                'configs/foundationalassist_v4_preprocessing.json',
                'data/processed/foundationalassist_v4/student_split.json',
                'data/processed/foundationalassist_v4/train.parquet',
                'data/processed/foundationalassist_v4/test.parquet',
                'src/preprocessing/pipeline.py', 'src/evaluation/metrics.py',
                'src/evaluation/sequential.py', 'src/evaluation/bootstrap.py',
                'scripts/train_foundational_rq1.py', 'scripts/evaluate_foundational_rq1_test.py',
                'src/models/baselines.py', 'src/models/pfa.py', 'src/models/bkt.py',
                'src/models/xgboost_model.py', 'requirements-lock.txt'}
    required.update(lock['models'].values())
    if not required <= set(lock['pinned_sha256']):
        raise ValueError('Incomplete final artifact pins')
    for relative, expected in lock['pinned_sha256'].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path) != expected:
            raise ValueError(f'Final artifact changed: {relative}')


def main():
    lock_path = ROOT / 'configs/foundationalassist_v4_rq1_final.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    validate_final_lock(lock, ROOT)
    config = json.loads((ROOT / 'configs/foundationalassist_v4_rq1_training.json').read_text())
    private = ROOT / 'data/processed/foundationalassist_v4/final_test'
    summary_path = ROOT / 'artifacts/tables/foundationalassist_v4_rq1_test.json'
    if private.exists() or summary_path.exists():
        raise FileExistsError('Final TEST already started; refusing another attempt')
    private.mkdir(parents=True)
    (private / 'started.json').write_text(json.dumps({
        'lock_sha256': digest(lock_path), 'started_utc': datetime.now(timezone.utc).isoformat()}))
    # The one-shot marker is written before reading any TEST labels.
    base = ROOT / 'data/processed/foundationalassist_v4'
    train, test = (pd.read_parquet(base / f'{part}.parquet') for part in ('train', 'test'))
    if not train.split.eq('train').all() or not test.split.eq('test').all():
        raise ValueError('Incorrect partitions')
    if set(train.user_id) & set(test.user_id):
        raise ValueError('Student overlap')
    warmup = config['evaluation']['warmup']
    features = add_problem_difficulty(add_history_features(pd.concat([train, test]), warmup=warmup),
                                      n_splits=config['problem_difficulty']['n_splits'],
                                      alpha=config['problem_difficulty']['alpha'])
    features = features.loc[features.split.eq('test')].copy()
    results, joined, calibration = {}, None, {}
    for name in MODELS:
        model = joblib.load(ROOT / lock['models'][name])
        pred, metrics = score_model(model, features, warmup, sequential=name == 'BKT')
        pred.to_parquet(private / f'{name}.parquet', index=False)
        identity = pred[['source_row', 'user_id', 'correct', 'is_scored']].sort_values('source_row').reset_index(drop=True)
        if joined is None:
            joined = identity.copy()
        else:
            pd.testing.assert_frame_equal(joined[list(identity.columns)], identity)
        joined[name] = pred.sort_values('source_row').probability.to_numpy()
        results[name] = metrics
        scored = pred.loc[pred.is_scored].copy()
        scored['bin'] = (scored.probability * 10).astype(int).clip(upper=9)
        calibration[name] = scored.groupby('bin').agg(
            mean_prediction=('probability', 'mean'), observed=('correct', 'mean'),
            count=('correct', 'size')).reset_index().to_dict('records')
        print(name, json.dumps(metrics), flush=True)
    reference = lock['reference']
    comparisons = {name: paired_student_brier_bootstrap(joined, name, reference,
                    iterations=config['bootstrap']['iterations'], seed=config['bootstrap']['seed'])
                   for name in MODELS if name != reference}
    summary = {'stage': 'final_test_v4', 'lock_sha256': digest(lock_path),
               'metrics': results, 'reference_chosen_on_validation': reference,
               'paired_student_brier_bootstrap': comparisons, 'calibration': calibration}
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
