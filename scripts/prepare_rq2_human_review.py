"""Create private blind rating packets from the already completed RQ2 TEST run.

Never calls Ollama, resamples TEST, or changes the frozen evaluation.
"""

from pathlib import Path
import argparse
import csv
import hashlib
import json
import random

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'data/processed/rq2_human_review'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_cases(cases, *, count=20, seed=43):
    ordered = sorted(cases, key=lambda case: case['scenario_id'])
    if len(ordered) < count or len({c['scenario_id'] for c in ordered}) != len(ordered):
        raise ValueError('scenario set is incomplete or duplicated')
    indices = np.random.default_rng(seed).choice(len(ordered), count, replace=False)
    return [ordered[int(i)] for i in indices]


def make_packets(cases, runs, *, count=20, seed=43):
    """Use the first Agent attempt, including INVALID, without replacement."""
    first = {}
    for run in runs:
        if run['repeat'] == 1:
            if run['scenario_id'] in first:
                raise ValueError('duplicate first Agent attempt')
            first[run['scenario_id']] = run
    chosen = select_cases(cases, count=count, seed=seed)
    rows, key = [], []
    for index, case in enumerate(chosen, 1):
        sid = case['scenario_id']
        if sid not in first:
            raise ValueError('missing first Agent attempt')
        shared = case['shared_input']
        candidates = shared['candidates']
        by_id = {str(item['problem_id']): item for item in candidates}
        if len(by_id) != len(candidates):
            raise ValueError('duplicate candidate IDs')
        if case['state'] != shared['state'] or case['bplus'] not in candidates:
            raise ValueError('shared input mismatch')
        run = first[sid]
        selections = [('B+', str(case['bplus']['problem_id']))]
        agent_id = str(run['selected_problem_id']) if run['candidate_valid'] else None
        if agent_id is not None and agent_id not in by_id:
            raise ValueError('recorded Agent selection outside candidates')
        selections.append(('Agent', agent_id))
        case_code = f'C{index:02d}'
        for policy, problem_id in selections:
            option_code = hashlib.sha256(f'{seed}:{sid}:{policy}'.encode()).hexdigest()[:10]
            key.append({'case_code': case_code, 'option_code': option_code,
                        'scenario_id': sid, 'policy': policy,
                        'status': 'VALID' if problem_id else 'INVALID'})
            if problem_id is None:
                continue
            selected = by_id[problem_id]
            rows.append({
                'case_code': case_code, 'option_code': option_code,
                'history_length': shared['state']['history_length'],
                'mastery_estimates': json.dumps(shared['state']['skills'], ensure_ascii=False,
                                                sort_keys=True),
                'graph_edges_prototype': json.dumps(shared['graph']['edges'], ensure_ascii=False),
                'candidates': json.dumps(candidates, ensure_ascii=False),
                'selected_problem_id': problem_id, 'selected_skill_id': selected['skill_id'],
                'selected_difficulty_proxy': selected['difficulty'],
                'state_score_0_2': '', 'graph_score_0_2': '', 'difficulty_score_0_2': '',
                'notes': '',
            })
    return rows, key


def write_csv(path, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PRIVATE)
    args = parser.parse_args()
    lock_path = ROOT / 'configs/protocol_c.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    rubric = ROOT / lock['human_evaluation']['rubric_path']
    if sha256(rubric) != lock['human_evaluation']['rubric_sha256']:
        raise ValueError('frozen rubric changed')
    source = ROOT / 'data/processed/rq2_test_scenarios'
    cases = json.loads((source / 'scenarios.json').read_text(encoding='utf-8'))
    runs = json.loads((source / 'agent_runs.json').read_text(encoding='utf-8'))
    if len(cases) != lock['scenario_protocol']['n_students'] or len(runs) != len(cases) * 3:
        raise ValueError('frozen TEST records incomplete')
    rows, key = make_packets(cases, runs,
                             count=lock['human_evaluation']['n_scenarios_if_available'],
                             seed=lock['human_evaluation']['blind_scenario_seed'])
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'data').resolve()):
        raise ValueError('review packets must remain inside ignored data/')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError('review output directory must be empty; do not overwrite packets')
    (output / 'sealed_key.json').write_text(json.dumps(key, indent=2), encoding='utf-8')
    for rater in (1, 2):
        packet = rows.copy()
        random.Random(43 + rater).shuffle(packet)
        write_csv(output / f'rater_{rater}.csv', packet)
    print(f'Prepared {len(key) // 2} blinded cases, {len(rows)} scorable options; files in {output}')
    print('Keep sealed_key.json private. Send each rater only their own CSV and rubric.')


if __name__ == '__main__':
    main()
