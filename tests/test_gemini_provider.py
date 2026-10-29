"""GeminiProvider degradation ladder with a fake SDK client (no network)."""
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from src.audit import llm as L


class Out(BaseModel):
    a: str


class FakeModels:
    def __init__(self, behaviours):
        self.behaviours, self.configs = list(behaviours), []

    def generate_content(self, model, contents, config):
        self.configs.append(config)
        b = self.behaviours.pop(0)
        if isinstance(b, Exception):
            raise b
        return b


def resp(text, finish="STOP"):
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason=finish)])


@pytest.fixture(autouse=True)
def tmp_compat(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "COMPAT_FILE", tmp_path / "compat.json")


def provider(behaviours):
    p = L.GeminiProvider("gemini-2.5-flash", api_key="k")
    p._client = SimpleNamespace(models=FakeModels(behaviours))
    return p


def test_plain_success_sets_schema_and_mime_type():
    p = provider([resp('{"a": "x"}')])
    c = p.complete("q", "sys", 0.1, 100, Out, 0)
    assert json.loads(c.text) == {"a": "x"} and not c.truncated
    cfg = p._client.models.configs[0]
    assert cfg.response_mime_type == "application/json" and cfg.response_schema is Out


def test_thinking_rejection_retries_without_thinking():
    p = provider([Exception("400 INVALID_ARGUMENT. Thinking budget is not supported for this model"), resp('{"a": "x"}')])
    p.complete("q", None, 0.1, 100, Out, 0)
    assert p.skip_thinking and p._client.models.configs[1].thinking_config is None


def test_schema_rejection_retries_with_schema_in_prompt():
    seen = []

    class M(FakeModels):
        def generate_content(self, model, contents, config):
            seen.append(contents)
            return super().generate_content(model, contents, config)

    p = L.GeminiProvider("m", api_key="k")
    p._client = SimpleNamespace(models=M([ValueError("Default value is not supported in the response schema"), resp('{"a": "x"}')]))
    p.complete("question", None, 0.1, 100, Out, None)
    assert p.skip_schema and "JSON Schema" in seen[1] and "JSON Schema" not in seen[0]


def test_max_tokens_marks_truncated_and_empty_raises():
    p = provider([resp('{"a": "cut', finish="FinishReason.MAX_TOKENS")])
    assert p.complete("q", None, 0.1, 10, Out, 0).truncated
    p = provider([resp("   ")])
    with pytest.raises(L.EmptyResponseError):
        p.complete("q", None, 0.1, 10, Out, 0)


def test_quota_error_is_classified_through_provider():
    msg = "429 RESOURCE_EXHAUSTED. quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier Please retry in 15h20m4s"
    p = provider([Exception(msg)])
    with pytest.raises(L.QuotaExhaustedError):
        p.complete("q", None, 0.1, 10, Out, 0)


def test_missing_key_or_model_fail_loudly():
    with pytest.raises(L.FatalLLMError):
        L.GeminiProvider("m", api_key="").ready_check()
    with pytest.raises(L.FatalLLMError):
        L.GeminiProvider("", api_key="k").ready_check()


def test_openai_compat_parses_and_maps_errors(monkeypatch):
    import requests

    class R:
        def __init__(self, code, body, headers=None):
            self.status_code, self._b, self.headers, self.text = code, body, headers or {}, json.dumps(body)

        def json(self):
            return self._b

    ok = R(200, {"choices": [{"message": {"content": '{"a": "z"}'}, "finish_reason": "stop"}]})
    monkeypatch.setattr(requests, "post", lambda *a, **k: ok)
    p = L.OpenAICompatProvider("m", "http://x/v1/", "key")
    assert json.loads(p.complete("q", "s", 0.1, 10, Out, None).text) == {"a": "z"}
    monkeypatch.setattr(requests, "post", lambda *a, **k: R(429, {"error": "per day limit"}))
    with pytest.raises(L.QuotaExhaustedError):
        p.complete("q", None, 0.1, 10, Out, None)
    monkeypatch.setattr(requests, "post", lambda *a, **k: R(429, {"error": "slow"}, {"retry-after": "5"}))
    with pytest.raises(L.RateLimitedError):
        p.complete("q", None, 0.1, 10, Out, None)
    monkeypatch.setattr(requests, "post", lambda *a, **k: R(401, {"error": "bad key"}))
    with pytest.raises(L.FatalLLMError):
        p.complete("q", None, 0.1, 10, Out, None)


GENERIC_400 = "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Request contains an invalid argument.', 'status': 'INVALID_ARGUMENT'}}"


def test_generic_400_drops_thinking_then_schema_and_remembers(tmp_path):
    p = provider([Exception(GENERIC_400), Exception(GENERIC_400), resp('{"a": "x"}')])
    c = p.complete("q", None, 0.1, 100, Out, 0)
    assert json.loads(c.text) == {"a": "x"}
    assert p.skip_thinking and p.skip_schema and p.degraded == ["no thinking config", "schema sent inside the prompt"]
    # a fresh provider for the same model starts in the working mode (no wasted requests)
    p2 = L.GeminiProvider("gemini-2.5-flash", api_key="k")
    assert p2.skip_thinking and p2.skip_schema


def test_generic_400_everywhere_gives_actionable_error():
    p = provider([Exception(GENERIC_400)] * 3)
    with pytest.raises(L.BadRequestError) as e:
        p.complete("q", None, 0.1, 100, Out, 0)
    assert "diagnose_llm" in str(e.value) and "model=gemini-2.5-flash" in str(e.value)


def test_reset_forgets_learned_flags():
    p = provider([Exception(GENERIC_400), resp('{"a": "x"}')])
    p.complete("q", None, 0.1, 100, Out, 0)
    assert p.skip_thinking
    p.reset()
    assert not p.skip_thinking and not L.GeminiProvider("gemini-2.5-flash", api_key="k").skip_thinking
