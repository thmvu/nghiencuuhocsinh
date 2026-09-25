"""Local RQ2 demo on a synthetic state; never a research observation."""

from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rq2.agent import build_agent_request, validate_agent_output
from src.rq2.candidates import generate_candidates
from src.rq2.ollama_client import call_local_ollama
from src.rq2.policy import recommend_bplus


def build_synthetic_demo(graph, pool, *, n_candidates=8):
    """Make an illustrative mastery gradient without using any student row."""
    skills = graph['skills']
    if not skills:
        raise ValueError('graph must contain skills')
    mastery = {skill: .2 + .6 * index / max(1, len(skills) - 1)
               for index, skill in enumerate(skills)}
    state = {'state_type': 'BKT_p_mastery', 'skills': mastery,
             'history_length': 12}
    candidates = generate_candidates(state, graph, pool,
                                     n_candidates=n_candidates)
    if len(candidates) != n_candidates:
        raise ValueError('not enough demo candidates')
    return {'state': state, 'graph': graph, 'candidates': candidates}


def run_demo(shared, *, model, temperature=0, num_ctx=2048, timeout=90,
             call=call_local_ollama):
    """Show B+ and Agent decisions on precisely the same synthetic input."""
    bplus = recommend_bplus(shared['state'], shared['graph'], shared['candidates'])
    request = build_agent_request(shared['state'], shared['graph'],
                                  shared['candidates'], model=model,
                                  temperature=temperature, num_ctx=num_ctx)
    content = call(request, timeout=timeout)
    agent = validate_agent_output(content, shared['candidates'])
    return {'stage': 'synthetic_demo_not_research_result',
            'graph_status': shared['graph'].get('status'),
            'state': shared['state'], 'candidates': shared['candidates'],
            'bplus': bplus, 'agent': agent}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bplus-only', action='store_true',
                        help='show deterministic B+ without calling Ollama')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'configs/protocol_c.json').read_text(encoding='utf-8'))
    paths = [lock['graph_path'], lock['candidate_pool_path']]
    for relative in paths:
        file = ROOT / relative
        if hashlib.sha256(file.read_bytes()).hexdigest() != lock['frozen_artifacts_sha256'][relative]:
            raise ValueError(f'frozen demo artifact changed: {relative}')
    graph = json.loads((ROOT / lock['graph_path']).read_text(encoding='utf-8'))
    pool = json.loads((ROOT / lock['candidate_pool_path']).read_text(encoding='utf-8'))
    shared = build_synthetic_demo(graph, pool,
                                  n_candidates=lock['scenario_protocol']['n_candidates'])
    if args.bplus_only:
        result = {'stage': 'synthetic_demo_not_research_result',
                  'graph_status': graph.get('status'), 'state': shared['state'],
                  'candidates': shared['candidates'],
                  'bplus': recommend_bplus(shared['state'], graph,
                                           shared['candidates'])}
    else:
        agent = lock['agent']
        result = run_demo(shared, model=agent['model'],
                          temperature=agent['temperature'],
                          num_ctx=agent['num_ctx'], timeout=agent['timeout_seconds'])
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
