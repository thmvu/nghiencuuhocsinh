"""Local author review of the frozen v3 packet; no inference or training."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from src.rq2.selection_agent_v3 import rubric_estimate

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/selection_v3/study'
REVIEW = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/selection_v3/author_review'
SUMMARY = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_selection_v3_study.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_source():
    summary = read(SUMMARY)
    audit_path = SUMMARY.with_name('foundationalassist_v4_rq2_selection_v3_study_audit.json')
    audit = read(audit_path)
    if (summary['status'] != 'completed_validation_not_test' or summary['test_opened'] or
            audit['summary_sha256'] != sha(SUMMARY) or
            not audit['requests_responses_hashes_metrics_verified']):
        raise ValueError('completed audited VALIDATION v3 required')
    for name, key in [('rubric_packet.json', 'rubric_packet_sha256'), ('runs.json', 'runs_sha256')]:
        if sha(STUDY / name) != summary[key]:
            raise ValueError('frozen review source hash differs: ' + name)
    packet, runs = read(STUDY / 'rubric_packet.json'), read(STUDY / 'runs.json')
    if len(packet) != 40 or len(runs) != 240:
        raise ValueError('fixed 40-item packet / 240 study rows required')
    for item in packet:
        row = runs[item['study_index']]
        if (not row['candidate_valid'] or item['input'] != row['request']['messages'][1]['content'] or
                item['choice'] != row['selected_problem_id'] or item['reason'] != row['reason'] or
                item['student_id'] != row['student_id'] or item['graph_variant'] != row['graph_variant']):
            raise ValueError('packet/study record mismatch')
    return packet, runs, {'packet_sha256': summary['rubric_packet_sha256'],
                          'runs_sha256': summary['runs_sha256'], 'study_summary_sha256': sha(SUMMARY)}


class ReviewStore:
    def __init__(self, packet, runs, pins, directory=REVIEW, *, demo=False):
        self.packet, self.runs, self.pins = deepcopy(packet), deepcopy(runs), deepcopy(pins)
        self.directory, self.demo = Path(directory), demo
        self.path = self.directory / 'reviews.json'
        self.data = {'version': 0, 'source': pins, 'reviewer': None, 'role': 'project_author',
                     'demo': demo, 'revealed': False, 'records': {}, 'history': []}
        if self.path.exists():
            self.data = read(self.path)
            if self.data['source'] != pins or self.data['demo'] != demo or self.data['role'] != 'project_author':
                raise ValueError('review belongs to another source/session')

    def state(self):
        records = self.data['records']
        chosen = sum('selection' in r for r in records.values())
        rated = sum('rating' in r for r in records.values())
        phase = 'rating' if self.data['revealed'] else ('ready' if chosen == len(self.packet) else 'selection')
        return {'version': self.data['version'], 'total': len(self.packet), 'chosen': chosen, 'rated': rated,
                'phase': phase, 'reviewer': self.data['reviewer'], 'role': 'project_author', 'demo': self.demo,
                'completed_selection': [int(i) for i, r in records.items() if 'selection' in r],
                'completed_rating': [int(i) for i, r in records.items() if 'rating' in r]}

    def case(self, index):
        if type(index) is not int or not 0 <= index < len(self.packet):
            raise ValueError('invalid case index')
        item = self.packet[index]
        shared = json.loads(item['input'])
        record = self.data['records'].get(str(index), {})
        value = {'index': index, 'code': f'Phiếu {index + 1:02d}', 'shared': shared,
                 'selection': record.get('selection'), 'rating': record.get('rating')}
        if self.data['revealed']:
            value.update(choice=item['choice'], reason=item['reason'])
        return value

    def save(self, body):
        if type(body.get('version')) is not int or body['version'] != self.data['version']:
            raise ValueError('Phiếu đã thay đổi ở cửa sổ khác. Tải lại trước khi lưu.')
        reviewer = body.get('reviewer')
        if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 100:
            raise ValueError('Nhập tên hoặc bí danh người chấm.')
        reviewer = reviewer.strip()
        if self.data['reviewer'] and self.data['reviewer'] != reviewer:
            raise ValueError('Phiên này đã gắn với một người chấm; dùng đúng bí danh đã lưu.')
        action = body.get('action')
        updated = deepcopy(self.data)
        if action == 'reveal':
            if self.state()['phase'] != 'ready':
                raise ValueError('Chọn hoặc ghi không đánh giá được ở toàn bộ phiếu trước khi xem Agent.')
            updated['revealed'] = True
            event = {'action': action}
        elif action in ('selection', 'rating'):
            index = body.get('index')
            self.case(index)
            note = body.get('note', '').strip() if isinstance(body.get('note', ''), str) else None
            if note is None or not 1 <= len(note) <= 2000:
                raise ValueError('Ghi lý do hoặc hạn chế (1–2.000 ký tự).')
            if action == 'selection':
                if self.data['revealed']:
                    raise ValueError('Lựa chọn đã khóa sau khi xem kết quả Agent.')
                choice, status = body.get('choice'), body.get('status')
                candidates = {c['problem_id'] for c in json.loads(self.packet[index]['input'])['candidates']}
                if (status == 'chosen' and (not isinstance(choice, str) or choice not in candidates)) or (status == 'cannot_assess' and choice is not None) or status not in ('chosen', 'cannot_assess'):
                    raise ValueError('Chọn một bài trong danh sách hoặc ghi không đánh giá được.')
                value = {'choice': choice, 'status': status, 'note': note}
            else:
                if not self.data['revealed']:
                    raise ValueError('Chưa mở phần chấm lời giải thích.')
                scores = body.get('scores')
                if not isinstance(scores, list) or len(scores) != 4 or any(s is not None and (type(s) is not int or s not in (0, 1, 2)) for s in scores):
                    raise ValueError('Bốn tiêu chí cần điểm 0/1/2 hoặc không đánh giá được.')
                value = {'scores': scores, 'note': note, 'complete': all(s is not None for s in scores)}
            updated['records'].setdefault(str(index), {})[action] = value
            event = {'action': action, 'index': index, 'value': value}
        else:
            raise ValueError('unknown review action')
        updated['reviewer'] = reviewer
        updated['version'] += 1
        event.update(version=updated['version'], time=datetime.now(timezone.utc).isoformat())
        updated['history'].append(event)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(updated, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        self.data = updated
        return self.state()

    def summary(self):
        ratings, choices, matches, completed = [], 0, 0, 0
        for index, item in enumerate(self.packet):
            record = self.data['records'].get(str(index), {})
            selection = record.get('selection', {})
            if selection.get('status') == 'chosen':
                choices += 1
                matches += selection['choice'] == item['choice']
            rating = record.get('rating')
            if rating and rating['complete']:
                completed += 1
                ratings.append({'student_id': item['student_id'], 'graph_variant': item['graph_variant'],
                                'scores': rating['scores']})
        rubric = rubric_estimate(self.runs, ratings) if completed == len(self.packet) else {'status': 'not_evaluated', 'unconditional_mean': None, 'pass': False}
        return {'scope': 'author_self_review_validation_metadata_only', 'demo': self.demo,
                'reviewer': self.data['reviewer'], 'role': 'project_author', 'independent_expert_review': False,
                'total': len(self.packet), 'fully_scored': completed, 'rubric': rubric,
                'human_choices_assessable': choices,
                'agreement_with_agent_descriptive': matches if self.data['revealed'] else None,
                'agreement_is_correctness': False, 'test_opened': False, 'lock_c_authorized': False,
                'training_exported': False, 'source': self.pins}


def demo_source():
    shared = {'state': {'history_length': 24, 'skills': {'A': .25, 'B': .70}, 'state_type': 'BKT_p_mastery'},
              'graph': {'skills': ['A', 'B'], 'skill_to_standard': {'A': '6.NS.A.1', 'B': '6.EE.B.7'},
                        'edges': [{'prerequisite': 'A', 'target': 'B'}]},
              'candidates': [{'problem_id': 'DEMO-1', 'skill_id': 'A', 'difficulty': .65, 'support': 100},
                             {'problem_id': 'DEMO-2', 'skill_id': 'B', 'difficulty': .8, 'support': 200}]}
    packet, runs = [], []
    for i, variant in enumerate(('curriculum_edges', 'no_edges')):
        data = deepcopy(shared)
        if i:
            data['graph']['edges'] = []
        packet.append({'study_index': i, 'student_id': 'synthetic', 'graph_variant': variant,
                       'input': json.dumps(data), 'choice': 'DEMO-1',
                       'reason': 'Mastery ước lượng của kỹ năng A là 25%. Bài DEMO-1 có tỷ lệ đúng TRAIN 65%, nhưng chưa có bằng chứng về lợi ích học tập.'})
        runs.append({'candidate_valid': True, 'graph_variant': variant})
    return packet, runs, {'synthetic_fixture': 'review-ui-demo-v1'}
