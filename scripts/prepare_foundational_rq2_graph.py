"""Materialize the v4 curriculum hypothesis using pinned TRAIN only."""

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.rq2.curriculum_graph import build_foundational_curriculum_graph


def main():
    config_path = ROOT / 'configs/foundationalassist_v4_rq2_curriculum_graph.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    lock = json.loads((ROOT / 'configs/foundationalassist_v4_rq1_final.json').read_text(encoding='utf-8'))
    inventory = json.loads((ROOT / 'configs/foundationalassist_v4_rq2_metadata_candidates.json').read_text(encoding='utf-8'))
    if config['pilot_skill_ids_by_node_code'] != inventory['pilot_skill_ids_by_node_code']:
        raise ValueError('graph scope differs from the v4 candidate inventory')
    if config['dataset_revision'] != inventory['dataset_revision']:
        raise ValueError('dataset revision mismatch')
    relative_train = 'data/processed/foundationalassist_v4/train.parquet'
    train_path = ROOT / relative_train
    train_hash = hashlib.sha256(train_path.read_bytes()).hexdigest()
    if train_hash != lock['pinned_sha256'][relative_train]:
        raise ValueError('TRAIN differs from the saved v4 lock')
    train = pd.read_parquet(train_path, columns=['skill_id', 'split'])
    graph = build_foundational_curriculum_graph(train, config)
    graph['input_sha256'] = {relative_train: train_hash,
                             str(config_path.relative_to(ROOT)).replace('\\', '/'):
                             hashlib.sha256(config_path.read_bytes()).hexdigest()}
    output_path = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_curriculum_graph.json'
    output_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': graph['status'], 'n_standards': len(set(graph['skill_to_standard'].values())),
                      'n_skills': len(graph['skills']), 'n_standard_edges': len(graph['standard_edges']),
                      'n_skill_edges': len(graph['edges']), 'test_access': False}, indent=2))


if __name__ == '__main__':
    main()
