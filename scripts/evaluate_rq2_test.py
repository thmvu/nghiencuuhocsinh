"""Run frozen RQ2 TEST once, only after Gate C and hash preflight pass."""

from pathlib import Path
import hashlib
import json
import sys
from urllib.request import urlopen

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rq2.test_evaluation import (run_test_cases, sample_test_scenarios,
                                     summarize_test_runs, validate_lock_c)


def digest(relative):
    path = ROOT / relative
    if not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f'missing or outside project: {relative}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_local_model(agent):
    """Match the frozen Ollama model bytes and quantization before TEST access."""
    with urlopen('http://127.0.0.1:11434/api/version', timeout=10) as response:
        version = json.loads(response.read().decode('utf-8'))['version']
    if version != agent['ollama_version']:
        raise ValueError('Ollama runtime version differs from Lock C')
    with urlopen('http://127.0.0.1:11434/api/tags', timeout=10) as response:
        catalog = json.loads(response.read().decode('utf-8'))
    models = [item for item in catalog['models'] if item.get('name') == agent['model']]
    if len(models) != 1:
        raise ValueError('frozen Ollama model is unavailable or ambiguous')
    installed = models[0]
    if (installed.get('digest') != agent['model_digest'] or
            installed.get('details', {}).get('quantization_level') != agent['quantization']):
        raise ValueError('installed Ollama model differs from Lock C')


def main():
    lock_path = ROOT / 'configs/protocol_c.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    validate_lock_c(lock, digest)
    lock_b = json.loads((ROOT / 'configs/protocol_b.json').read_text(encoding='utf-8'))
    if (lock_b['stage'] != 'B' or
            lock_b['input_sha256']['test'] != lock['test_input_sha256'] or
            lock_b['models']['BKT']['path'] != lock['bkt_checkpoint_path'] or
            lock_b['models']['BKT']['sha256'] != digest(lock['bkt_checkpoint_path'])):
        raise ValueError('RQ2 Lock C differs from RQ1 Lock B')
    verify_local_model(lock['agent'])
    output = ROOT / 'artifacts/tables/rq2_test_summary.json'
    private = ROOT / 'data/processed/rq2_test_scenarios'
    marker = private / 'evaluation_started.json'
    if output.exists() or marker.exists():
        raise FileExistsError('RQ2 TEST was already evaluated; refusing a second run')

    private.mkdir(parents=True, exist_ok=True)
    with marker.open('x', encoding='utf-8') as stream:
        json.dump({'lock_c_sha256': digest('configs/protocol_c.json'),
                   'status': 'started_one_shot'}, stream)

    # All locks and hashes are checked before reading any TEST row or label.
    test = pd.read_parquet(ROOT / 'data/processed/test.parquet')
    bkt = joblib.load(ROOT / lock['bkt_checkpoint_path'])
    graph = json.loads((ROOT / lock['graph_path']).read_text(encoding='utf-8'))
    pool = json.loads((ROOT / lock['candidate_pool_path']).read_text(encoding='utf-8'))
    protocol, agent = lock['scenario_protocol'], lock['agent']
    cases = sample_test_scenarios(
        test, bkt, graph, pool, n_students=protocol['n_students'],
        seed=protocol['seed'], min_history=protocol['min_history'],
        n_candidates=protocol['n_candidates'])
    runs = run_test_cases(
        cases, model=agent['model'], runs_per_scenario=agent['runs_per_scenario'],
        temperature=agent['temperature'], num_ctx=agent['num_ctx'],
        timeout=agent['timeout_seconds'])
    summary = summarize_test_runs(
        runs, expected_students=protocol['n_students'],
        runs_per_scenario=agent['runs_per_scenario'],
        bootstrap_iterations=lock['bootstrap']['iterations'],
        bootstrap_seed=lock['bootstrap']['seed'])
    summary.update({'lock_c_sha256': digest('configs/protocol_c.json'),
                    'test_input_sha256': lock['test_input_sha256'],
                    'model': agent['model'], 'model_digest': agent['model_digest'],
                    'quantization': agent['quantization'],
                    'graph_sha256': digest(lock['graph_path']),
                    'candidate_pool_sha256': digest(lock['candidate_pool_path'])})

    # Per-student/run identities are private; only the aggregate is tracked.
    (private / 'scenarios.json').write_text(json.dumps(cases, indent=2, allow_nan=False,
                                                    default=str), encoding='utf-8')
    (private / 'agent_runs.json').write_text(json.dumps(runs, indent=2, allow_nan=False,
                                                     default=str), encoding='utf-8')
    output.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
