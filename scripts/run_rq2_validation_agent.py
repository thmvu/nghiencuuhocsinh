"""Run one local Agent pass on RQ2 VALIDATION scenarios only."""

from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rq2.agent_validation import run_validation_cases, summarize_agent_validation


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config_path = ROOT / 'configs/rq2_agent_development.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if (config['stage'] != 'validation_development_not_lock_c' or
            config['test_access'] != 'forbidden_until_lock_c_and_gate_c' or
            config['repair_attempts'] != 0 or config['runs_per_scenario'] != 1):
        raise ValueError('unexpected RQ2 Agent development protocol')
    private = ROOT / 'data/processed/rq2_validation_scenarios'
    scenarios_path = private / 'scenarios.json'
    cases = json.loads(scenarios_path.read_text(encoding='utf-8'))
    expected = json.loads((ROOT / 'artifacts/tables/rq2_validation_summary.json').read_text(encoding='utf-8'))
    if digest(scenarios_path) != expected['validation_scenarios_sha256']:
        raise ValueError('validation scenario artifact changed since preparation')
    if len(cases) != expected['n_scenarios'] or len({case['student_id'] for case in cases}) != len(cases):
        raise ValueError('validation scenario count/student separation changed')
    runs = run_validation_cases(
        cases, model=config['model'], temperature=config['temperature'],
        num_ctx=config['num_ctx'], timeout=config['timeout_seconds'])
    summary = summarize_agent_validation(runs)
    summary.update({'model': config['model'], 'temperature': config['temperature'],
                    'num_ctx': config['num_ctx'], 'timeout_seconds': config['timeout_seconds'],
                    'repair_attempts': config['repair_attempts'],
                    'runs_per_scenario': config['runs_per_scenario'],
                    'development_config_sha256': digest(config_path),
                    'validation_scenarios_sha256': digest(scenarios_path),
                    'lock_b_sha256': expected['lock_b_sha256']})
    (private / 'agent_runs.json').write_text(json.dumps(runs, indent=2, allow_nan=False), encoding='utf-8')
    output = ROOT / 'artifacts/tables/rq2_agent_validation_summary.json'
    output.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
