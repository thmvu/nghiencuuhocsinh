"""One-shot RQ1 TEST evaluation, allowed only after Configuration Lock B."""
from pathlib import Path
import hashlib
import json
import sys

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.bootstrap import paired_student_brier_bootstrap
from src.evaluation.metrics import evaluate_predictions
from src.evaluation.sequential import sequential_predict

NAMES = ('Global', 'Problem', 'PFA', 'BKT', 'XGBoost')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_path(root, relative, expected):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'missing or unsafe locked artifact: {relative}')
    if digest(path) != expected:
        raise ValueError(f'locked artifact hash mismatch: {relative}')
    return path


def preflight(root, lock):
    """Check all Gate B evidence before reading TEST labels or checkpoints."""
    if (lock.get('stage') != 'B' or lock.get('gate_b') != 'RQ1 PRE-TEST CHECKLIST PASS'
            or lock.get('test_opened') is not False):
        raise ValueError('Gate B is not explicitly complete')
    selection = lock.get('selection', {})
    if (selection.get('pfa_C') != .1 or selection.get('xgboost') !=
            {'max_depth': 4, 'learning_rate': .1, 'n_estimators': 300}
            or selection.get('calibrator') != 'none'):
        raise ValueError('Lock B selection differs from completed validation')
    evaluation = lock.get('evaluation', {})
    bootstrap = evaluation.get('bootstrap', {})
    if (evaluation.get('warmup') != 5 or evaluation.get('scored_only') is not True
            or bootstrap != {'unit': 'student', 'iterations': 1000, 'seed': 42,
                             'ci_quantiles': [.025, .975], 'metric': 'brier_score',
                             'pairing': 'same_scored_rows',
                             'difference': 'model_minus_XGBoost',
                             'aggregation': 'interaction_weighted'}):
        raise ValueError('Lock B evaluation protocol differs from preregistered protocol')
    paths = {}
    paths['protocol_a'] = _verified_path(root, 'configs/protocol_a.json', lock['protocol_a_sha256'])
    paths['split_manifest'] = _verified_path(root, 'data/processed/student_split.json',
                                              lock['split_manifest_sha256'])
    for part in ('train', 'validation', 'test'):
        paths[part] = _verified_path(root, f'data/processed/{part}.parquet',
                                     lock['input_sha256'][part])
    if set(lock['models']) != set(NAMES):
        raise ValueError('Lock B must identify all five models')
    paths['models'] = {name: _verified_path(root, lock['models'][name]['path'],
                                           lock['models'][name]['sha256'])
                       for name in NAMES}
    for relative, sha in lock.get('validation_artifact_sha256', {}).items():
        _verified_path(root, relative, sha)
    for relative, sha in lock.get('code_sha256', {}).items():
        _verified_path(root, relative, sha)
    return paths


def compare_predictions(predictions):
    """Join five predictions on source row and demand one common scored population."""
    if set(predictions) != set(NAMES):
        raise ValueError('All five locked models are required')
    common = None
    identity = None
    for name in NAMES:
        frame = predictions[name]
        if frame.source_row.duplicated().any() or len(frame) == 0:
            raise ValueError(f'{name} has duplicate or empty row identities')
        frame = frame.set_index('source_row').sort_index()
        required = frame[['user_id', 'correct', 'is_scored']].copy()
        # Parquet StringDtype and sequential evaluator object dtype carry the
        # same student identities; compare values after normalizing the dtype.
        required['user_id'] = required['user_id'].astype(str)
        if common is None:
            identity = required.copy()
            common = required.copy()
        elif not required.equals(identity):
            raise ValueError(f'{name} differs in rows, labels, students or scored mask')
        common[name] = frame.probability
    return common.reset_index()


def _calibration(scored):
    boundaries = np.linspace(0, 1, 11)
    rows = []
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.plot([0, 1], [0, 1], '--', color='#777777', label='Perfect calibration')
    for name in NAMES:
        bins = np.minimum(np.searchsorted(boundaries, scored[name].to_numpy(), side='right') - 1, 9)
        grouped = scored.assign(bin=bins).groupby('bin').agg(
            count=('correct', 'size'), mean_prediction=(name, 'mean'),
            observed_rate=('correct', 'mean'))
        for index, item in grouped.iterrows():
            rows.append({'model': name, 'bin': int(index), **item.to_dict()})
        ax.plot(grouped.mean_prediction, grouped.observed_rate, marker='o', label=name)
    ax.set(xlabel='Mean predicted probability', ylabel='Observed success rate',
           title='RQ1 final TEST calibration (10 fixed-width bins)', xlim=(0, 1), ylim=(0, 1))
    ax.legend(frameon=False)
    ax.grid(alpha=.2)
    fig.tight_layout()
    return fig, pd.DataFrame(rows)


def run(root=ROOT):
    lock_path = root / 'configs/protocol_b.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    paths = preflight(root, lock)
    # TEST labels are first accessed only after all lock evidence has passed.
    test = pd.read_parquet(paths['test'])
    if not test.split.eq('test').all() or test.source_row.duplicated().any():
        raise ValueError('TEST partition identities invalid')
    models = {name: joblib.load(paths['models'][name]) for name in NAMES}
    predictions = {}
    warmup = lock['evaluation']['warmup']
    for name, model in models.items():
        if name == 'BKT':
            predictions[name] = sequential_predict(test, model, warmup=warmup)
            continue
        frozen = model.global_parameters_snapshot()
        frame = test[['source_row', 'user_id', 'correct', 'history_length']].copy()
        frame['is_scored'] = test.scored.astype(bool)
        frame['probability'] = model.predict_batch(test)
        if model.global_parameters_snapshot() != frozen:
            raise RuntimeError(f'{name} fitted parameters changed during TEST prediction')
        sample = test[test.user_id.isin(sorted(test.user_id.unique())[:2])]
        sequential = sequential_predict(sample, model, warmup=warmup)
        lookup = frame.set_index('source_row')
        np.testing.assert_allclose(sequential.probability,
                                   lookup.loc[sequential.source_row, 'probability'], atol=1e-12)
        predictions[name] = frame
    common = compare_predictions(predictions)
    if not common.is_scored.eq(test.set_index('source_row').scored.reindex(common.source_row).to_numpy()).all():
        raise ValueError('TEST scoring mask differs from frozen preprocessing')
    metrics = {name: evaluate_predictions(predictions[name]) for name in NAMES}
    if len({(item['n_rows'], item['n_students']) for item in metrics.values()}) != 1:
        raise ValueError('Unequal TEST scoring populations')
    bootstrap = lock['evaluation']['bootstrap']
    uncertainty = {name: paired_student_brier_bootstrap(
        common, name, 'XGBoost', iterations=bootstrap['iterations'], seed=bootstrap['seed'])
        for name in NAMES if name != 'XGBoost'}
    scored = common.loc[common.is_scored].copy()
    fig, bins = _calibration(scored)
    tables = root / 'artifacts/tables'
    plots = root / 'artifacts/plots'
    reports = root / 'reports'
    for folder in (tables, plots, reports):
        folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(plots / 'rq1_test_calibration.png', dpi=180)
    plt.close(fig)
    bins.to_csv(tables / 'rq1_test_calibration_bins.csv', index=False)
    result = {'stage': 'final_test', 'lock_b_sha256': digest(lock_path),
              'test_sha256': lock['input_sha256']['test'], 'metrics': metrics,
              'paired_student_brier_bootstrap': uncertainty,
              'calibration': '10 fixed-width bins; no calibrator fitted'}
    (tables / 'rq1_test_results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    lines = ['# RQ1 — final TEST results', '',
             'All five frozen train-fitted models were evaluated on the same post-warm-up TEST rows.', '',
             '| Model | Rows | Students | Brier ↓ | ROC-AUC ↑ | Log Loss ↓ |',
             '|---|---:|---:|---:|---:|---:|']
    for name, item in metrics.items():
        auc = 'undefined' if item['roc_auc'] is None else f"{item['roc_auc']:.4f}"
        lines.append(f"| {name} | {item['n_rows']} | {item['n_students']} | {item['brier_score']:.4f} | {auc} | {item['log_loss']:.4f} |")
    lines += ['', 'Paired student bootstrap compares interaction-weighted Brier differences '
              '(model minus XGBoost); positive values favor XGBoost.', '',
              '| Model | Difference | 95% CI |', '|---|---:|---:|']
    for name, item in uncertainty.items():
        lines.append(f"| {name} | {item['difference']:.4f} | [{item['ci_low']:.4f}, {item['ci_high']:.4f}] |")
    lines += ['', 'Calibration uses 10 fixed-width probability bins and no fitted calibrator. '
              'See `artifacts/plots/rq1_test_calibration.png`.', '']
    (reports / 'rq1_test_results.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, allow_nan=False))
