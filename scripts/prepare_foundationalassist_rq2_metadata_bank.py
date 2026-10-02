"""Create a private, TRAIN-only RQ2 candidate inventory with no item text."""

from collections import Counter
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.rq2.candidates import build_foundational_metadata_pool


CONFIG_PATH = ROOT / 'configs/foundationalassist_v4_rq2_metadata_candidates.json'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4'
TRAIN_PATH = PRIVATE / 'train.parquet'
REVIEW_PATH = PRIVATE / 'rq2_content_review.json'


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    if config.get('stage') != 'candidate_inventory_development_not_lock_c':
        raise ValueError('unexpected metadata candidate config stage')
    if config.get('source_split') != 'train_only' or config.get('test_access') is not False:
        raise ValueError('metadata bank must be TRAIN-only')
    if config.get('rq2_text_eligible_filter') is not False or config.get('question_text_in_output') is not False:
        raise ValueError('metadata bank must be independent of text eligibility')
    if not TRAIN_PATH.is_file() or not REVIEW_PATH.is_file():
        raise FileNotFoundError('FoundationalASSIST v4 TRAIN and content-review inventory are required')

    train = pd.read_parquet(TRAIN_PATH)
    review = json.loads(REVIEW_PATH.read_text(encoding='utf-8'))
    conflict_ids = {
        str(item['problem_id']) for item in review
        if 'metadata_conflict' in item.get('reasons', [])
    }
    skill_ids = {
        str(skill_id)
        for ids in config['pilot_skill_ids_by_node_code'].values()
        for skill_id in ids
    }
    bank = build_foundational_metadata_pool(
        train, skill_ids=skill_ids, excluded_problem_ids=conflict_ids)
    if not bank:
        raise ValueError('no TRAIN metadata candidates remain in the configured skill scope')

    by_skill = Counter(item['skill_id'] for item in bank)
    by_code = {
        code: sum(by_skill.get(str(skill_id), 0) for skill_id in ids)
        for code, ids in config['pilot_skill_ids_by_node_code'].items()
    }
    summary = {
        'stage': config['stage'],
        'test_access': False,
        'content_text_in_bank': False,
        'rq2_text_eligible_used_for_filtering': False,
        'excluded_metadata_conflict_problem_count': len(conflict_ids),
        'pilot_node_code_count': len(config['pilot_skill_ids_by_node_code']),
        'pilot_skill_id_count': len(skill_ids),
        'candidate_problem_skill_pairs': len(bank),
        'unique_problem_count': len({item['problem_id'] for item in bank}),
        'candidate_pairs_by_skill_id': dict(sorted(by_skill.items())),
        'candidate_pairs_by_node_code': by_code,
        'difficulty_definition': config['difficulty_proxy'],
        'minimum_support': config['minimum_support_in_inventory'],
        'human_content_review_required_for_text_display_or_pedagogical_scoring': True,
    }

    output_path = ROOT / config['output_path']
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bank, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    summary_path = output_path.with_name('rq2_metadata_candidate_bank_summary.json')
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
