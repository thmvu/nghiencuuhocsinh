"""Local Agent request and strict recommendation-output contract.

This module prepares Ollama chat requests; it does not call a remote service
or count synthetic responses as RQ2 evaluation results.
"""

import json
import math

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Recommendation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    problem_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


SYSTEM_PROMPT = (
    'You recommend one practice problem for a student. Use only the supplied '
    'BKT latent mastery state, prerequisite graph, and candidate list. '
    'The state is an estimate, not ground truth. Choose exactly one candidate '
    'problem_id. Return JSON with problem_id and a short reason grounded in '
    'the supplied inputs. Do not claim that the recommendation improves learning.'
)


def _validated_inputs(state, graph, candidates):
    if not isinstance(state, dict) or state.get('state_type') != 'BKT_p_mastery':
        raise ValueError('BKT latent mastery state required')
    skills = state.get('skills')
    if not isinstance(skills, dict) or not skills:
        raise ValueError('nonempty per-skill state required')
    if (not isinstance(state.get('history_length'), int) or
            state['history_length'] < 0):
        raise ValueError('nonnegative history length required')
    if any(not isinstance(key, str) or not isinstance(value, (int, float)) or
           not math.isfinite(value) or not 0 <= value <= 1
           for key, value in skills.items()):
        raise ValueError('finite skill mastery probabilities required')
    if not isinstance(graph, dict) or not isinstance(graph.get('skills'), list) or not isinstance(graph.get('edges'), list):
        raise ValueError('graph skills and edges required')
    if not isinstance(candidates, list) or not candidates:
        raise ValueError('nonempty candidate list required')
    ids = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {'problem_id', 'skill_id', 'difficulty', 'support'}:
            raise ValueError('candidate schema mismatch')
        if (not isinstance(candidate['problem_id'], str) or not candidate['problem_id'] or
                not isinstance(candidate['skill_id'], str) or
                candidate['skill_id'] not in graph['skills'] or
                not isinstance(candidate['difficulty'], (int, float)) or
                not math.isfinite(candidate['difficulty']) or
                not 0 <= candidate['difficulty'] <= 1 or
                not isinstance(candidate['support'], int) or candidate['support'] < 1):
            raise ValueError('invalid candidate value')
        ids.append(candidate['problem_id'])
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate candidate problem IDs')


def build_agent_request(state, graph, candidates, *, model, temperature=0, num_ctx=2048):
    """Build a local Ollama /api/chat request with the shared RQ2 inputs."""
    _validated_inputs(state, graph, candidates)
    if (not isinstance(model, str) or not model.strip() or
            not isinstance(temperature, (int, float)) or not math.isfinite(temperature) or
            not 0 <= temperature <= 2 or
            not isinstance(num_ctx, int) or num_ctx < 256):
        raise ValueError('invalid local model runtime configuration')
    content = json.dumps({'state': state, 'graph': graph, 'candidates': candidates},
                         sort_keys=True, allow_nan=False)
    return {'model': model, 'stream': False,
            'messages': [{'role': 'system', 'content': SYSTEM_PROMPT},
                         {'role': 'user', 'content': content}],
            'format': Recommendation.model_json_schema(),
            'options': {'temperature': temperature, 'num_ctx': num_ctx}}


def validate_agent_output(content, candidates):
    """Reject malformed JSON and selections outside the shared candidate set."""
    try:
        recommendation = Recommendation.model_validate_json(content)
    except (ValidationError, ValueError, TypeError) as error:
        raise ValueError('invalid Agent JSON output') from error
    if not recommendation.reason.strip():
        raise ValueError('Agent reason cannot be blank')
    ids = {candidate['problem_id'] for candidate in candidates}
    if recommendation.problem_id not in ids:
        raise ValueError('Agent selected a problem outside the candidate set')
    return recommendation.model_dump()
