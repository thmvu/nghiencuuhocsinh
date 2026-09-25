"""Prepare RQ2 VALIDATION cases only; never read RQ2 TEST data."""

from pathlib import Path
import hashlib
import json
import sys

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rq2.validation import build_validation_cases, summarize_validation_cases


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lock_path = ROOT / 'configs/protocol_b.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    dev_path = ROOT / 'configs/rq2_development.json'
    dev = json.loads(dev_path.read_text(encoding='utf-8'))
    if lock['stage'] != 'B' or dev['stage'] != 'validation_development_not_lock_c':
        raise ValueError('RQ2 validation development requires completed RQ1 Lock B')
    if dev['test_access'] != 'forbidden_until_lock_c_and_gate_c':
        raise ValueError('RQ2 TEST gate must remain closed')
    model_path = ROOT / lock['models']['BKT']['path']
    if digest(model_path) != lock['models']['BKT']['sha256']:
        raise ValueError('BKT checkpoint differs from Lock B')
    partitions = {}
    for split in ('train', 'validation'):
        path = ROOT / f'data/processed/{split}.parquet'
        if digest(path) != lock['input_sha256'][split]:
            raise ValueError(f'{split} partition differs from Lock B')
        frame = pd.read_parquet(path)
        if not frame.split.eq(split).all():
            raise ValueError(f'incorrect {split} partition')
        partitions[split] = frame
    bkt = joblib.load(model_path)
    cases, graph, pool = build_validation_cases(
        partitions['train'], partitions['validation'], bkt,
        n_scenarios=dev['validation_scenarios'], seed=dev['seed'],
        n_skills=dev['graph_skills'],
        min_support=dev['candidate_min_train_support'],
        n_candidates=dev['candidates_per_scenario'],
        min_history=dev['snapshot_min_history'])
    summary = summarize_validation_cases(cases, graph, pool)
    summary.update({'lock_b_sha256': digest(lock_path),
                    'development_config_sha256': digest(dev_path),
                    'bkt_checkpoint_sha256': digest(model_path),
                    'input_sha256': {split: lock['input_sha256'][split]
                                     for split in ('train', 'validation')}})
    private = ROOT / 'data/processed/rq2_validation_scenarios'
    private.mkdir(parents=True, exist_ok=True)
    scenario_path = private / 'scenarios.json'
    scenario_path.write_text(
        json.dumps(cases, indent=2, allow_nan=False), encoding='utf-8')
    (private / 'candidate_pool.json').write_text(
        json.dumps(pool, indent=2, allow_nan=False), encoding='utf-8')
    summary['validation_scenarios_sha256'] = digest(scenario_path)
    tables = ROOT / 'artifacts/tables'
    tables.mkdir(parents=True, exist_ok=True)
    (tables / 'rq2_prototype_graph.json').write_text(
        json.dumps(graph, indent=2, allow_nan=False), encoding='utf-8')
    (tables / 'rq2_validation_summary.json').write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
