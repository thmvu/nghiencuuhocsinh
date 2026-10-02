"""FoundationalASSIST author-proposed graph; isolated from legacy ASSIST09."""

from copy import deepcopy

import pandas as pd

from src.rq2.graph import require_train_only


def build_foundational_curriculum_graph(train: pd.DataFrame, config: dict) -> dict:
    """Expand structurally checked standard mappings without merging BKT states.

    Structural validation is not expert review. Each standard edge is a hypothesis,
    and expanded skill edges are annotations, not conjunctive mastery requirements.
    """
    if config.get('stage') != 'validation_development_not_lock_c' or config.get('test_access') is not False:
        raise ValueError('graph is restricted to VALIDATION development')
    if config.get('expert_validated') is not False:
        raise ValueError('this builder cannot certify expert validation')
    if config.get('status') != 'author_proposed_curriculum_constraints_not_expert_validated':
        raise ValueError('author-proposed status must be explicit')
    if not {'skill_id', 'split'} <= set(train.columns) or train.empty:
        raise ValueError('nonempty tagged TRAIN skill rows are required')
    require_train_only(train)
    mapping = config['pilot_skill_ids_by_node_code']
    skill_codes = {}
    for code, ids in mapping.items():
        if not ids:
            raise ValueError('standard has no skill mapping')
        for skill in ids:
            if not isinstance(skill, str) or skill in skill_codes:
                raise ValueError('skill IDs must be unique strings across standards')
            skill_codes[skill] = code
    if not set(skill_codes) <= set(train.skill_id.dropna().astype(str)):
        raise ValueError('a configured skill is absent from TRAIN')
    siblings = [set(group) for group in config['sibling_groups']]
    if any(not group <= set(mapping) for group in siblings):
        raise ValueError('unknown sibling standard')
    adjacency = {code: set() for code in mapping}
    seen = set()
    edges = []
    for edge in config['standard_edges']:
        before, after = edge['source'], edge['target']
        if before not in mapping or after not in mapping or before == after:
            raise ValueError('unknown standard or self-edge')
        if (before, after) in seen:
            raise ValueError('duplicate standard edge')
        if any({before, after} <= group for group in siblings):
            raise ValueError('directed sibling edge is not permitted in this draft')
        refs = edge.get('source_refs', [])
        if not refs or not edge.get('rationale') or not str(edge.get('basis', '')).startswith('author_'):
            raise ValueError('edge requires explicit inference basis and source rationale')
        for ref in refs:
            source = config['sources'].get(ref, {})
            if not source.get('url', '').startswith('https://') or not source.get('title') or not source.get('accessed'):
                raise ValueError('edge source provenance is incomplete')
        seen.add((before, after))
        adjacency[before].add(after)
        for source_skill in mapping[before]:
            for target_skill in mapping[after]:
                edges.append({'prerequisite': source_skill, 'target': target_skill,
                              'source_standard': before, 'target_standard': after,
                              'edge_class': 'cross_standard_curriculum_sequence',
                              'basis': edge['basis'], 'rationale': edge['rationale'],
                              'source_refs': list(refs), 'human_review': 'not_performed'})
    indegree = {code: 0 for code in mapping}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1
    ready = sorted(code for code, degree in indegree.items() if degree == 0)
    visited = []
    while ready:
        code = ready.pop(0)
        visited.append(code)
        for target in sorted(adjacency[code]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if len(visited) != len(mapping):
        raise ValueError('curriculum graph contains a cycle')
    return {'skills': sorted(skill_codes), 'edges': edges,
            'status': config['status'], 'version': config['version'],
            'stage': config['stage'], 'test_access': False, 'expert_validated': False,
            'edge_semantics': config['edge_semantics'],
            'skill_state_semantics': config['skill_state_semantics'],
            'skill_to_standard': skill_codes, 'standard_topological_order': visited,
            'sibling_groups': deepcopy(config['sibling_groups']),
            'standard_edges': deepcopy(config['standard_edges']),
            'sources': deepcopy(config['sources']), 'review': deepcopy(config['review'])}
