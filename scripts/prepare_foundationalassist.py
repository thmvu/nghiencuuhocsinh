"""Create isolated v4 preprocessing artifacts and a persistent student split; no training."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.preprocessing.foundational import clean_primary, make_split, content_screen

BASE = ROOT / 'adaptive-learning-nckh/data/raw/FoundationalASSIST/Data'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4'
LOCK = ROOT / 'configs/foundationalassist_v4_preprocessing.json'
SUMMARY = ROOT / 'artifacts/tables/foundationalassist_v4_preprocessing.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def main():
    if LOCK.exists():
        lock = json.loads(LOCK.read_text(encoding='utf-8'))
        for relative, expected in lock['pinned_sha256'].items():
            if digest(ROOT / relative) != expected:
                raise ValueError(f'locked artifact differs: {relative}')
        print('Existing v4 lock and saved split verified; no artifacts regenerated.')
        return
    if PRIVATE.exists() and any(PRIVATE.iterdir()):
        raise FileExistsError('partial v4 artifacts exist; inspect rather than replace split')
    audit = json.loads((ROOT / 'artifacts/tables/foundationalassist_initial_audit.json').read_text(encoding='utf-8'))
    for name, info in audit['provenance'].items():
        if digest(BASE / f'{name}.csv') != info['sha256']:
            raise ValueError('raw differs from audited revision')
    raw, problems, skills = [pd.read_csv(BASE / f'{name}.csv', dtype=str, keep_default_na=False)
                             for name in ('Interactions', 'Problems', 'Skills')]
    frame, funnel = clean_primary(raw, skills)
    mapping = make_split(frame.user_id, seed=42)
    frame['split'] = frame.user_id.map(mapping)
    problem_rows = problems.drop_duplicates()
    groups = problem_rows.groupby('problem_id', sort=True)
    conflict_ids = {key for key, group in groups if len(group) > 1}
    skill_counts = skills.groupby('problem_id').skill_id.nunique()
    bank, reasons = [], Counter()
    for pid, group in groups:
        record = group.iloc[0].to_dict()
        screen = content_screen(record, conflict=pid in conflict_ids,
                                skill_count=int(skill_counts.get(pid, 0)))
        reasons.update(screen['reasons'])
        bank.append({'problem_id': pid, **screen,
                     'metadata_variants': group.to_dict('records'),
                     'skill_ids': sorted(skills.loc[skills.problem_id.eq(pid), 'skill_id'].unique().tolist()),
                     'review': {'content_complete': None, 'options_answers_parseable': None,
                                'math_preserved': None, 'no_external_dependency': None,
                                'skill_mapping_appropriate': None, 'reviewer': None, 'source': None}})
    PRIVATE.mkdir(parents=True, exist_ok=True)
    save(PRIVATE / 'student_split.json', {'seed': 42, 'ratios': [.7, .15, .15],
                                         'unit': 'user_id', 'assignments': mapping})
    for part in ('train', 'validation', 'test'):
        frame.loc[frame.split.eq(part)].to_parquet(PRIVATE / f'{part}.parquet', index=False)
    save(PRIVATE / 'rq2_content_review.json', bank)
    summary = {'status': 'preprocessing_locked_training_not_authorized', 'funnel': funnel,
               'split_counts': {part: {'students': int(group.user_id.nunique()), 'rows': len(group)}
                                for part, group in frame.groupby('split')},
               'metadata_conflict_problem_count': len(conflict_ids),
               'rq1_rows_on_metadata_conflict_problems': int(frame.problem_id.isin(conflict_ids).sum()),
               'skills_used': int(frame.skill_id.nunique()),
               'rq2_content': {'n_problems': len(bank),
                               'automatic_screen_pass': sum(x['automatic_screen_pass'] for x in bank),
                               'rq2_text_eligible': 0, 'review_status': 'pending',
                               'reason_counts_overlapping': dict(reasons)},
               'test_metrics_computed': False}
    save(SUMMARY, summary)
    paths = [BASE / f'{name}.csv' for name in ('Interactions', 'Problems', 'Skills')]
    paths += [PRIVATE / 'student_split.json', *[PRIVATE / f'{part}.parquet' for part in ('train', 'validation', 'test')],
              ROOT / 'src/preprocessing/foundational.py', Path(__file__).resolve(), SUMMARY]
    lock = {'version': 'foundationalassist-v4-preprocessing-1',
            'stage': 'preprocessing_and_student_split', 'training_authorized': False,
            'next_gate': 'model_feature_and_evaluation_protocol_lock_before_training',
            'dataset_revision': audit['provenance']['Interactions']['download_revision'],
            'seed': 42, 'ratios': [.7, .15, .15], 'split_reuse_required': True,
            'split_path': str((PRIVATE / 'student_split.json').relative_to(ROOT)).replace('\\', '/'),
            'cleaning': {'dedup': 'id plus seven literal business fields; keep first source row',
                         'same_business_different_id': 'retain', 'missing_invalid_label_time': 'exclude',
                         'skill_unit': 'skill_id', 'primary': 'single_skill_problem',
                         'metadata_conflict': 'RQ1 retained if eligible; RQ2 quarantine',
                         'chronology': 'UTC end_time; reject student ties',
                         'state_updates': 'eligible filtered interactions only'},
            'rq2_text_eligible': 'false until documented review of all content conditions; automatic screening is insufficient',
            'current_interaction_forbidden_features': ['answer_text', 'hint_count', 'saw_answer', 'discrete_score'],
            'pinned_sha256': {str(path.relative_to(ROOT)).replace('\\', '/'): digest(path) for path in paths}}
    save(LOCK, lock)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
