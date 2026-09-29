"""Locked FoundationalASSIST TRAIN/VALIDATION runs; never opens TEST.

Each group is single-attempt. A private start marker survives interruption so
rerunning requires an explicit audit, rather than silently spending fit budget.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import sys
import time

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.metrics import evaluate_predictions
from src.evaluation.sequential import sequential_predict
from src.models.baselines import GlobalBaseline, ProblemBaseline
from src.models.bkt import BKT
from src.models.pfa import PFA, PFAConvergenceError
from src.models.xgboost_model import XGBoostModel, NUMERIC_FEATURES

GROUPS = ('baselines_pfa', 'bkt', 'xgboost')
REQUIRED_CODE = (
    'scripts/train_foundational_rq1.py', 'src/models/baselines.py',
    'src/models/pfa.py', 'src/models/bkt.py', 'src/models/xgboost_model.py',
    'src/evaluation/metrics.py', 'src/evaluation/sequential.py',
)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def validate_config(config):
    """Reject settings that the shared, historically frozen adapters cannot honor."""
    evaluation = config['evaluation']
    if (evaluation['primary_metric'] != 'brier_score'
            or evaluation.get('calibrator', 'none') != 'none'
            or evaluation.get('log_loss_clip_epsilon', 1e-15) != 1e-15):
        raise ValueError('Unsupported evaluation configuration')
    warmup = evaluation['warmup']
    if isinstance(warmup, bool) or not isinstance(warmup, int) or warmup < 0:
        raise ValueError('Invalid warmup')
    pfa = config['pfa']
    for key, expected in {'penalty': 'L2', 'solver': 'lbfgs', 'fit_intercept': True}.items():
        if pfa[key] != expected:
            raise ValueError(f'PFA adapter does not support {key}')
    if len(pfa['C_candidates']) != pfa['maximum_fits'] or not pfa['C_candidates']:
        raise ValueError('PFA candidate budget mismatch')
    xgb = config['xgboost']
    for key, expected in {'objective': 'binary:logistic', 'tree_method': 'hist',
                          'n_jobs': 1, 'early_stopping': False,
                          'problem_id_encoding': 'omitted'}.items():
        if xgb[key] != expected:
            raise ValueError(f'XGBoost adapter does not support {key}')
    fixed = {'min_child_weight': 5, 'subsample': 1.0, 'colsample_bytree': 1.0,
             'reg_lambda': 1.0, 'reg_alpha': 0.0, 'gamma': 0.0}
    if xgb['fixed'] != fixed or xgb['features'] != list(NUMERIC_FEATURES) + ['skill_one_hot']:
        raise ValueError('XGBoost fixed settings/features differ from adapter')
    if xgb['grid_order'] != ['max_depth', 'learning_rate', 'n_estimators']:
        raise ValueError('Unsupported grid order')
    if np.prod([len(xgb['grid'][key]) for key in xgb['grid_order']]) != xgb['maximum_fits']:
        raise ValueError('XGBoost candidate budget mismatch')


def load_development_data(root=ROOT):
    root = Path(root)
    config_path = root / 'configs/foundationalassist_v4_rq1_training.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    validate_config(config)
    base = root / 'data/processed/foundationalassist_v4/features'
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
    if digest(config_path) != manifest['config_sha256']:
        raise ValueError('Training config changed after feature preparation')
    preprocessing_path = root / config['preprocessing_lock']
    if digest(preprocessing_path) != manifest['preprocessing_lock_sha256']:
        raise ValueError('Preprocessing lock changed')
    preprocessing = json.loads(preprocessing_path.read_text(encoding='utf-8'))
    if digest(root / preprocessing['split_path']) != manifest['split_sha256']:
        raise ValueError('Saved student split changed')
    if digest(root / 'requirements-lock.txt') != manifest['requirements_sha256']:
        raise ValueError('Requirements lock changed')
    pins = manifest['code_sha256']
    if not set(REQUIRED_CODE).issubset(pins):
        raise ValueError('Missing required source pins')
    for name, expected in pins.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path) != expected:
            raise ValueError(f'Code hash mismatch: {name}')
    # Verify BOTH partitions before reading either. No TEST path is constructed.
    for part in ('train', 'validation'):
        if digest(base / f'{part}.parquet') != manifest['partitions'][part]['sha256']:
            raise ValueError(f'Feature partition hash mismatch: {part}')
    data = {}
    for part in ('train', 'validation'):
        frame = pd.read_parquet(base / f'{part}.parquet')
        if frame.empty or not frame.split.eq(part).all():
            raise ValueError(f'Incorrect/empty {part} partition')
        if frame.source_row.duplicated().any() or frame.duplicated(['user_id', 'order_id']).any():
            raise ValueError('Duplicate interaction/chronology')
        ordered = frame.sort_values(['user_id', 'order_id', 'source_row'], kind='stable')
        expected_history = ordered.groupby('user_id', sort=False).cumcount()
        if not np.array_equal(ordered.history_length.to_numpy(), expected_history.to_numpy()):
            raise ValueError('History length differs from complete student sequence')
        if not frame.scored.eq(frame.history_length.ge(config['evaluation']['warmup'])).all():
            raise ValueError('Common scoring mask differs from configured warmup')
        data[part] = frame
    if not set(data['train'].user_id).isdisjoint(data['validation'].user_id):
        raise ValueError('TRAIN/VALIDATION student overlap')
    return config, manifest, data['train'], data['validation']


def score_model(model, validation, warmup, sequential=False):
    if sequential:
        prediction = sequential_predict(validation, model, warmup=warmup)
    else:
        prediction = validation[['source_row', 'user_id', 'order_id', 'correct', 'history_length']].copy()
        prediction['is_scored'] = validation.scored.astype(bool)
        before = model.global_parameters_snapshot()
        prediction['probability'] = model.predict_batch(validation)
        if before != model.global_parameters_snapshot():
            raise RuntimeError('Prediction changed fitted parameters')
        sample = validation[validation.user_id.isin(sorted(validation.user_id.unique())[:3])]
        seq = sequential_predict(sample, model, warmup=warmup)
        expected = prediction.set_index('source_row').loc[seq.source_row]
        np.testing.assert_allclose(seq.probability, expected.probability, rtol=0, atol=1e-12)
        if not np.array_equal(seq.is_scored, expected.is_scored):
            raise ValueError('Batch/sequential scoring masks differ')
    if len(prediction) != len(validation) or set(prediction.source_row) != set(validation.source_row):
        raise ValueError('Prediction coverage differs')
    expected = validation.set_index('source_row').loc[prediction.source_row]
    if not np.array_equal(prediction.is_scored, expected.scored):
        raise ValueError('Model evaluation mask differs')
    metrics = evaluate_predictions(prediction)
    if metrics['brier_score'] is None:
        raise ValueError('No scored validation rows')
    metrics['n_unscored_students'] = int(validation.user_id.nunique() - metrics['n_students'])
    return prediction, metrics


def run(group, root=ROOT):
    if group not in GROUPS:
        raise ValueError('Unknown group')
    root = Path(root)
    summary_path = root / f'artifacts/tables/foundationalassist_v4_{group}_validation.json'
    private = root / 'data/processed/foundationalassist_v4/training_runs'
    marker = private / f'{group}.started.json'
    if summary_path.exists() or marker.exists():
        raise FileExistsError('Group already started/completed; audit partial run before any retry')
    config, manifest, train, validation = load_development_data(root)
    private.mkdir(parents=True, exist_ok=True)
    with marker.open('x', encoding='utf-8') as stream:
        json.dump({'group': group, 'config_sha256': manifest['config_sha256'],
                   'started_utc': datetime.now(timezone.utc).isoformat()}, stream)
    models = root / 'artifacts/models/foundationalassist_v4'
    predictions = root / 'data/processed/foundationalassist_v4/predictions'
    models.mkdir(parents=True, exist_ok=True)
    predictions.mkdir(parents=True, exist_ok=True)
    output = {'stage': 'validation_development_not_final_test', 'status': 'running',
              'group': group, 'test_opened': False, 'python': platform.python_version(),
              'config_sha256': manifest['config_sha256'], 'code_sha256': manifest['code_sha256'],
              'feature_manifest_path': 'data/processed/foundationalassist_v4/features/manifest.json',
              'feature_manifest_sha256': digest(root / 'data/processed/foundationalassist_v4/features/manifest.json'),
              'input_sha256': {p: manifest['partitions'][p]['sha256'] for p in ('train', 'validation')},
              'selection_metric': 'validation_brier_score', 'tie_break': 'first_candidate',
              'results': [], 'candidates': [], 'model_sha256': {}}
    progress = private / f'{group}.progress.json'

    def persist():
        write_json(progress, output)

    def save_model(name, model, prediction):
        path = models / f'{name}.joblib'
        joblib.dump(model, path)
        restored = joblib.load(path)
        if restored.global_parameters_snapshot() != model.global_parameters_snapshot():
            raise RuntimeError('Checkpoint roundtrip changed model parameters')
        prediction.to_parquet(predictions / f'validation_{name}.parquet', index=False)
        output['model_sha256'][name] = digest(path)

    def fit_score(name, model, parameters=None):
        start = time.perf_counter()
        record = {'model': name, 'parameters': parameters or {}}
        try:
            model.fit(train)
            prediction, metrics = score_model(model, validation, config['evaluation']['warmup'], name == 'BKT')
            record.update(status='valid', **metrics)
        except PFAConvergenceError:
            record.update(status='invalid', reason='PFA did not converge within locked budget')
            prediction = None
        record['fit_evaluate_seconds'] = time.perf_counter() - start
        output['candidates'].append(record)
        persist()
        print(json.dumps(record, allow_nan=False), flush=True)
        return prediction, record

    persist()
    try:
        if group == 'baselines_pfa':
            for name, model in [('Global', GlobalBaseline()), ('Problem', ProblemBaseline(alpha=config['problem_difficulty']['alpha']))]:
                prediction, record = fit_score(name, model)
                save_model(name, model, prediction)
                output['results'].append(record)
            cfg = config['pfa']
            candidates = [({'C': c}, PFA(C=c, max_iter=cfg['max_iter'], tol=cfg['tol'], seed=cfg['seed'])) for c in cfg['C_candidates']]
            name = 'PFA'
        elif group == 'bkt':
            candidates = [({}, BKT(config=config['bkt']))]
            name = 'BKT'
        else:
            cfg = config['xgboost']
            order = cfg['grid_order']
            parameters = [dict(zip(order, values)) for values in product(*(cfg['grid'][key] for key in order))]
            candidates = [(params, XGBoostModel(**params, seed=cfg['seed'])) for params in parameters]
            name = 'XGBoost'
        best_score, selected = float('inf'), None
        for parameters, model in candidates:
            prediction, record = fit_score(name, model, parameters)
            if record['status'] == 'valid' and record['brier_score'] < best_score:
                best_score, selected = record['brier_score'], record
                save_model(name, model, prediction)
                if name == 'BKT':
                    output['fit_diagnostics'] = model.fit_diagnostics_
        if selected is None:
            raise RuntimeError('All locked candidates invalid; do not expand budget')
        output['results'].append(selected)
        output['selected_parameters'] = selected['parameters']
        output['status'] = 'completed'
        persist()
        write_json(summary_path, output)
        return output
    except Exception as exc:
        output['status'] = 'failed'
        # Exception type only: arbitrary exception strings could include private rows.
        output['failure_type'] = type(exc).__name__
        persist()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=GROUPS, required=True)
    args = parser.parse_args()
    run(args.group)
