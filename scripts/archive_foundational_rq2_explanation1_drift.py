"""Preserve the failed runtime gate; never relabel it as a validated study."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import digest, local_json, read_json, save
from scripts.run_foundational_rq2_explanation1 import PRIVATE, OUTPUT, aggregate, prepare_explanation


def main():
    if (PRIVATE / 'runs.json').exists():
        raise ValueError('archive already exists; never overwrite')
    config, _, schedule, cohorts, pins, baseline = prepare_explanation()
    summary = read_json(OUTPUT)
    if summary['agent_status'] != 'in_progress' or summary['input_sha256'] != pins:
        raise ValueError('only preserve this interrupted end gate')
    current = local_json('version')['version']
    if current == summary['ollama_version']:
        raise ValueError('runtime drift not observed')
    models = local_json('tags')['models']
    if not any(m['name'] == config['model'] and m['digest'] == config['model_digest'] for m in models):
        raise ValueError('model changed as well; separate audit required')
    rows = read_json(PRIVATE / 'runs.partial.json')
    if len(rows) != len(schedule):
        raise ValueError('expected full preserved calls')
    for relative, expected in pins.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('source or previous study changed')
    save(PRIVATE / 'runs.json', rows)
    summary.update(agent_status='completed_runtime_drift_not_validated', study_calls_completed=len(rows),
                   observed_final_ollama_version=current, runtime_identity_unchanged=False,
                   model_digest_still_matches=True, runtime_change_boundary_unknown=True,
                   cohorts=aggregate(rows, baseline, cohorts, ['curriculum_edges', 'no_edges']),
                   private_runs_sha256=digest(PRIVATE / 'runs.json'), previous_studies_unchanged=True,
                   raw_drafts_semantically_verified=False, archive_script_sha256=digest(Path(__file__)))
    save(OUTPUT, summary)
    print({'status': summary['agent_status'], 'calls_preserved': len(rows), 'start': summary['ollama_version'], 'end': current})


if __name__ == '__main__':
    main()
