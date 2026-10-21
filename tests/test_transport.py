import base64
from contextlib import contextmanager
from email.message import Message
import gzip
import hashlib
import io
import json
import math
from unittest.mock import patch
import zlib

import pytest

from duckmind import APIError, ChallengeError, DuckMind, GPT6Luna, RatelimitError
from duckmind._challenge import solve_challenge
from duckmind._durable import generate_jwk, _prime
from duckmind._http import Response, Session
from duckmind.cli import _list_models, _usage

HOMEPAGE = '<html data-version-tag="serp_current" data-version-sha="new_hash"></html>'
DONE = 'data: {"message":"OK"}\n\ndata: [DONE]\n\n'


class Raw(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body.encode() if isinstance(body, str) else body)
        self.status = status
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def getcode(self):
        return self.status


def response(text='', status=200, headers=None):
    return Response(Raw(text, status, headers))


def page(client, url, **kwargs):
    return response(HOMEPAGE)


@pytest.fixture
def client():
    with patch.object(Session, 'get', page), DuckMind(backoff_base=0) as client:
        with patch('duckmind.client.time.sleep'), patch('duckmind.client.generate_jwk', return_value={'kty':'RSA'}):
            yield client


def test_frontend_version_tracks_the_homepage_without_overriding_explicit_version():
    with patch.object(Session, 'get', page):
        with DuckMind() as client:
            assert client.fe_version == 'serp_current-new_hash'
            assert client.model == GPT6Luna
            assert client._client.headers['Accept-Encoding'] == 'gzip, deflate'
        with DuckMind(fe_version='explicit') as client:
            assert client.fe_version == 'explicit'


def test_current_model_stream_and_payload(client):
    @contextmanager
    def stream(method, url, **kwargs):
        assert url.endswith('/duckchat/v1/chat')
        assert kwargs['headers']['x-fe-version'] == 'serp_current-new_hash'
        payload = json.loads(kwargs['content'])
        assert payload['model'] == GPT6Luna
        assert payload['reasoningEffort'] == 'none'
        assert payload['metadata']['toolChoice']['WebSearch'] is True
        yield response(DONE)
    with patch.object(client._client, 'stream', stream), patch.object(client, '_fetch_challenge_header', return_value='challenge'):
        assert client.ask('Reply OK', web_search=True) == 'OK'


def test_challenge_uses_duck_ai_origin():
    code = '(async function(){return {client_hashes:[navigator.userAgent,location.origin]};})()'
    challenge = base64.b64encode(code.encode()).decode()
    solved = json.loads(base64.b64decode(solve_challenge(challenge, 'test-agent')))
    expected = base64.b64encode(hashlib.sha256(b'https://duck.ai').digest()).decode()
    assert solved['client_hashes'][1] == expected
    assert solved['meta']['origin'] == 'https://duck.ai'


def test_retired_model_error_is_actionable():
    with pytest.raises(APIError, match='list_models') as error:
        DuckMind._raise_for_status(response('{"type":"ERR_MODEL_UNAVAILABLE"}',404))
    assert error.value.status_code == 404


def test_cli_lists_current_models_and_subscription_requirements(capsys):
    _list_models()
    output = capsys.readouterr().out
    assert 'gpt-6-luna' in output
    assert 'claude-opus-4-8' in output
    assert 'Pro subscription' in output
    assert 'gpt-4o-mini' not in output
    help_text = io.StringIO()
    _usage(help_text)
    assert 'default: luna / gpt-6-luna' in help_text.getvalue()


@pytest.mark.parametrize('encoding,compress',[('gzip',gzip.compress),('deflate',zlib.compress)])
def test_stdlib_transport_decodes_compressed_unicode_lines(encoding,compress):
    body = 'data: {"message":"caffè"}\r\n\r\ndata: [DONE]\r\n\r\n'
    compressed = compress(body.encode())
    resp = response(compressed,headers={'Content-Encoding':encoding})
    assert list(DuckMind._iter_sse(resp)) == ['{"message":"caffè"}','[DONE]']
    assert response(compressed,headers={'Content-Encoding':encoding}).text == body


def test_sse_multiline_data_and_comments():
    text = ': heartbeat\n\nevent: message\ndata: {"message":\ndata: "OK"}\n\ndata: [DONE]\n\n'
    assert list(DuckMind._iter_sse(response(text))) == ['{"message":\n"OK"}','[DONE]']


def test_status_requests_cannot_reuse_a_cached_challenge(client):
    urls = []
    def get(url, **kwargs):
        urls.append(url)
        return response(headers={'x-vqd-hash-1':'challenge'})
    with patch.object(client._client,'get',get), patch('duckmind.client.solve_challenge',lambda token,ua:token):
        assert client._fetch_challenge_header() == 'challenge'
        assert client._fetch_challenge_header() == 'challenge'
    assert len(set(urls)) == 2


def test_challenge_retry_clears_pending_token(client):
    attempts = []
    def attempt(payload):
        attempts.append(client._pending_hash)
        if len(attempts) == 1:
            raise ChallengeError('expired')
        yield {'message':'OK'}
    client._pending_hash = 'spent'
    with patch.object(client,'_attempt_stream',attempt):
        assert client.ask('Hi') == 'OK'
    assert attempts == ['spent',None]


def test_rate_limit_retry_honors_retry_after(client):
    attempts = []
    def attempt(payload):
        attempts.append(1)
        if len(attempts) == 1:
            raise RatelimitError('wait',retry_after='20')
        yield {'message':'OK'}
    with patch.object(client,'_attempt_stream',attempt), patch('duckmind.client.time.sleep') as sleep:
        assert client.ask('Hi') == 'OK'
    assert sleep.call_args.args[0] >= 20


def test_metadata_before_error_does_not_prevent_retry(client):
    attempts = []
    def attempt(payload):
        attempts.append(1)
        yield {'role':'assistant'}
        if len(attempts) == 1:
            raise OSError('connection reset')
        yield {'message':'OK'}
    with patch.object(client,'_attempt_stream',attempt):
        assert client.ask('Hi') == 'OK'
    assert len(attempts) == 2


def test_partial_visible_output_is_never_replayed(client):
    attempts = []
    def attempt(payload):
        attempts.append(1)
        yield {'message':'partial'}
        raise OSError('connection reset')
    with patch.object(client,'_attempt_stream',attempt):
        stream = client.stream('Hi')
        assert next(stream) == 'partial'
        with pytest.raises(OSError):
            next(stream)
    assert len(attempts) == 1


def test_incomplete_stream_is_not_accepted(client):
    @contextmanager
    def stream(*args,**kwargs):
        yield response('data: {"message":"incomplete"}\n\n')
    with patch.object(client._client,'stream',stream), patch.object(client,'_fetch_challenge_header',return_value='challenge'):
        with pytest.raises(APIError,match='before completion'):
            client.ask('Hi')


def test_public_jwk_has_required_shape():
    key = generate_jwk()
    assert key['kty'] == 'RSA'
    assert key['alg'] == 'RSA-OAEP-256'
    n = int.from_bytes(base64.urlsafe_b64decode(key['n']+'=='),'big')
    assert n.bit_length() == 2048
    assert n & 1
    assert key['e'] == 'AQAB'


def test_generated_small_primes_are_prime():
    for _ in range(8):
        value = _prime(16)
        assert value.bit_length() == 16
        assert all(value % divisor for divisor in range(2, math.isqrt(value) + 1))
