from copy import deepcopy
from http.server import HTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.rq2.human_review_ui import ReviewStore, demo_source
from scripts.run_foundational_rq2_review_ui import make_handler


class ReviewUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = demo_source()
        self.store = ReviewStore(*self.source, directory=self.temp.name, demo=True)

    def save(self, **body):
        return self.store.save({'version': self.store.data['version'], 'reviewer': 'author', **body})

    def choose_all(self):
        for index in range(2):
            self.save(action='selection', index=index, choice='DEMO-1', status='chosen', note='Synthetic reason')

    def reveal(self):
        self.choose_all()
        self.save(action='reveal')

    def test_every_answer_hidden_until_all_choices_locked(self):
        self.assertNotIn('choice', self.store.case(1))
        self.assertNotIn('reason', self.store.case(0))
        self.assertIsNone(self.store.summary()['agreement_with_agent_descriptive'])
        self.save(action='selection', index=0, choice='DEMO-1', status='chosen', note='My reason')
        with self.assertRaises(ValueError):
            self.save(action='reveal')
        self.assertNotIn('choice', self.store.case(0))
        self.save(action='selection', index=1, choice=None, status='cannot_assess', note='Insufficient information')
        self.assertEqual(self.store.state()['phase'], 'ready')
        self.save(action='reveal')
        self.assertEqual(self.store.case(0)['choice'], 'DEMO-1')
        with self.assertRaises(ValueError):
            self.save(action='selection', index=0, choice='DEMO-2', status='chosen', note='After reveal')

    def test_no_rating_before_reveal_and_no_invalid_scores(self):
        with self.assertRaises(ValueError):
            self.save(action='rating', index=0, scores=[2]*4, note='Premature')
        self.reveal()
        for scores in ([2, 2], [3]*4, [True]*4, ['2']*4, [1.0]*4):
            with self.assertRaises(ValueError):
                self.save(action='rating', index=0, scores=scores, note='Invalid')

    def test_unassessable_not_turned_into_zero_or_complete_rubric(self):
        self.reveal()
        self.save(action='rating', index=0, scores=[None, None, None, 0], note='Cannot read the language')
        self.save(action='rating', index=1, scores=[2]*4, note='All four assessed')
        summary = self.store.summary()
        self.assertEqual(self.store.state()['rated'], 2)
        self.assertEqual(summary['fully_scored'], 1)
        self.assertEqual(summary['rubric']['status'], 'not_evaluated')
        self.assertIsNone(summary['rubric']['unconditional_mean'])
        self.assertFalse(summary['independent_expert_review'])
        self.assertFalse(summary['lock_c_authorized'])

    def test_rubric_uses_frozen_estimator_without_changing_source(self):
        original = deepcopy(self.source)
        self.reveal()
        self.save(action='rating', index=0, scores=[2]*4, note='Assessable')
        self.save(action='rating', index=1, scores=[1]*4, note='Assessable')
        self.assertEqual(self.store.summary()['rubric']['unconditional_mean'], 1.5)
        self.assertEqual(self.source, original)
        self.assertFalse(self.store.summary()['training_exported'])

    def test_resume_keeps_reviewer_versions_and_provenance(self):
        self.choose_all()
        resumed = ReviewStore(*self.source, directory=self.temp.name, demo=True)
        self.assertEqual(resumed.data, self.store.data)
        with self.assertRaises(ValueError):
            resumed.save({'version': 0, 'reviewer': 'author', 'action': 'reveal'})
        with self.assertRaises(ValueError):
            resumed.save({'version': 2, 'reviewer': 'different author', 'action': 'reveal'})
        with self.assertRaises(ValueError):
            ReviewStore(self.source[0], self.source[1], {'different': 'source'}, directory=self.temp.name, demo=True)

    def test_disk_failure_does_not_commit_in_memory_or_destroy_prior_save(self):
        self.save(action='selection', index=0, choice='DEMO-1', status='chosen', note='Before')
        before = deepcopy(self.store.data)
        with patch('src.rq2.human_review_ui.os.replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.save(action='selection', index=1, choice='DEMO-2', status='chosen', note='Not saved')
        self.assertEqual(self.store.data, before)
        self.assertEqual(json.loads(Path(self.store.path).read_text(encoding='utf-8')), before)

    def test_rejects_outside_candidate_choice_or_missing_explanation(self):
        for choice, note in [('OUTSIDE', 'Reason'), ([], 'Reason'), ('DEMO-1', '')]:
            with self.assertRaises(ValueError):
                self.save(action='selection', index=0, choice=choice, status='chosen', note=note)

    def test_http_blocks_other_origins_bad_token_and_private_paths(self):
        server = HTTPServer(('127.0.0.1', 0), make_handler(self.store, 0))
        port = server.server_address[1]
        server.RequestHandlerClass = make_handler(self.store, port)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{port}'
        with urlopen(base + '/api/state') as response:
            state = json.load(response)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        body = json.dumps({'version': 0, 'reviewer': 'author', 'action': 'selection', 'index': 0,
                           'choice': 'DEMO-1', 'status': 'chosen', 'note': 'Reason'}).encode()
        for headers in ({'X-Review-Token': 'wrong'}, {'X-Review-Token': state['token'], 'Origin': 'https://other.example'}):
            request = Request(base + '/api/save', body, {'Content-Type': 'application/json', **headers})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError) as error:
            urlopen(base + '/data/processed/runs.json')
        self.assertEqual(error.exception.code, 404)
        with urlopen(base + '/api/case?index=0') as response:
            case = json.load(response)
        self.assertNotIn('choice', case)
        self.assertNotIn('student_id', case)
