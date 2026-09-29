"""Read-only schema/provenance audit. No preprocessing rules or split are applied."""
from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'adaptive-learning-nckh/data/raw/FoundationalASSIST'


def audit():
    tables, provenance = {}, {}
    for name in ('Interactions', 'Problems', 'Skills'):
        path = BASE / 'Data' / f'{name}.csv'
        # Preserve literal field values, including empty strings and strings such as NA.
        tables[name] = pd.read_csv(path, dtype=str, keep_default_na=False)
        metadata = BASE / '.cache/huggingface/download/Data' / f'{name}.csv.metadata'
        lines = metadata.read_text().splitlines() if metadata.exists() else []
        provenance[name] = {'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'download_revision': lines[0] if lines else None,
                            'download_etag': lines[1] if len(lines) > 1 else None}
    i, p, s = (tables[name] for name in ('Interactions', 'Problems', 'Skills'))
    fields = ['user_id', 'problem_id', 'end_time', 'discrete_score',
              'answer_text', 'hint_count', 'saw_answer']
    assert set(i.columns) == set(fields + ['id', 'Unnamed: 0'])
    semantic = i.drop(columns=['Unnamed: 0'])
    unique = semantic.drop_duplicates()  # In-memory diagnostic only; raw stays untouched.
    time = pd.to_datetime(unique.end_time, errors='coerce', utc=True, format='mixed')
    numeric = pd.to_numeric(i.discrete_score, errors='coerce')
    problem_unique = p.drop_duplicates()
    skills_per_problem = s.groupby('problem_id').skill_id.nunique()
    result = {
        'status': 'read_only_audit_no_rules_locked_no_training',
        'provenance': provenance,
        'schema': {name: {'shape': list(frame.shape), 'columns': list(frame.columns),
                         'empty_fields': {c: int(frame[c].eq('').sum()) for c in frame}}
                   for name, frame in tables.items()},
        'duplicates': {
            'exact_raw_repeated_rows': int(i.duplicated().sum()),
            'export_index_unique': bool(i['Unnamed: 0'].is_unique),
            'repeated_rows_including_interaction_id_excluding_export_index': int(semantic.duplicated().sum()),
            'repeated_rows_on_requested_seven_fields': int(i.duplicated(fields).sum()),
            'repeated_interaction_ids': int(i.id.duplicated().sum()),
            'interaction_ids_with_conflicting_business_fields': int((unique.groupby('id').size() > 1).sum()),
            'same_seven_fields_with_distinct_interaction_ids': int((unique.groupby(fields, dropna=False).id.nunique() > 1).sum()),
            'diagnostic_unique_rows': len(unique),
            'readme_unique_interactions': 1722169,
            'readme_minus_diagnostic_unique_rows': 1722169 - len(unique),
        },
        'target': {'blank_score_raw': int(i.discrete_score.eq('').sum()),
                   'numeric_missing_or_invalid_raw': int(numeric.isna().sum()),
                   'nonempty_invalid_score_raw': int((numeric.isna() & i.discrete_score.ne('')).sum()),
                   'nonbinary_score_raw': int((numeric.notna() & ~numeric.isin([0, 1])).sum()),
                   'blank_score_diagnostic_unique': int(unique.discrete_score.eq('').sum())},
        'chronology': {'blank_time_diagnostic_unique': int(unique.end_time.eq('').sum()),
                       'unparseable_nonempty_time': int((time.isna() & unique.end_time.ne('')).sum()),
                       'student_timestamp_ties_diagnostic_unique': int(unique.assign(time=time).dropna(subset=['time']).duplicated(['user_id', 'time']).sum())},
        'joins': {'interaction_problems_missing_metadata': len(set(i.problem_id) - set(p.problem_id)),
                  'interaction_problems_missing_skill_mapping': len(set(i.problem_id) - set(s.problem_id)),
                  'problem_exact_repeated_rows': int(p.duplicated().sum()),
                  'problem_ids_with_conflicting_metadata': int((problem_unique.groupby('problem_id').size() > 1).sum()),
                  'multi_skill_problems': int((skills_per_problem > 1).sum()),
                  'unique_skills': int(s.skill_id.nunique()),
                  'unique_node_codes': int(s.node_code.nunique()),
                  'problem_rows_with_img_tag': int(p['Problem Body'].str.contains('<img', case=False).sum())},
        'interpretation': ['Same interaction id and all seven business fields repeat; no raw rows removed.',
                           'README difference of 226 remains unexplained; do not invent missing rows.',
                           'Download revision comes from local Hugging Face cache metadata, not a new remote integrity check.',
                           'Absence of an img tag does not establish text completeness.',
                           'Skills is a mapping table, not an explicit prerequisite graph.'],
    }
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, ensure_ascii=False))
