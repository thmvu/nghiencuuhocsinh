"""Durable local call journal; responses precede all post-call runtime queries."""

from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
from urllib.error import HTTPError


class RuntimeIntegrityError(ValueError):
    pass


class RuntimeJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # An existing journal means calls may have happened: never silently repeat.
        with self.path.open('x', encoding='utf-8'):
            pass
        self.call_index = 0

    def append(self, index, event, **fields):
        entry = {'call_index': index, 'event': event,
                 'recorded_at_utc': datetime.now(timezone.utc).isoformat(), **deepcopy(fields)}
        with self.path.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def observe(self, index, phase, read_identity, expected):
        try:
            observed = read_identity()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.append(index, 'runtime_observation_failed', phase=phase,
                        error_type=type(error).__name__, error_message=str(error))
            raise RuntimeIntegrityError('runtime observation unavailable: ' + phase) from error
        self.append(index, 'runtime_observed', phase=phase, identity=observed)
        if observed != expected:
            self.append(index, 'runtime_mismatch', phase=phase, expected=expected)
            raise RuntimeIntegrityError('runtime identity changed: ' + phase)
        return observed

    def chat(self, request, *, timeout, call, read_identity, expected):
        self.call_index += 1
        index = self.call_index
        self.append(index, 'request_started', request=request)
        self.observe(index, 'before_call', read_identity, expected)
        try:
            response = call(request, timeout=timeout)
        except (OSError, ValueError, KeyError, TypeError) as error:
            failure_to_raise = error
            detail = {'error_type': type(error).__name__, 'error_message': str(error)}
            if isinstance(error, HTTPError):
                body = error.read()
                detail.update(http_status=error.code, http_body=body.decode('utf-8', errors='replace'))
                failure_to_raise = HTTPError(error.url, error.code, error.msg, error.hdrs, io.BytesIO(body))
            self.append(index, 'transport_failed', **detail)
            self.observe(index, 'after_transport_failure', read_identity, expected)
            raise failure_to_raise from error
        # Crucial ordering: durable raw response before query/validation/further calls.
        self.append(index, 'response_received', raw_response=response)
        self.observe(index, 'after_call', read_identity, expected)
        return response
