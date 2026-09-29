"""Prepare TRAIN/VALIDATION RQ1 features only. Never opens TEST."""
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.preprocessing.pipeline import add_history_features, add_problem_difficulty

CONFIG = ROOT / 'configs/foundationalassist_v4_rq1_training.json'
BASE = ROOT / 'data/processed/foundationalassist_v4'
CODE = ['src/preprocessing/pipeline.py', 'src/evaluation/sequential.py',
        'src/evaluation/metrics.py', 'src/models/baselines.py', 'src/models/pfa.py',
        'src/models/bkt.py', 'src/models/xgboost_model.py',
        'scripts/prepare_foundational_rq1_features.py', 'scripts/train_foundational_rq1.py']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    lock_path = ROOT / config['preprocessing_lock']
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    split_path = ROOT / lock['split_path']
    if digest(split_path) != lock['pinned_sha256'][lock['split_path']]:
        raise ValueError('saved student split changed')
    assignments = json.loads(split_path.read_text(encoding='utf-8'))['assignments']
    out = BASE / 'features'
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('features already exist; never silently regenerate')
    frames, inputs = [], {}
    for part in ('train', 'validation'):
        path = BASE / f'{part}.parquet'
        expected = lock['pinned_sha256'][path.relative_to(ROOT).as_posix()]
        if digest(path) != expected:
            raise ValueError(f'locked {part} data changed')
        frame = pd.read_parquet(path)
        if not frame.split.eq(part).all() or not frame.user_id.map(assignments).eq(part).all():
            raise ValueError('split membership mismatch')
        frames.append(frame)
        inputs[part] = expected
    if set(frames[0].user_id) & set(frames[1].user_id):
        raise ValueError('student overlap')
    combined = pd.concat(frames, ignore_index=True)
    features = add_problem_difficulty(
        add_history_features(combined, warmup=config['evaluation']['warmup']),
        n_splits=config['problem_difficulty']['n_splits'],
        alpha=config['problem_difficulty']['alpha'])
    columns = ['source_row', 'user_id', 'order_id', 'problem_id', 'skill_id', 'correct', 'split',
               'prior_skill_success', 'prior_skill_failure', 'prior_skill_count',
               'prior_skill_accuracy', 'prior_overall_accuracy', 'history_length', 'scored',
               'problem_difficulty']
    features = features[columns]
    if features.isna().any().any() or features.source_row.duplicated().any():
        raise ValueError('invalid feature table')
    # Gather hashes before any output is written; no code may be missing at lock time.
    code = {name: digest(ROOT / name) for name in CODE}
    manifest = {'stage': 'TRAIN_VALIDATION_features_no_TEST_access',
                'config_sha256': digest(CONFIG), 'preprocessing_lock_sha256': digest(lock_path),
                'split_sha256': digest(split_path), 'input_sha256': inputs,
                'code_sha256': code, 'requirements_sha256': digest(ROOT / 'requirements-lock.txt'),
                'partitions': {}}
    out.mkdir(parents=True, exist_ok=True)
    for part in ('train', 'validation'):
        frame = features.loc[features.split.eq(part)].copy()
        path = out / f'{part}.parquet'
        frame.to_parquet(path, index=False)
        manifest['partitions'][part] = {'sha256': digest(path), 'rows': len(frame),
                                       'students': int(frame.user_id.nunique()),
                                       'scored_rows': int(frame.scored.sum()),
                                       'scored_students': int(frame.loc[frame.scored].user_id.nunique())}
    text = json.dumps(manifest, indent=2)
    (out / 'manifest.json').write_text(text, encoding='utf-8')
    (ROOT / 'artifacts/tables/foundationalassist_v4_feature_manifest.json').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
