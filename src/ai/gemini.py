"""M08 structured Gemini REST client; standard library and injectable HTTP.

Google's generateContent REST uses responseFormat.text.schema for structured
JSON. No request occurs at import/construction. Model choice is explicit via
GEMINI_MODEL; secrets stay in the x-goog-api-key header, never URL/log/error text.
"""

from __future__ import annotations

import json
import math
import os
import re
from copy import deepcopy
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.core.models import Notice


INPUT_FIELDS = ('institution', 'title', 'category', 'published_at', 'apply_start', 'apply_end', 'content_text', 'url')
OUTPUT_FIELDS = ('relevant', 'category', 'participation_type', 'reason', 'keywords')
POLICY_PATH = Path(__file__).resolve().parents[2] / 'config' / 'relevance_policy.yaml'
ERROR_CODES = frozenset({
    'MALFORMED_JSON', 'INVALID_POLICY', 'INVALID_OUTPUT_SCHEMA', 'INVALID_TIMEOUT',
    'MISSING_OR_INVALID_CONFIGURATION', 'INVALID_INPUT_FIELDS', 'API_ERROR',
    'NETWORK_OR_TIMEOUT', 'MALFORMED_API_RESPONSE', 'ANALYSIS_ERROR',
})


class GeminiError(Exception):
    """Safe diagnostic code only; never includes raw HTTP/LLM error content."""
    def __init__(self, code: str, *, retryable: bool = False):
        self.code = code if isinstance(code, str) and code in ERROR_CODES else 'ANALYSIS_ERROR'
        self.retryable = retryable
        super().__init__(self.code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError('nonstandard JSON constant')


def strict_json(text):
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_bad_constant)
    except (ValueError, TypeError, RecursionError):
        raise GeminiError('MALFORMED_JSON') from None


def load_policy(path: str | Path = POLICY_PATH) -> dict:
    """Policy is JSON syntax (valid YAML 1.2), avoiding a YAML dependency."""
    try:
        policy = strict_json(Path(path).read_text(encoding='utf-8'))
        if (not isinstance(policy, dict) or policy.get('version') != 1
            or tuple(policy['input_fields']) != INPUT_FIELDS
            or not isinstance(policy['question'], str) or not policy['question'].strip()
            or not isinstance(policy['rules'], list) or not policy['rules']
            or any(not isinstance(rule, str) or not rule.strip() for rule in policy['rules'])
            or set(policy['output_schema']['properties']) != set(OUTPUT_FIELDS)
            or set(policy['output_schema']['required']) != set(OUTPUT_FIELDS)):
            raise ValueError('policy schema')
        return policy
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, GeminiError):
        raise GeminiError('INVALID_POLICY') from None


def notice_payload(notice: Notice) -> dict:
    return {name: getattr(notice, name) for name in INPUT_FIELDS}


def parse_decision(text: str) -> dict:
    decision = strict_json(text)
    if not isinstance(decision, dict) or set(decision) != set(OUTPUT_FIELDS):
        raise GeminiError('INVALID_OUTPUT_SCHEMA')
    if type(decision['relevant']) is not bool:
        raise GeminiError('INVALID_OUTPUT_SCHEMA')
    for name in ('category', 'participation_type', 'reason'):
        if not isinstance(decision[name], str) or not decision[name].strip():
            raise GeminiError('INVALID_OUTPUT_SCHEMA')
    keywords = decision['keywords']
    if not isinstance(keywords, list) or any(not isinstance(k, str) or not k.strip() for k in keywords):
        raise GeminiError('INVALID_OUTPUT_SCHEMA')
    try:
        json.dumps(decision, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (UnicodeError, ValueError):
        raise GeminiError('INVALID_OUTPUT_SCHEMA') from None
    return decision


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward an API credential to a redirect destination.
        return None


class GeminiClient:
    def __init__(self, *, api_key=None, model=None, timeout=30.0, policy_path=POLICY_PATH, opener=None):
        self._api_key = api_key if api_key is not None else os.environ.get('GEMINI_API_KEY', '')
        self.model = model if model is not None else os.environ.get('GEMINI_MODEL', '')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise GeminiError('INVALID_TIMEOUT')
        self.timeout = timeout
        self.policy = load_policy(policy_path)
        self._open = opener if opener is not None else build_opener(_NoRedirect()).open

    def generate(self, payload: dict) -> str:
        if (not isinstance(self._api_key, str) or not self._api_key.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in self._api_key)
            or not isinstance(self.model, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', self.model)):
            raise GeminiError('MISSING_OR_INVALID_CONFIGURATION', retryable=True)
        if set(payload) != set(INPUT_FIELDS):
            raise GeminiError('INVALID_INPUT_FIELDS')
        instruction = json.dumps({
            'question': self.policy['question'], 'rules': self.policy['rules'],
            'examples': self.policy.get('examples', []),
        }, ensure_ascii=False)
        body = {
            'systemInstruction': {'parts': [{'text': instruction}]},
            'contents': [{'role': 'user', 'parts': [{'text': json.dumps({'notice_data': payload}, ensure_ascii=False)}]}],
            'generationConfig': {
                'responseFormat': {'text': {'mimeType': 'APPLICATION_JSON', 'schema': deepcopy(self.policy['output_schema'])}},
                'candidateCount': 1, 'maxOutputTokens': 2048,
            },
        }
        request = Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent',
            data=json.dumps(body, ensure_ascii=False).encode('utf-8'), method='POST',
            headers={'Content-Type': 'application/json', 'x-goog-api-key': self._api_key,
                     'User-Agent': 'NoticeMonitor/0.1'},
        )
        try:
            with self._open(request, timeout=self.timeout) as response:
                if response.getcode() != 200:
                    raise GeminiError('API_ERROR', retryable=response.getcode() == 429 or response.getcode() >= 500)
                data = strict_json(response.read().decode('utf-8'))
        except HTTPError as error:
            retryable = error.code == 429 or error.code >= 500
            error.close()
            raise GeminiError('API_ERROR', retryable=retryable) from None
        except (TimeoutError, URLError, ConnectionError):
            raise GeminiError('NETWORK_OR_TIMEOUT', retryable=True) from None
        except UnicodeError:
            raise GeminiError('MALFORMED_API_RESPONSE') from None
        try:
            if not isinstance(data, dict) or 'error' in data or data.get('promptFeedback', {}).get('blockReason'):
                raise ValueError('API rejection')
            candidates = data['candidates']
            if not isinstance(candidates, list) or len(candidates) != 1 or candidates[0].get('finishReason') != 'STOP':
                raise ValueError('incomplete/blocked generation')
            parts = candidates[0]['content']['parts']
            if not isinstance(parts, list):
                raise ValueError('invalid parts')
            texts = [part['text'] for part in parts if not part.get('thought', False)]
            if not texts or any(not isinstance(text, str) for text in texts):
                raise ValueError('missing text')
            return ''.join(texts)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GeminiError('MALFORMED_API_RESPONSE') from None
