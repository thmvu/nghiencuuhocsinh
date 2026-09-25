import io
import json
import unittest

from src.rq2.ollama_client import call_local_ollama


class OllamaClientTests(unittest.TestCase):
    def test_posts_nonstream_request_to_loopback_and_extracts_content(self):
        seen = {}

        def opener(request, timeout):
            seen['url'] = request.full_url
            seen['body'] = json.loads(request.data)
            seen['timeout'] = timeout
            return io.BytesIO(json.dumps({'message': {'content': '{"problem_id":"p1","reason":"x"}'}}).encode())

        content = call_local_ollama({'model': 'mock', 'stream': False},
                                    timeout=3, opener=opener)
        self.assertEqual(seen['url'], 'http://127.0.0.1:11434/api/chat')
        self.assertEqual(seen['body']['model'], 'mock')
        self.assertEqual(seen['timeout'], 3)
        self.assertIn('problem_id', content)

    def test_rejects_streaming_and_malformed_response(self):
        with self.assertRaises(ValueError):
            call_local_ollama({'model': 'mock', 'stream': True}, opener=lambda *_: None)
        with self.assertRaises(ValueError):
            call_local_ollama({'model': 'mock', 'stream': False},
                              opener=lambda *_: io.BytesIO(b'{"message": {}}'))


if __name__ == '__main__':
    unittest.main()
