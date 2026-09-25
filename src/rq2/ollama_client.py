"""Minimal loopback-only Ollama chat transport for RQ2 development."""

import json
from urllib.request import Request, urlopen


OLLAMA_CHAT_URL = 'http://127.0.0.1:11434/api/chat'


def call_local_ollama(request, *, timeout=60, opener=urlopen):
    """Send one nonstreaming structured-output request to local Ollama."""
    if not isinstance(request, dict) or request.get('stream') is not False:
        raise ValueError('nonstreaming Ollama request required')
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError('positive timeout required')
    payload = json.dumps(request, allow_nan=False).encode('utf-8')
    http_request = Request(OLLAMA_CHAT_URL, data=payload,
                           headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with opener(http_request, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
        content = result['message']['content']
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as error:
        raise ValueError('invalid Ollama chat response') from error
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Ollama returned empty content')
    return content
